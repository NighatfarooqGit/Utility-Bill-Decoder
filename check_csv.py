"""Quick sanity check on level1 and level2 CSV output."""
import csv, json, sys
from pathlib import Path

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("train/output")

with open(out / "level1.csv", encoding="utf-8", newline="") as f:
    rows1 = list(csv.DictReader(f))

print("level1.csv columns:", list(rows1[0].keys()))
print("rows:", len(rows1))
for r in rows1:
    j = r["json"]
    assert "\n" not in j, f"JSON has newlines in {r['bill_id']}"
    obj = json.loads(j)
    print(f"  {r['bill_id']}  JSON len={len(j)}  keys={len(obj)}")

with open(out / "level2.csv", encoding="utf-8", newline="") as f:
    rows2 = list(csv.DictReader(f))

print("\nlevel2.csv columns:", list(rows2[0].keys()))
print("rows:", len(rows2))
empty = [r for r in rows2 if not r["answer"].strip()]
fallback = [r for r in rows2 if "could not determine" in r["answer"]]
print("empty answers:", len(empty))
print("fallback answers:", len(fallback))
print("\nAll CSV checks passed." if not empty else "WARNING: empty answers found!")
