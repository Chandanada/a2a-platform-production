# A2A Platform — Railway Production Deployment

# Complete Step-by-Step Guide

# Stack: A2A Protocol + AP2 Protocol | PostgreSQL | 10 Services

==============================================================
OVERVIEW
===

10 services → 10 public Railway URLs:

1. registry           ← Deploy FIRST (everything depends on this)
2. sourcing\_agent     ← Hiring: GitHub candidate search
3. scheduler\_agent    ← Hiring: Gmail interview scheduling
4. background\_agent   ← Hiring: AI background verification
5. travel\_agent       ← Travel: Flight + hotel planning
6. hr\_ops\_agent       ← HR: Offer letters, contracts, payroll
7. ap2\_payment\_agent  ← Payment: AP2 v0.1 CartMandate + PaymentMandate
8. hiring\_dashboard   ← UI: Full hiring flow
9. trip\_dashboard     ← UI: Travel + AP2 payment flow
10. hr\_dashboard      ← UI: HR operations

==============================================================
PREREQUISITES
===

You need:
✅ GitHub account (you have one — confirmed)
✅ Railway account (free at railway.app)
✅ Gmail app password (already set: YOUR\_GMAILPASS\_HERE)
✅ Groq API key (already set)

==============================================================
STEP 1 — Push to GitHub
===

1. Go to github.com → New Repository
2. Name it: a2a-platform-production
3. Set to Public
4. Click "Create repository"
5. Open PowerShell and run:

   cd Downloads\\a2a-production    (wherever you extracted this zip)
git init
git add .
git commit -m "Initial A2A Platform"
git remote add origin https://github.com/YOUR\_USERNAME/a2a-platform-production.git
git push -u origin main

   Replace YOUR\_USERNAME with your actual GitHub username.

   ==============================================================
STEP 2 — Create Railway Account
   ===

6. Go to railway.app
7. Click "Start a New Project"
8. Sign in with GitHub (use same account)
9. Authorize Railway

   ==============================================================
STEP 3 — Add PostgreSQL Database
   ===

10. In Railway dashboard → New Project → "Provision PostgreSQL"
11. Wait for it to spin up (30 seconds)
12. Click on the PostgreSQL service
13. Go to "Variables" tab
14. Copy the DATABASE\_URL value — looks like:
postgresql://postgres:xxxx@postgres.railway.internal:5432/railway

    SAVE THIS — you'll need it for the registry service.

    ==============================================================
STEP 4 — Deploy Registry (FIRST — most important)
    ===

15. In Railway project → Add Service → "GitHub Repo"
16. Select: a2a-platform-production
17. Root Directory: registry
18. Railway will detect Python and deploy automatically
19. After deploy → Settings → Networking → Generate Domain
20. COPY THE URL: e.g. https://a2a-registry-prod.up.railway.app
21. Go to Variables tab and add ALL of these:
DATABASE\_URL    = (paste the PostgreSQL URL from Step 3)
REGISTRY\_URL    = https://a2a-registry-prod.up.railway.app
API\_KEY         = a2a-admin-key-changeme-in-production
22. Redeploy → wait for "Deployment successful"
23. VERIFY: Open https://a2a-registry-prod.up.railway.app
You should see the registry homepage with agent directory.

    ==============================================================
STEP 5 — Deploy All 6 Remote Agents
    ===

    For EACH agent below, do the same steps:
→ Add Service → GitHub Repo → set Root Directory → set Variables

    \------ SOURCING AGENT ------
Root Directory: sourcing\_agent
Variables:
GROQ\_API\_KEY    = YOUR\_GROQ\_API\_KEY\_HERE
GITHUB\_TOKEN    = YOUR\_GITHUB\_TOKEN\_HERE
REGISTRY\_URL    = https://a2a-registry-prod.up.railway.app
AGENT\_BASE\_URL  = https://SOURCING-URL.up.railway.app  ← set after deploy

    \------ SCHEDULER AGENT ------
Root Directory: scheduler\_agent
Variables:
GROQ\_API\_KEY           = YOUR\_GROQ\_API\_KEY\_HERE
GMAIL\_SENDER           = chandannov2291@gmail.com
GMAIL\_APP\_PASS         = YOUR\_GMAILPASS\_HERE
INTERVIEW\_NOTIFY\_EMAILS= chandannov2291@gmail.com,dubeyneha1191@gmail.com
MEET\_LINK              = meet.google.com/a2a-demo-hiring-2026
REGISTRY\_URL           = https://a2a-registry-prod.up.railway.app
AGENT\_BASE\_URL         = https://SCHEDULER-URL.up.railway.app  ← set after deploy

    \------ BACKGROUND CHECK AGENT ------
Root Directory: background\_agent
Variables:
GROQ\_API\_KEY   = YOUR\_GROQ\_API\_KEY\_HERE
REGISTRY\_URL   = https://a2a-registry-prod.up.railway.app
AGENT\_BASE\_URL = https://BGCHECK-URL.up.railway.app  ← set after deploy

    \------ TRAVEL AGENT ------
Root Directory: travel\_agent
Variables:
GROQ\_API\_KEY   = YOUR\_GROQ\_API\_KEY\_HERE
REGISTRY\_URL   = https://a2a-registry-prod.up.railway.app
AGENT\_BASE\_URL = https://TRAVEL-URL.up.railway.app  ← set after deploy

    \------ HR OPS AGENT ------
