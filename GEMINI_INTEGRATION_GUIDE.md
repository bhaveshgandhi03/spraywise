# Google Gemini API Integration Guide for KisanRakshak

## Project Analysis

### Current Architecture
The KisanRakshak project uses Anthropic's Claude API for two optional AI tasks:
1. **Photo Reading**: Extract structured data from pesticide packet images
2. **AI Summaries**: Generate plain-language explanations of safety checks

The app works fine WITHOUT an API key - all safety rules and checks function perfectly.

### Key Files Modified
1. `app/llm.py` - AI provider implementation
2. `app/config.py` - Configuration management
3. `requirements.txt` - Dependencies
4. `.env.example` - Environment template
5. `render.yaml` - Deployment configuration
6. `tests/test_api.py` - Unit tests

---

## Step 1: Get Google Gemini API Key (FREE)

### Obtain Free API Key
1. Visit https://ai.google.dev/
2. Click **"Get API Key"** or go to https://aistudio.google.com/apikey
3. Sign in with your Google account (create one if needed)
4. Click **"Create API Key"** → **"Create API Key in new project"**
5. Copy the generated API key
6. ✅ **Free tier**: 60 requests/minute, 1500 requests/day (sufficient for testing)

### Keep Your Key Safe
- ❌ Never commit `.env` to Git
- ✅ Use environment variables only
- ✅ Add to `.gitignore` (already done)

---

## Step 2: Local Setup

### 2.1 Update Environment File
```bash
cd C:\Users\bhave\OneDrive\Desktop\hackathon\spraywise
cp .env.example .env
```

Edit `.env`:
```
GOOGLE_GEMINI_API_KEY=paste_your_api_key_here
GOOGLE_GEMINI_MODEL=gemini-2.0-flash
MAX_LLM_CALLS_PER_DAY=300
RATE_ANALYZE_PER_MIN=6
RATE_OTHER_PER_MIN=40
MAX_IMAGE_MB=5
LLM_TIMEOUT_S=40
ENABLE_EXPLANATION=true
```

### 2.2 Install Dependencies
```bash
# Activate venv (if not already active)
.venv\Scripts\activate

# Install new dependency
pip install google-generativeai>=0.6.0

# Install all requirements
pip install -r requirements-dev.txt
```

### 2.3 Run Locally
```bash
# Load environment variables
$env:GOOGLE_GEMINI_API_KEY = "your_key_here"
$env:GOOGLE_GEMINI_MODEL = "gemini-2.0-flash"

# Start server
uvicorn app.main:app --reload

# Test in browser
# http://127.0.0.1:8000
```

### 2.4 Test the API
```bash
# Health check (works without API key)
curl http://localhost:8000/api/health

# Upload a pesticide packet photo
# POST to http://localhost:8000/api/analyze with image file

# Or test without photo using samples
curl http://localhost:8000/api/samples
```

---

## Step 3: Deploy to Render

### 3.1 Push to GitHub
```bash
git add -A
git commit -m "Integrate Google Gemini API"
git push origin main
```

### 3.2 Connect Render
1. Visit https://render.com
2. Sign in or create account
3. Click **"New +"** → **"Blueprint"**
4. Select your GitHub repository
5. Render auto-reads `render.yaml`
6. Click **"Create Blueprint"**

### 3.3 Set Environment Variables
1. In Render dashboard, go to your service
2. Click **Settings** → **Environment** (or **Environment Variables**)
3. Add:
   ```
   GOOGLE_GEMINI_API_KEY = your_api_key_here
   GOOGLE_GEMINI_MODEL = gemini-2.0-flash
   ```
4. Save/Redeploy

### 3.4 Test Live
```bash
curl https://your-service-name.onrender.com/api/health
# Should show: "photo_reading": true
```

---

## Step 4: Files Changed

### Summary of Changes
| File | Changes |
|------|---------|
| `app/llm.py` | Replace Anthropic client with Google Generative AI client; update API calls |
| `app/config.py` | Replace `ANTHROPIC_API_KEY` with `GOOGLE_GEMINI_API_KEY` |
| `requirements.txt` | Add `google-generativeai>=0.6.0`; remove `anthropic>=0.40` |
| `.env.example` | Update variable names to use `GOOGLE_GEMINI_*` |
| `render.yaml` | Update environment variable names |

### No Changes Needed
- `app/main.py` - Calls abstract `llm` module, agnostic to provider
- `app/engine.py` - Pure rules, no AI involvement
- `app/security.py` - No provider dependency
- `tests/test_api.py` - Uses mocked `llm` functions
- Frontend code - No changes required

