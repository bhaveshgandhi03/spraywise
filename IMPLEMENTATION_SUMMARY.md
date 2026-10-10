# Google Gemini API Integration - Complete Implementation Summary

## 📊 Project Overview

**KisanRakshak** - An AI pesticide packet reader for Indian farmers with safety checks and spray planning.

### Original Architecture
- **Provider**: Anthropic Claude (paid API)
- **Functions**: Photo reading + AI explanations (optional)
- **Status**: Works without API key for rules/search/plans

### New Architecture  
- **Provider**: Google Gemini (FREE tier)
- **Functions**: Photo reading + AI explanations (optional)
- **Status**: Photo scanning now requires user confirmation; the legacy `/api/analyze` route returns 409.

---

## 🎯 Files Modified (5 Core Changes)

### 1. **[app/config.py](/app/config.py)** - Configuration
**Change**: Environment variable names
```python
# OLD
ANTHROPIC_API_KEY -> GOOGLE_GEMINI_API_KEY
ANTHROPIC_MODEL -> GOOGLE_GEMINI_MODEL
model="claude-sonnet-5-5" -> model="gemini-2.0-flash"

# NEW (line 30-31)
key = os.getenv("GOOGLE_GEMINI_API_KEY", "").strip() or None
model=os.getenv("GOOGLE_GEMINI_MODEL", "gemini-2.0-flash")
```

### 2. **[app/llm.py](/app/llm.py)** - AI Provider Implementation
**Major changes**:
- Import: `anthropic` → `google.genai`
- Client: `anthropic.Anthropic()` → `google.genai.client.Client(ApiKeyCredential)`
- Image handling: base64 encoding → raw bytes with mime type
- Response: `.content[0].text` → `.text`

**Key functions updated**:
- `_client()` - Creates Google Genai client instead of Anthropic
- `extract_label()` - Calls `models.generate_content()` with vision API
- `explain()` - Generates farmer-friendly summaries using Gemini

### 3. **[requirements.txt](/requirements.txt)** - Dependencies
```diff
- anthropic>=0.40
+ google-genai>=0.1.0
```

### 4. **[.env.example](/env.example)** - Environment Template
```diff
- ANTHROPIC_API_KEY=your_key_here
- ANTHROPIC_MODEL=claude-sonnet-5-5
+ GOOGLE_GEMINI_API_KEY=your_key_here
+ GOOGLE_GEMINI_MODEL=gemini-2.0-flash
```

### 5. **[render.yaml](/render.yaml)** - Deployment Config
```yaml
# OLD
ANTHROPIC_API_KEY: { sync: false }
ANTHROPIC_MODEL: claude-sonnet-5-5

# NEW
GOOGLE_GEMINI_API_KEY: { sync: false }
GOOGLE_GEMINI_MODEL: gemini-2.0-flash
```

---

## ✨ Safety and coverage safeguards
- `app/main.py` - Reads images separately; runs checks after fields are confirmed.
- `app/engine.py` - Returns explicit product/crop reference coverage status.
- Frontend - Lets users review and correct extracted safety-critical label fields.
- Tests - Cover confirmation flow and unknown product/crop results.
- Dataset - Not expanded with unverified product claims; the About view exposes sources and known gaps.

---

## 🚀 Quick Setup (Choose One Path)

### Path A: Automated (Windows)
```powershell
cd C:\Users\bhave\OneDrive\Desktop\hackathon\spraywise
.\setup_gemini.bat  # Installs venv + dependencies
```

### Path B: Manual
```powershell
cd C:\Users\bhave\OneDrive\Desktop\hackathon\spraywise

# Activate venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Or just Gemini SDK:
pip install google-genai>=0.1.0
```

---

## 🔑 Get Free API Key (2 minutes)

1. Visit: **https://ai.google.dev/**
2. Click **"Get API Key"** button
3. Sign in with Google account
4. Click **"Create API Key"** → **"Create API Key in new project"**
5. Copy the generated key
6. **Free tier**: 60 req/min, 1500 req/day

---

## 💻 Local Development Setup