Root Directory: hr\_ops\_agent
Variables:
GROQ\_API\_KEY   = YOUR\_GROQ\_API\_KEY\_HERE
REGISTRY\_URL   = https://a2a-registry-prod.up.railway.app
AGENT\_BASE\_URL = https://HROPS-URL.up.railway.app  ← set after deploy

    \------ AP2 PAYMENT AGENT ------
Root Directory: ap2\_payment\_agent
Variables:
GROQ\_API\_KEY           = YOUR\_GROQ\_API\_KEY\_HERE
GMAIL\_SENDER           = chandannov2291@gmail.com
GMAIL\_APP\_PASS         = YOUR\_GMAILPASS\_HERE
INTERVIEW\_NOTIFY\_EMAILS= chandannov2291@gmail.com,dubeyneha1191@gmail.com
REGISTRY\_URL           = https://a2a-registry-prod.up.railway.app
AGENT\_BASE\_URL         = https://AP2-URL.up.railway.app  ← set after deploy
DEMO\_SIGNING\_SECRET    = ap2-demo-signing-secret-2026

    ==============================================================
STEP 6 — Deploy 3 Dashboards
    ===

    \------ HIRING DASHBOARD ------
Root Directory: hiring\_dashboard
Variables:
REGISTRY\_URL = https://a2a-registry-prod.up.railway.app

    \------ TRIP DASHBOARD (with AP2) ------
Root Directory: trip\_dashboard
Variables:
REGISTRY\_URL           = https://a2a-registry-prod.up.railway.app
GMAIL\_SENDER           = chandannov2291@gmail.com
GMAIL\_APP\_PASS         = YOUR\_GMAILPASS\_HERE
INTERVIEW\_NOTIFY\_EMAILS= chandannov2291@gmail.com,dubeyneha1191@gmail.com
DEMO\_SIGNING\_SECRET    = ap2-demo-signing-secret-2026
APP\_URL                = https://TRIP-URL.up.railway.app  ← set after deploy

    \------ HR DASHBOARD ------
Root Directory: hr\_dashboard
Variables:
REGISTRY\_URL = https://a2a-registry-prod.up.railway.app

    ==============================================================
STEP 7 — Register All 6 Agents in Registry
    ===

    Open your registry URL → /register page.

    Register each agent (replace URLs with actual Railway domains):

24. Candidate Sourcing Agent
URL:      https://SOURCING-URL.up.railway.app
Skill ID: find\_candidates
Skill:    Find Candidates
25. Interview Scheduler Agent
URL:      https://SCHEDULER-URL.up.railway.app
Skill ID: schedule\_interview
Skill:    Schedule Interview
26. Background Check Agent
URL:      https://BGCHECK-URL.up.railway.app
Skill ID: verify\_candidate
Skill:    Verify Candidate
27. Travel Agent
URL:      https://TRAVEL-URL.up.railway.app
Skill ID: plan\_trip
Skill:    Plan Trip
28. HR Ops Agent
URL:      https://HROPS-URL.up.railway.app
Skill ID: generate\_offer\_letter
Skill:    Generate Offer Letter
29. AP2 Payment Agent
URL:      https://AP2-URL.up.railway.app
Skill ID: process\_payment
Skill:    Process Payment

    ==============================================================
STEP 8 — Verify Everything Works
    ===

    Open these URLs and verify:

    Registry:          https://a2a-registry-prod.up.railway.app
Analytics:         https://a2a-registry-prod.up.railway.app/analytics
Audit Logs:        https://a2a-registry-prod.up.railway.app/audit
Register Page:     https://a2a-registry-prod.up.railway.app/register

    Hiring Dashboard:  https://HIRING-URL.up.railway.app
Trip Dashboard:    https://TRIP-URL.up.railway.app
HR Dashboard:      https://HR-URL.up.railway.app

    Agent Cards (should return JSON):
https://SOURCING-URL.up.railway.app/.well-known/agent-card.json
https://TRAVEL-URL.up.railway.app/.well-known/agent-card.json
https://AP2-URL.up.railway.app/.well-known/agent-card.json

    ==============================================================
STEP 9 — Test Each Flow
    ===

    TEST 1 — Hiring Flow:
Open Hiring Dashboard → Enter job title → Run
Should: Source candidates → Schedule interviews → Background check
Check:  /audit shows new hiring flow

    TEST 2 — Travel + AP2 Flow:
Open Trip Dashboard → Enter trip details → Find flights → Select → Pay
Should: IntentMandate → CartMandate → PaymentMandate → Booking confirmed
Check:  Gmail inbox for AP2 booking confirmation email

    TEST 3 — HR Ops:
Open HR Dashboard → Generate offer letter / Review contract / Process payroll
Check:  /audit shows hr\_ops flows

    ==============================================================
IMPORTANT NOTES
    ===

* Railway free tier: 500 hours/month per service (enough for demo)
* Auto-deploy: every git push to GitHub auto-redeploys
* Logs: Railway dashboard → service → Deployments → View logs
* PostgreSQL: persists across deployments (unlike SQLite)
* If deploy fails: check logs for missing env vars

  ==============================================================
YOUR SERVICE URLS (fill in after deployment)
  ===

  Registry:         \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
Sourcing Agent:   \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
Scheduler Agent:  \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
Background Agent: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
Travel Agent:     \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
HR Ops Agent:     \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
AP2 Payment:      \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
Hiring Dashboard: \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
Trip Dashboard:   \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_
HR Dashboard:     \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_

