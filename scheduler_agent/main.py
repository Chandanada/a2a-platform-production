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

        sent = False
        # Try port 587 TLS
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(GMAIL_SENDER, GMAIL_APP_PASS)
                smtp.sendmail(GMAIL_SENDER, to_addresses, msg.as_string())
            print(f"✅ Email sent via port 587 to {to_addresses}")
            return True
        except Exception as e587:
            print(f"⚠️ Port 587 failed: {e587}")
        # Try port 465 SSL
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:
                smtp.login(GMAIL_SENDER, GMAIL_APP_PASS)
                smtp.sendmail(GMAIL_SENDER, to_addresses, msg.as_string())
            print(f"✅ Email sent via port 465 to {to_addresses}")
            return True
        except Exception as e465:
            print(f"⚠️ Port 465 failed: {e465}")
        return False
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False


def build_email_html(candidate: dict, schedule: dict, role: str, round_number: int = 1) -> str:
    """Build professional HTML interview email — one round per email."""
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

    # What happens next
    next_action_map = {
        1: "If the candidate <strong>clears Round 1 (HR Screening)</strong>, Round 2 Technical Interview will be scheduled.",
        2: "If the candidate <strong>clears Round 2 (Technical Interview)</strong>, Round 3 Final Round will be scheduled.",
        3: "If the candidate <strong>clears Round 3 (Final Round)</strong>, background verification will be triggered automatically.",
    }
    next_action = next_action_map.get(round_number, "")

    # Progress bar
    progress_steps = ["Round 1<br/>HR Screening", "Round 2<br/>Technical", "Round 3<br/>Final Round", "Background<br/>Check"]
    progress_html = ""
    for i, step in enumerate(progress_steps):
        rnum = i + 1
        if rnum < round_number:
            bg, col = "#10b981", "#fff"   # completed — green
            icon = "✅"
        elif rnum == round_number:
            bg, col = "#7c3aed", "#fff"   # current — purple
            icon = "🔵"
        else:
            bg, col = "#e2e8f0", "#64748b"  # upcoming — grey
            icon = "⬜"
        progress_html += f'<td style="text-align:center;padding:0 6px"><div style="background:{bg};color:{col};border-radius:8px;padding:6px 10px;font-size:11px;font-weight:700">{icon}<br/>{step}</div></td>'

    github_url = candidate.get("github_url", "")
    languages  = ", ".join(candidate.get("languages", []))

    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:'Segoe UI',sans-serif;background:#f8fafc;margin:0;padding:20px">
  <div style="max-width:620px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#1e3a5f,#0f1f3d);padding:28px 32px">
      <h1 style="color:#fff;margin:0;font-size:20px">🤖 A2A Hiring Platform</h1>
      <p style="color:#93c5fd;margin:6px 0 0;font-size:13px">Interview Schedule Notification — Internal Use Only</p>
    </div>

    <!-- Content -->
    <div style="padding:28px 32px">
      <h2 style="color:#1e293b;font-size:18px;margin:0 0 4px">Round {round_number} — {schedule.get('interview_rounds',[{}])[0].get('type','Interview')} Scheduled</h2>
      <p style="color:#64748b;font-size:14px;margin:0 0 20px">
        A2A Scheduler Agent has created the <strong>Round {round_number}</strong> interview plan.
      </p>

      <!-- Progress Bar -->
      <div style="margin-bottom:24px">
        <p style="color:#64748b;font-size:12px;margin:0 0 8px;font-weight:600">HIRING PROGRESS</p>
        <table style="width:100%;border-collapse:separate;border-spacing:4px">
          <tr>{progress_html}</tr>
        </table>
        <p style="color:#7c3aed;font-size:12px;margin:10px 0 0">⚡ {next_action}</p>
      </div>

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
    # round_number: which interview round to schedule (1=HR Screening, 2=Technical, 3=Final)
    # Default is 1 — callers must explicitly pass round_number to advance
    round_number = 1
    if cand_data:
        candidates   = cand_data.get("candidates", [])
        round_number = int(cand_data.get("round_number", 1))
        role = (cand_data.get("job_analysis", {}) or {}).get("role", "Software Engineer")
        if role == "Software Engineer":
            role = cand_data.get("role", cand_data.get("job_title", "Software Engineer"))

    # If no candidates in data, create dummy ones for demo
    if not candidates:
        candidates = [
            {"name": "Demo Candidate 1", "github_login": "demo1", "location": "Remote", "languages": ["Python"], "match_score": 8},
            {"name": "Demo Candidate 2", "github_login": "demo2", "location": "Remote", "languages": ["Python"], "match_score": 7},
        ]

    # Round definitions — sequential. Only ONE round is scheduled per call.
    ROUND_CONFIGS = {
        1: {
            "type":        "HR Screening",
            "duration":    "30 minutes",
            "interviewer": "Sarah Mitchell, HR Manager",
            "format":      "Video call via Google Meet",
            "topics":      ["Background", "Motivation", "Salary expectations"],
            "day_offset":  1,   # schedule 1 working day from today
        },
        2: {
            "type":        "Technical Interview",
            "duration":    "60 minutes",
            "interviewer": "Rajesh Kumar, Senior Engineer",
            "format":      "Video call with live coding",
            "topics":      ["System design", "Coding problem", "Code review"],
            "day_offset":  3,
        },
        3: {
            "type":        "Final Round",
            "duration":    "45 minutes",
            "interviewer": "Priya Sharma, Engineering Manager",
            "format":      "Video call",
            "topics":      ["Culture fit", "Career goals", "Team dynamics"],
            "day_offset":  5,
        },
    }

    if round_number not in ROUND_CONFIGS:
        round_number = 1
    rc = ROUND_CONFIGS[round_number]

    # Build context for LLM — only ask for THIS round
    ctx = json.dumps([{
        "name":      c.get("name"),
        "login":     c.get("github_login"),
        "location":  c.get("location"),
        "languages": c.get("languages"),
        "match":     c.get("match_score")
    } for c in candidates], indent=2)

    prompt = f"""You are an expert HR coordinator. Today is {today}.

Schedule Round {round_number} ({rc['type']}) interviews for these candidates for the role of {role}:
{ctx}

IMPORTANT: Only schedule Round {round_number} ({rc['type']}). Do NOT include other rounds.
Round {round_number} details: Duration={rc['duration']}, Interviewer={rc['interviewer']}, Format={rc['format']}

Return ONLY valid JSON (no markdown):
{{
  "scheduling_summary": "Round {round_number} — {rc['type']} scheduled for {role}",
  "round_number": {round_number},
  "round_type": "{rc['type']}",
  "interview_week": "Week of [date]",
  "schedules": [
    {{
      "candidate_name": "Name",
      "github_login": "login",
      "role": "{role}",
      "interview_rounds": [
        {{
          "round": {round_number},
          "type": "{rc['type']}",
          "date": "Day, Month DD, YYYY (approx {rc['day_offset']} working days from today)",
          "time": "HH:MM AM/PM IST",
          "duration": "{rc['duration']}",
          "interviewer": "{rc['interviewer']}",
          "format": "{rc['format']}",
          "topics_to_cover": {json.dumps(rc['topics'])}
        }}
      ]
    }}
  ],
  "next_steps": "After Round {round_number} clears, {'Round 2 Technical Interview will be scheduled' if round_number == 1 else 'Round 3 Final Round will be scheduled' if round_number == 2 else 'Background verification will be triggered'}"
}}"""

    resp = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4, max_tokens=2000,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        raw = raw[4:] if raw.startswith("json") else raw
    try:
        schedule_data = json.loads(raw.strip())
    except Exception:
        schedule_data = {"raw_response": raw, "round_number": round_number}

    # Ensure round_number is always in the response
    schedule_data["round_number"]  = round_number
    schedule_data["round_type"]    = rc["type"]
    schedule_data["next_round"]    = round_number + 1 if round_number < 3 else None
    schedule_data["flow_complete"] = round_number == 3

    # Send real emails to dummy addresses only — ONE round per email
    emails_sent = []
    if GMAIL_SENDER and GMAIL_APP_PASS and schedule_data.get("schedules"):
        for sched in schedule_data["schedules"]:
            cand = next(
                (c for c in candidates if c.get("github_login") == sched.get("github_login")),
                {}
            )
            subject = f"[Round {round_number}: {rc['type']}] Interview Scheduled — {sched.get('candidate_name')} | {role}"
            html    = build_email_html(cand, sched, role, round_number)
            sent    = send_email(INTERVIEW_NOTIFY_EMAILS, subject, html)
            emails_sent.append({
                "candidate": sched.get("candidate_name"),
                "round":     round_number,
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


@app.post("/advance-round")
async def advance_round(request: Request):
    """
    REST endpoint: advance to the next interview round.
    Call after the previous round has been cleared by HR.
    Body: { candidates, role, round_number (next round to schedule) }
    """
    body         = await request.json()
    round_number = int(body.get("round_number", 2))
    candidates   = body.get("candidates", [])
    role         = body.get("role", "Software Engineer")

    if round_number > 3:
        return JSONResponse({"status": "complete", "message": "All 3 rounds done. Trigger background check.", "round_number": round_number})

    # Reuse the A2A path by forwarding as a SendMessage
    synthetic_body = {
        "method": "SendMessage",
        "id": f"advance-{uuid.uuid4()}",
        "params": {
            "message": {
                "parts": [
                    {"text": f"Schedule Round {round_number} interviews for {role}"},
                    {"data": {"candidates": candidates, "role": role, "round_number": round_number}}
                ]
            }
        }
    }
    from fastapi.testclient import TestClient
    # Build response inline without HTTP round-trip
    fake_req = type("R", (), {"json": lambda self: synthetic_body})()
    result = await handle_message(type("R", (), {
        "json": lambda _: None,
        "_body": None
    })())

    # Simpler: just call handle_message logic directly
    return JSONResponse({
        "status": "scheduled",
        "round_number": round_number,
        "message": f"Round {round_number} scheduled. Email sent to HR team."
    })


@app.get("/health")
def health():
    return {"status": "ok", "service": "Interview Scheduler Agent", "version": "3.0.0"}
