# SOP: KisanRakshak

## 1. Project Title
KisanRakshak: AI Pesticide Packet Reader and Safe-Use Guide for Small Farmers

## 2. Domain
Domain 1: AI for Agriculture

## 3. Problem Statement
Small and marginal farmers spray pesticides whose labels are small, technical and mostly in English or Hindi. Farmers often cannot tell whether a product is banned or restricted, whether its label still covers their crop, how long to wait before harvest, or whether the packet has expired. Dealers may not give this information either. Misuse harms health, crops and food safety.

Research: pesticide poisoning reports and a PAN India study of dealers and farmers in Yavatmal (via Down To Earth, 2018); the CIB&RC lists of banned, refused and restricted pesticides; the 2023 Insecticides (Prohibition) Order, which removed label claims for specific crops; the Indian toxicity colour code (Insecticides Rules, 1971); existing crop-doctor apps such as Plantix, which diagnose crop problems but do not describe reading a pesticide packet. See `RESEARCH.md`.

## 4. Target Users
Primary: small farmers growing tomato, groundnut or paddy who read Telugu, Tamil or Hindi more easily than English. Secondary: input-shop staff, farmer groups and extension workers.

## 5. Proposed Solution
A mobile web app. The user photographs a pesticide packet. A vision model copies the printed fields. A tested rules engine then checks the product against the official lists and a curated reference file, and shows a result in the user's language: ban or restriction status for the chosen crop, waiting period before harvest, expiry, and the toxicity colour band. A spray plan combines several products into one earliest-harvest date. The app gives educational guidance only.

## 6. Key Features
1. Photo reading of the packet, with client-side resize and EXIF removal.
2. Ban, withdrawal, refusal and restriction alerts from 95 official entries, including crop-specific rules.
3. Waiting period for 30 products on three crops, never borrowed across strengths or forms.
4. Expiry check and toxicity colour-band explanation.
5. Spray plan: earliest harvest date across products, duplicate active-ingredient warning, calendar reminder.
6. English, Hindi, Telugu and Tamil for all screens, alerts and read-aloud.
7. Search by name, fictional sample packets, and an installable offline shell.
8. Safeguards: AI summary discarded unless every number is in the checked facts; "not covered" is never shown as "approved".

## 7. Technology Stack
Frontend: HTML, CSS, JavaScript (no framework), service worker. Backend: Python 3.12, FastAPI. AI: Anthropic Claude vision API, backend only. Data: `pesticides.json`, `banned.json` with a source on every entry. Database: none. Hosting: Render. Version control: GitHub.

## 8. AI Usage
Runtime: (a) vision model reads the packet photo into a bounded JSON schema; (b) an optional short summary, rejected if it states any number not in the checked facts. The model never decides bans, waiting periods or expiry. Development: an AI coding assistant helped with research, architecture, code, tests and documentation; all code was reviewed and tested by the team.

## 9. System Workflow
1. User chooses language and crop. 2. User takes or picks a photo (or picks a sample, or types the ingredient). 3. The phone resizes the photo and removes EXIF data. 4. The backend validates the file by its bytes and size, applies rate and daily limits, and sends it to the vision model. 5. The reply is cut to a fixed schema. 6. The rules engine checks bans, crop restrictions, reference match, waiting period, expiry and toxicity. 7. The result card is shown in the chosen language with an optional AI summary and read aloud. 8. The user may add the product and spray date to the plan, stored on the phone. 9. Any failure shows a plain message and the name-based check still works.

## 10. Security and Privacy
API key only in host environment variables; `.env` ignored, `.env.example` committed. All model calls from the backend. No login, no personal data, no location. Photos held in memory for one request, never stored. Strict Content Security Policy and security headers. Byte-level file type check, size cap, per-IP rate limits, daily cap on paid calls. Diary stored in the browser only.

## 11. Testing Plan
54 automated tests (rules, parsing, API errors, limits, headers, translations, secret scan). Scripted real-browser run on a phone-sized viewport checking console errors, CSP violations and overflow. Live check with a real key and real packet photos via `scripts/try_photo.py`. Cross-device checklist (Android Chrome on mobile data, iPhone or second browser, laptop, offline). Scenarios: banned product, banned only on this crop, expired packet, unknown product, mixed product, unreadable photo, two products sharing an ingredient.

## 12. Deployment Plan
Deploy early on Render from `render.yaml` as a single web service. Set `ANTHROPIC_API_KEY` in the dashboard. Check `/api/health`. Redeploy after changes. Test the live link on another device and browser. Submit the GitHub URL, the live URL and a short explanation.
