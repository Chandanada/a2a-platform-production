"""
Interview Scheduler Agent — v3 (Gmail-Powered)
================================================
- Creates real interview schedules using Groq LLM
- Sends REAL emails via Gmail SMTP to dummy addresses only
- NEVER contacts real GitHub profiles
- Serves official A2A Agent Card at /.well-known/agent-card.json
- Handles A2A SendMessage (JSON-RPC 2.0)
"""
import os, json, uuid, smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from groq import Groq

load_dotenv()
GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
GMAIL_SENDER    = os.getenv("GMAIL_SENDER")
GMAIL_APP_PASS  = os.getenv("GMAIL_APP_PASS")
AGENT_BASE_URL  = os.getenv("AGENT_BASE_URL", "http://localhost:8002")

# Dummy email addresses — ONLY these receive emails, never real profiles
INTERVIEW_NOTIFY_EMAILS = os.getenv(
    "INTERVIEW_NOTIFY_EMAILS",
    "chandannov2291@gmail.com,dubeyneha1191@gmail.com"
).split(",")

# Placeholder Meet link
MEET_LINK = os.getenv("MEET_LINK", "meet.google.com/a2a-demo-hiring-2026")

groq_client = Groq(api_key=GROQ_API_KEY)

app = FastAPI(title="Interview Scheduler Agent", version="3.0.0")

