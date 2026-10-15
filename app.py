"""
Utility Bill Decoder — Gradio web interface
Run: python source/app.py   (from the project root)
"""
import csv, json, sys, tempfile
from pathlib import Path

import gradio as gr

# Allow imports from source/ when launched from project root
sys.path.insert(0, str(Path(__file__).parent))
import llm, prompts, normalize
from main import (
    extract_level1, extract_facts, answer_questions,
    find_image, read_csv, write_csv, sanity_warnings, safe, FALLBACK,
)

IMG_EXT = (".png", ".jpg", ".jpeg")

# ── helpers ────────────────────────────────────────────────────────────────

def fmt_json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False)


def charges_table(bill):
    rows = [[c["type"], c["amount"]] for c in (bill.get("charges") or [])]
    return rows or [["—", "—"]]


def taxes_table(bill):
    rows = [[t["type"], t["amount"]] for t in (bill.get("taxes") or [])]
    return rows or [["—", "—"]]


def summary_table(bill):
    fields = [
        ("Provider",               bill.get("provider")),
        ("Tariff",                 bill.get("tariff")),
        ("Sanctioned load (kW)",   bill.get("sanctioned_load_kw")),
        ("Bill month",             bill.get("bill_month")),
        ("Reading date",           bill.get("reading_date")),
        ("Issue date",             bill.get("issue_date")),
        ("Due date",               bill.get("due_date")),
        ("Previous reading",       bill.get("previous_reading")),
        ("Current reading",        bill.get("current_reading")),
        ("Units consumed",         bill.get("units_consumed")),
        ("Total charges",          bill.get("total_charges")),
        ("Total taxes",            bill.get("total_taxes")),
        ("Current bill",           bill.get("current_bill")),
        ("Arrears",                bill.get("arrears")),
        ("Payable within due date",bill.get("payable_within_due_date")),
        ("Payable after due date", bill.get("payable_after_due_date")),
    ]
    return [[k, str(v) if v is not None else "null"] for k, v in fields]


# ── Tab 1: single bill extraction ──────────────────────────────────────────

def run_extract(image_file):
    if image_file is None:
        return "Upload a bill image first.", [], [], [], ""
    try:
        bill = extract_level1(image_file)
        warnings = sanity_warnings(bill)
        warn_text = "\n".join(f"⚠ {w}" for w in warnings) if warnings else "✓ No sanity warnings."
        return (
            warn_text,
            summary_table(bill),
            charges_table(bill),
            taxes_table(bill),
            fmt_json(bill),
        )
    except Exception as e:
        return f"Error: {e}", [], [], [], ""


# ── Tab 2: Q&A ─────────────────────────────────────────────────────────────

def run_qa(image_file, question):
    if image_file is None:
        return "Upload a bill image first."
    if not question.strip():
        return "Type a question."
    try:
        bill  = extract_level1(image_file)
        facts = safe(lambda: extract_facts(image_file), {})
        rows  = [{"question_id": "Q1", "question": question.strip()}]
        answers = answer_questions(image_file, bill, facts, rows)
        return answers.get("Q1", FALLBACK)
    except Exception as e:
        return f"Error: {e}"


# ── Tab 3: run full test folder ─────────────────────────────────────────────

def run_batch(bills_dir, level1_csv, level2_csv):
    """Process a folder of bills and return two filled-in CSV files."""
    if not bills_dir or not bills_dir.strip():
        return None, None, "Enter the path to your bills folder."
    bills_path = Path(bills_dir.strip())
    if not bills_path.exists():
        return None, None, f"Folder not found: {bills_path}"
    if level1_csv is None or level2_csv is None:
        return None, None, "Upload both CSV template files."

    log_lines = []

    try:
        f1, rows1 = read_csv(level1_csv)
        f2, rows2 = read_csv(level2_csv)
    except Exception as e:
        return None, None, f"Could not read CSV templates: {e}"

    for r in rows1:
        bill_id = r["bill_id"]
        log_lines.append(f"Processing {bill_id}…")
        img = find_image(str(bills_path), bill_id)
        if img is None:
            log_lines.append(f"  ✗ image not found for {bill_id}")
            bill, facts = normalize.level1({}), {}
        else:
            bill  = safe(lambda img=img: extract_level1(img), normalize.level1({}))
            facts = safe(lambda img=img: extract_facts(img), {})
            warnings = sanity_warnings(bill)
            for w in warnings:
                log_lines.append(f"  ⚠ {w}")
        r["json"] = json.dumps(bill, ensure_ascii=False, separators=(",", ":"))
        rows_q = [x for x in rows2 if x["bill_id"] == bill_id]
        answers = answer_questions(img, bill, facts, rows_q)
        for x in rows_q:
            x["answer"] = answers[x["question_id"]]
        log_lines.append(f"  ✓ {bill_id} done")

    # Write to temp files so Gradio can offer them as downloads
    tmp1 = tempfile.NamedTemporaryFile(
        delete=False, suffix="_level1.csv", mode="w",
        newline="", encoding="utf-8"
    )
    tmp2 = tempfile.NamedTemporaryFile(
        delete=False, suffix="_level2.csv", mode="w",
        newline="", encoding="utf-8"
    )
    write_csv(tmp1.name, f1, rows1)
    write_csv(tmp2.name, f2, rows2)
    tmp1.close()
    tmp2.close()

    log_lines.append(f"\nDone. Model: {llm.last_model or 'cached'}")
    return tmp1.name, tmp2.name, "\n".join(log_lines)


