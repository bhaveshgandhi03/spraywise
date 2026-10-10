# Quick Setup Guide - Google Gemini API for KisanRakshak

## 🚀 Quick Start (5 minutes)

### Step 1: Get Free Google Gemini API Key
1. Go to https://ai.google.dev/
2. Click **"Get API Key"** button
3. Sign in with Google account (or create one)
4. Click **"Create API Key"** → **"Create API Key in new project"**
5. Copy the generated key to clipboard
6. ✅ **FREE**: 60 requests/min, 1500/day

### Step 2: Setup Locally

#### Option A: Automatic Setup (Windows)
```powershell
cd C:\Users\bhave\OneDrive\Desktop\hackathon\spraywise
.\setup_gemini.bat
```

#### Option B: Manual Setup
```powershell
# Navigate to project
cd C:\Users\bhave\OneDrive\Desktop\hackathon\spraywise

# Activate virtual environment (if needed)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Or just the new dependency
pip install google-generativeai>=0.6.0
```

### Step 3: Create .env File
```powershell
# Copy template
Copy-Item .env.example .env

# Edit .env and replace:
# GOOGLE_GEMINI_API_KEY=paste_your_key_here
# (Or use any text editor to open .env)
```

### Step 4: Run Locally
```powershell
# Set environment variables
$env:GOOGLE_GEMINI_API_KEY = "your_api_key_here"
$env:GOOGLE_GEMINI_MODEL = "gemini-2.0-flash"

# Start the server
uvicorn app.main:app --reload

# Open in browser
# http://127.0.0.1:8000
```

### Step 5: Test
```powershell
# Health check
curl http://localhost:8000/api/health

# Should return:
# {"status":"ok","photo_reading":true,...}
```

---

## 🌐 Deploy to Render

### Step 1: Commit Changes
```bash
git add -A
git commit -m "Integrate Google Gemini API for photo reading"
git push origin main
```

### Step 2: Deploy
1. Go to https://render.com
2. Sign in (create account if needed)
3. Click **"New +"** → **"Blueprint"**
4. Select your GitHub repository
5. Click **"Create Blueprint"**
6. Render auto-deploys

### Step 3: Add API Key to Render
1. In Render dashboard, go to your service
2. Click **Settings** → **Environment** (or **Environment Variables**)
3. Add new variable:
   - Key: `GOOGLE_GEMINI_API_KEY`
   - Value: `paste_your_key_here`
4. Save/Redeploy

### Step 4: Test Live
```bash
# Replace YOUR-SERVICE with actual name
curl https://YOUR-SERVICE.onrender.com/api/health

# Should return: "photo_reading": true
```

---

## 📋 Checklist: Local Setup

- [ ] Python 3.12+ installed
- [ ] Virtual environment (.venv exists)
- [ ] google-generativeai installed
- [ ] .env created with API key
- [ ] Server runs without errors
- [ ] http://127.0.0.1:8000 loads
- [ ] Can upload test image
- [ ] /api/health returns "photo_reading": true
- [ ] Tests pass: `pytest tests/`

---

## 📋 Checklist: Deployment

- [ ] Code pushed to GitHub
- [ ] Render service created and deployed
- [ ] Environment variables set in Render
- [ ] https://YOUR-SERVICE.onrender.com loads
- [ ] Photo upload works
- [ ] /api/health returns "photo_reading": true
- [ ] Works on mobile device
- [ ] Works in different browser

---

## 🐛 Troubleshooting

### Error: "GOOGLE_GEMINI_API_KEY is not set"
```powershell
# Set environment variable
$env:GOOGLE_GEMINI_API_KEY = "your_key"

# Or create .env file in project root
# Edit it and add: GOOGLE_GEMINI_API_KEY=your_key
```

### Error: "ModuleNotFoundError: No module named 'google'"
```powershell
# Install the package
pip install google-generativeai>=0.6.0
```

### Error: "429 Too Many Requests"
You've exceeded free tier limit (1500/day or 60/min). Wait for reset or upgrade API key.

### App runs but photo upload returns 503
Check Render logs. Likely causes:
- API key not set in Render environment
- Render service needs restart

### Image recognition not working but app loads
- Verify API key is correct
- Check /api/health shows "photo_reading": true
- Try smaller image (< 5MB)
- Check Render logs for API errors

---

## 📝 Files Changed

| File | Change |
|------|--------|
| `app/llm.py` | Anthropic → Google Gemini |
| `app/config.py` | Config variable names updated |
| `requirements.txt` | anthropic → google-generativeai |
| `.env.example` | Variable names updated |
| `render.yaml` | Environment variables updated |
| NEW: `setup_gemini.bat` | Windows setup helper |
| NEW: `GEMINI_INTEGRATION_GUIDE.md` | Detailed guide |

---

## 🔐 Security

- ✅ API key never in code (use .env only)
- ✅ .env in .gitignore (never commit)
- ✅ Use environment variables for deployment
- ✅ Render's `sync: false` keeps key secret
- ✅ No logs contain API key

---

## 📚 Resources

- Google AI SDK: https://ai.google.dev/tutorials
- Python SDK Docs: https://ai.google.dev/api/python/google/generativeai
- Gemini API Reference: https://ai.google.dev/api
- Render Documentation: https://render.com/docs
- Project README: See [README.md](README.md)

---

## 💡 Tips

- **Free Tier**: 60 req/min, 1500/day — enough for demos
- **Model**: `gemini-2.0-flash` is latest, fastest, and cheapest
- **Image Size**: Keep under 5MB for best performance
- **Timeout**: 40 seconds allows time for processing
- **Max Calls**: Set to 300/day to stay in free tier

---

## Next Steps

1. Run setup_gemini.bat OR follow Manual Setup
2. Create .env with your API key
3. Test locally: `uvicorn app.main:app --reload`
4. Push to GitHub
5. Deploy via Render
6. Set API key in Render dashboard
7. Test live URL

**You're ready to go!** 🎉
