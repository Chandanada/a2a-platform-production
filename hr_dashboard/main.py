"""
HR Ops Dashboard — A2A Client Agent
Discovers HR Ops Agent from registry and performs:
- Offer letter generation
- Contract review  
- Payroll processing
"""
import os, uuid, json, httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse

load_dotenv()
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://localhost:8000")
app = FastAPI(title="HR Ops Dashboard", version="1.0.0")


async def discover_agent(skill: str) -> dict | None:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{REGISTRY_URL}/registry/discover",
                             params={"skill": skill}, timeout=10.0)
        agents = r.json().get("agents", [])
        return agents[0] if agents else None


async def send_message(agent_url: str, text: str, data: dict = None) -> dict:
    parts = [{"text": text, "mediaType": "text/plain"}]
    if data:
        parts.append({"data": data, "mediaType": "application/json"})
    payload = {"jsonrpc": "2.0", "id": f"req-{str(uuid.uuid4())[:8]}",
               "method": "SendMessage",
               "params": {"message": {"role": "user", "messageId": str(uuid.uuid4()), "parts": parts}}}
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(agent_url, json=payload)
        return r.json()


def extract_artifact(resp: dict) -> dict:
    try:
        parts = resp["result"]["task"]["artifacts"][0]["parts"]
        return next((p["data"] for p in parts if "data" in p), {})
    except Exception:
        return {}


@app.get("/registry-status")
async def registry_status():
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{REGISTRY_URL}/registry/health", timeout=5.0)
            return r.json()
    except Exception:
        return {"status": "error", "registered_agents": 0}


@app.post("/hr-ops")
async def hr_ops(request: Request):
    body    = await request.json()
    task    = body.get("task", "generate_offer_letter")
    flow_id = str(uuid.uuid4())
    report  = {"flow_id": flow_id, "steps": [], "result": {}, "status": "in_progress", "task": task}
    def step(msg): report["steps"].append(msg)

    # Map task to skill
    skill_map = {
        "generate_offer_letter": "generate_offer_letter",
        "review_contract":       "review_contract",
        "process_payroll":       "process_payroll",
    }
    skill = skill_map.get(task, "generate_offer_letter")

    step(f"🔍 Querying registry for HR Ops Agent (skill: {skill})...")
    agent = await discover_agent(skill)
    if not agent:
        report["status"] = "failed"
        report["error"]  = "No HR Ops Agent registered. Go to localhost:8000/register to add one."
        return JSONResponse(report, status_code=404)

    url = agent["supportedInterfaces"][0]["url"]
    step(f"✅ Found: {agent['name']} at {url}")
    step("📋 Fetching Agent Card...")
    async with httpx.AsyncClient() as client:
        card = (await client.get(f"{url}/.well-known/agent-card.json", timeout=8.0)).json()
    step(f"✅ Agent Card — Skills: {[s['id'] for s in card.get('skills', [])]}")
    step(f"📤 Sending {task} request via A2A SendMessage...")
    resp   = await send_message(url, f"HR Ops task: {task}", data=body)
    result = extract_artifact(resp)
    report["result"] = result
    report["status"] = "completed"
    step("✅ HR Ops task completed!")
    return JSONResponse(report)


