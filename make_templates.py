import csv
from pathlib import Path

bills = sorted(p.stem for p in Path("../train/bills").iterdir()
               if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
QUESTIONS = [
    "How much of my bill is taxes?",
    "What is the total amount I need to pay by the due date?",
    "How much extra will I pay if I pay after the due date?",
    "How does my usage this month compare with my average of the previous months?",
    "Which month in my usage history was the highest?",
    "How many months in my history went above 200 units?",
    "What is my average cost per unit this month?",
    "Explain the biggest charge on my bill.",
    "Do I have any arrears or credit carried forward?",
    "If I use 10% more units next month, roughly how many units would that be?",
    "What are my sanctioned load and tariff?",
    "What does the message board on the bill say?",
]
out = Path("../train/csv")
out.mkdir(parents=True, exist_ok=True)
with open(out / "level1.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["bill_id", "json"])
    for b in bills:
        w.writerow([b, ""])
with open(out / "level2.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["bill_id", "question_id", "question", "answer"])
    for b in bills:
        for i, q in enumerate(QUESTIONS, 1):
            w.writerow([b, f"Q{i}", q, ""])
print("templates written for", len(bills), "bills")