AGENT_CARD = {
    "name":        "Interview Scheduler Agent",
    "description": "Schedules interviews for shortlisted candidates and sends real email notifications to internal HR team. Never contacts candidates directly.",
    "supportedInterfaces": [{"url": AGENT_BASE_URL, "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}],
    "provider":    {"organization": "A2A Hiring Platform", "url": os.getenv("REGISTRY_URL", "")},
    "iconUrl":     None,
    "version":     "3.0.0",
    "documentationUrl": os.getenv("REGISTRY_URL","") + "/agents/agents/Interview%20Scheduler%20Agent",
    "capabilities": {
        "streaming": False, "pushNotifications": False,
        "stateTransitionHistory": False, "extendedAgentCard": False
    },
    "securitySchemes": None, "security": None,
    "defaultInputModes":  ["application/json"],
    "defaultOutputModes": ["application/json"],
    "skills": [{
        "id":          "schedule_interview",
        "name":        "Schedule Interview",
        "description": "Creates interview schedule and sends real email notifications to internal HR team addresses only. Candidates are never contacted directly.",
        "tags":        ["scheduling", "email", "interview", "hiring", "gmail"],
        "examples":    ["Schedule interviews for 3 shortlisted candidates next week"],
        "inputModes":  ["application/json"],
        "outputModes": ["application/json"],
        "securityRequirements": None
    }],
    "signatures": None
}


@app.get("/.well-known/agent-card.json")
def get_agent_card():
    return JSONResponse(content=AGENT_CARD)


def send_email(to_addresses: list, subject: str, html_body: str) -> bool:
    """Send real email via Gmail SMTP."""
    if not GMAIL_SENDER or not GMAIL_APP_PASS:
        print("⚠️ Gmail not configured — skipping email send")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"A2A Hiring Platform <{GMAIL_SENDER}>"
        msg["To"]      = ", ".join(to_addresses)
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_SENDER, GMAIL_APP_PASS)
            smtp.sendmail(GMAIL_SENDER, to_addresses, msg.as_string())
        return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False


def build_email_html(candidate: dict, schedule: dict, role: str) -> str:
    """Build professional HTML interview email."""
    rounds_html = ""
    for r in schedule.get("interview_rounds", []):
        rounds_html += f"""
        <tr>
          <td style="padding:12px;border-bottom:1px solid #e2e8f0">
            <strong>Round {r.get('round')} — {r.get('type')}</strong><br/>
            <span style="color:#64748b;font-size:13px">
              📅 {r.get('date')} at {r.get('time')} ({r.get('duration')})<br/>
              👤 Interviewer: {r.get('interviewer')}<br/>
              🎥 Format: {r.get('format')}<br/>
              🔗 Meeting: <a href="https://{MEET_LINK}">{MEET_LINK}</a>
            </span>
          </td>
        </tr>"""

    github_url = candidate.get("github_url", "")
    languages  = ", ".join(candidate.get("languages", []))

    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:'Segoe UI',sans-serif;background:#f8fafc;margin:0;padding:20px">
  <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#1e3a5f,#0f1f3d);padding:28px 32px">
      <h1 style="color:#fff;margin:0;font-size:20px">🤖 A2A Hiring Platform</h1>
      <p style="color:#93c5fd;margin:6px 0 0;font-size:13px">Interview Schedule Notification — Internal Use Only</p>
    </div>

    <!-- Content -->
    <div style="padding:28px 32px">
      <h2 style="color:#1e293b;font-size:18px;margin:0 0 4px">Interview Scheduled</h2>
      <p style="color:#64748b;font-size:14px;margin:0 0 24px">
        A2A Scheduler Agent has created an interview plan for the following candidate.
      </p>

      <!-- Candidate Card -->
      <div style="background:#f1f5f9;border-radius:12px;padding:20px;margin-bottom:24px">
        <h3 style="color:#1e293b;margin:0 0 12px;font-size:16px">👤 Candidate Profile</h3>
        <table style="width:100%;border-collapse:collapse">
          <tr><td style="padding:4px 0;color:#64748b;width:140px">Name</td><td style="color:#1e293b;font-weight:600">{candidate.get('name', 'N/A')}</td></tr>
          <tr><td style="padding:4px 0;color:#64748b">GitHub</td><td><a href="{github_url}" style="color:#3b82f6">{github_url}</a></td></tr>
          <tr><td style="padding:4px 0;color:#64748b">Location</td><td style="color:#1e293b">{candidate.get('location', 'N/A')}</td></tr>
          <tr><td style="padding:4px 0;color:#64748b">Languages</td><td style="color:#1e293b">{languages}</td></tr>
          <tr><td style="padding:4px 0;color:#64748b">GitHub Repos</td><td style="color:#1e293b">{candidate.get('public_repos', 0)} public repos</td></tr>
          <tr><td style="padding:4px 0;color:#64748b">Match Score</td><td style="color:#10b981;font-weight:700">{candidate.get('match_score', 'N/A')}% match</td></tr>
          <tr><td style="padding:4px 0;color:#64748b">Role</td><td style="color:#1e293b;font-weight:600">{role}</td></tr>
        </table>
      </div>

      <!-- Interview Rounds -->
      <h3 style="color:#1e293b;font-size:16px;margin:0 0 12px">📅 Interview Schedule</h3>
      <table style="width:100%;border-collapse:collapse;background:#f8fafc;border-radius:10px;overflow:hidden">
        {rounds_html}
      </table>

      <!-- Disclaimer -->
      <div style="margin-top:24px;padding:14px;background:#fef3c7;border-radius:8px;border-left:4px solid #f59e0b">
        <p style="margin:0;font-size:12px;color:#92400e">
          ⚠️ <strong>Internal Use Only.</strong> This email is sent to HR team only.
          The candidate has NOT been contacted. Profile data sourced from GitHub Public API.
          Match scores are AI estimates only.
        </p>
      </div>
    </div>

    <!-- Footer -->
    <div style="background:#f1f5f9;padding:16px 32px;text-align:center">
      <p style="color:#94a3b8;font-size:12px;margin:0">
        Generated by A2A Interview Scheduler Agent · 
        <a href="https://a2a-platform-production-production.up.railway.app" style="color:#3b82f6">A2A Registry</a>
      </p>
    </div>
  </div>
</body>
</html>"""


@app.post("/")
async def handle_message(request: Request):
    body = await request.json()
    if body.get("method") != "SendMessage":
        return JSONResponse(content={
            "jsonrpc": "2.0", "id": body.get("id"),
            "error": {"code": -32601, "message": "Method not found"}
        }, status_code=400)

    parts     = body.get("params", {}).get("message", {}).get("parts", [])
    user_text = next((p["text"] for p in parts if "text" in p), "")
    cand_data = next((p["data"] for p in parts if "data" in p), None)
    today     = datetime.now().strftime("%B %d, %Y")

    candidates = []
    role = "Software Engineer"
    if cand_data:
        candidates = cand_data.get("candidates", [])
        role = (cand_data.get("job_analysis", {}) or {}).get("role", "Software Engineer")
        # Also try top-level role field
        if role == "Software Engineer":
            role = cand_data.get("role", cand_data.get("job_title", "Software Engineer"))
    
    # If no candidates in data, create dummy ones for demo
    if not candidates:
        candidates = [
            {"name": "Demo Candidate 1", "github_login": "demo1", "location": "Remote", "languages": ["Python"], "match_score": 8},
            {"name": "Demo Candidate 2", "github_login": "demo2", "location": "Remote", "languages": ["Python"], "match_score": 7},
        ]

    # Build context for LLM
    ctx = json.dumps([{
        "name":      c.get("name"),
        "login":     c.get("github_login"),
        "location":  c.get("location"),
        "languages": c.get("languages"),
        "match":     c.get("match_score")
    } for c in candidates], indent=2)

    prompt = f"""You are an expert HR coordinator. Today is {today}.

Schedule interviews for these candidates for the role of {role}:
{ctx}

Return ONLY valid JSON (no markdown):
{{
  "scheduling_summary": "Brief overview",
  "interview_week": "Week of [date]",
  "schedules": [
    {{
      "candidate_name": "Name",
      "github_login": "login",
      "role": "{role}",
      "interview_rounds": [
        {{
          "round": 1,
          "type": "HR Screening",
          "date": "Monday, April 14, 2026",
          "time": "10:00 AM IST",
          "duration": "30 minutes",
          "interviewer": "Sarah Mitchell, HR Manager",
          "format": "Video call via Google Meet",
          "topics_to_cover": ["Background", "Motivation", "Salary expectations"]
        }},
        {{
          "round": 2,
          "type": "Technical Interview",
          "date": "Wednesday, April 16, 2026",
          "time": "2:00 PM IST",
          "duration": "60 minutes",
          "interviewer": "Rajesh Kumar, Senior Engineer",
          "format": "Video call with live coding",
          "topics_to_cover": ["System design", "Coding problem", "Code review"]
        }},
        {{
          "round": 3,
          "type": "Final Round",
          "date": "Friday, April 18, 2026",
          "time": "4:00 PM IST",
          "duration": "45 minutes",
          "interviewer": "Priya Sharma, Engineering Manager",
          "format": "Video call",
          "topics_to_cover": ["Culture fit", "Career goals", "Team dynamics"]
        }}
      ]
    }}
  ],
  "next_steps": "What happens after all interviews"
}}"""

    resp = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5, max_tokens=3000,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        raw = raw[4:] if raw.startswith("json") else raw
    try:
        schedule_data = json.loads(raw.strip())
    except Exception:
        schedule_data = {"raw_response": raw}

    # Send real emails to dummy addresses only
    emails_sent = []
    if GMAIL_SENDER and GMAIL_APP_PASS and schedule_data.get("schedules"):
        for sched in schedule_data["schedules"]:
            # Find matching candidate data
            cand = next(
                (c for c in candidates if c.get("github_login") == sched.get("github_login")),
                {}
            )
            subject = f"Interview Scheduled — {sched.get('candidate_name')} | {role}"
            html    = build_email_html(cand, sched, role)
            sent    = send_email(INTERVIEW_NOTIFY_EMAILS, subject, html)
            emails_sent.append({
                "candidate": sched.get("candidate_name"),
                "sent_to":   INTERVIEW_NOTIFY_EMAILS,
                "success":   sent
            })

    schedule_data["email_notifications"] = emails_sent
    schedule_data["email_disclaimer"]    = "Emails sent to internal HR team only. Candidates were NOT contacted."
    schedule_data["meet_link_used"]      = MEET_LINK

    return JSONResponse(content={
        "jsonrpc": "2.0", "id": body.get("id", "req-001"),
        "result": {
            "task": {
                "id": str(uuid.uuid4()), "contextId": str(uuid.uuid4()),
                "status": {"state": "TASK_STATE_COMPLETED"},
                "artifacts": [{
                    "artifactId": str(uuid.uuid4()),
                    "name": "interview_schedule",
                    "parts": [{"data": schedule_data, "mediaType": "application/json"}]
                }]
            }
        }
    })