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


async def send_message(agent_url: str, text: str, data: dict = None, timeout: float = 60.0) -> dict:
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
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(agent_url, json=payload)
        try:
            return r.json()
        except Exception:
            return {"error": f"Agent returned non-JSON (HTTP {r.status_code}): {r.text[:200]}"}


def extract_artifact(resp: dict) -> dict:
    try:
        parts = resp["result"]["task"]["artifacts"][0]["parts"]
        return next((p["data"] for p in parts if "data" in p), {})
    except Exception:
        return {}


@app.post("/hire")
async def hire(request: Request):
    body           = await request.json()
    job_title      = body.get("job_title", "Software Engineer")
    experience     = body.get("experience_years", 3)
    location       = body.get("location", "Remote")
    notes          = body.get("notes", "")
    num_candidates = body.get("num_candidates", 5)
    flow_id        = str(uuid.uuid4())

    report = {"request": body, "steps": [], "candidates": {}, "schedule": {}, "background_checks": {}, "status": "in_progress"}
    def step(msg): report["steps"].append(msg)

    # STEP 1: Find Candidates
    step("🔍 Step 1: Querying registry for Candidate Sourcing Agent...")
    agent = await discover_agent("find_candidates")
    if not agent:
        report["status"] = "failed"
        report["steps"].append("❌ No sourcing agent found in registry.")
        return JSONResponse(report, status_code=404)
    url = agent["supportedInterfaces"][0]["url"]
    step(f"✅ Found: {agent['name']} at {url}")

    try:
        card = await fetch_agent_card(url)
        step(f"✅ Agent Card — Skills: {[s['id'] for s in card.get('skills',[])]}")
    except Exception as e:
        step(f"⚠️ Agent card: {e}")

    step(f"📤 Step 2: Sending request for {num_candidates} candidates via A2A SendMessage...")
    msg = f"Find {num_candidates} top candidates for {job_title} with {experience} years experience in {location}. {notes}"
    try:
        resp  = await send_message(url, msg)
        if resp.get("error") and "result" not in resp:
            step(f"❌ Sourcing agent error: {resp.get('error','Unknown')}")
            report["status"] = "failed"
            return JSONResponse(report)
        cands = extract_artifact(resp)
    except Exception as e:
        step(f"❌ Sourcing agent failed: {e}")
        report["status"] = "failed"
        return JSONResponse(report)

    report["candidates"] = cands
    num_found = len(cands.get("candidates", []))
    step(f"✅ Received {num_found} candidates")

    # STEP 2: Schedule Interviews
    step("🔍 Step 3: Querying registry for Interview Scheduler Agent...")
    sched_agent = await discover_agent("schedule_interview")
    if not sched_agent:
        report["status"] = "partial"
        step("⚠️ No scheduler agent found — skipping interviews")
    else:
        surl = sched_agent["supportedInterfaces"][0]["url"]
        step(f"✅ Found: {sched_agent['name']} at {surl}")
        step("📤 Step 4: Scheduling interviews via A2A SendMessage...")
        try:
            # Add job_title to the data sent to scheduler
            sched_data = {**cands, "job_title": job_title, "location": location}
            sresp    = await send_message(surl, f"Schedule Round 1 interviews for {job_title} candidates.", data=sched_data, timeout=90.0)
            if sresp.get("error") and "result" not in sresp:
                step(f"⚠️ Scheduler returned error: {sresp.get('error','')}")
            else:
                schedule = extract_artifact(sresp)
                report["schedule"] = schedule
                step(f"✅ Interviews scheduled")
        except Exception as e:
            step(f"⚠️ Scheduler error: {str(e)[:100]}")

    # STEP 3: Background Checks
    step("🔍 Step 5: Querying registry for Background Check Agent...")
    bg_agent = await discover_agent("verify_candidate")
    if not bg_agent:
        report["status"] = "partial"
        step("⚠️ No background check agent found — skipping")
    else:
        bgurl = bg_agent["supportedInterfaces"][0]["url"]
        step(f"✅ Found: {bg_agent['name']} at {bgurl}")
        step("📤 Step 6: Running background checks via A2A SendMessage...")
        try:
            bgresp = await send_message(bgurl, f"Run background checks for {job_title} candidates.", data=cands)
            checks = extract_artifact(bgresp)
            report["background_checks"] = checks
            step("✅ Background checks complete")
        except Exception as e:
            step(f"⚠️ Background check error: {e}")

    report["status"] = "completed"
    step("🎉 Full hiring flow completed!")

    # Log to audit
    try:
        import json as _json
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{REGISTRY_URL}/registry/audit/create", json={
                "flow_id": flow_id, "flow_type": "hiring",
                "title": job_title, "subtitle": f"{experience} yrs exp",
                "location": location, "experience_years": experience
            })
            await client.post(f"{REGISTRY_URL}/registry/audit/save", json={
                "flow_id": flow_id, "status": "completed",
                "agents_used": _json.dumps(["Sourcing Agent","Scheduler Agent","Background Agent"]),
                "result_count": num_found,
                "result_data": _json.dumps(cands),
                "secondary_data": _json.dumps(report.get("schedule",{})),
                "tertiary_data": _json.dumps(report.get("background_checks",{})),
                "completed_at": "now"
            })
    except Exception as e:
        print(f"Audit log error: {e}")

    return JSONResponse(report)


