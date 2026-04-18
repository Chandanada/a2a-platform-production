"""
Hiring Manager Client Agent — v2
==================================
Full 3-step A2A hiring flow:
1. Sourcing Agent  → find candidates
2. Scheduler Agent → schedule interviews
3. Background Agent → verify candidates
"""
import os, uuid, httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse

load_dotenv()
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://localhost:8000")

app = FastAPI(title="Hiring Manager Client Agent", version="2.0.0")


async def discover_agent(skill: str) -> dict | None:
    """Curated Registry discovery — A2A spec strategy 2"""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{REGISTRY_URL}/registry/discover", params={"skill": skill}, timeout=10.0)
        agents = r.json().get("agents", [])
        return agents[0] if agents else None


async def fetch_agent_card(agent_url: str) -> dict:
    """Fetch official Agent Card from /.well-known/agent-card.json"""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{agent_url}/.well-known/agent-card.json", timeout=10.0)
        return r.json()


async def send_message(agent_url: str, text: str, data: dict = None) -> dict:
    """Send official A2A SendMessage (JSON-RPC 2.0)"""
    parts = [{"text": text, "mediaType": "text/plain"}]
    if data:
        parts.append({"data": data, "mediaType": "application/json"})
    payload = {
        "jsonrpc": "2.0",
        "id": f"req-{str(uuid.uuid4())[:8]}",
        "method": "SendMessage",
        "params": {
            "message": {
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "parts": parts
            }
        }
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(agent_url, json=payload)
        return r.json()


def extract_artifact(resp: dict) -> dict:
    try:
        parts = resp["result"]["task"]["artifacts"][0]["parts"]
        return next((p["data"] for p in parts if "data" in p), {})
    except Exception:
        return {}


@app.post("/hire")
async def hire(request: Request):
    body        = await request.json()
    job_title   = body.get("job_title", "Software Engineer")
    experience  = body.get("experience_years", 3)
    location    = body.get("location", "Remote")
    notes       = body.get("notes", "")

    report = {"request": body, "steps": [], "candidates": {}, "schedule": {}, "background_checks": {}, "status": "in_progress"}

    def step(msg): report["steps"].append(msg)

    # ── STEP 1: Find Candidates ────────────────────────────────────────────────
    step("🔍 Step 1: Querying registry for Candidate Sourcing Agent...")
    agent = await discover_agent("find_candidates")
    if not agent:
        return JSONResponse({"error": "No sourcing agent registered. Go to localhost:8000/register to register one."}, status_code=404)
    url = agent["supportedInterfaces"][0]["url"]
    step(f"✅ Found: {agent['name']} at {url}")

    step("📋 Step 2: Fetching Agent Card from /.well-known/agent-card.json...")
    card = await fetch_agent_card(url)
    step(f"✅ Agent Card — Skills: {[s['id'] for s in card.get('skills',[])]}")

    step("📤 Step 3: Sending hiring request via A2A SendMessage...")
    msg   = f"Find 3 top candidates for {job_title} with {experience} years experience. Location: {location}. {notes}"
    resp  = await send_message(url, msg)
    cands = extract_artifact(resp)
    report["candidates"] = cands
    step(f"✅ Received {len(cands.get('candidates',[]))} candidates")

    # ── STEP 2: Schedule Interviews ────────────────────────────────────────────
    step("🔍 Step 4: Querying registry for Interview Scheduler Agent...")
    agent = await discover_agent("schedule_interview")
    if not agent:
        report["status"] = "partial"; step("⚠️ No scheduler agent found.")
        return JSONResponse(report)
    url = agent["supportedInterfaces"][0]["url"]
    step(f"✅ Found: {agent['name']} at {url}")

    step("📋 Step 5: Fetching Scheduler Agent Card...")
    card = await fetch_agent_card(url)
    step(f"✅ Agent Card — Skills: {[s['id'] for s in card.get('skills',[])]}")

    step("📤 Step 6: Sending candidates to Scheduler Agent via A2A SendMessage...")
    resp     = await send_message(url, f"Schedule interviews for {job_title} candidates.", data=cands)
    schedule = extract_artifact(resp)
    report["schedule"] = schedule
    step(f"✅ Interview schedule created")

    # ── STEP 3: Background Check ───────────────────────────────────────────────
    step("🔍 Step 7: Querying registry for Background Check Agent...")
    agent = await discover_agent("verify_candidate")
    if not agent:
        report["status"] = "partial"; step("⚠️ No background check agent found. Register one at localhost:8000/register")
        return JSONResponse(report)
    url = agent["supportedInterfaces"][0]["url"]
    step(f"✅ Found: {agent['name']} at {url}")

    step("📋 Step 8: Fetching Background Check Agent Card...")
    card = await fetch_agent_card(url)
    step(f"✅ Agent Card — Skills: {[s['id'] for s in card.get('skills',[])]}")

    step("📤 Step 9: Running background checks via A2A SendMessage...")
    resp   = await send_message(url, f"Run background checks for {job_title} candidates.", data=cands)
    checks = extract_artifact(resp)
    report["background_checks"] = checks
    step("✅ Background checks completed for all candidates")

    report["status"] = "completed"
    step("🎉 Full hiring flow completed — Candidates sourced, interviewed, and verified!")
    return JSONResponse(report)


@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse("""<!DOCTYPE html>
<html>
<head>
  <title>Hiring Manager Agent</title>
  <style>
    :root { --bg:#0a0e1a;--card:#1a2235;--border:#1e2d45;--blue:#3b82f6;--green:#10b981;--text:#e2e8f0;--muted:#64748b; }
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Segoe UI',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding:40px 20px}
    .wrap{max-width:760px;margin:0 auto}
    h1{font-size:26px;font-weight:800;margin-bottom:6px}
    .sub{color:var(--muted);font-size:14px;margin-bottom:32px}
    .card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:28px;margin-bottom:20px}
    .field{margin-bottom:16px}
    label{display:block;font-size:13px;font-weight:600;color:#94a3b8;margin-bottom:6px}
    input{width:100%;background:#0a0e1a;border:1px solid var(--border);color:var(--text);padding:10px 14px;border-radius:8px;font-size:13px;outline:none}
    input:focus{border-color:var(--blue)}
    .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .btn{width:100%;background:var(--blue);color:#fff;border:none;padding:14px;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;margin-top:8px}
    .btn:hover{background:#1d4ed8}
    .btn:disabled{background:#334155;cursor:not-allowed}
    .steps{margin-bottom:16px}
    .step{padding:5px 0;font-size:13px;color:var(--green);border-bottom:1px solid var(--border)}
    .step:last-child{border:none}
    pre{font-size:11px;color:var(--muted);overflow-x:auto;white-space:pre-wrap;background:#0a0e1a;border:1px solid var(--border);border-radius:8px;padding:16px;margin-top:12px}
    .section-title{font-size:12px;font-weight:700;color:var(--blue);text-transform:uppercase;letter-spacing:1px;margin:16px 0 8px}
    #result{display:none}
  </style>
</head>
<body>
<div class="wrap">
  <h1>🤖 Hiring Manager Agent</h1>
  <p class="sub">A2A Client Agent — Discovers remote agents from registry and runs complete 3-step hiring flow</p>

  <div id="registryStatus" style="background:#0f1f3d;border:1px solid #1e3a5f;border-radius:10px;padding:14px 18px;margin-bottom:20px;font-size:13px;color:#93c5fd">
    ⏳ Checking registry status...
  </div>

  <div class="card">
    <div class="grid">
      <div class="field"><label>Job Title</label><input id="job" value="Senior Python Engineer"/></div>
      <div class="field"><label>Experience (years)</label><input id="exp" type="number" value="5"/></div>
    </div>
    <div class="grid">
      <div class="field"><label>Location</label><input id="loc" value="Remote"/></div>
      <div class="field"><label>Additional Notes</label><input id="notes" placeholder="e.g. Must know FastAPI"/></div>
    </div>
    <button class="btn" id="btn" onclick="run()">🚀 Start Full Hiring Flow (3 Steps)</button>
  </div>

  <div id="result" style="display:none">
    <div class="card">
      <div class="section-title">📊 Flow Progress</div>
      <div class="steps" id="steps"></div>
    </div>
    <div class="card" id="cardCands" style="display:none">
      <div class="section-title">👥 Sourced Candidates</div>
      <pre id="outCands"></pre>
    </div>
    <div class="card" id="cardSched" style="display:none">
      <div class="section-title">📅 Interview Schedule</div>
      <pre id="outSched"></pre>
    </div>
    <div class="card" id="cardBg" style="display:none">
      <div class="section-title">🔍 Background Check Report</div>
      <pre id="outBg"></pre>
    </div>
  </div>
</div>
<script>
// Check registry status on page load
window.addEventListener('DOMContentLoaded', async () => {
  const el = document.getElementById('registryStatus');
  try {
    const res  = await fetch('http://localhost:8000/registry/health');
    const data = await res.json();
    const count = data.registered_agents || 0;
    if (count === 0) {
      el.style.background = '#2d1515';
      el.style.borderColor = '#7f1d1d';
      el.style.color = '#f87171';
      el.innerHTML = `❌ <strong>No agents registered yet.</strong> The hiring flow will not work until you register agents. 
        <a href="http://localhost:8000/register" target="_blank" style="color:#60a5fa;font-weight:600;margin-left:8px">
          → Register Agents Now
        </a>`;
    } else {
      el.style.background = '#0a2318';
      el.style.borderColor = '#065f46';
      el.style.color = '#10b981';
      el.innerHTML = `✅ <strong>${count} agent(s) registered</strong> and ready. You can start the hiring flow.
        <a href="http://localhost:8000" target="_blank" style="color:#60a5fa;font-weight:600;margin-left:8px">
          → View Registry
        </a>`;
    }
  } catch(e) {
    el.style.background = '#2d1515';
    el.style.borderColor = '#7f1d1d';
    el.style.color = '#f87171';
    el.innerHTML = '❌ Registry is not running. Start the platform using start.bat first.';
  }
});

async function run() {
  const btn = document.getElementById('btn');
  btn.disabled = true; btn.textContent = '⏳ Running...';
  document.getElementById('result').style.display = 'block';
  document.getElementById('steps').innerHTML = '';
  ['cardCands','cardSched','cardBg'].forEach(id => document.getElementById(id).style.display='none');

  try {
    const res  = await fetch('/hire',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
      job_title: document.getElementById('job').value,
      experience_years: parseInt(document.getElementById('exp').value),
      location: document.getElementById('loc').value,
      notes: document.getElementById('notes').value
    })});
    const data = await res.json();

    // Show steps
    const stepsEl = document.getElementById('steps');
    if (data.error) {
      const d = document.createElement('div');
      d.className='step';
      d.style.color='#f87171';
      d.innerHTML = `❌ ${data.error}<br/><br/>
        <a href="http://localhost:8000/register" target="_blank"
           style="color:#3b82f6;font-weight:600">
          → Go to Registry and register your agents first
        </a>`;
      stepsEl.appendChild(d);
    } else {
      (data.steps||[]).forEach(s => {
        const d = document.createElement('div');
        d.className='step';
        d.style.color = s.includes('❌') || s.includes('⚠️') ? '#f87171' : '#10b981';
        d.textContent = s;
        stepsEl.appendChild(d);
      });

      // Only show sections if data exists
      if (data.candidates && Object.keys(data.candidates).length > 0) {
        document.getElementById('cardCands').style.display='block';
        document.getElementById('outCands').textContent = JSON.stringify(data.candidates, null, 2);
      }
      if (data.schedule && Object.keys(data.schedule).length > 0) {
        document.getElementById('cardSched').style.display='block';
        document.getElementById('outSched').textContent = JSON.stringify(data.schedule, null, 2);
      }
      if (data.background_checks && Object.keys(data.background_checks).length > 0) {
        document.getElementById('cardBg').style.display='block';
        document.getElementById('outBg').textContent = JSON.stringify(data.background_checks, null, 2);
      }
    }
  } catch(e) {
    const d = document.createElement('div');
    d.className='step'; d.style.color='#f87171';
    d.textContent = `Network error: ${e.message}`;
    document.getElementById('steps').appendChild(d);
  }

  btn.disabled=false; btn.textContent='🚀 Start Full Hiring Flow (3 Steps)';
}
</script>
</body>
</html>""")


# ── Audit logging helper ──────────────────────────────────────────────────────
import httpx as _httpx
import json as _json

async def _log_audit(flow_id, title, subtitle="", location="",
                     flow_type="hiring", agents_used=None,
                     result_count=0, result_data=None,
                     secondary_data=None, tertiary_data=None,
                     emails_sent_to=None, status="completed"):
    try:
        reg = os.getenv("REGISTRY_URL", "http://localhost:8000")
        async with _httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{reg}/registry/audit/create", json={
                "flow_id": flow_id, "flow_type": flow_type,
                "title": title, "subtitle": subtitle, "location": location
            })
            await client.post(f"{reg}/registry/audit/save", json={
                "flow_id": flow_id, "status": status,
                "agents_used": _json.dumps(agents_used or []),
                "result_count": result_count,
                "result_data": _json.dumps(result_data) if result_data else None,
                "secondary_data": _json.dumps(secondary_data) if secondary_data else None,
                "tertiary_data": _json.dumps(tertiary_data) if tertiary_data else None,
                "emails_sent_to": _json.dumps(emails_sent_to) if emails_sent_to else None,
                "completed_at": "now"
            })
    except Exception as e:
        print(f"[Audit] log error: {e}")
