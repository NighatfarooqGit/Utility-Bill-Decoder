# Utility Bill Decoder

AI-powered solution for the WTQ Build Track challenge. Reads electricity bills from K-Electric (KE), LESCO, and IESCO, extracts structured data (Level 1), and answers customer questions about each bill (Level 2).

## Requirements

- Python 3.12
- Dependencies listed in `requirements.txt`

## Setup

1. **Install dependencies** (from the project root):

   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables**:

   ```bash
   cp source/.env.example .env
   # Edit .env and set API_KEY to your Google AI Studio key
   ```

3. **Test your API key**:

   ```bash
   python source/test_key.py
   # Expected output: {'ok': True}
   ```

## Running the solution

### Web interface (recommended for demo)

```bash
python source/app.py
```

Opens a browser UI with three tabs:
- **Extract Bill** — upload any bill image and see the structured JSON fields, charges table, taxes table, and sanity warnings instantly
- **Ask a Question** — upload a bill and ask anything about it in plain English
- **Run Test Batch** — point it at your `test/bills` folder, upload the two CSV templates, click Run, and download the completed CSVs

### Process test bills and generate both CSV files (command line)

Run from the **project root** directory:

```bash
python source/main.py run \
  --bills  test/bills \
  --level1 test/csv/level1.csv \
  --level2 test/csv/level2.csv \
  --out    output
```

This reads every bill image in `test/bills/`, fills in the `json` column of `level1.csv` (Level 1 extraction), fills in the `answer` column of `level2.csv` (Level 2 Q&A), and writes the completed files to `output/`.

### Process training bills (for development / testing)

```bash
python source/main.py run \
  --bills  train/bills \
  --level1 train/csv/level1.csv \
  --level2 train/csv/level2.csv \
  --out    train/output
```

### Extract a single bill (debug)

```bash
python source/main.py extract train/bills/KESC_0008.png
python source/main.py extract train/bills/KESC_0008.png --expected train/expected_KESC_0008.json
```

### Ask questions about a single bill (debug)

```bash
python source/main.py ask train/bills/KESC_0008.png "How much of my bill is taxes?" "What is my tariff?"
```

### Validate output files

```bash
python source/validate.py output 10 120
```

### Build the submission ZIP

```bash
python source/make_zip.py
```

## Project structure

```
.
├── source/
│   ├── main.py            # Entry point: extract, ask, run commands
│   ├── llm.py             # Google Gemini API client with caching and retry
│   ├── prompts.py         # All prompts: Level 1 extraction, facts, Q&A
│   ├── normalize.py       # Schema enforcement, sanity checks, derived stats
│   ├── validate.py        # Post-run CSV validation
│   ├── make_templates.py  # Generate blank CSV templates from a bills folder
│   ├── make_zip.py        # Build submission.zip
│   ├── test_key.py        # Quick API key smoke test
│   ├── README.md          # This file
│   └── .env.example       # Environment variable template
├── train/
│   ├── bills/             # 5 training bill images
│   ├── csv/               # Blank CSV templates for training bills
│   └── output/            # Generated training results
├── output/                # Generated test results (created at runtime)
├── requirements.txt
└── .env                   # Your API key (not included in submission)
```

## How it works

1. **Level 1 — Extraction** (`llm.py` + `prompts.py` + `normalize.py`):  
   Each bill image is sent to the Gemini model with a detailed extraction prompt that includes the full JSON schema, field-by-field rules, and the worked KESC_0008 example from the guide. The raw response is normalised (type coercion, date formatting, sign rules for credits/subsidies) and sanity-checked before being written to `level1.csv`.

2. **Level 2 — Q&A** (`prompts.py` → `qa_prompt`):  
   A second pass extracts extra bill details (usage history, billing history, charge line labels, message board text). Pre-computed derived statistics (tax percentage, average usage, cost per unit, etc.) are calculated in Python and injected into the Q&A prompt alongside the Level 1 data, so the model only needs to compose the answer rather than do arithmetic.

3. **Caching** (`llm.py`):  
   Every model response is cached in `source/.cache/` keyed by a SHA-256 hash of the model name, prompt, and image bytes. Re-running the pipeline on unchanged inputs is instant and free.

## Environment variables

| Variable             | Purpose                         | Example                    |
|----------------------|---------------------------------|----------------------------|
| `MODEL_PROVIDER`     | Must be `google`                | `google`                   |
| `MODEL_NAME`         | Primary model ID                | `gemini-3.5-flash-lite`    |
| `MODEL_FALLBACK_NAME`| Fallback model ID               | `gemini-3.1-flash-lite`    |
| `API_KEY`            | Google AI Studio API key        | `your-api-key-here`        |

## AI usage

| Category                  | Tools / models used                                      |
|---------------------------|----------------------------------------------------------|
| **Bill reading (runtime)** | Google Gemini `gemini-3.5-flash-lite` (primary), `gemini-3.1-flash-lite` (fallback) |
| **Code assistance**        | Kiro (Anthropic Claude) — used to help write and review source code |
| **Other AI tools**         | None                                                     |

Only the Gemini models listed above are called at runtime. No other LLMs, invoice extraction APIs, or Azure/AWS services are used.
