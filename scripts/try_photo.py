"""Live check with your own API key and a real packet photo.

    ANTHROPIC_API_KEY=... python scripts/try_photo.py photo.jpg paddy

Prints what the model read from the packet and the full rules-engine analysis.
Run this once before the demo: it is the only path the automated tests cannot cover (a real API call).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import engine, llm  # noqa: E402
from app.config import load_settings  # noqa: E402
from app.security import sniff_image  # noqa: E402

if len(sys.argv) < 2:
    sys.exit("usage: python scripts/try_photo.py <photo> [tomato|groundnut|paddy|other]")
data = Path(sys.argv[1]).read_bytes()
crop = sys.argv[2] if len(sys.argv) > 2 else "other"
media = sniff_image(data)
if not media:
    sys.exit("not a JPEG, PNG or WebP image")
settings = load_settings()
label = llm.extract_label(data, media, settings)
print("--- read from packet ---")
print(json.dumps(label, indent=2, ensure_ascii=False))
print("--- analysis ---")
res = engine.analyze({**label, "source": "scan"}, crop)
print(json.dumps({k: res[k] for k in ("verdict", "waiting", "expiry", "toxicity", "alerts")}, indent=2, ensure_ascii=False))
