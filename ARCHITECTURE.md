# Architecture: How Google Gemini Integrates with KisanRakshak

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Browser)                       │
│  HTML/CSS/JavaScript - No Changes                           │
│  - Photo upload form                                        │
│  - Pesticide search                                         │
│  - Spray plan creation                                      │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP Requests
                       ↓
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Backend (app/main.py)                   │
│  Routes:                                                     │
│  - GET  /api/health         (no key needed)                 │
│  - POST /api/analyze        (NEEDS Gemini API)              │
│  - POST /api/check          (no key needed)                 │
│  - POST /api/plan           (no key needed)                 │
│  - GET  /api/samples        (no key needed)                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        ↓                             ↓
   ┌─────────────┐            ┌──────────────┐
   │  Rules      │            │  AI Provider │
   │  Engine     │            │  (llm.py)    │
   │             │            │              │
   │engine.py    │            │- OLD: Claude │
   │             │            │- NEW: Gemini │
   └──────┬──────┘            └──────┬───────┘
          │                          │
          │ Pure Python              │ API Call
          │ (no AI)                  │
          │                          ↓
          │                  ┌────────────────┐
          │                  │Google Gemini   │
          │                  │    API         │
          │                  │                │
          │                  │- Vision model  │
          │                  │- Text model    │
          │                  │                │
          │                  │(Free tier OK)  │
          │                  └────────────────┘
          │
          ↓
   ┌──────────────────┐
   │  Result JSON     │
   │  - Verdict       │
   │  - Waiting days  │
   │  - Alerts        │
   │  - Summary       │
   └────────────────→(sent to frontend)
```

---

## 📊 Data Flow: Photo Analysis

### Request
```
User uploads image
    ↓
Frontend sends to /api/analyze
    ↓
FastAPI receives image
    ├─ Validate: is it an image?
    ├─ Validate: is it under 5MB?
    ├─ Check: rate limit OK?
    └─ Check: daily budget OK?
    ↓
```

### Processing
```
llm.extract_label(image_bytes, mime_type, settings)
    ↓
Creates Google Gemini client with API key
    ↓
Sends to Gemini Vision API:
    - System prompt: "Read pesticide packet"
    - Image: photo bytes + MIME type
    - Max tokens: 1200
    - Temperature: 0 (deterministic)
    ↓
Gemini returns JSON:
    {
      "product_name": "...",
      "ingredients": [...],
      "waiting_period": "...",
      ...
    }
```

### Analysis
```
engine.analyze(label_data, crop)
    ↓
Checks against rules:
    ├─ Is it banned in India?
    ├─ Is it restricted for this crop?
    ├─ What's the waiting period?
    ├─ Is it expired?
    └─ Any duplicate ingredients?
    ↓
Returns verdict:
    - "safe" | "caution" | "danger"
    - With explanations
```

### Summary (Optional)
```
If API key is set:
    llm.explain(facts, language, settings)
    ↓
    Calls Gemini to write farmer-friendly summary
    ↓
    Validates: does summary contain only known numbers?
    ↓
    Returns 3-4 sentences in requested language
```

### Response
```
Return JSON to frontend:
    {
      "verdict": "...",
      "waiting": {...},
      "toxicity": {...},
      "alerts": [...],
      "summary": "...",  // optional, from AI
      "source": "scan"
    }
    ↓
Frontend displays results
```

---

## 🔄 Request Lifecycle (No API Key Needed)

These work WITHOUT Gemini API key:

```
/api/check (manual label entry)
    ↓
engine.analyze() ← Pure Python, no AI
    ↓
Returns verdict immediately
    ↓
Status: 200 OK
```

```
/api/samples (demo packets)
    ↓
samples.build() ← Hardcoded data
    ↓
engine.analyze() ← Pure Python
    ↓
Status: 200 OK
```

```
/api/plan (spray schedule)
    ↓
engine.plan() ← Pure Python logic
    ↓
Returns harvest dates, warnings
    ↓
Status: 200 OK
```

**Bottom line**: Photo upload is the ONLY feature needing API key!

---

## 🔑 API Key Flow

### Local Development
```
1. User creates .env
   GOOGLE_GEMINI_API_KEY=AIza...

