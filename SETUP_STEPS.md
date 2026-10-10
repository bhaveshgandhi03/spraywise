# Step-by-Step: Google Gemini Integration for KisanRakshak

## 📋 Overview

This guide walks you through integrating Google Gemini API (FREE tier) with the KisanRakshak pesticide packet reader app.

**Why Google Gemini?**
- ✅ FREE: 60 req/min, 1500/day (enough for demos)
- ✅ Vision-capable: Reads images like Anthropic
- ✅ Cheap: ~$0.075/1M tokens vs $3/1M for Anthropic
- ✅ No credit card needed for free tier

---

## 🎯 PART 1: Get API Key (5 mins)

### Option A: Web Browser
1. Open: https://ai.google.dev/
2. Click big blue **"Get API Key"** button
3. Sign in with Google (or create account)
4. Click **"Create API Key"** → **"Create API Key in new project"**
5. **COPY** the key that appears
6. Keep it safe! Never share or commit to Git

### Option B: Direct Link
1. Go directly to: https://aistudio.google.com/apikey
2. Sign in if needed
3. Click **"Create API Key"** → **"Create API Key in new project"**
4. Copy the generated key

**✅ You now have a FREE API key!**

---

## 💻 PART 2: Setup Locally (Windows) - 5 minutes

### Quick Method (Automated)
```powershell
# Navigate to project
cd C:\Users\bhave\OneDrive\Desktop\hackathon\spraywise

# Run setup script
.\setup_gemini.bat

# That's it! Follow prompts
```

### Manual Method (Step-by-Step)

**Step 1: Create .env File**
```powershell
cd C:\Users\bhave\OneDrive\Desktop\hackathon\spraywise

# Copy template
Copy-Item .env.example .env

# Now open .env in any text editor and paste your API key
# Replace: GOOGLE_GEMINI_API_KEY=your_key_here
# With:    GOOGLE_GEMINI_API_KEY=abc123xyz789...
```

**Step 2: Activate Virtual Environment**
```powershell
.venv\Scripts\activate
```
You should see `(.venv)` in your terminal.

**Step 3: Install Dependencies**
```powershell
pip install -r requirements-dev.txt

# Or just the Gemini SDK:
pip install google-genai>=0.1.0
```

**Step 4: Verify Installation**
```powershell
python -c "from google.genai import client; print('Success!')"
# Should print: Success!
```

---

## 🚀 PART 3: Run Locally (5 minutes)

### Start the Server
```powershell
# Make sure you're in project directory
cd C:\Users\bhave\OneDrive\Desktop\hackathon\spraywise

# Make sure venv is activated
.venv\Scripts\activate

# Set API key (Windows PowerShell)
$env:GOOGLE_GEMINI_API_KEY = "your_actual_key_here"

# Start development server
uvicorn app.main:app --reload
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### Test in Browser
1. Open: http://127.0.0.1:8000
2. You should see KisanRakshak home page
3. Try uploading a pesticide packet photo
4. Or click "View Samples" to try demo packets

### Test API (Terminal)
```powershell
# Health check (no API key needed)
curl http://localhost:8000/api/health

# Should return:
# {"status":"ok","photo_reading":true,"products":30,"banned_entries":95,"llm_calls_today":0}
```

---

## 🌐 PART 4: Deploy to Render (10 minutes)

### Step 1: Commit Changes
```powershell
cd C:\Users\bhave\OneDrive\Desktop\hackathon\spraywise

git add -A
git commit -m "Integrate Google Gemini API for pesticide packet reading"
git push origin main
```

### Step 2: Create Render Service
1. Go to: https://render.com
2. Sign in (or create free account)
3. Click **"New +"** button (top right)
4. Select **"Blueprint"**
5. Select your GitHub repository
6. Click **"Create Blueprint"**
7. Wait 2-3 minutes for deployment...

### Step 3: Set API Key in Render Dashboard
1. Wait for deployment to complete
2. Go to your Render dashboard
3. Click on your service (kisanrakshak)
4. Click **"Settings"** in left menu
5. Look for **"Environment"** section
6. Click **"Add Environment Variable"**
7. Enter:
   - **Key**: `GOOGLE_GEMINI_API_KEY`
   - **Value**: `your_actual_api_key_here`
8. Click **"Save"**
9. Service will auto-redeploy (2-3 minutes)

### Step 4: Test Live URL
```powershell
# Replace YOUR-SERVICE with your actual service name from Render
# (It will be like: kisanrakshak-abc12.onrender.com)

curl https://YOUR-SERVICE.onrender.com/api/health

# Should return: {"status":"ok","photo_reading":true,...}

# Then open in browser:
# https://YOUR-SERVICE.onrender.com
```

---

## ✅ Verification Checklist

### Local Setup
- [ ] .env file created with API key
- [ ] `pip install google-genai` succeeded
- [ ] `uvicorn app.main:app --reload` starts without errors
- [ ] http://127.0.0.1:8000 loads in browser
- [ ] Can upload image (tries to analyze)
- [ ] Can view sample packets
- [ ] Can search by pesticide name
- [ ] Can create spray plans
- [ ] Health endpoint shows: `"photo_reading": true`

### Render Deployment
- [ ] GitHub repository has latest code
- [ ] Render service created successfully
- [ ] Deployment completed (green checkmark)
- [ ] API key set in Render environment
- [ ] https://YOUR-SERVICE.onrender.com loads
- [ ] Photo upload works on live site
- [ ] Health endpoint returns: `"photo_reading": true`
- [ ] Mobile device can access
- [ ] Works in different browser

---

## 🔍 How to Find Your Service Name

Once deployed on Render, find your service URL:

1. Go to https://render.com
2. Log in
3. Click on your service in the dashboard
4. Top of page shows: `Your Service URL`
5. Will look like: `https://kisanrakshak-abc12.onrender.com`

