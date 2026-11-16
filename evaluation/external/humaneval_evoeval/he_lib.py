"""Shared helpers for the HumanEval+ vs. EvoEval_subtle memorization check (design.md).

Loads the two pinned datasets, builds the reference documents and prompts
(design §4), and assembles and runs programs. Execution reuses the
CodeUpdateArena runner (`cua_lib.run_program`: pinned environment,
`python -I -`, empty temporary folder, sentinel rule), so both external
studies execute code the same way.

The datasets' own code (prompts, reference solutions, tests) and every model
answer run only in the pinned environment (design §3.1).
"""
import ast
import hashlib
import importlib.util
import json
import re
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load_cua_lib():
    """Loaded by file path, not via sys.path: both external folders have a
    build_tasks.py, so putting codeupdatearena/ on sys.path would shadow ours."""
    spec = importlib.util.spec_from_file_location("cua_lib", HERE.parent / "codeupdatearena" / "cua_lib.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cua_lib = _load_cua_lib()

PYTHON = cua_lib.CUA_PYTHON
SENTINEL = cua_lib.SENTINEL
ELIGIBILITY_TIMEOUT_S = 10  # design §3.3
ANSWER_TIMEOUT_S = 30       # design §4
PAIR_NUMBERS = range(100)   # EvoEval/n <-> HumanEval/n, n = 0..99 (design §3.2)

DATASETS = {
    "original": {"name": "HumanEval+", "huggingFace": "evalplus/humanevalplus",
                 "revision": "d32357cf319e50e9c8d8dab5ea876c72b0fd321b",
                 "sha256": "908377f1daf28dcb36846db73a5662b2e05a9907407c2696c89ad9d3b0b04492",
                 "file": HERE / "data" / "humanevalplus.jsonl", "idPrefix": "HumanEval/"},
    "subtle": {"name": "EvoEval_subtle", "huggingFace": "evoeval/EvoEval_subtle",
               "revision": "b1d6d9da3220957e7d299b0fc90189babb45ce88",
               "sha256": "7049d125c6ca5525df2973c70c5fcb0a4c175bd5cbac6cbe8598a3eaa4d4386d",
               "file": HERE / "data" / "evoeval_subtle.jsonl", "idPrefix": "EvoEval/"},
}
VERSIONS = ("original", "subtle")
IMPORT_LINE_RE = re.compile(r"^(import\s|from\s+\S+\s+import\s)")


# ---------------------------------------------------------------- datasets

def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def text_sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def download(version):
    """Fetches one dataset at its pinned revision into data/ (design §3.1);
    refuses a file whose SHA-256 differs."""
    info = DATASETS[version]
    path = info["file"]
    if not path.exists():
        path.parent.mkdir(exist_ok=True)
        url = f"https://huggingface.co/datasets/{info['huggingFace']}/resolve/{info['revision']}/test.jsonl"
        partial = path.with_suffix(".partial")
        urllib.request.urlretrieve(url, partial)
        partial.rename(path)
    if file_sha256(path) != info["sha256"]:
        raise SystemExit(f"{path.name}: SHA-256 differs from the pinned {info['sha256']}")
    return path


def load_version(version):
    """task number -> record, after checking the file's hash."""
    info = DATASETS[version]
    path = download(version)
    records = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                if not record["task_id"].startswith(info["idPrefix"]):
                    raise SystemExit(f"{path.name}: unexpected task id {record['task_id']}")
                records[int(record["task_id"][len(info["idPrefix"]):])] = record
    return records


def load_pairs():
    """n -> {"original": HumanEval+/n, "subtle": EvoEval/n} for n = 0..99."""
    original, subtle = load_version("original"), load_version("subtle")
    return {n: {"original": original[n], "subtle": subtle[n]} for n in PAIR_NUMBERS}


def record_hashes(record):
    """Per-version hashes recorded at selection and re-checked when scoring (design §3.6)."""
    return {field: text_sha256(record[field]) for field in ("prompt", "canonical_solution", "test")}


# ------------------------------------------------------------ prompt parts

def header(record):
    """Everything in the prompt before `def <entry_point>(`."""
    marker = f"def {record['entry_point']}("
    index = record["prompt"].find(marker)
    if index < 0:
        raise ValueError(f"{record['task_id']}: no {marker} in the prompt")
    return record["prompt"][:index]


def header_is_plain(record):
    """Design §3.3: only blank lines and import lines before the target function."""
    return all(not line.strip() or IMPORT_LINE_RE.match(line) for line in header(record).splitlines())


def header_imports(record):
    """The import lines prepended to every answer (design §4)."""
    return [line for line in header(record).splitlines() if IMPORT_LINE_RE.match(line)]


def _target_function(record):
    tree = ast.parse(record["prompt"])
    found = [node for node in tree.body
             if isinstance(node, ast.FunctionDef) and node.name == record["entry_point"]]
    if len(found) != 1:
        raise ValueError(f"{record['task_id']}: expected one def {record['entry_point']}")
    return found[0]


def signature(record):
    """`name(params) -> ret` as written in the prompt: the def line(s) up to the
    docstring, joined, without `def` and the final colon (design §4)."""
    node = _target_function(record)
    lines = record["prompt"].splitlines()[node.lineno - 1:node.body[0].lineno - 1]
    text = " ".join(line.strip() for line in lines)
    if not text.startswith("def ") or not text.endswith(":"):
        raise ValueError(f"{record['task_id']}: unexpected signature {text!r}")
    return text[len("def "):-1].rstrip()


def docstring(record):
    text = ast.get_docstring(_target_function(record), clean=True)
    if not text:
        raise ValueError(f"{record['task_id']}: no docstring")
    return text.strip()


def reference_doc_title(record):
    return f"Specification of {record['entry_point']}"


def reference_doc_content(record):
    return f"Signature: {signature(record)}\n\n{docstring(record)}"


def task_prompt(record):
    return (f"Based on the specification of {record['entry_point']}, write a Python function "
            f"{signature(record)} that does what the specification describes.")


def task_id(position, version, record):
    return f"{'hep' if version == 'original' else 'evs'}_{position:03d}_{record['entry_point']}"


def make_task(position, version, record):
    """Same five fields as the app's BatchTasks.json."""
    return {"id": task_id(position, version, record),
            "category": "humaneval_plus" if version == "original" else "evoeval_subtle",
            "prompt": task_prompt(record), "reference_doc_title": reference_doc_title(record),
            "reference_doc_content": reference_doc_content(record)}


# -------------------------------------------------------------- programs

def build_program(imports, code, test, call_name):
    """imports + code + the dataset's test + check(<call_name>) + sentinel.

    The test is compiled on its own, with Python's integer-digit limit lifted
    only while compiling and restored before it runs (design §4, amended
    2026-11-15 before any selection): some tests contain literals longer than
    the 4,300-digit default and lift the limit themselves with
    sys.set_int_max_str_digits(0) — but in one concatenated program the
    literal is parsed before that line can run (EvoEval/83 failed this way).
    At run time the limit is exactly what the test sets."""
    test_runner = (
        "import sys as _he_sys\n"
        "_he_limit = _he_sys.get_int_max_str_digits()\n"
        "_he_sys.set_int_max_str_digits(0)\n"
        f"_he_test = compile({test!r}, '<test>', 'exec')\n"
        "_he_sys.set_int_max_str_digits(_he_limit)\n"
        "exec(_he_test)")
    parts = ["\n".join(imports), code, test_runner, f"check({call_name})", f"print({SENTINEL!r})"]
    return "\n".join(parts) + "\n"


def reference_code(record):
    return record["prompt"] + record["canonical_solution"]


def renamed_reference_code(original, subtle):
    """The original's reference solution, callable under the Subtle entry point
    (design §3.3, "the change is tested")."""
    code = reference_code(original)
    if original["entry_point"] != subtle["entry_point"]:
        code += f"\n\n{subtle['entry_point']} = {original['entry_point']}\n"
    return code


def defines(code, name):
    return re.search(rf"^\s*def\s+{re.escape(name)}\s*\(", code, re.MULTILINE) is not None


def run(imports, code, test, call_name, timeout_s):
    """'passed', 'failed' or 'timeout' (cua_lib.run_program's sentinel rule)."""
    return cua_lib.run_program(build_program(imports, code, test, call_name), PYTHON, timeout_s)


def candidate_result(record, code, timeout_s=ANSWER_TIMEOUT_S):
    """Design §4: the version's header imports + the extracted code vs. its own test."""
    if code is None:
        return "no_code"
    return run(header_imports(record), code, record["test"], record["entry_point"], timeout_s)


def original_solution_result(original, subtle, code, timeout_s=ANSWER_TIMEOUT_S):
    """Design §4, signature: a Subtle answer against the original's test, calling
    the Subtle entry point if the code defines it, else the original's. Both
    versions' header imports are prepended (the answer was written for the
    Subtle prompt; the original's test may need its own)."""
    if code is None:
        return "no_code"
    name = subtle["entry_point"] if defines(code, subtle["entry_point"]) else original["entry_point"]
    imports = list(dict.fromkeys(header_imports(subtle) + header_imports(original)))
    return run(imports, code, original["test"], name, timeout_s)