### Step 1: Create .env
```bash
cd C:\Users\bhave\OneDrive\Desktop\hackathon\spraywise
Copy-Item .env.example .env
```

Edit `.env`:
```env
GOOGLE_GEMINI_API_KEY=paste_your_actual_key_here
GOOGLE_GEMINI_MODEL=gemini-2.0-flash
MAX_LLM_CALLS_PER_DAY=300
RATE_ANALYZE_PER_MIN=6
RATE_OTHER_PER_MIN=40
MAX_IMAGE_MB=5
LLM_TIMEOUT_S=40
ENABLE_EXPLANATION=true
```

### Step 2: Run Server
```powershell
# Activate environment (if needed)
.venv\Scripts\activate

# Set API key
$env:GOOGLE_GEMINI_API_KEY = "your_key_here"

# Start development server
uvicorn app.main:app --reload

# Open browser
# http://127.0.0.1:8000
```

### Step 3: Test Endpoints
```bash
# Health check (no key needed)
curl http://localhost:8000/api/health
# Returns: {"status":"ok","photo_reading":true,...}

# List samples
curl http://localhost:8000/api/samples

# Test photo upload
# POST image to http://localhost:8000/api/read-label, confirm the fields,
# then POST the confirmed label to http://localhost:8000/api/check
```

---

## 🌐 Deploy to Render (Live URL)

### Step 1: Push Code
```bash
cd C:\Users\bhave\OneDrive\Desktop\hackathon\spraywise
git add -A
git commit -m "Integrate Google Gemini API for photo reading"
git push origin main
```

### Step 2: Create Render Service
1. Visit: **https://render.com**
2. Sign in / Create account
3. Click **"New +"** → **"Blueprint"**
4. Select your GitHub repository
5. Click **"Create Blueprint"**
6. Wait for deployment (2-3 minutes)

### Step 3: Set API Key in Render
1. Go to Render dashboard
2. Click on your service
3. Click **"Settings"** → **"Environment"**
4. Add variable:
   - Key: `GOOGLE_GEMINI_API_KEY`
   - Value: `paste_your_key_here`
5. Click **"Save"** / **"Redeploy"**

### Step 4: Verify Live
```bash
# Replace YOUR-SERVICE with actual name from Render
curl https://YOUR-SERVICE.onrender.com/api/health
# Should show: "photo_reading": true
```

---

## 📋 Deployment Checklist