---

## API Changes Breakdown

### Old (Anthropic)
```python
client = anthropic.Anthropic(api_key=key, timeout=timeout_s, max_retries=1)
resp = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=1200,
    system=system_prompt,
    messages=[...]
)
text = resp.content[0].text
```

### New (Google Gemini)
```python
import google.generativeai as genai
genai.configure(api_key=key)
model = genai.GenerativeModel('gemini-2.0-flash')
resp = model.generate_content(
    contents=[content_parts],
    generation_config=genai.types.GenerationConfig(
        max_output_tokens=1200,
        temperature=0
    )
)
text = resp.text
```

### Key Differences
1. **Image Encoding**: Both accept base64 images, but different schemas
2. **JSON Extraction**: Same prompt strategy works
3. **Error Handling**: Different exception types
4. **Response Format**: `.text` instead of `.content[0].text`

---

## Troubleshooting

### Issue: "GOOGLE_GEMINI_API_KEY is not set"
**Solution**: 
```bash
$env:GOOGLE_GEMINI_API_KEY = "your_key"
# Or add to .env and source it
```

### Issue: "Error 429: Quota exceeded"
**Solution**: You've hit the free tier limit (1500/day or 60/min). Wait for reset or upgrade.

### Issue: "Image format not supported"
**Solution**: Ensure image is JPEG, PNG, or WebP. Gemini doesn't support all formats.

### Issue: "Invalid JSON in reply"
**Solution**: Add retry logic or adjust the prompt. Gemini sometimes returns markdown-wrapped JSON.

---

## Model Choices

### Recommended for Production
- **`gemini-2.0-flash`** (Default) - Fast, cheaper, vision-capable
- Vision API: ✅ Can read images
- Cost: ~$0.075/1M input tokens (very cheap)

### Alternative Options
- `gemini-1.5-pro` - More accurate but slower
- `gemini-1.5-flash` - Older version of flash

### Why NOT `gemini-pro` (text-only)
- Cannot process images → photo reading won't work
- Use vision-capable models only

---

## Free Tier Limits

| Metric | Limit | Resets |
|--------|-------|--------|
| Requests/min | 60 | Every minute |
| Requests/day | 1500 | Midnight UTC |
| Max batch size | 10 MB | Per request |

For hackathons, this is sufficient. Use `MAX_LLM_CALLS_PER_DAY=300` in config to stay safe.

---

## Testing Checklist

### Local Testing
- [ ] Health check returns `"photo_reading": true`
- [ ] Can upload and analyze pesticide packet photo
- [ ] Can search by pesticide name
- [ ] Can view sample packets
- [ ] Can create spray plans
- [ ] Explanations generate in 4 languages

### Render Deployment
- [ ] Service deploys without errors
- [ ] `/api/health` endpoint returns `"photo_reading": true`
- [ ] Photo upload works (test with small image first)
- [ ] No API key in logs or database
- [ ] Works on mobile device and different browser

---

## Security Best Practices

1. ✅ API key in environment variables only (not code)
2. ✅ `.env` in `.gitignore` (already done)
3. ✅ Never print API key in logs
4. ✅ Use Render's environment variables (not in YAML)
5. ✅ Set `sync: false` in `render.yaml` for secrets
6. ✅ Rotate key if ever leaked

---

## Quick Reference Commands

### Local Development
```bash
# Activate venv
.venv\Scripts\activate

# Set API key (Windows PowerShell)
$env:GOOGLE_GEMINI_API_KEY = "your_key"
$env:GOOGLE_GEMINI_MODEL = "gemini-2.0-flash"

# Run server
uvicorn app.main:app --reload

# Run tests
pytest tests/

# View logs
Get-Content logs/app.log -Tail 50
```

### Deployment
```bash
git add -A
git commit -m "Add Gemini API integration"
git push origin main
# Render auto-redeploys

# Check live
curl https://your-service.onrender.com/api/health
```

---

## Next Steps

1. ✅ Get API key from ai.google.dev
2. ✅ Create `.env` with credentials
3. ✅ Update `requirements.txt`
4. ✅ Modify `app/llm.py` and `app/config.py`
5. ✅ Test locally with photo upload
6. ✅ Push to GitHub
7. ✅ Deploy via Render
8. ✅ Set environment variables in Render dashboard
9. ✅ Test live URL from another device

---

## Support Resources

- Google AI Docs: https://ai.google.dev/tutorials
- Gemini API Reference: https://ai.google.dev/api/python/google/generativeai
- Render Docs: https://render.com/docs
- Project README: See `README.md`