---

## 🐛 Troubleshooting

### Problem: "GOOGLE_GEMINI_API_KEY not set"
**Solution:**
```powershell
# Check if environment variable is set
$env:GOOGLE_GEMINI_API_KEY

# If empty, set it
$env:GOOGLE_GEMINI_API_KEY = "your_key_here"

# Verify
$env:GOOGLE_GEMINI_API_KEY  # Should print your key
```

### Problem: "ModuleNotFoundError: No module named 'google'"
**Solution:**
```powershell
pip install google-genai>=0.1.0
```

### Problem: "429 Quota exceeded"
You've hit the free tier limit (1500 requests/day or 60/min).
- **Solution 1**: Wait until tomorrow (quota resets at midnight UTC)
- **Solution 2**: Upgrade to paid plan
- **Prevention**: Keep `MAX_LLM_CALLS_PER_DAY=300` in config

### Problem: "Photo returns 503 error" (on Render)
**Solution:**
1. Check Render logs for error messages
2. Verify API key is in Render environment (not in YAML)
3. Restart the service: Click **"Restart"** button

### Problem: "Connection timeout"
**Solution:**
- Free Render tier goes to sleep after 15 minutes inactivity
- Just visit the URL again (takes ~30 seconds to wake up)

---

## 📝 What Changed?

### Before (Anthropic)
- Environment: `ANTHROPIC_API_KEY=...`
- Model: `ANTHROPIC_MODEL=claude-sonnet-5-5`
- SDK: `anthropic>=0.40`

### After (Google Gemini)
- Environment: `GOOGLE_GEMINI_API_KEY=...`
- Model: `GOOGLE_GEMINI_MODEL=gemini-2.0-flash`
- SDK: `google-genai>=0.1.0`

### Files Changed
- `app/config.py` - Variable names
- `app/llm.py` - Provider implementation
- `requirements.txt` - Dependencies
- `.env.example` - Template
- `render.yaml` - Deployment config

### Files NOT Changed
- `app/main.py` - API endpoints unchanged
- `app/engine.py` - Rules engine unchanged
- Frontend (static/) - Unchanged
- Database schema - Unchanged
- Tests - Unchanged

**Result: Drop-in replacement!**

---

## 💡 Pro Tips

### Tip 1: Keep API Key Secret
```bash
# ✅ DO: Set via environment
$env:GOOGLE_GEMINI_API_KEY = "key"

# ❌ DON'T: Put in code
# ❌ DON'T: Commit .env to Git
# ❌ DON'T: Share in messages
```

### Tip 2: Monitor Usage
Check `/api/health` endpoint to see:
- `"photo_reading": true` (API key is set)
- `"llm_calls_today": 0` (tracks daily usage)

### Tip 3: Test Without Key First
All these work WITHOUT API key:
- Search by pesticide name
- View sample packets
- Create spray plans
- Check waiting periods
- Only photo upload needs key

### Tip 4: Use Smaller Images
- Max 5MB per image
- JPEG/PNG/WebP only
- Smaller = faster response
- Reduces API token usage

---

## 🚀 Quick Command Reference

### Local Development
```bash
# Navigate to project
cd C:\Users\bhave\OneDrive\Desktop\hackathon\spraywise

# Activate environment
.venv\Scripts\activate

# Set API key (Windows)
$env:GOOGLE_GEMINI_API_KEY = "your_key"

# Start server
uvicorn app.main:app --reload

# Run tests
pytest tests/ -v

# Deactivate venv
deactivate
```

### Deployment
```bash
# Commit changes
git add -A
git commit -m "Integrate Gemini API"
git push origin main

# Render auto-deploys
# Then set API key in Render dashboard
```

---

## 📞 Getting Help

| Problem | Resource |
|---------|----------|
| Google Gemini API docs | https://ai.google.dev/api/python/google/genai |
| Render deployment | https://render.com/docs |
| Python FastAPI | https://fastapi.tiangolo.com/ |
| Project README | See `README.md` in project root |

---

## 🎉 Success!

Once you've completed all steps:

1. ✅ Local development working
2. ✅ Live URL on Render
3. ✅ Can upload pesticide photos
4. ✅ AI reads packets and provides guidance
5. ✅ Free tier supports demos

You're ready to demonstrate to judges!

---

## 📋 Pre-Demo Checklist

Before showing to judges:

- [ ] Take a real photo of pesticide packet
- [ ] Test upload on local version
- [ ] Test upload on live Render URL
- [ ] Test on mobile device
- [ ] Show /api/health endpoint
- [ ] Explain how safety checks work
- [ ] Show spray plan creation
- [ ] Test in 4 languages
- [ ] Demonstrate offline mode (PWA)

---

## Next Action

**👉 CREATE .env FILE AND RUN LOCALLY!**

```powershell
cd C:\Users\bhave\OneDrive\Desktop\hackathon\spraywise
Copy-Item .env.example .env
# Edit .env and add your API key
$env:GOOGLE_GEMINI_API_KEY = "paste_key_here"
uvicorn app.main:app --reload
```

Then open: **http://127.0.0.1:8000**

**You've got this!** 🚀
