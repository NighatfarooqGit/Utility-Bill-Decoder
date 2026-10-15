"""
Build submission.zip at the project root.

Layout inside the ZIP (as required by the guide):
  output/level1.csv
  output/level2.csv
  source/README.md
  source/.env.example
  source/*.py
  demo/demo.mp4  (optional)
"""
import re, zipfile, pathlib, sys

# Project root is one level above this script (source/)
project_root = pathlib.Path(__file__).resolve().parent.parent

SKIP_PARTS = {"__pycache__", ".env", ".cache", "venv", ".git"}
SKIP_FILES  = {"make_zip.py", "test_key.py", "make_templates.py", "check_csv.py"}

def collect(folder_name):
    folder = project_root / folder_name
    if not folder.exists():
        return []
    files = []
    for p in folder.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(project_root)
        parts = set(rel.parts)
        if parts & SKIP_PARTS:
            continue
        if p.name in SKIP_FILES:
            continue
        files.append(p)
    return files

# Gather files
output_files = collect("output")
source_files = collect("source")
demo_files   = collect("demo")

if not output_files:
    print("WARNING: output/ folder is empty or missing. Run the pipeline first.")

all_files = output_files + source_files + demo_files

# Scan for accidental API key leaks
KEY_RE = re.compile(r"AIza[0-9A-Za-z_\-]{20,}|AQ\.[0-9A-Za-z_\-]{20,}")
TEXT_EXTS = {".py", ".md", ".txt", ".example", ".csv", ".json", ".env"}
for p in all_files:
    if p.suffix.lower() in TEXT_EXTS:
        text = p.read_text(encoding="utf-8", errors="ignore")
        if KEY_RE.search(text):
            sys.exit(f"ERROR: potential API key found in {p.relative_to(project_root)}. Remove it first.")

out = project_root / "submission.zip"
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in all_files:
        arc = p.relative_to(project_root).as_posix()
        z.write(p, arc)
        print(f"  + {arc}")

size_mb = round(out.stat().st_size / 1e6, 2)
print(f"\nCreated: {out}")
print(f"Size:    {size_mb} MB  (limit: 15 MB)")
if size_mb > 15:
    print("WARNING: ZIP exceeds 15 MB limit!")
