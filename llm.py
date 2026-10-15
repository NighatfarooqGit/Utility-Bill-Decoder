import os, re, json, time, hashlib, mimetypes
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

ALLOWED = {"gemini-3.5-flash-lite", "gemini-3.1-flash-lite"}
PROVIDER = os.getenv("MODEL_PROVIDER", "google")
MODELS = [m for m in (os.getenv("MODEL_NAME", "gemini-3.5-flash-lite"),
                      os.getenv("MODEL_FALLBACK_NAME")) if m]
if PROVIDER != "google" or any(m not in ALLOWED for m in MODELS):
    raise SystemExit(f"Only these models are allowed: {sorted(ALLOWED)} (provider: google)")
if not os.getenv("API_KEY"):
    raise SystemExit("API_KEY is missing. Copy .env.example to .env and add your key.")

client = genai.Client(api_key=os.getenv("API_KEY"))
CACHE_DIR = Path(__file__).resolve().parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)
MIN_GAP = 4.5  # stay under 15 requests per minute
_last_call = 0.0
last_model = None


def parse_json(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in response")
    return json.loads(text[start:end + 1])


def ask_json(prompt, image_path=None):
    """Send a prompt (and optional bill image) to the model and return parsed JSON."""
    global _last_call, last_model
    image_bytes, mime = None, None
    if image_path:
        image_bytes = Path(image_path).read_bytes()
        mime = mimetypes.guess_type(str(image_path))[0] or "image/png"
    last_error = None
    for model in MODELS:
        h = hashlib.sha256(model.encode() + prompt.encode() + (image_bytes or b""))
        cache_file = CACHE_DIR / (h.hexdigest() + ".json")
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))
        for attempt in range(3):
            wait = MIN_GAP - (time.time() - _last_call)
            if wait > 0:
                time.sleep(wait)
            try:
                _last_call = time.time()
                contents = [prompt]
                if image_bytes:
                    contents = [types.Part.from_bytes(data=image_bytes, mime_type=mime), prompt]
                resp = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                data = parse_json(resp.text)
                cache_file.write_text(json.dumps(data), encoding="utf-8")
                last_model = model
                return data
            except Exception as e:
                last_error = e
                msg = str(e)
                print(f"  [{model}] attempt {attempt + 1} failed: {msg[:120]}")
                if "404" in msg:
                    break              # wrong model name: try the fallback model
                time.sleep(20 if "429" in msg else 3 * (attempt + 1))
    raise RuntimeError(f"All models failed: {last_error}")