@app.get("/registry-status")
async def registry_status():
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{REGISTRY_URL}/registry/health", timeout=5.0)
            return r.json()
    except Exception:
        return {"status": "error", "registered_agents": 0}


@app.get("/", response_class=HTMLResponse)
async def home():
    reg = REGISTRY_URL
    return HTMLResponse(f"""<!DOCTYPE html>
<html>
<head>
  <title>Hiring Manager — A2A Platform</title>
  <style>
    :root{{--bg:#0a0f1e;--card:#111827;--card2:#1a2235;--border:#1e2d45;--purple:#7c3aed;--pink:#ec4899;--violet:#a78bfa;--text:#e2e8f0;--muted:#64748b;--green:#10b981;--red:#f87171;--amber:#f59e0b;--blue:#3b82f6}}
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding:0}}
    nav{{background:rgba(10,15,30,0.97);border-bottom:1px solid var(--border);padding:0 32px;display:flex;align-items:center;justify-content:space-between;height:58px;position:sticky;top:0;z-index:100}}
    .brand{{display:flex;align-items:center;gap:10px}}
    .logo{{width:32px;height:32px;border-radius:10px;background:linear-gradient(135deg,#7c3aed,#ec4899);display:flex;align-items:center;justify-content:center;font-size:16px}}
    .brand-name{{font-size:15px;font-weight:800;color:#fff}}
    .nav-badge{{background:rgba(124,58,237,0.15);border:1px solid rgba(124,58,237,0.3);color:var(--violet);font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;margin-left:8px}}
    .nav-links a{{color:var(--muted);text-decoration:none;font-size:13px;padding:6px 14px;border-radius:8px}}
    .nav-links a:hover{{color:var(--text);background:rgba(124,58,237,0.1)}}
    .container{{max-width:900px;margin:0 auto;padding:28px 24px}}
    h1{{font-size:24px;font-weight:900;margin-bottom:4px}}
    .sub{{color:var(--muted);font-size:13px;margin-bottom:20px}}
    .sbar{{padding:12px 16px;border-radius:10px;margin-bottom:20px;font-size:13px;font-weight:600}}
    .sbar.checking{{background:rgba(124,58,237,0.08);border:1px solid rgba(124,58,237,0.2);color:var(--violet)}}
    .sbar.ok{{background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);color:var(--green)}}
    .sbar.error{{background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.25);color:var(--red)}}
    .card{{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:26px;margin-bottom:20px}}
    .ct{{font-size:12px;font-weight:700;color:var(--violet);text-transform:uppercase;letter-spacing:1px;margin-bottom:16px}}
    .g2{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}}
    .g3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:14px}}
    .f{{display:flex;flex-direction:column;gap:5px}}
    label{{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}}
    input,select,textarea{{background:#080c1a;border:1px solid var(--border);color:var(--text);padding:10px 12px;border-radius:8px;font-size:13px;outline:none;width:100%;font-family:inherit}}
    input:focus,select:focus,textarea:focus{{border-color:var(--purple)}}
    select option{{background:#111827}}
    .rbtn{{width:100%;background:linear-gradient(135deg,#7c3aed,#ec4899);color:#fff;border:none;padding:13px;border-radius:10px;font-size:14px;font-weight:700;cursor:pointer;margin-top:8px;transition:opacity .2s}}
    .rbtn:hover{{opacity:.88}}.rbtn:disabled{{opacity:.4;cursor:not-allowed}}
    #result{{display:none}}
    .rc{{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:22px;margin-bottom:14px}}
    .rct{{font-size:12px;font-weight:700;color:var(--violet);text-transform:uppercase;letter-spacing:1px;margin-bottom:12px}}
    .step{{padding:5px 0;font-size:13px;border-bottom:1px solid var(--border);color:var(--green)}}
    .step:last-child{{border:none}}.step.e{{color:var(--red)}}
    .cand-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin-top:12px}}
    .cand-card{{background:var(--card2);border:1px solid var(--border);border-radius:12px;padding:16px}}
    .cand-name{{font-size:14px;font-weight:700;margin-bottom:4px}}
    .cand-score{{display:inline-block;background:rgba(16,185,129,0.1);color:var(--green);border:1px solid rgba(16,185,129,0.25);border-radius:20px;padding:2px 10px;font-size:11px;font-weight:700;margin-bottom:8px}}
    .cand-detail{{font-size:12px;color:var(--muted);margin-bottom:3px}}
    a.gh-link{{color:var(--violet);text-decoration:none;font-size:12px;font-weight:600}}
    a.gh-link:hover{{text-decoration:underline}}
  </style>
</head>
<body>
<nav>
  <div class="brand">
    <div class="logo">🤖</div>
    <span class="brand-name">Hiring Manager</span>
    <span class="nav-badge">Google A2A Protocol</span>
  </div>
  <div class="nav-links" style="display:flex;gap:2px">
    <a href="{reg}" target="_blank">Registry</a>
    <a href="{reg}/audit" target="_blank">Audit Logs</a>
    <a href="{reg}/analytics" target="_blank">Analytics</a>
  </div>
</nav>
<div class="container">
  <h1>🚀 Hiring Manager</h1>
  <p class="sub">A2A Client Agent — discovers remote agents from registry and runs complete 3-step hiring flow</p>

  <div id="regBar" class="sbar checking">⏳ Checking registry...</div>

  <div class="card">
    <div class="ct">🧑‍💼 Job Requirements</div>
    <div class="g2">
      <div class="f"><label>Job Title</label><input id="jt" value="Senior Python Engineer"/></div>
      <div class="f"><label>Experience (years)</label><input id="exp" type="number" value="5" min="0" max="20"/></div>
    </div>
    <div class="g3">
      <div class="f">
        <label>Location</label>
        <select id="loc">
          <option value="Remote">Remote</option>
          <option value="India">India (On-site)</option>
          <option value="Bangalore">Bangalore</option>
          <option value="Mumbai">Mumbai</option>
          <option value="Delhi">Delhi</option>
          <option value="Hyderabad">Hyderabad</option>
          <option value="Pune">Pune</option>
          <option value="Outside India">Outside India</option>
          <option value="USA">USA</option>
          <option value="UK">UK</option>
          <option value="Singapore">Singapore</option>
          <option value="UAE">UAE</option>
        </select>
      </div>
      <div class="f">
        <label>No. of Candidates</label>
        <select id="numcands">
          <option value="3">3 candidates</option>
          <option value="5" selected>5 candidates</option>
          <option value="8">8 candidates</option>
          <option value="10">10 candidates</option>
          <option value="15">15 candidates</option>
        </select>
      </div>
      <div class="f"><label>Additional Notes</label><input id="notes" placeholder="e.g. Must know FastAPI, Docker"/></div>
    </div>
    <button class="rbtn" id="btn" onclick="startHiring()">🚀 Start Full Hiring Flow (3 Steps)</button>
  </div>

  <div id="result">
    <div class="rc"><div class="rct">📊 A2A Flow Progress</div><div id="steps"></div></div>
    <div id="candidatesSection" style="display:none">
      <div class="rc">
        <div class="rct">👥 Candidates Found</div>
        <div id="candidatesGrid" class="cand-grid"></div>
      </div>
    </div>
    <div id="scheduleSection" style="display:none">
      <div class="rc">
        <div class="rct">📅 Interview Schedule</div>
        <div id="scheduleContent"></div>
      </div>
    </div>
    <div id="bgSection" style="display:none">
      <div class="rc">
        <div class="rct">🔎 Background Checks</div>
        <div id="bgContent"></div>
      </div>
    </div>
  </div>
</div>

<script>
const REGISTRY = '{reg}';

async function checkReg() {{
  const bar = document.getElementById('regBar');
  try {{
    const r = await fetch('/registry-status');
    const d = await r.json();
    if (d.status === 'ok' && d.registered_agents > 0) {{
      bar.className = 'sbar ok';
      bar.innerHTML = `✅ <strong>${{d.registered_agents}} agents registered.</strong>
        <a href="${{REGISTRY}}" target="_blank" style="color:var(--green);margin-left:10px;font-weight:600">→ Registry</a>
        <a href="${{REGISTRY}}/analytics" target="_blank" style="color:var(--green);margin-left:10px;font-weight:600">→ Analytics</a>`;
    }} else {{
      bar.className = 'sbar error';
      bar.innerHTML = `❌ No agents registered. <a href="${{REGISTRY}}/register" target="_blank" style="color:var(--red);margin-left:8px;font-weight:600">→ Register Agents</a>`;
    }}
  }} catch(e) {{
    bar.className = 'sbar error';
    bar.innerHTML = `❌ Registry not reachable.`;
  }}
}}
window.addEventListener('DOMContentLoaded', checkReg);

function addStep(msg) {{
  const el = document.getElementById('steps');
  const d = document.createElement('div');
  d.className = 'step' + (msg.includes('❌') || msg.includes('Error') ? ' e' : '');
  d.textContent = msg;
  el.appendChild(d);
  el.scrollTop = el.scrollHeight;
}}

async function startHiring() {{
  const btn = document.getElementById('btn');
  btn.disabled = true; btn.textContent = '⏳ Running hiring flow...';
  document.getElementById('result').style.display = 'block';
  document.getElementById('steps').innerHTML = '';
  document.getElementById('candidatesSection').style.display = 'none';
  document.getElementById('scheduleSection').style.display = 'none';
  document.getElementById('bgSection').style.display = 'none';

  try {{
    const res = await fetch('/hire', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        job_title:        document.getElementById('jt').value,
        experience_years: parseInt(document.getElementById('exp').value),
        location:         document.getElementById('loc').value,
        num_candidates:   parseInt(document.getElementById('numcands').value),
        notes:            document.getElementById('notes').value
      }})
    }});
    const data = await res.json();

    if (data.error) {{ addStep('❌ ' + data.error); }}
    (data.steps || []).forEach(s => addStep(s));

    // Show candidates
    const cands = data.candidates?.candidates || data.candidates?.result?.candidates || [];
    if (cands.length > 0) {{
      document.getElementById('candidatesSection').style.display = 'block';
      const grid = document.getElementById('candidatesGrid');
      grid.innerHTML = '';
      cands.forEach(c => {{
        const score = c.match_score || c.score || c.ai_match_score || '—';
        const scoreColor = score >= 8 ? 'var(--green)' : score >= 6 ? 'var(--amber)' : 'var(--muted)';
        grid.innerHTML += `<div class="cand-card">
          <div class="cand-name">${{c.name || c.login || 'Unknown'}}</div>
          <span class="cand-score" style="background:rgba(16,185,129,0.1);color:${{scoreColor}}">Score: ${{score}}/10</span>
          <div class="cand-detail">🔧 ${{(c.skills || c.top_skills || []).slice(0,4).join(', ') || 'N/A'}}</div>
          <div class="cand-detail">📍 ${{c.location || 'Unknown'}}</div>
          ${{c.github_url || c.html_url ? `<a href="${{c.github_url || c.html_url}}" target="_blank" class="gh-link">→ GitHub Profile</a>` : ''}}
        </div>`;
      }});
    }}

    // Show schedule
    const sched = data.schedule;
    if (sched && Object.keys(sched).length > 0) {{
      document.getElementById('scheduleSection').style.display = 'block';
      const sc = document.getElementById('scheduleContent');
      const interviews = sched.scheduled_interviews || sched.interviews || [];
      if (interviews.length > 0) {{
        sc.innerHTML = interviews.map(i => `<div style="padding:10px;border-bottom:1px solid var(--border);font-size:13px">
          <strong>${{i.candidate_name || i.name || 'Candidate'}}</strong> — Round 1
          <span style="color:var(--muted);margin-left:8px">${{i.scheduled_time || i.time || 'Time TBD'}}</span>
          ${{i.meet_link ? `<a href="https://${{i.meet_link}}" target="_blank" style="color:var(--violet);margin-left:8px;font-weight:600">→ Meet Link</a>` : ''}}
        </div>`).join('');
      }} else {{
        sc.innerHTML = `<pre style="font-size:11px;color:var(--muted);overflow-x:auto;white-space:pre-wrap">${{JSON.stringify(sched,null,2)}}</pre>`;
      }}
    }}

    // Show background checks
    const bg = data.background_checks;
    if (bg && Object.keys(bg).length > 0) {{
      document.getElementById('bgSection').style.display = 'block';
      const bgc = document.getElementById('bgContent');
      const checks = bg.verification_results || bg.results || [];
      if (checks.length > 0) {{
        bgc.innerHTML = checks.map(c => `<div style="padding:10px;border-bottom:1px solid var(--border);font-size:13px;display:flex;justify-content:space-between">
          <strong>${{c.candidate_name || c.name || 'Candidate'}}</strong>
          <span style="color:${{c.overall_status === 'PASS' || c.status === 'verified' ? 'var(--green)' : 'var(--amber)'}}">
            ${{c.overall_status || c.status || 'Checked'}}
          </span>
        </div>`).join('');
      }} else {{
        bgc.innerHTML = `<pre style="font-size:11px;color:var(--muted);overflow-x:auto;white-space:pre-wrap">${{JSON.stringify(bg,null,2)}}</pre>`;
      }}
    }}

    checkReg();
  }} catch(e) {{
    addStep('❌ Error: ' + e.message);
  }}
  btn.disabled = false; btn.textContent = '🚀 Start Full Hiring Flow (3 Steps)';
}}
</script>
</body>
</html>""")


# ── Audit logging ─────────────────────────────────────────────────────────────
import json as _json

async def _log_audit(flow_id, title, subtitle="", location="",
                     flow_type="hiring", agents_used=None,
                     result_count=0, result_data=None,
                     secondary_data=None, tertiary_data=None,
                     emails_sent_to=None, status="completed"):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{REGISTRY_URL}/registry/audit/create", json={
                "flow_id": flow_id, "flow_type": flow_type,
                "title": title, "subtitle": subtitle, "location": location
            })
            await client.post(f"{REGISTRY_URL}/registry/audit/save", json={
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
