"""Shared helpers for the CodeUpdateArena replication (design.md).

Reproduces the authors' program assembly and UPass rule
(github.com/leo-liuzy/CodeUpdateArena, src/test_beds/test_bed.py
`check_unit_tests`, src/data/manager_update.py `get_update_statements`,
src/utils/update.py `UpdateType.from_tag`, src/utils/code.py
`Function.get_function_name`) without importing or running any of their code.

The dataset's own code (update implementations, unit tests, reference
solutions) and every model answer run only in the pinned environment
(CUA_PYTHON, design §3.1), one subprocess per program, with `python -I`,
from an empty temporary directory.
"""
import ast
import hashlib
import json
import os
import re
import subprocess
import tempfile
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_FILE = HERE / "data" / "arena-ungrouped.jsonl"
DATASET_REVISION = "3fe9d5f914524241a9e09b379464b5e8ac7472db"
PINNED_VERSIONS = {"python": "3.11", "numpy": "1.26.4", "pandas": "2.2.2", "torch": "2.2.2", "sympy": "1.12"}
CUA_PYTHON = Path(os.environ.get("CUA_PYTHON", Path.home() / "Developer" / "cua-env" / ".venv" / "bin" / "python"))
TIMEOUT_S = 10  # design §4: per program
SENTINEL = "__CUA_UNIT_TEST_FINISHED_7f3a__"

# Mirrors src/utils/update.py (Action / Place / Aspect enums).
ACTIONS = {"add", "modify", "deprecate"}
PLACES = {"function", "argument", "output"}
ASPECTS = {"null", "name", "semantics", "data type", "default value(s)", "supported value(s)"}


# ---------------------------------------------------------------- dataset

def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_hash(record):
    """SHA-256 of a problem's full record (recorded at selection, re-checked when scoring)."""
    return text_sha256(json.dumps(record, sort_keys=True, ensure_ascii=False))


def load_dataset(path=DATA_FILE):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def package_of(record):
    """Package = first part of the API path (their prepare_arena_dataset)."""
    return record["update"]["api_path"].split(".")[0]


UNIT_TEST_SEPARATOR = "\n\n\n\n"


def split_unit_tests(text):
    """One string per unit test. In the Hugging Face file the tests are joined
    with four newlines (checked on all 670 problems: every test starts with
    `def` after exactly four newlines). The authors' prepare_arena_dataset
    splits their own copy on two newlines; on this file that would cut tests
    with blank lines inside, so the file's real separator is used."""
    return text.split(UNIT_TEST_SEPARATOR)


def split_imports(text):
    """Their prepare_arena_dataset: one import statement per line."""
    return text.split("\n")


# ------------------------------------------------------ update statements

def parse_update_type(tag):
    """UpdateType.from_tag: 'action-place[-aspect]', aspect underscores = spaces."""
    factors = tag.split("-")
    if not 2 <= len(factors) <= 3:
        raise ValueError(f"bad update tag {tag!r}")
    action, place = factors[0].lower(), factors[1].lower()
    aspect = factors[2].lower().replace("_", " ") if len(factors) == 3 else "null"
    if action not in ACTIONS or place not in PLACES or aspect not in ASPECTS:
        raise ValueError(f"bad update tag {tag!r}")
    return action, place, aspect


def defined_function_name(source):
    """Function.get_function_name: the single `def name(` in the code with its
    imports removed (after ast round-trip, so comments don't count); None if
    the code doesn't parse or defines zero or several functions."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # dataset code has invalid escapes like "\d"
            tree = ast.parse(source)
    except SyntaxError:
        return None

    class _DropImports(ast.NodeTransformer):
        def visit_Import(self, node):
            return None

        def visit_ImportFrom(self, node):
            return None

    slimmed = ast.unparse(_DropImports().visit(tree))
    names = re.findall(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", slimmed, re.DOTALL | re.IGNORECASE)
    return names[0] if len(names) == 1 else None


def update_statement(update_tag, api_path, implementation):
    """Manager.get_update_statements: the line(s) that install the update into
    the package. Raises ValueError where the authors' function fails."""
    action, place, aspect = parse_update_type(update_tag)
    parts = api_path.split(".")
    parent_path, old_name = ".".join(parts[:-1]), parts[-1]
    new_name = defined_function_name(implementation)
    if new_name is None:
        raise ValueError("implementation must define exactly one function")
    if place in ("argument", "output") or (action, aspect) == ("add", "semantics"):
        if old_name != new_name:
            raise ValueError("argument/output update must keep the function name")
        return f"{api_path} = {new_name}"
    if (action, aspect) == ("deprecate", "null"):
        if old_name != new_name:
            raise ValueError("deprecation must keep the function name")
        return f"del {api_path}"
    if (action, aspect) == ("modify", "name"):
        if old_name == new_name:
            raise ValueError("rename must change the function name")
        return f"del {parent_path}.{old_name}\nsetattr({parent_path}, '{new_name}', {new_name})"
    if (action, aspect) == ("add", "null"):
        if old_name == new_name:
            raise ValueError("added function must have a new name")
        return f"setattr({parent_path}, '{new_name}', {new_name})"
    raise ValueError(f"unexpected update scenario {update_tag!r}")


def _section(code, comment):
    """wrap_code_in_short_comment (comments only; keeps line numbers readable)."""
    return f"########## Start: {comment} ##########\n{code}\n##########  End : {comment} ##########"


