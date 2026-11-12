# Test-strength check — rule 4 review (2026-11-11)

Rule 4 of `test_strength_design.md`: every newly failing answer is listed with the first input where it differs from the reference; inputs in an ambiguous part of the spec are removed for both systems and the check re-run.

The researcher delegated this review ("I trust your decision making"). Run: `python3 test_strength.py` (sequential, 4 min); every frozen pass/fail reproduced (2,640 answers); 905 frozen passes → 817 survive, **88 newly failing**, in 7 tasks.

| Task | Answers | First differing input | Why it is defined by the spec/prompt |
|---|---|---|---|
| task_002_window_limiter | 18 | `max 3, timestamps [9, 1, 5]`, calls `11, 15, 19, 21` | Spec: timestamps are "in any order" and "discard every timestamp earlier than now − 10". The answers stop discarding at the first in-window timestamp (they assume a sorted list), so 1 is never removed at now = 15. The final list is compared only after an accepted request, so the task_002 judgment call (discarding on rejection) is not involved. |
| task_002_window_limiter | 7 | `max 1, timestamps []`, calls `0, 0, 10, 11` | Spec: discard timestamps *earlier than* now − 10, so at now = 10 the timestamp 0 stays and the request is rejected. The answers drop it (off-by-one at the window edge). |
| task_003_account_id_validation | 25 | `"ABC1234X"` → raises `ValueError` | Prompt: return True if valid "or False otherwise". A non-digit check character is invalid (rule 4 of the spec); raising instead of returning False is wrong. |
| task_003_account_id_validation | 1 | `"A1C12340"` → True | Rule 2: the first 3 characters must be uppercase letters; `1` is a digit. |
| task_010_coordinate_pack | 21 | `(0.04, −0.04)` → `"05000499"` | Spec: "rounding to the nearest integer"; −0.4 rounds to 0 → 500. The answers truncate (`int(499.6)` = 499). Not a rounding tie (ties are never generated). |
| task_011_duration_format | 5 | `360000` → `"40h00m"` | Spec: `{hours}h{minutes:02d}m` for any duration ≥ 3600, no upper bound; 100 hours must print `100h00m`. |
| task_023_batch_code | 5 | `"BT-2X-00FF-E"` → raises `ValueError` | Prompt says return False otherwise; YY must be a 2-digit year. |
| task_023_batch_code | 3 | `"BT-29-0001-B"` → False | Year 29 is in 20–39; 0+0+0+1 = 1 → "B"; valid. |
| task_024_sensor_label | 1 | `"abcdeF1"` → True | Rule 3: only lowercase letters, digits and `_`. |
| task_025_flight_slot | 2 | `"13h15/1"` → raises `ValueError` | Shape must be `HH:MM/R`; prompt says return False otherwise. |

**Decision: no input is ambiguous → nothing removed, no re-run.** All 88 failures are genuine bugs on behavior the spec or prompt defines. `results_test_strength.json` is the final step A result.