@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse("""<!DOCTYPE html>
<html>
<head>
  <title>HR Ops Dashboard — A2A Platform</title>
  <style>
    :root{--bg:#0a0f1e;--card:#111827;--card2:#1a2235;--border:#1e2d45;--pink:#ec4899;--pink2:#f9a8d4;--text:#e2e8f0;--muted:#64748b;--muted2:#374151;--green:#10b981;--red:#f87171;--amber:#f59e0b}
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding:32px 20px}
    .wrap{max-width:900px;margin:0 auto}
    nav{display:flex;align-items:center;justify-content:space-between;margin-bottom:28px}
    .brand{display:flex;align-items:center;gap:10px}
    .logo{width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#ec4899,#8b5cf6);display:flex;align-items:center;justify-content:center;font-size:18px}
    .brand-name{font-size:16px;font-weight:800}
    .nav-links{display:flex;gap:8px}
    .nav-links a{color:var(--pink);font-size:13px;text-decoration:none;font-weight:600;padding:6px 12px;background:rgba(236,72,153,0.08);border:1px solid rgba(236,72,153,0.2);border-radius:8px}
    h1{font-size:26px;font-weight:900;margin-bottom:4px}
    .sub{color:var(--muted);font-size:13px;margin-bottom:20px}
    .status-bar{padding:12px 16px;border-radius:10px;margin-bottom:20px;font-size:13px;font-weight:600}
    .status-bar.checking{background:rgba(236,72,153,0.08);border:1px solid rgba(236,72,153,0.2);color:var(--pink)}
    .status-bar.ok{background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);color:var(--green)}
    .status-bar.error{background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.25);color:var(--red)}

    /* Task Tabs */
    .tabs{display:flex;gap:8px;margin-bottom:20px}
    .tab-btn{flex:1;padding:12px;border-radius:10px;border:1px solid var(--border);background:var(--card);color:var(--muted);font-size:13px;font-weight:600;cursor:pointer;transition:all 0.2s;text-align:center}
    .tab-btn.active{background:rgba(236,72,153,0.12);border-color:rgba(236,72,153,0.4);color:var(--pink)}
    .tab-btn:hover{border-color:rgba(236,72,153,0.3);color:var(--text)}

    .panel{display:none}
    .panel.active{display:block}
    .card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:26px;margin-bottom:20px}
    .card-title{font-size:12px;font-weight:700;color:var(--pink);text-transform:uppercase;letter-spacing:1px;margin-bottom:16px}
    .grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
    .grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px}
    .field{display:flex;flex-direction:column;gap:5px}
    label{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px}
    input,select,textarea{background:#080c1a;border:1px solid var(--border);color:var(--text);padding:10px 12px;border-radius:8px;font-size:13px;outline:none;width:100%;font-family:inherit}
    input:focus,select:focus,textarea:focus{border-color:var(--pink)}
    textarea{resize:vertical;min-height:80px}
    select option{background:#111827}
    .run-btn{width:100%;background:linear-gradient(135deg,#ec4899,#8b5cf6);color:#fff;border:none;padding:13px;border-radius:10px;font-size:14px;font-weight:700;cursor:pointer;margin-top:8px;transition:opacity 0.2s}
    .run-btn:hover{opacity:0.88}
    .run-btn:disabled{opacity:0.4;cursor:not-allowed}

    #result{display:none}
    .res-card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:22px;margin-bottom:14px}
    .res-title{font-size:11px;font-weight:700;color:var(--pink);text-transform:uppercase;letter-spacing:1px;margin-bottom:12px}
    .step{padding:5px 0;font-size:13px;border-bottom:1px solid var(--border);color:var(--green)}
    .step:last-child{border:none}
    .step.err{color:var(--red)}
    pre{font-size:11px;color:var(--muted);overflow-x:auto;white-space:pre-wrap;background:#080c1a;border:1px solid var(--border);border-radius:8px;padding:12px;margin-top:8px;max-height:420px;overflow-y:auto}

    .result-section{background:var(--card2);border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:12px}
    .result-section h3{font-size:12px;font-weight:700;color:var(--pink2);text-transform:uppercase;margin-bottom:10px}
    .flag-item{background:#080c1a;border:1px solid var(--border);border-radius:8px;padding:10px;margin-bottom:6px}
    .flag-item.high{border-color:rgba(248,113,113,0.4)}
    .flag-item.medium{border-color:rgba(245,158,11,0.4)}
    .flag-item.low{border-color:rgba(16,185,129,0.4)}
    .flag-title{font-size:13px;font-weight:700;margin-bottom:3px}
    .flag-detail{font-size:12px;color:var(--muted)}
    .sev-badge{font-size:10px;border-radius:20px;padding:2px 8px;font-weight:600;display:inline-block;margin-left:6px}
    .sev-High{background:rgba(248,113,113,0.15);color:var(--red);border:1px solid rgba(248,113,113,0.3)}
    .sev-Medium{background:rgba(245,158,11,0.15);color:var(--amber);border:1px solid rgba(245,158,11,0.3)}
    .sev-Low{background:rgba(16,185,129,0.15);color:var(--green);border:1px solid rgba(16,185,129,0.3)}
  </style>
</head>
<body>
<div class="wrap">
  <nav>
    <div class="brand">
      <div class="logo">👔</div>
      <span class="brand-name">HR Ops Dashboard</span>
    </div>
    <div class="nav-links">
      <a href="http://localhost:8000" target="_blank">Registry</a>
      <a href="http://localhost:8003" target="_blank">Hiring</a>
      <a href="http://localhost:8007" target="_blank">Travel</a>
    </div>
  </nav>

  <h1>HR Operations</h1>
  <p class="sub">A2A Client Agent — discovers HR Ops Agent from registry and handles offer letters, contract review, and payroll.</p>

  <div id="statusBar" class="status-bar checking">⏳ Checking registry...</div>

  <!-- TABS -->
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('offer',this)">📄 Offer Letter</button>
    <button class="tab-btn" onclick="switchTab('contract',this)">⚖️ Contract Review</button>
    <button class="tab-btn" onclick="switchTab('payroll',this)">💰 Payroll</button>
  </div>

  <!-- OFFER LETTER PANEL -->
  <div id="panel-offer" class="panel active">
    <div class="card">
      <div class="card-title">📄 Generate Offer Letter</div>
      <div class="grid2">
        <div class="field"><label>Candidate Name</label><input id="o-name" value="Rajesh Kumar"/></div>
        <div class="field"><label>Role / Designation</label><input id="o-role" value="Senior Python Engineer"/></div>
      </div>
      <div class="grid3">
        <div class="field"><label>CTC (LPA)</label><input id="o-ctc" type="number" value="18"/></div>
        <div class="field"><label>Joining Date</label><input id="o-join" value="May 1, 2026"/></div>
        <div class="field"><label>Location</label><input id="o-loc" value="Bangalore, Karnataka"/></div>
      </div>
      <div class="field" style="margin-bottom:12px"><label>Company Name</label><input id="o-company" value="TechCorp India Pvt. Ltd."/></div>
      <button class="run-btn" id="btn-offer" onclick="runTask('offer')">📄 Generate Offer Letter</button>
    </div>
  </div>

  <!-- CONTRACT REVIEW PANEL -->
  <div id="panel-contract" class="panel">
    <div class="card">
      <div class="card-title">⚖️ Contract Review</div>
      <div class="grid2">
        <div class="field"><label>Contract Type</label>
          <select id="c-type">
            <option>Vendor Agreement</option><option>NDA</option>
            <option>Employment Contract</option><option>SaaS Agreement</option><option>Consultancy Agreement</option>
          </select>
        </div>
        <div class="field"><label>Vendor / Party Name</label><input id="c-vendor" value="XYZ Software Solutions Pvt. Ltd."/></div>
      </div>
      <div class="field" style="margin-bottom:12px"><label>Contract Value</label><input id="c-value" value="₹15,00,000 per year"/></div>
      <button class="run-btn" id="btn-contract" onclick="runTask('contract')">⚖️ Review Contract</button>
    </div>
  </div>

  <!-- PAYROLL PANEL -->
  <div id="panel-payroll" class="panel">
    <div class="card">
      <div class="card-title">💰 Process Payroll</div>
      <div class="field" style="margin-bottom:12px">
        <label>Payroll Month</label>
        <input id="p-month" value="April 2026"/>
      </div>
      <div class="field" style="margin-bottom:12px">
        <label>Employees (JSON format)</label>
        <textarea id="p-employees">[
  {"name": "Rajesh Kumar",  "role": "Senior Engineer",  "ctc_lpa": 18},
  {"name": "Priya Sharma",  "role": "Product Manager",  "ctc_lpa": 22},
  {"name": "Ankit Verma",   "role": "Junior Engineer",  "ctc_lpa": 8},
  {"name": "Meera Nair",    "role": "UX Designer",      "ctc_lpa": 14},
  {"name": "Rohit Agarwal", "role": "DevOps Engineer",  "ctc_lpa": 16}
]</textarea>
      </div>
      <button class="run-btn" id="btn-payroll" onclick="runTask('payroll')">💰 Process Payroll</button>
    </div>
  </div>

  <!-- RESULTS -->
  <div id="result">
    <div class="res-card">
      <div class="res-title">📊 Flow Progress</div>
      <div id="steps"></div>
    </div>
    <div class="res-card" id="resultCard" style="display:none">
      <div class="res-title" id="resultTitle">Result</div>
      <div id="resultContent"></div>
    </div>
  </div>
</div>

<script>
let currentTask = 'offer';
function switchTab(t, btn) {
  currentTask = t;
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`panel-${t}`).classList.add('active');
  btn.classList.add('active');
  document.getElementById('result').style.display = 'none';
}

async function checkRegistry() {
  const bar = document.getElementById('statusBar');
  try {
    const r = await fetch('/registry-status');
    const d = await r.json();
    if (d.status === 'ok' && d.registered_agents > 0) {
      bar.className = 'status-bar ok';
      bar.innerHTML = `✅ <strong>${d.registered_agents} agent(s) registered.</strong>
        <a href="http://localhost:8000" target="_blank" style="color:#f9a8d4;margin-left:10px;font-weight:600">→ Registry</a>`;
    } else {
      bar.className = 'status-bar error';
      bar.innerHTML = `❌ No agents registered. <a href="http://localhost:8000/register" target="_blank" style="color:#f9a8d4;margin-left:8px;font-weight:600">→ Register HR Ops Agent</a>`;
    }
  } catch(e) { bar.className = 'status-bar error'; bar.innerHTML = '❌ Registry not reachable.'; }
}
window.addEventListener('DOMContentLoaded', checkRegistry);

async function runTask(t) {
  const btns = {'offer':'btn-offer','contract':'btn-contract','payroll':'btn-payroll'};
  const btn = document.getElementById(btns[t]);
  btn.disabled = true; btn.textContent = '⏳ Running...';
  document.getElementById('result').style.display = 'block';
  document.getElementById('steps').innerHTML = '';
  document.getElementById('resultCard').style.display = 'none';

  let payload = {};
  if (t === 'offer') payload = {task:'generate_offer_letter',
    candidate_name: document.getElementById('o-name').value,
    role: document.getElementById('o-role').value,
    ctc_lpa: parseFloat(document.getElementById('o-ctc').value),
    joining_date: document.getElementById('o-join').value,
    location: document.getElementById('o-loc').value,
    company_name: document.getElementById('o-company').value};
  else if (t === 'contract') payload = {task:'review_contract',
    contract_type: document.getElementById('c-type').value,
    vendor_name: document.getElementById('c-vendor').value,
    contract_value: document.getElementById('c-value').value};
  else {
    let emps = [];
    try { emps = JSON.parse(document.getElementById('p-employees').value); } catch(e){}
    payload = {task:'process_payroll', month: document.getElementById('p-month').value, employees: emps};
  }

  try {
    const res  = await fetch('/hr-ops', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data = await res.json();
    const el   = document.getElementById('steps');
    (data.steps||[]).forEach(s => {
      const d = document.createElement('div');
      d.className = 'step' + (s.includes('❌') ? ' err' : '');
      d.textContent = s; el.appendChild(d);
    });
    if (data.error) {
      const d = document.createElement('div');
      d.className = 'step err';
      d.innerHTML = `❌ ${data.error} <a href="http://localhost:8000/register" target="_blank" style="color:#f9a8d4;margin-left:6px">→ Register HR Ops Agent</a>`;
      el.appendChild(d);
    }
    if (data.result && Object.keys(data.result).length > 0) {
      document.getElementById('resultCard').style.display = 'block';
      renderResult(t, data.result);
    }
    checkRegistry();
  } catch(e) {
    const d = document.createElement('div');
    d.className = 'step err'; d.textContent = `Error: ${e.message}`;
    document.getElementById('steps').appendChild(d);
  }
  btn.disabled = false;
  btn.textContent = t==='offer'?'📄 Generate Offer Letter':t==='contract'?'⚖️ Review Contract':'💰 Process Payroll';
}

function renderResult(t, res) {
  const titles = {offer:'📄 Offer Letter', contract:'⚖️ Contract Review', payroll:'💰 Payroll Summary'};
  document.getElementById('resultTitle').textContent = titles[t];
  const c = document.getElementById('resultContent');

  if (t === 'offer') {
    const ol = res.offer_letter || res;
    const comp = ol.compensation || {};
    c.innerHTML = `
      <div class="result-section">
        <h3>Offer Summary</h3>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
          <div><div style="font-size:11px;color:var(--muted)">Candidate</div><div style="font-weight:700">${ol.candidate_name||''}</div></div>
          <div><div style="font-size:11px;color:var(--muted)">Role</div><div style="font-weight:700">${ol.role||''}</div></div>
          <div><div style="font-size:11px;color:var(--muted)">CTC</div><div style="font-weight:700;color:#f9a8d4">₹${ol.annual_ctc_lpa||comp.annual_ctc_lpa||''} LPA</div></div>
          <div><div style="font-size:11px;color:var(--muted)">Joining</div><div style="font-weight:700">${ol.joining_date||''}</div></div>
          <div><div style="font-size:11px;color:var(--muted)">Location</div><div style="font-weight:700">${ol.location||''}</div></div>
          <div><div style="font-size:11px;color:var(--muted)">Probation</div><div style="font-weight:700">${ol.probation_period||'3 months'}</div></div>
        </div>
      </div>
      <div class="result-section">
        <h3>Benefits</h3>
        <div style="font-size:13px;color:var(--muted)">${(ol.benefits||[]).join('<br>')}</div>
      </div>
      <div class="result-section">
        <h3>Next Steps</h3>
        <div style="font-size:13px;color:var(--muted)">${(res.next_steps||[]).join('<br>')}</div>
      </div>
      <div class="result-section"><h3>Full Details (JSON)</h3><pre>${JSON.stringify(res,null,2)}</pre></div>`;
  } else if (t === 'contract') {
    const flags = res.red_flags || [];
    const missing = res.missing_clauses || [];
    c.innerHTML = `
      <div class="result-section">
        <h3>Overall Assessment</h3>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">
          <div><div style="font-size:11px;color:var(--muted)">Risk Level</div><div style="font-weight:700">${(res.review_summary||res).overall_risk||''}</div></div>
          <div><div style="font-size:11px;color:var(--muted)">Recommendation</div><div style="font-weight:700;color:#f9a8d4">${(res.review_summary||res).recommendation||''}</div></div>
          <div><div style="font-size:11px;color:var(--muted)">Red Flags</div><div style="font-weight:700;color:var(--red)">${flags.length} found</div></div>
        </div>
      </div>
      <div class="result-section">
        <h3>Red Flags Found</h3>
        ${flags.map(f=>`<div class="flag-item ${f.severity}">
          <div class="flag-title">${f.clause||''} <span class="sev-badge sev-${f.severity}">${f.severity}</span></div>
          <div class="flag-detail">${f.issue||''}</div>
          <div class="flag-detail" style="color:var(--amber);margin-top:4px">→ ${f.recommendation||''}</div>
        </div>`).join('')}
      </div>
      <div class="result-section">
        <h3>Missing Clauses</h3>
        <div style="font-size:13px;color:var(--muted)">${missing.join('<br>')}</div>
      </div>
      <div class="result-section"><h3>Full Details (JSON)</h3><pre>${JSON.stringify(res,null,2)}</pre></div>`;
  } else {
    const s = res.summary || {};
    const payslips = res.employee_payslips || [];
    c.innerHTML = `
      <div class="result-section">
        <h3>Payroll Summary — ${res.payroll_month||''}</h3>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
          <div><div style="font-size:11px;color:var(--muted)">Total Employees</div><div style="font-weight:700">${s.total_employees||payslips.length}</div></div>
          <div><div style="font-size:11px;color:var(--muted)">Total Net Payroll</div><div style="font-weight:700;color:#f9a8d4">₹${(s.total_net_payroll_inr||0).toLocaleString('en-IN')}</div></div>
          <div><div style="font-size:11px;color:var(--muted)">Total CTC</div><div style="font-weight:700">₹${(s.total_cost_to_company_inr||0).toLocaleString('en-IN')}</div></div>
        </div>
      </div>
      <div class="result-section">
        <h3>Employee Payslips</h3>
        ${payslips.map(p=>`<div style="background:#080c1a;border:1px solid var(--border);border-radius:8px;padding:10px;margin-bottom:6px;display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:8px">
          <div><div style="font-weight:700;font-size:13px">${p.name||''}</div><div style="font-size:11px;color:var(--muted)">${p.role||''}</div></div>
          <div><div style="font-size:11px;color:var(--muted)">Gross</div><div style="font-size:13px">₹${(p.monthly_gross_inr||0).toLocaleString('en-IN')}</div></div>
          <div><div style="font-size:11px;color:var(--muted)">Deductions</div><div style="font-size:13px;color:var(--red)">-₹${((p.deductions||{}).total_deductions_inr||0).toLocaleString('en-IN')}</div></div>
          <div><div style="font-size:11px;color:var(--muted)">Take Home</div><div style="font-size:13px;font-weight:700;color:#f9a8d4">₹${(p.net_take_home_inr||0).toLocaleString('en-IN')}</div></div>
        </div>`).join('')}
      </div>
      <div class="result-section"><h3>Full Details (JSON)</h3><pre>${JSON.stringify(res,null,2)}</pre></div>`;
  }
}
</script>
</body>
</html>""")


# ── Audit logging helper ──────────────────────────────────────────────────────
import httpx as _httpx_hr
import json as _json_hr

async def _log_hr_audit(flow_id, task, status="completed"):
    try:
        reg = os.getenv("REGISTRY_URL", "http://localhost:8000")
        labels = {
            "generate_offer_letter": "Offer Letter Generated",
            "review_contract":       "Contract Reviewed",
            "process_payroll":       "Payroll Processed"
        }
        async with _httpx_hr.AsyncClient(timeout=5.0) as client:
            await client.post(f"{reg}/registry/audit/create", json={
                "flow_id": flow_id, "flow_type": "hr_ops",
                "title":   labels.get(task, task),
                "subtitle": task, "location": "HR Operations"
            })
            await client.post(f"{reg}/registry/audit/save", json={
                "flow_id": flow_id, "status": status,
                "agents_used": _json_hr.dumps(["HR Ops Agent"]),
                "result_count": 1, "completed_at": "now"
            })
    except Exception as e:
        print(f"[Audit] hr log error: {e}")