2. App loads config
   os.getenv("GOOGLE_GEMINI_API_KEY")

3. Key stored in Settings dataclass
   settings.api_key = "AIza..."

4. When photo uploaded:
   - Check: if not settings.api_key → return 503
   - If key exists → call Gemini API

5. Key never:
   ✅ Printed in logs
   ✅ Stored in database
   ✅ Sent to frontend
   ❌ Committed to Git
```

### Production (Render)
```
1. Deploy to Render
   ├─ render.yaml says: GOOGLE_GEMINI_API_KEY exists
   ├─ But NOT in YAML (sync: false)
   ├─ Must be set in Render dashboard

2. Set in Dashboard
   ├─ Key: GOOGLE_GEMINI_API_KEY
   ├─ Value: AIza... (pasted directly)
   ├─ Render stores encrypted

3. At Runtime
   ├─ Render injects as environment variable
   ├─ App reads from os.getenv()
   ├─ Used for API calls
   ├─ Never stored or logged

4. Key never:
   ✅ In YAML file
   ✅ In logs
   ✅ In database
   ✅ Visible in Git
```

---

## 📁 Module Responsibilities

### `app/config.py`
```
Responsibility: Load config from environment
│
├─ Read: GOOGLE_GEMINI_API_KEY
├─ Read: GOOGLE_GEMINI_MODEL
├─ Read: MAX_LLM_CALLS_PER_DAY
├─ Read: RATE_* (rate limits)
├─ Read: ENABLE_EXPLANATION
│
└─ Return: Settings dataclass
   (immutable config object)
```

### `app/llm.py`
```
Responsibility: AI provider interface
│
├─ extract_label(image, mime_type, settings)
│  └─ Takes: image bytes + settings
│  └─ Returns: JSON schema with packet info
│
├─ explain(facts, language, settings)
│  └─ Takes: analysis results + language
│  └─ Returns: 3-4 sentence summary
│
└─ Exceptions:
   ├─ LLMUnavailable (no key)
   └─ LLMError (API call failed)
```

### `app/engine.py`
```
Responsibility: Rules engine (pure Python)
│
├─ analyze(label, crop)
│  └─ Takes: packet info + crop
│  └─ Returns: verdict + waiting days + alerts
│
├─ plan(spray_history, today)
│  └─ Takes: list of sprays + date
│  └─ Returns: earliest harvest date
│
└─ Checks bans, restrictions, waiting periods
   (NO AI involved, NO API calls)
```

### `app/main.py`
```
Responsibility: HTTP API routes
│
├─ /api/health       ← Check status
├─ /api/analyze      ← Upload photo (calls llm.py)
├─ /api/check        ← Manual entry (calls engine.py)
├─ /api/plan         ← Spray schedule (calls engine.py)
├─ /api/samples      ← Demo packets (calls samples.py)
└─ / (static)        ← Frontend HTML/CSS/JS

All routes call llm.py optionally
llm.py is agnostic to provider
```

---

## 🔀 Provider Switching (Future)

The modular design allows easy provider switching:

### To Switch to Claude (Anthropic)
```python
# In app/llm.py:
def _client(settings: Settings):
    import anthropic
    return anthropic.Anthropic(api_key=settings.api_key)

def extract_label(image, media_type, settings):
    # Use Anthropic API instead
    ...

# In app/config.py:
key = os.getenv("ANTHROPIC_API_KEY")
model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")

# Done! Rest of code unchanged
```

### To Switch to OpenAI (GPT)
```python
# In app/llm.py:
def _client(settings: Settings):
    from openai import OpenAI
    return OpenAI(api_key=settings.api_key)

# Use OpenAI vision API
# Done! Rest of code unchanged
```

**Key insight**: Only `llm.py` changes. Everything else stays the same!

---

## 🏢 Deployment Topology

### Local Development
```
You
  ↓
Windows Terminal
  ↓
.env (contains API key)
  ↓
Python .venv
  ↓
FastAPI/Uvicorn Server (localhost:8000)
  ↓