# ── UI layout ───────────────────────────────────────────────────────────────

THEME = gr.themes.Soft(primary_hue="blue", neutral_hue="slate")

with gr.Blocks(title="Utility Bill Decoder") as demo:
    gr.Markdown(
        """
        # ⚡ Utility Bill Decoder
        AI-powered extraction and Q&A for K-Electric, LESCO, and IESCO electricity bills.
        """
    )

    # ── Tab 1 ──────────────────────────────────────────────────────────────
    with gr.Tab("Extract Bill"):
        gr.Markdown("Upload a bill image to extract all structured fields.")
        with gr.Row():
            with gr.Column(scale=1):
                img_input = gr.Image(
                    type="filepath", label="Bill image (.png / .jpg)",
                    height=420,
                )
                extract_btn = gr.Button("Extract", variant="primary")
                warn_box = gr.Textbox(label="Sanity check", lines=3, interactive=False)
            with gr.Column(scale=2):
                with gr.Tabs():
                    with gr.Tab("Summary"):
                        summary_out = gr.Dataframe(
                            headers=["Field", "Value"],
                            datatype=["str", "str"],
                            interactive=False,
                            wrap=True,
                        )
                    with gr.Tab("Charges"):
                        charges_out = gr.Dataframe(
                            headers=["Type", "Amount (PKR)"],
                            datatype=["str", "number"],
                            interactive=False,
                        )
                    with gr.Tab("Taxes"):
                        taxes_out = gr.Dataframe(
                            headers=["Type", "Amount (PKR)"],
                            datatype=["str", "number"],
                            interactive=False,
                        )
                    with gr.Tab("Raw JSON"):
                        json_out = gr.Code(language="json", label="Level 1 JSON")

        extract_btn.click(
            fn=run_extract,
            inputs=img_input,
            outputs=[warn_box, summary_out, charges_out, taxes_out, json_out],
        )

    # ── Tab 2 ──────────────────────────────────────────────────────────────
    with gr.Tab("Ask a Question"):
        gr.Markdown("Upload a bill, then ask anything about it in plain English.")
        with gr.Row():
            with gr.Column(scale=1):
                qa_img = gr.Image(
                    type="filepath", label="Bill image",
                    height=350,
                )
                qa_question = gr.Textbox(
                    label="Your question",
                    placeholder="e.g. How much of my bill is taxes?",
                    lines=2,
                )
                qa_btn = gr.Button("Ask", variant="primary")
            with gr.Column(scale=2):
                qa_answer = gr.Textbox(
                    label="Answer", lines=8, interactive=False
                )

        gr.Examples(
            examples=[
                ["How much of my bill is taxes?"],
                ["What is the total amount I need to pay by the due date?"],
                ["How much extra will I pay if I pay after the due date?"],
                ["How does my usage this month compare with my average?"],
                ["Which month in my history had the highest usage?"],
                ["What is my average cost per unit this month?"],
                ["Explain the biggest charge on my bill."],
                ["Do I have any arrears or credit carried forward?"],
                ["What are my sanctioned load and tariff?"],
                ["What does the message board on the bill say?"],
            ],
            inputs=qa_question,
        )

        qa_btn.click(
            fn=run_qa,
            inputs=[qa_img, qa_question],
            outputs=qa_answer,
        )

    # ── Tab 3 ──────────────────────────────────────────────────────────────
    with gr.Tab("Run Test Batch"):
        gr.Markdown(
            """
            Process all test bills at once and download the completed CSV files.
            1. Enter the path to your `test/bills` folder (or `train/bills` to test on training data).
            2. Upload the two blank CSV templates.
            3. Click **Run** — both completed CSVs will appear as downloads.
            """
        )
        with gr.Row():
            with gr.Column():
                batch_dir = gr.Textbox(
                    label="Bills folder path",
                    placeholder="e.g.  train/bills  or  test/bills",
                    value="train/bills",
                )
                batch_l1 = gr.File(label="level1.csv template", file_types=[".csv"])
                batch_l2 = gr.File(label="level2.csv template", file_types=[".csv"])
                batch_btn = gr.Button("Run batch", variant="primary")
            with gr.Column():
                batch_log  = gr.Textbox(label="Progress log", lines=18, interactive=False)
                out_l1     = gr.File(label="Download level1.csv")
                out_l2     = gr.File(label="Download level2.csv")

        batch_btn.click(
            fn=run_batch,
            inputs=[batch_dir, batch_l1, batch_l2],
            outputs=[out_l1, out_l2, batch_log],
        )

    gr.Markdown(
        """
        ---
        Models: `gemini-3.5-flash-lite` (primary) · `gemini-3.1-flash-lite` (fallback) · Google AI Studio
        """
    )

if __name__ == "__main__":
    demo.launch(theme=THEME, inbrowser=True)
