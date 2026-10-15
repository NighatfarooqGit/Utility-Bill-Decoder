import argparse, csv, json
from pathlib import Path

import llm, prompts, normalize

IMG_EXT = (".png", ".jpg", ".jpeg")
FALLBACK = "I could not determine this from the bill."


def sanity_warnings(bill):
    fn = getattr(normalize, "sanity", None)
    return fn(bill) if fn else []


def safe(fn, default):
    try:
        return fn()
    except Exception as e:
        print("  ERROR:", str(e)[:200])
        return default


def find_image(bills_dir, bill_id):
    for ext in IMG_EXT:
        p = Path(bills_dir) / f"{bill_id}{ext}"
        if p.exists():
            return p
    for p in Path(bills_dir).iterdir():
        if p.stem.lower() == bill_id.lower():
            return p
    return None


def extract_level1(img):
    return normalize.level1(llm.ask_json(prompts.level1_prompt(), img))


def extract_facts(img):
    return safe(lambda: llm.ask_json(prompts.FACTS_PROMPT, img), {})


def answer_questions(img, bill, facts, rows):
    if img is None or not rows:
        return {r["question_id"]: FALLBACK for r in rows}
    qs = [{"id": r["question_id"], "question": r["question"]} for r in rows]
    derived = normalize.derive(bill, facts)
    data = safe(lambda: llm.ask_json(prompts.qa_prompt(bill, facts, derived, qs), img), {})
    out = {}
    for q in qs:
        a = data.get(q["id"])
        if isinstance(a, (dict, list)):
            a = json.dumps(a, ensure_ascii=False)
        if not (isinstance(a, str) and a.strip()):  # retry this one question alone
            single = safe(lambda q=q: llm.ask_json(
                prompts.qa_prompt(bill, facts, derived, [q]), img), {})
            a = single.get(q["id"])
        out[q["id"]] = a.strip() if isinstance(a, str) and a.strip() else FALLBACK
    return out


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def write_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def diff(exp, got, path=""):
    out = []
    if isinstance(exp, dict):
        got = got if isinstance(got, dict) else {}
        for k in exp:
            out += diff(exp[k], got.get(k), f"{path}.{k}")
    elif isinstance(exp, list):
        if not isinstance(got, list) or len(got) != len(exp):
            n = len(got) if isinstance(got, list) else got
            out.append(f"{path}: expected {len(exp)} items, got {n}")
        else:
            for i, (e, g) in enumerate(zip(exp, got)):
                out += diff(e, g, f"{path}[{i}]")
    elif isinstance(exp, (int, float)) and not isinstance(exp, bool):
        if not isinstance(got, (int, float)) or abs(exp - got) > 1:
            out.append(f"{path}: expected {exp}, got {got}")
    elif exp != got:
        out.append(f"{path}: expected {exp!r}, got {got!r}")
    return out


def cmd_extract(a):
    bill = extract_level1(a.image)
    print(json.dumps(bill, indent=2, ensure_ascii=False))
    for msg in sanity_warnings(bill):
        print("WARNING:", msg)
    if a.facts:
        print(json.dumps(extract_facts(a.image), indent=2, ensure_ascii=False))
    if a.expected:
        exp = json.loads(Path(a.expected).read_text(encoding="utf-8"))
        problems = diff(exp, bill)
        print("\nMATCHES EXPECTED" if not problems else "\nDIFFERENCES:\n" + "\n".join(problems))


def cmd_ask(a):
    bill = extract_level1(a.image)
    facts = extract_facts(a.image)
    rows = [{"question_id": f"Q{i + 1}", "question": q} for i, q in enumerate(a.questions)]
    for qid, ans in answer_questions(a.image, bill, facts, rows).items():
        print(f"\n{qid}: {ans}")


def cmd_run(a):
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    f1, rows1 = read_csv(a.level1)
    f2, rows2 = read_csv(a.level2)
    flagged = []
    for r in rows1:
        bill_id = r["bill_id"]
        print(f"\n=== {bill_id}")
        img = find_image(a.bills, bill_id)
        if img is None:
            print("  image not found")
            bill, facts = normalize.level1({}), {}
        else:
            bill = safe(lambda: extract_level1(img), normalize.level1({}))
            facts = extract_facts(img)
            warnings = sanity_warnings(bill)
            for msg in warnings:
                print("  WARNING:", msg)
            if warnings:
                flagged.append(bill_id)
        r["json"] = json.dumps(bill, ensure_ascii=False, separators=(",", ":"))
        rows_q = [x for x in rows2 if x["bill_id"] == bill_id]
        answers = answer_questions(img, bill, facts, rows_q)
        for x in rows_q:
            x["answer"] = answers[x["question_id"]]
        write_csv(out_dir / "level1.csv", f1, rows1)   # saved after every bill
        write_csv(out_dir / "level2.csv", f2, rows2)
    print("\nDone. Model used last:", llm.last_model)
    if flagged:
        print("Bills with warnings (open these images and check by eye):", ", ".join(flagged))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Utility Bill Decoder")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract", help="Level 1 JSON for one bill image")
    e.add_argument("image")
    e.add_argument("--expected")
    e.add_argument("--facts", action="store_true")
    e.set_defaults(fn=cmd_extract)
    q = sub.add_parser("ask", help="answer questions about one bill")
    q.add_argument("image")
    q.add_argument("questions", nargs="+")
    q.set_defaults(fn=cmd_ask)
    r = sub.add_parser("run", help="process a folder of bills and fill both CSV templates")
    r.add_argument("--bills", required=True)
    r.add_argument("--level1", required=True)
    r.add_argument("--level2", required=True)
    r.add_argument("--out", required=True)
    r.set_defaults(fn=cmd_run)
    args = p.parse_args()
    args.fn(args)