### Before Going Live
- [ ] All code committed and pushed
- [ ] Local server works: `http://127.0.0.1:8000`
- [ ] Can upload test image locally
- [ ] Tests pass: `pytest tests/`
- [ ] No API key in `.env` (it's in `.gitignore`)
- [ ] Render service created and running
- [ ] API key set in Render environment (not in YAML)

### After Deployment
- [ ] Service URL responds (https://YOUR-SERVICE.onrender.com)
- [ ] `/api/health` shows `"photo_reading": true`
- [ ] Photo upload works via web UI
- [ ] Mobile browser access works
- [ ] Different browser access works

---

## 🔧 Configuration Reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `GOOGLE_GEMINI_API_KEY` | none | Enables photo reading (no default) |
| `GOOGLE_GEMINI_MODEL` | `gemini-2.0-flash` | Vision model to use |
| `MAX_LLM_CALLS_PER_DAY` | 300 | Daily budget cap |
| `RATE_ANALYZE_PER_MIN` | 6 | Photo analysis rate limit |
| `RATE_OTHER_PER_MIN` | 40 | Other endpoint rate limit |
| `MAX_IMAGE_MB` | 5 | Upload size limit |
| `LLM_TIMEOUT_S` | 40 | API request timeout |
| `ENABLE_EXPLANATION` | true | Turn summaries on/off |

---

## 📊 Model Comparison

### Why gemini-2.0-flash?
| Feature | gemini-2.0-flash | claude-sonnet-5-5 |
|---------|------------------|-------------------|
| **Vision** | ✅ | ✅ |
| **Speed** | ⚡ Faster | ⚡⚡ |
| **Cost** | 💰 $0.075/1M | 💰💰 $3/1M |
| **Free Tier** | ✅ 1500/day | ❌ No free tier |
| **JSON Output** | ✅ Good | ✅✅ Better |

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| "GOOGLE_GEMINI_API_KEY not set" | Set env var: `$env:GOOGLE_GEMINI_API_KEY = "key"` |
| "ModuleNotFoundError: google.genai" | Install: `pip install google-genai` |
| "429 Quota exceeded" | Hit free tier limit (1500/day). Wait or upgrade. |
| "Invalid JSON in reply" | Gemini sometimes wraps JSON in markdown. Already handled. |
| "Photo not recognized" | Ensure image is JPEG/PNG/WebP and under 5MB |
| App works but photo returns 503 | Check Render logs, verify API key is set |

---

## 🔐 Security Checklist

✅ **What We Did Right**:
- API key never in code (environment variables only)
- `.env` in `.gitignore` (never committed)
- Render's `sync: false` prevents key leakage
- Images held in memory only (never written to disk)
- No API key in logs
- No API key in error messages
- Per-IP rate limiting
- Daily budget cap

✅ **Best Practices**:
- Rotate API key if ever exposed
- Monitor daily usage (stay under 1500/day)
- Use environment-specific keys for prod/dev
- Enable Render's activity logs

---

## 📚 New Documentation Files

| File | Purpose |
|------|---------|
| `GEMINI_INTEGRATION_GUIDE.md` | Detailed technical guide |
| `QUICK_START.md` | Quick reference for setup |
| `setup_gemini.bat` | Windows automated setup |

---

## 🧪 Testing

### Run All Tests
```bash
.venv\Scripts\python.exe -m pytest tests/ -v
```

### Run Specific Test
```bash
.venv\Scripts\python.exe -m pytest tests/test_api.py::test_health_and_static_site -v
```

### Mock vs Real Tests
- **Mocked** (tests/*): LLM calls are mocked → don't need API key
- **Real** (scripts/try_photo.py): Actually calls API → needs real key

---

## 💡 Development Tips

### Enable Debug Logging
```python
# In app/main.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Disable AI Summaries (for testing)
```env
ENABLE_EXPLANATION=false
```

### Increase Rate Limits (local only)
```env
RATE_ANALYZE_PER_MIN=100
RATE_OTHER_PER_MIN=1000
```

### Use Different Model
```env
GOOGLE_GEMINI_MODEL=gemini-1.5-pro
```

---

## 📖 API Endpoints

| Endpoint | Purpose | Needs Key |
|----------|---------|-----------|
| `GET /api/health` | Status check | ❌ |
| `POST /api/read-label` | Read photo for confirmation | ✅ |
| `POST /api/check` | Analyze confirmed scanned or manual fields | ❌ |
| `POST /api/analyze` | Legacy route; returns 409 because confirmation is required | ❌ |
| `POST /api/plan` | Spray schedule | ❌ |
| `GET /api/samples` | Sample packets | ❌ |
| `GET /api/meta` | Metadata, sources, and coverage gaps | ❌ |

**Note**: Most endpoints work without API key! Only photo upload needs it.

---

## 🎯 Next Steps

### Immediate
1. ✅ Copy `.env.example` to `.env`
2. ✅ Paste API key in `.env`
3. ✅ Run locally: `uvicorn app.main:app --reload`
4. ✅ Test in browser: http://127.0.0.1:8000

### This Week
1. ✅ Deploy to Render
2. ✅ Set API key in Render dashboard
3. ✅ Test live URL
4. ✅ Get user feedback

### Before Submission
1. ✅ Test on mobile device
2. ✅ Test in different browser
3. ✅ Run full test suite
4. ✅ Check security headers
5. ✅ Verify no API key in logs

---

## 📞 Support

- **Google AI Docs**: https://ai.google.dev/tutorials
- **Gemini API Ref**: https://ai.google.dev/api/python/google/genai
- **Render Docs**: https://render.com/docs
- **Project README**: See `README.md`

---

## 🎉 You're Ready!

The project is configured for Google Gemini API. Rules, search, and planning work without an API key. Photo scans require confirmation before checks; old clients should use `/api/read-label` followed by `/api/check`.

**Next action**: Create `.env` and run locally! 🚀