def build_program(imports, implementation, statement, candidate, unit_test, test_name, with_update=True):
    """check_unit_tests' program: imports, updated implementation, update
    statement (only with the update), candidate, unit test, call. A final
    sentinel line marks a run that reached the end without an exception."""
    parts = [
        _section("\n".join(imports), "Import statement(s)"),
        _section(implementation, "Updated API implementation"),
    ]
    if with_update:
        parts.append(_section(statement, "Update statement(s)"))
    parts += [candidate, unit_test, f"{test_name}()", f"print({SENTINEL!r})"]
    return "\n".join(parts)


# -------------------------------------------------------------- execution

def run_program(program, python=CUA_PYTHON, timeout_s=TIMEOUT_S):
    """Runs one program in a fresh subprocess. Returns "passed", "failed" or
    "timeout" ("passed" = reached the end and exited 0)."""
    env = {"PATH": "/usr/bin:/bin", "HOME": tempfile.gettempdir(),
           "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    with tempfile.TemporaryDirectory(prefix="cua_run_") as cwd:
        try:
            done = subprocess.run([str(python), "-I", "-"], input=program, cwd=cwd, env=env,
                                  capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return "timeout"
    finished = done.returncode == 0 and done.stdout.rstrip().endswith(SENTINEL)
    return "passed" if finished else "failed"


def problem_parts(record):
    """Everything about a problem that the program needs, or an error string."""
    upd = record["update"]
    try:
        statement = update_statement(upd["update_type"], upd["api_path"], upd["implementation"])
    except ValueError as error:
        return None, f"update statement: {error}"
    tests = []
    for test in split_unit_tests(record["unit_tests"]):
        tests.append((test, defined_function_name(test)))
    return {"imports": split_imports(record["imports"]), "implementation": upd["implementation"],
            "statement": statement, "tests": tests}, None


def evaluate(record, candidate, python=CUA_PYTHON, timeout_s=TIMEOUT_S, full=False):
    """Scores one candidate against one problem.

    pass  = every unit test passes with the update installed;
    upass = pass and at least one unit test fails without it
            (their pass_criterion: all_pass_w_update and not all_pass_wo_update).
    A unit test whose function name can't be found (their Function check
    fails) counts as failed in both versions.

    With full=False, runs stop as soon as the outcome is decided (first
    failing test with the update; first failing test without it). With
    full=True every test runs both ways (used for eligibility, design §3.2,
    which needs to know that every test finishes within the timeout).
    """
    parts, error = problem_parts(record)
    if parts is None:
        return {"pass": False, "upass": False, "error": error, "with": [], "without": []}

    def run(test, name, with_update):
        if name is None:
            return "unparseable"
        program = build_program(parts["imports"], parts["implementation"], parts["statement"],
                                candidate, test, name, with_update)
        return run_program(program, python, timeout_s)

    with_results = []
    for test, name in parts["tests"]:
        with_results.append(run(test, name, True))
        if with_results[-1] != "passed" and not full:
            break
    all_pass = len(with_results) == len(parts["tests"]) and all(r == "passed" for r in with_results)

    without_results = []
    if all_pass or full:
        for test, name in parts["tests"]:
            without_results.append(run(test, name, False))
            if without_results[-1] != "passed" and not full:
                break
    any_fail_without = any(r != "passed" for r in without_results)
    return {"pass": all_pass, "upass": all_pass and any_fail_without, "error": None,
            "with": with_results, "without": without_results}


def parallel_map(function, items, jobs=1):
    if jobs <= 1:
        return [function(item) for item in items]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(function, items))


# ----------------------------------------------------------------- tasks

# Signatures in the dataset start with "def " (632), "function " (3) or nothing (35); the
# entry point is the first name followed by "(" (checked on all 670: the reference
# solution defines exactly that function).
FUNCTION_NAME_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def entry_point(solution_signature):
    match = FUNCTION_NAME_RE.search(solution_signature)
    if not match:
        raise ValueError(f"no function name in {solution_signature!r}")
    return match.group(1)


def signature_for_prompt(solution_signature):
    """'def f(a, b) -> int:' -> 'f(a, b) -> int' (design §4): from the function
    name on, without a trailing colon."""
    match = FUNCTION_NAME_RE.search(solution_signature)
    text = solution_signature[match.start(1):].strip() if match else solution_signature.strip()
    return text[:-1].rstrip() if text.endswith(":") else text


def task_id(order, api_path):
    return f"cua_{order:03d}_{api_path.replace('.', '_')}"


def reference_doc_title(record):
    return f"Update to {record['update']['api_path']}"


def reference_doc_content(record):
    """Description, then the new signature, then the docstring (design §4)."""
    upd = record["update"]
    return "\n\n".join([upd["description"].strip(), f"New signature: {upd['signature'].strip()}",
                        upd["docstring"].strip()])


def task_prompt(record):
    """The main study's template (design §4); unit tests are never shown."""
    return (f"Based on the documentation of the update to {record['update']['api_path']}, write a Python function "
            f"{signature_for_prompt(record['solution_signature'])} that solves the following problem. "
            f"Scenario: {record['scenario'].strip()} Problem: {record['problem'].strip()}")


def make_task(order, record):
    """Same five fields as the app's BatchTasks.json."""
    return {"id": task_id(order, record["update"]["api_path"]), "category": package_of(record),
            "prompt": task_prompt(record), "reference_doc_title": reference_doc_title(record),
            "reference_doc_content": reference_doc_content(record)}
