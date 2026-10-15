import csv, json, sys
from pathlib import Path
from normalize import KEYS

out = Path(sys.argv[1])
problems = []
rows1 = list(csv.DictReader(open(out / "level1.csv", encoding="utf-8", newline="")))
rows2 = list(csv.DictReader(open(out / "level2.csv", encoding="utf-8", newline="")))
n1 = int(sys.argv[2]) if len(sys.argv) > 2 else 10
n2 = int(sys.argv[3]) if len(sys.argv) > 3 else 120
if len(rows1) != n1: problems.append(f"level1 has {len(rows1)} rows, expected {n1}")
if len(rows2) != n2: problems.append(f"level2 has {len(rows2)} rows, expected {n2}")
for r in rows1:
    try:
        d = json.loads(r["json"])
        missing = [k for k in KEYS if k not in d]
        nulls = [k for k in KEYS if d.get(k) is None]
        print(r["bill_id"], "| missing keys:", missing, "| null fields:", len(nulls))
        if missing: problems.append(f"{r['bill_id']} missing {missing}")
    except Exception as e:
        problems.append(f"{r['bill_id']} bad JSON: {e}")
for r in rows2:
    if not r["answer"].strip(): problems.append(f"empty answer {r['bill_id']} {r['question_id']}")
    if "could not determine" in r["answer"]: print("fallback answer:", r["bill_id"], r["question_id"])
print("\nPROBLEMS:" if problems else "\nAll checks passed.")
for p in problems: print(" -", p)