Browser (http://127.0.0.1:8000)
  ↓
Google Gemini API (real API calls)
```

### Production (Render)
```
Internet
  ↓
Render Free Tier
  ├─ Git auto-deploy from GitHub
  ├─ Python 3.12.7 runtime
  ├─ Environment variables (secure)
  │  └─ GOOGLE_GEMINI_API_KEY
  ├─ FastAPI application
  └─ Static files (frontend)
  ↓
User's Browser
  ├─ http (free tier only)
  └─ HTTPS (paid tier)
  ↓
Google Gemini API (real API calls)
```

---

## 📊 API Request Breakdown

### Request Size
```
Photo Upload:
  ├─ Multipart form data
  ├─ Image: up to 5 MB
  ├─ Metadata: ~100 bytes
  └─ Total: ≤ 5.1 MB
```

### Response Size
```
Analysis Result:
  ├─ JSON object
  ├─ Label data: ~2 KB
  ├─ Analysis: ~1 KB
  ├─ Summary (optional): ~500 bytes
  └─ Total: ≤ 5 KB
```

### API Call (to Gemini)
```
Request:
  ├─ Image: ~5 MB (compressed by SDK)
  ├─ Prompt: ~200 bytes
  └─ Total: ~5 MB

Response:
  ├─ JSON: ~2 KB
  └─ Tokens used: ~100-200
```

---

## ⚡ Performance Characteristics

### Latency
```
Photo Upload Flow:
  ├─ Upload: ~1-2 seconds
  ├─ Gemini API call: ~5-10 seconds
  ├─ Rules analysis: <100ms
  ├─ AI summary: ~2-3 seconds
  └─ Total: ~10-15 seconds
```

### Throughput (Free Tier)
```
Rate Limits:
  ├─ Photo analysis: 6 per minute
  ├─ Other endpoints: 40 per minute
  ├─ Daily budget: 1500 total
  └─ Enough for: ~12 hours of demo usage
```

### Costs (Free Tier)
```
Google Gemini Free:
  ├─ Photos/day: 1500 max
  ├─ Cost: $0
  ├─ Upgrade price: $0.075 per 1M tokens
  └─ Example: 1000 photos = ~$0.15
```

---

## 🔒 Security Architecture

### Authentication
```
No user login needed
  ↓
API key stored securely:
  ├─ Local: .env (not committed)
  ├─ Production: Render environment (encrypted)
  └─ Never in logs or frontend
```

### Authorization
```
Per-IP rate limiting:
  ├─ Prevent abuse
  ├─ Track by client IP
  └─ Limits: 6/min analyze, 40/min others

Daily budget:
  ├─ Hard cap on API calls
  ├─ Prevents bill shock
  └─ Set to 300 calls/day
```

### Input Validation
```
Images:
  ├─ Must be JPEG/PNG/WebP
  ├─ Must be < 5 MB
  └─ Checked before API call

JSON:
  ├─ Schema validation via Pydantic
  ├─ Size limits enforced
  └─ Invalid data rejected early
```

### Response Safety
```
Photo results:
  ├─ API key never in response
  ├─ No internal paths exposed
  ├─ Errors don't leak details
  └─ Summary validated for facts only
```

---

## 📈 Scaling Notes

### For Hackathon
- ✅ Free tier (1500/day) enough
- ✅ ~20 people × 3 demos = 60 photos
- ✅ Easy within quota

### For Production (If Submitted)
- 📈 Scale to 100+ users/day
- 💳 Upgrade to paid API
- 🚀 Increase rate limits
- 📊 Monitor usage dashboard
- 🔄 Set up auto-scaling

---

## 🎯 Key Design Decisions

### Decision 1: Why google-genai (not google-generativeai)?
- ✅ Newer, actively maintained
- ✅ No deprecation warnings
- ✅ Better performance
- ❌ Old version shows FutureWarning

### Decision 2: Why Free Tier?
- ✅ No credit card needed
- ✅ Sufficient for hackathon
- ✅ Easy to upgrade if needed
- ✅ Perfect for demos

### Decision 3: Why Temperature=0?
- ✅ Deterministic output (same input = same output)
- ✅ Better for JSON extraction
- ✅ Farmer needs consistent results

### Decision 4: Why Modular Design?
- ✅ Easy to switch providers
- ✅ Easy to add new features
- ✅ Easy to test independently
- ✅ Follows clean code principles

---

**Architecture Summary**: Modular, maintainable, provider-agnostic, and ready for production!
