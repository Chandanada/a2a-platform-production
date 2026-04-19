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

# ── HTML Page — plain string, no f-string, use __REGISTRY__ as placeholder ────
HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
  <title>Hiring Manager — A2A Platform</title>
  <style>
    :root{--bg:#0a0f1e;--card:#111827;--card2:#1a2235;--border:#1e2d45;--violet:#a78bfa;--text:#e2e8f0;--muted:#64748b;--green:#10b981;--red:#f87171;--amber:#f59e0b}
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
    nav{background:rgba(10,15,30,0.97);border-bottom:1px solid var(--border);padding:0 32px;display:flex;align-items:center;justify-content:space-between;height:58px;position:sticky;top:0;z-index:100}
    .brand{display:flex;align-items:center;gap:10px}
    .logo{width:32px;height:32px;border-radius:10px;background:linear-gradient(135deg,#7c3aed,#ec4899);display:flex;align-items:center;justify-content:center;font-size:16px}
    .brand-name{font-size:15px;font-weight:800;color:#fff}
    .nav-badge{background:rgba(124,58,237,0.15);border:1px solid rgba(124,58,237,0.3);color:var(--violet);font-size:10px;font-weight:700;padding:2px 8px;border-radius:20px;margin-left:8px}
    .nav-links a{color:var(--muted);text-decoration:none;font-size:13px;padding:6px 14px;border-radius:8px}
    .nav-links a:hover{color:var(--text);background:rgba(124,58,237,0.1)}
    .container{max-width:960px;margin:0 auto;padding:28px 24px}
    h1{font-size:24px;font-weight:900;margin-bottom:4px}
    .sub{color:var(--muted);font-size:13px;margin-bottom:20px}
    .card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:26px;margin-bottom:20px}
    .ct{font-size:12px;font-weight:700;color:var(--violet);text-transform:uppercase;letter-spacing:1px;margin-bottom:16px}
    .g2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
    .g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:14px}
    .f{display:flex;flex-direction:column;gap:5px}
    label{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
    input,select{background:#080c1a;border:1px solid var(--border);color:var(--text);padding:10px 12px;border-radius:8px;font-size:13px;outline:none;width:100%;font-family:inherit}
    input:focus,select:focus{border-color:#7c3aed}
    select option{background:#111827}
    .rbtn{width:100%;background:linear-gradient(135deg,#7c3aed,#ec4899);color:#fff;border:none;padding:13px;border-radius:10px;font-size:14px;font-weight:700;cursor:pointer;margin-top:8px}
    .rbtn:hover{opacity:.88}.rbtn:disabled{opacity:.4;cursor:not-allowed}
    #result{display:none}
    .rc{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:22px;margin-bottom:14px}
    .rct{font-size:12px;font-weight:700;color:var(--violet);text-transform:uppercase;letter-spacing:1px;margin-bottom:12px}
    #steps{max-height:260px;overflow-y:auto}
    .step{padding:5px 0;font-size:13px;border-bottom:1px solid var(--border);color:var(--green)}
    .step.e{color:var(--red)}
    .adv-btn{width:100%;background:linear-gradient(135deg,#10b981,#059669);color:#fff;border:none;padding:11px;border-radius:8px;font-weight:700;cursor:pointer;font-size:13px;margin-top:12px}
    .bg-btn{width:100%;background:linear-gradient(135deg,#f59e0b,#d97706);color:#fff;border:none;padding:11px;border-radius:8px;font-weight:700;cursor:pointer;font-size:13px;margin-top:12px}
    .next-info{margin-top:12px;padding:12px 14px;background:rgba(124,58,237,0.08);border:1px solid rgba(124,58,237,0.25);border-radius:10px;font-size:13px;color:var(--muted)}
    /* Candidate selection */
    .cand-sel-list{margin-top:12px}
    .cand-sel-item{display:flex;align-items:center;gap:12px;padding:10px 14px;background:var(--card2);border:1px solid var(--border);border-radius:10px;margin-bottom:8px;cursor:pointer;transition:border-color .2s}
    .cand-sel-item:hover{border-color:#7c3aed}
    .cand-sel-item.selected{border-color:#10b981;background:rgba(16,185,129,0.07)}
    .cand-sel-item input[type=checkbox]{width:18px;height:18px;accent-color:#10b981;cursor:pointer;flex-shrink:0}
    .cand-sel-info{flex:1}
    .cand-sel-name{font-size:14px;font-weight:700;color:var(--text)}
    .cand-sel-meta{font-size:12px;color:var(--muted);margin-top:2px}
    .cand-sel-score{font-size:12px;font-weight:700;color:var(--green);margin-left:auto}
    .sel-count{font-size:13px;color:var(--amber);font-weight:600;margin-top:8px}
    /* Resume flows */
    .flow-card{background:var(--card2);border:1px solid var(--border);border-radius:12px;padding:16px;margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;gap:12px}
    .flow-info{flex:1}
    .flow-title{font-size:14px;font-weight:700;color:var(--text)}
    .flow-meta{font-size:12px;color:var(--muted);margin-top:3px}
    .flow-status{font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;background:rgba(245,158,11,0.15);color:var(--amber);border:1px solid rgba(245,158,11,0.3)}
    .resume-btn{background:linear-gradient(135deg,#7c3aed,#ec4899);color:#fff;border:none;padding:8px 18px;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;white-space:nowrap}
    .resume-btn:hover{opacity:.88}
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
    <a href="__REGISTRY__" target="_blank">Registry</a>
    <a href="__REGISTRY__/audit" target="_blank">Audit Logs</a>
    <a href="__REGISTRY__/analytics" target="_blank">Analytics</a>
  </div>
</nav>
<div class="container">
  <h1>🚀 Hiring Manager</h1>
  <p class="sub">A2A Client Agent — sequential hiring flow with candidate selection per round</p>

  <!-- Resume active flows -->
  <div id="resumeSection" style="display:none">
    <div class="card">
      <div class="ct">📂 Resume Active Hiring Flows</div>
      <div id="resumeList"></div>
    </div>
  </div>

  <!-- New flow form -->
  <div class="card">
    <div class="ct">🧑‍💼 Start New Hiring Flow</div>
    <div class="g2">
      <div class="f"><label>Job Title</label><input id="jt" value="Senior Python Engineer"/></div>
      <div class="f"><label>Experience (Years)</label><input id="exp" type="number" value="5" min="0" max="20"/></div>
    </div>
    <div class="g3">
      <div class="f">
        <label>Location</label>
        <select id="loc">
          <option>Remote</option><option>India (On-site)</option><option>Bangalore</option>
          <option>Mumbai</option><option>Delhi</option><option>Hyderabad</option>
          <option>Pune</option><option>USA</option><option>UK</option><option>Singapore</option><option>UAE</option>
        </select>
      </div>
      <div class="f">
        <label>No. of Candidates to Source</label>
        <select id="numcands">
          <option value="1">1</option><option value="2">2</option><option value="3">3</option>
          <option value="5" selected>5</option><option value="8">8</option><option value="10">10</option>
        </select>
      </div>
      <div class="f"><label>Additional Notes</label><input id="notes" placeholder="e.g. Must know FastAPI"/></div>
    </div>
    <button class="rbtn" id="btn" onclick="startHiring()">🚀 Start Hiring Flow (Source + Round 1)</button>
  </div>

  <div id="result">
    <div class="rc"><div class="rct">📊 A2A Flow Progress</div><div id="steps"></div></div>

    <!-- Round 1 section with candidate checkboxes -->
    <div id="round1Section" style="display:none">
      <div class="rc">
        <div class="rct">📅 Round 1 — HR Screening</div>
        <div id="round1Content"></div>
        <div class="next-info" style="margin-top:14px">
          ✅ Check which candidates <strong>cleared</strong> Round 1, then schedule Round 2 for them only:
        </div>
        <div class="cand-sel-list" id="round1CandList"></div>
        <div class="sel-count" id="round1SelCount"></div>
        <button class="adv-btn" onclick="advanceRound(2)">Schedule Round 2 (Technical) for Selected Candidates →</button>
      </div>
    </div>

    <!-- Round 2 section with candidate checkboxes -->
    <div id="round2Section" style="display:none">
      <div class="rc">
        <div class="rct">💻 Round 2 — Technical Interview</div>
        <div id="round2Content"></div>
        <div class="next-info" style="margin-top:14px">
          ✅ Check which candidates <strong>cleared</strong> Round 2, then schedule Round 3 for them only:
        </div>
        <div class="cand-sel-list" id="round2CandList"></div>
        <div class="sel-count" id="round2SelCount"></div>
        <button class="adv-btn" onclick="advanceRound(3)">Schedule Round 3 (Final Round) for Selected Candidates →</button>
      </div>
    </div>

    <!-- Round 3 section with candidate checkboxes -->
    <div id="round3Section" style="display:none">
      <div class="rc">
        <div class="rct">🏁 Round 3 — Final Round</div>
        <div id="round3Content"></div>
        <div class="next-info" style="margin-top:14px">
          ✅ Check which candidates <strong>cleared</strong> the Final Round, then run background verification:
        </div>
        <div class="cand-sel-list" id="round3CandList"></div>
        <div class="sel-count" id="round3SelCount"></div>
        <button class="bg-btn" onclick="runBgCheck()">Run Background Verification for Selected Candidates →</button>
      </div>
    </div>

    <!-- Background check results -->
    <div id="bgSection" style="display:none">
      <div class="rc"><div class="rct">🔎 Background Verification</div><div id="bgContent"></div></div>
    </div>
  </div>
</div>

<script>
var REGISTRY = '__REGISTRY__';
var _flowData = {};          // current session flow
var _currentRoundCands = {}; // candidates shown in each round's checkbox list

// ── On load: check registry + load resume flows ─────────────────────────────
window.addEventListener('DOMContentLoaded', function() {
  loadActiveFlows();
});

function loadActiveFlows() {
  fetch('/active-flows').then(function(r){ return r.json(); }).then(function(d){
    var flows = d.flows || [];
    if (flows.length === 0) return;
    var sec = document.getElementById('resumeSection');
    var list = document.getElementById('resumeList');
    sec.style.display = 'block';
    var statusLabel = {
      'awaiting_round_1': 'Round 1 — Awaiting Candidate Selection',
      'awaiting_round_2': 'Round 2 — Awaiting Candidate Selection',
      'awaiting_round_3': 'Round 3 — Awaiting Candidate Selection',
      'awaiting_bg_check':'All Rounds Done — Background Check Pending',
      'in_progress':       'In Progress'
    };
    list.innerHTML = flows.map(function(f) {
      return '<div class="flow-card">' +
        '<div class="flow-info">' +
          '<div class="flow-title">' + (f.title||'Untitled') + ' — ' + (f.location||'Remote') + '</div>' +
          '<div class="flow-meta">Started: ' + (f.started_at||'') + ' &nbsp;|&nbsp; ' + (f.total_cands||0) + ' candidates sourced</div>' +
        '</div>' +
        '<span class="flow-status">' + (statusLabel[f.status] || f.status) + '</span>' +
        '<button class="resume-btn" onclick="resumeFlow(\'' + f.flow_id + '\')">Resume →</button>' +
      '</div>';
    }).join('');
  }).catch(function(){});
}

async function resumeFlow(flowId) {
  var r = await fetch('/flow-state/' + flowId);
  var state = await r.json();
  if (!state.found) { alert('Could not load flow state.'); return; }

  // Restore _flowData
  _flowData = {
    flow_id:    state.flow_id,
    request:    { job_title: state.title, location: state.location },
    candidates: { candidates: state.candidates },
    status:     state.status,
    schedule:   {}
  };

  document.getElementById('result').style.display = 'block';
  document.getElementById('steps').innerHTML = '';
  addStep('📂 Resuming flow: ' + state.title + ' (' + state.started_at + ')');
  addStep('👥 ' + state.candidates.length + ' candidates loaded from previous session');

  var currentRound = state.current_round || 1;
  var statusMap = { 'awaiting_round_2': 2, 'awaiting_round_3': 3, 'awaiting_bg_check': 4 };
  var nextRound = statusMap[state.status] || 1;

  // Show the appropriate round section with candidate selection
  if (nextRound === 1) {
    show('round1Section');
    renderCandidateCheckboxes(state.candidates, 1, []);
    addStep('⏳ Select which candidates cleared Round 1 and schedule Round 2.');
  } else if (nextRound === 2) {
    var cleared = state.cleared_candidates || [];
    addStep('✅ Round 1 cleared by: ' + cleared.map(function(c){ return c.name||c.login; }).join(', '));
    show('round2Section');
    renderCandidateCheckboxes(cleared, 2, []);
    addStep('⏳ Select which candidates cleared Round 2 and schedule Round 3.');
  } else if (nextRound === 3) {
    var cleared = state.cleared_candidates || [];
    show('round3Section');
    renderCandidateCheckboxes(cleared, 3, []);
    addStep('⏳ Select which candidates cleared Round 3 and run background check.');
  } else if (nextRound === 4) {
    var cleared = state.cleared_candidates || [];
    show('round3Section');
    renderCandidateCheckboxes(cleared, 3, cleared);
    addStep('⏳ All rounds complete. Run background verification for cleared candidates.');
  }
}

function addStep(msg) {
  var el = document.getElementById('steps');
  var d = document.createElement('div');
  d.className = msg.indexOf('❌') >= 0 ? 'step e' : 'step';
  d.textContent = msg;
  el.appendChild(d);
  el.scrollTop = el.scrollHeight;
}

function show(id) { var e = document.getElementById(id); if(e) e.style.display='block'; }
function hide(id) { var e = document.getElementById(id); if(e) e.style.display='none'; }

function renderSchedule(sched, containerId) {
  var el = document.getElementById(containerId);
  if (!sched || !sched.schedules) { el.innerHTML = ''; return; }
  el.innerHTML = sched.schedules.map(function(s) {
    var r = (s.interview_rounds || [])[0] || {};
    return '<div style="padding:10px 14px;border-bottom:1px solid var(--border);font-size:13px">' +
      '<strong>' + (s.candidate_name||'Candidate') + '</strong><br/>' +
      '<span style="color:var(--muted);font-size:12px">📅 ' + (r.date||'TBD') + ' at ' + (r.time||'TBD') +
      ' &nbsp;|&nbsp; 👤 ' + (r.interviewer||'') + '</span></div>';
  }).join('');
}

function renderCandidateCheckboxes(candidates, roundNum, preSelected) {
  var listId = 'round' + roundNum + 'CandList';
  var countId = 'round' + roundNum + 'SelCount';
  _currentRoundCands[roundNum] = candidates;
  var preIds = (preSelected || []).map(function(c){ return c.github_login || c.login || c.name; });
  var html = candidates.map(function(c) {
    var id = c.github_login || c.login || c.name || 'cand';
    var checked = preIds.length === 0 || preIds.indexOf(id) >= 0;  // default all checked, or pre-selected
    var score = c.match_score || c.score || '?';
    var col = score >= 8 ? 'var(--green)' : score >= 6 ? 'var(--amber)' : 'var(--muted)';
    return '<div class="cand-sel-item' + (checked ? ' selected' : '') + '" onclick="toggleCand(this)">' +
      '<input type="checkbox" data-id="' + id + '" data-round="' + roundNum + '" ' + (checked?'checked':'') + ' onclick="event.stopPropagation();toggleCand(this.parentElement)"/>' +
      '<div class="cand-sel-info">' +
        '<div class="cand-sel-name">' + (c.name || c.login || id) + '</div>' +
        '<div class="cand-sel-meta">📍 ' + (c.location||'Unknown') + (c.github_url ? ' &nbsp;·&nbsp; <a href="'+c.github_url+'" target="_blank" style="color:var(--violet)">GitHub</a>' : '') + '</div>' +
      '</div>' +
      '<span class="cand-sel-score" style="color:' + col + '">Score: ' + score + '/10</span>' +
    '</div>';
  }).join('');
  document.getElementById(listId).innerHTML = html;
  updateSelCount(roundNum);
}

function toggleCand(item) {
  var cb = item.querySelector('input[type=checkbox]');
  cb.checked = !cb.checked;
  item.className = 'cand-sel-item' + (cb.checked ? ' selected' : '');
  updateSelCount(parseInt(cb.dataset.round));
}

function updateSelCount(roundNum) {
  var cbs = document.querySelectorAll('#round' + roundNum + 'CandList input[type=checkbox]');
  var sel = Array.from(cbs).filter(function(cb){ return cb.checked; }).length;
  var el = document.getElementById('round' + roundNum + 'SelCount');
  el.textContent = sel + ' of ' + cbs.length + ' candidates selected for next round';
}

function getSelectedCandidates(roundNum) {
  var cbs = document.querySelectorAll('#round' + roundNum + 'CandList input[type=checkbox]');
  var allCands = _currentRoundCands[roundNum] || [];
  var selIds = Array.from(cbs).filter(function(cb){ return cb.checked; }).map(function(cb){ return cb.dataset.id; });
  return allCands.filter(function(c) {
    var id = c.github_login || c.login || c.name || 'cand';
    return selIds.indexOf(id) >= 0;
  });
}

// ── Start new hiring flow ───────────────────────────────────────────────────
function startHiring() {
  var btn = document.getElementById('btn');
  btn.disabled = true; btn.textContent = '⏳ Sourcing + Scheduling Round 1...';
  show('result');
  document.getElementById('steps').innerHTML = '';
  ['round1Section','round2Section','round3Section','bgSection'].forEach(hide);

  fetch('/hire', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      job_title:        document.getElementById('jt').value,
      experience_years: parseInt(document.getElementById('exp').value) || 3,
      location:         document.getElementById('loc').value,
      num_candidates:   parseInt(document.getElementById('numcands').value) || 5,
      notes:            document.getElementById('notes').value
    })
  })
  .then(function(r){ return r.json(); })
  .then(function(data) {
    _flowData = data;
    (data.steps || []).forEach(addStep);

    var allCands = (data.candidates && data.candidates.candidates) ? data.candidates.candidates : [];

    // Show Round 1 section with candidate checkboxes — always
    show('round1Section');
    renderSchedule(data.schedule, 'round1Content');
    renderCandidateCheckboxes(allCands, 1, []);  // default all checked
    document.getElementById('round1Section').scrollIntoView({behavior:'smooth'});

    loadActiveFlows();  // refresh resume list
  })
  .catch(function(e){ addStep('❌ Error: ' + e.message); })
  .finally(function(){ btn.disabled=false; btn.textContent='🚀 Start Hiring Flow (Source + Round 1)'; });
}

// ── Advance to next round with ONLY selected candidates ──────────────────────
function advanceRound(toRound) {
  var fromRound = toRound - 1;
  var selected  = getSelectedCandidates(fromRound);
  if (selected.length === 0) { alert('Please select at least one candidate who cleared Round ' + fromRound); return; }

  var role   = (_flowData.request && _flowData.request.job_title) ? _flowData.request.job_title : 'Software Engineer';
  var flowId = _flowData.flow_id || '';
  var btn    = event.target;
  btn.disabled = true; btn.textContent = '⏳ Scheduling Round ' + toRound + ' for ' + selected.length + ' candidate(s)...';

  addStep('✅ ' + selected.length + ' candidate(s) cleared Round ' + fromRound + ': ' +
    selected.map(function(c){ return c.name||c.login||'?'; }).join(', '));
  addStep('📤 Scheduling Round ' + toRound + '...');

  // Save cleared candidates to persistent state
  fetch('/save-flow-state', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ flow_id: flowId, cleared_candidates: selected, current_round: fromRound })
  }).catch(function(){});

  fetch('/schedule-round', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ round_number: toRound, candidates: selected, role: role, flow_id: flowId })
  })
  .then(function(r){ return r.json(); })
  .then(function(data) {
    (data.steps || []).forEach(addStep);
    if (!data.success) { addStep('❌ ' + (data.error||'Failed')); btn.disabled=false; btn.textContent='Retry'; return; }

    var sec = 'round' + toRound + 'Section';
    show(sec);
    renderSchedule(data.schedule, 'round' + toRound + 'Content');
    renderCandidateCheckboxes(selected, toRound, []);  // show only cleared candidates
    document.getElementById(sec).scrollIntoView({behavior:'smooth'});

    btn.textContent = '✅ Done — Round ' + toRound + ' scheduled';
    btn.style.background = '#374151'; btn.style.cursor = 'not-allowed';
  })
  .catch(function(e){ addStep('❌ ' + e.message); btn.disabled=false; });
}

// ── Run background check on ONLY selected final-round candidates ─────────────
function runBgCheck() {
  var selected = getSelectedCandidates(3);
  if (selected.length === 0) { alert('Please select at least one candidate who cleared Round 3'); return; }

  var role   = (_flowData.request && _flowData.request.job_title) ? _flowData.request.job_title : 'Software Engineer';
  var flowId = _flowData.flow_id || '';
  var btn    = event.target;
  btn.disabled = true; btn.textContent = '⏳ Running background checks for ' + selected.length + ' candidate(s)...';

  addStep('✅ ' + selected.length + ' candidate(s) cleared Round 3: ' +
    selected.map(function(c){ return c.name||c.login||'?'; }).join(', '));
  addStep('🔍 Running background verification...');

  fetch('/save-flow-state', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ flow_id: flowId, cleared_candidates: selected, current_round: 3 })
  }).catch(function(){});

  fetch('/run-background-check', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ candidates: selected, role: role, flow_id: flowId })
  })
  .then(function(r){ return r.json(); })
  .then(function(data) {
    (data.steps || []).forEach(addStep);
    if (!data.success) { addStep('❌ ' + (data.error||'Failed')); btn.disabled=false; return; }
    show('bgSection');
    var checks = (data.background_checks && (data.background_checks.results || data.background_checks.verification_results)) || [];
    document.getElementById('bgContent').innerHTML = checks.length > 0
      ? checks.map(function(c) {
          var pass = c.overall_status==='PASS' || c.status==='verified';
          return '<div style="padding:10px 14px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;font-size:13px">' +
            '<strong>' + (c.candidate_name||c.name||'Candidate') + '</strong>' +
            '<span style="color:' + (pass?'var(--green)':'var(--amber)') + '">' + (c.overall_status||c.status||'Checked') + '</span></div>';
        }).join('')
      : '<pre style="font-size:11px;color:var(--muted);white-space:pre-wrap">' + JSON.stringify(data.background_checks,null,2) + '</pre>';
    document.getElementById('bgSection').scrollIntoView({behavior:'smooth'});
    addStep('🎉 Pipeline complete! Source → R1 → R2 → R3 → Background Check done!');
    btn.textContent='✅ Done'; btn.style.background='#374151'; btn.style.cursor='not-allowed';
  })
  .catch(function(e){ addStep('❌ ' + e.message); btn.disabled=false; });
}
</script>
</body>
</html>"""


async def discover_agent(skill: str) -> dict | None:
    """Curated Registry discovery — A2A spec strategy 2"""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{REGISTRY_URL}/registry/discover", params={"skill": skill}, timeout=10.0)
            agents = r.json().get("agents", [])
            return agents[0] if agents else None
    except Exception as e:
        print(f"[discover_agent] failed for skill={skill}: {e}")
        return None


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
  try:
    body           = await request.json()
    job_title      = body.get("job_title", "Software Engineer")
    experience     = body.get("experience_years", 3)
    location       = body.get("location", "Remote")
    notes          = body.get("notes", "")
    num_candidates = body.get("num_candidates", 5)
    flow_id        = str(uuid.uuid4())

    report = {"request": body, "steps": [], "candidates": {}, "schedule": {}, "background_checks": {}, "status": "in_progress", "flow_id": flow_id}
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

    # STEP 2: Schedule Round 1 — with Render wake-up ping + retry
    step("🔍 Step 3: Querying registry for Interview Scheduler Agent...")
    sched_agent = await discover_agent("schedule_interview")
    schedule = {}
    scheduler_ok = False
    if not sched_agent:
        step("⚠️ No scheduler agent found in registry")
    else:
        surl = sched_agent["supportedInterfaces"][0]["url"]
        step(f"✅ Found: {sched_agent['name']} at {surl}")
        # Wake up Render — free tier sleeps and returns 502 on cold start
        step("🔔 Waking up scheduler (Render cold start may take 30s)...")
        import asyncio
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=35.0) as client:
                    ping = await client.get(f"{surl}/health")
                    if ping.status_code < 500:
                        step("✅ Scheduler is awake — proceeding")
                        break
                    if attempt < 2:
                        step(f"⏳ Still starting up, waiting 15s (attempt {attempt+1}/3)...")
                        await asyncio.sleep(15)
            except Exception:
                if attempt < 2:
                    await asyncio.sleep(15)
        step("📤 Step 4: Scheduling Round 1 (HR Screening) via A2A SendMessage...")
        try:
            sched_data = {**cands, "job_title": job_title, "location": location, "round_number": 1}
            sresp = await send_message(surl,
                f"Schedule Round 1 HR Screening interviews for {job_title} candidates.",
                data=sched_data, timeout=120.0)
            if sresp.get("error") and "result" not in sresp:
                step(f"⚠️ Scheduler error: {sresp.get('error','')[:100]}")
            else:
                schedule = extract_artifact(sresp)
                report["schedule"] = schedule
                num_sched = len(schedule.get("schedules", []))
                email_note = schedule.get("email_notifications", [])
                email_sent = any(e.get("success") for e in email_note)
                scheduler_ok = True
                step(f"✅ Round 1 (HR Screening) scheduled for {num_sched} candidate(s)")
                step("📧 Round 1 email sent to HR team — check inbox" if email_sent else "⚠️ Email not sent — check GMAIL_SENDER / GMAIL_APP_PASS on Render")
        except Exception as e:
            step(f"⚠️ Scheduler error: {str(e)[:120]}")

    report["status"] = "awaiting_round_1"
    report["scheduler_ok"] = scheduler_ok

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
                "flow_id": flow_id, "status": "in_progress",
                "agents_used": _json.dumps(["Sourcing Agent", "Scheduler Agent (Round 1)"]),
                "result_count": num_found,
                "result_data": _json.dumps(cands),
                "secondary_data": _json.dumps(schedule),
            })
    except Exception as e:
        print(f"Audit log error: {e}")

    return JSONResponse(report)

  except Exception as e:
    return JSONResponse({"steps": [f"❌ Server error: {str(e)}"], "status": "failed",
                         "candidates": {}, "schedule": {}, "background_checks": {}}, status_code=200)


@app.post("/schedule-round")
async def schedule_round(request: Request):
    """Advance to the next interview round — called by HR after clearing previous round."""
    body         = await request.json()
    round_number = int(body.get("round_number", 2))
    candidates   = body.get("candidates", [])
    role         = body.get("role", "Software Engineer")
    flow_id      = body.get("flow_id", str(uuid.uuid4()))

    steps = []
    def step(msg): steps.append(msg)

    round_names = {1: "HR Screening", 2: "Technical Interview", 3: "Final Round"}
    round_name  = round_names.get(round_number, f"Round {round_number}")

    step(f"🔍 Querying registry for Interview Scheduler Agent...")
    sched_agent = await discover_agent("schedule_interview")
    if not sched_agent:
        return JSONResponse({"success": False, "steps": steps, "error": "No scheduler agent found"})

    surl = sched_agent["supportedInterfaces"][0]["url"]
    step(f"✅ Found scheduler: {surl}")
    step(f"📤 Scheduling Round {round_number} ({round_name})...")

    try:
        data = {"candidates": candidates, "role": role, "round_number": round_number}
        sresp = await send_message(
            surl,
            f"Schedule Round {round_number} {round_name} interviews for {role} candidates.",
            data=data,
            timeout=120.0
        )
        if sresp.get("error") and "result" not in sresp:
            return JSONResponse({"success": False, "steps": steps, "error": sresp.get("error", "")})

        schedule = extract_artifact(sresp)
        email_note = schedule.get("email_notifications", [])
        email_sent = any(e.get("success") for e in email_note)
        step(f"✅ Round {round_number} ({round_name}) scheduled for {len(schedule.get('schedules',[]))} candidate(s)")
        if email_sent:
            step(f"📧 Round {round_number} notification sent to HR team")

        # Update audit
        try:
            import json as _json
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(f"{REGISTRY_URL}/registry/audit/save", json={
                    "flow_id": flow_id,
                    "status": "in_progress" if round_number < 3 else "rounds_complete",
                    "secondary_data": _json.dumps(schedule),
                })
        except Exception:
            pass

        return JSONResponse({
            "success": True,
            "steps": steps,
            "schedule": schedule,
            "round_number": round_number,
            "next_round": round_number + 1 if round_number < 3 else None,
            "flow_complete": round_number == 3
        })
    except Exception as e:
        return JSONResponse({"success": False, "steps": steps, "error": str(e)})


@app.post("/run-background-check")
async def run_background_check(request: Request):
    """Run background verification — only called after all 3 interview rounds are cleared."""
    body       = await request.json()
    candidates = body.get("candidates", [])
    role       = body.get("role", "Software Engineer")
    flow_id    = body.get("flow_id", str(uuid.uuid4()))

    steps = []
    def step(msg): steps.append(msg)

    step("🔍 Querying registry for Background Check Agent...")
    bg_agent = await discover_agent("verify_candidate")
    if not bg_agent:
        return JSONResponse({"success": False, "steps": steps, "error": "No background check agent found"})

    bgurl = bg_agent["supportedInterfaces"][0]["url"]
    step(f"✅ Found: {bg_agent['name']} at {bgurl}")
    step(f"📤 Running background checks for {len(candidates)} candidate(s) who cleared all 3 rounds...")

    try:
        data   = {"candidates": candidates, "job_title": role}
        bgresp = await send_message(bgurl, f"Run background checks for {role} candidates who cleared all interview rounds.", data=data, timeout=120.0)
        checks = extract_artifact(bgresp)
        passed = sum(1 for c in checks.get("results", []) if c.get("overall_status") == "PASS")
        step(f"✅ Background checks complete — {passed}/{len(candidates)} cleared")

        # Final audit update
        try:
            import json as _json
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(f"{REGISTRY_URL}/registry/audit/save", json={
                    "flow_id": flow_id,
                    "status": "completed",
                    "tertiary_data": _json.dumps(checks),
                    "completed_at": "now",
                    "agents_used": _json.dumps(["Sourcing Agent", "Scheduler Agent", "Background Agent"])
                })
        except Exception:
            pass

        return JSONResponse({"success": True, "steps": steps, "background_checks": checks, "passed": passed})
    except Exception as e:
        return JSONResponse({"success": False, "steps": steps, "error": str(e)})



@app.get("/registry-status")
async def registry_status():
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{REGISTRY_URL}/registry/health", timeout=5.0)
            return r.json()
    except Exception:
        return {"status": "error", "registered_agents": 0}


@app.get("/active-flows")
async def get_active_flows():
    """Return all in-progress hiring flows so HR can resume from any session."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{REGISTRY_URL}/registry/audit", params={"flow_type": "hiring", "limit": 20})
            logs = r.json().get("logs", [])
            active = []
            for log in logs:
                if log.get("status") in ("in_progress", "awaiting_round_1", "awaiting_round_2",
                                          "awaiting_round_3", "rounds_complete"):
                    # Parse stored flow state
                    cands = []
                    try:
                        import json as _j
                        rd = log.get("result_data")
                        if isinstance(rd, str): rd = _j.loads(rd)
                        if isinstance(rd, dict): cands = rd.get("candidates", [])
                    except Exception: pass
                    active.append({
                        "flow_id":     log.get("flow_id"),
                        "title":       log.get("title"),
                        "subtitle":    log.get("subtitle"),
                        "location":    log.get("location"),
                        "status":      log.get("status"),
                        "started_at":  log.get("started_at", "")[:10],
                        "candidates":  cands,
                        "total_cands": len(cands),
                    })
            return {"flows": active}
    except Exception as e:
        return {"flows": [], "error": str(e)}


@app.post("/save-flow-state")
async def save_flow_state(request: Request):
    """Save which candidates cleared a round so HR can resume later."""
    import json as _j
    body            = await request.json()
    flow_id         = body.get("flow_id")
    cleared_cands   = body.get("cleared_candidates", [])
    current_round   = body.get("current_round", 1)
    status          = f"awaiting_round_{current_round + 1}" if current_round < 3 else "awaiting_bg_check"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{REGISTRY_URL}/registry/audit/save", json={
                "flow_id":   flow_id,
                "status":    status,
                "extra_data": _j.dumps({"cleared_candidates": cleared_cands, "current_round": current_round})
            })
        return {"success": True, "status": status, "cleared": len(cleared_cands)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/flow-state/{flow_id}")
async def get_flow_state(flow_id: str):
    """Get stored state for a specific flow — used when HR resumes after days."""
    import json as _j
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{REGISTRY_URL}/registry/audit", params={"flow_type": "hiring", "limit": 50})
            logs = r.json().get("logs", [])
            log = next((l for l in logs if l.get("flow_id") == flow_id), None)
            if not log:
                return {"found": False}
            # Parse stored data
            cands, extra = [], {}
            try:
                rd = log.get("result_data")
                if isinstance(rd, str): rd = _j.loads(rd)
                if isinstance(rd, dict): cands = rd.get("candidates", [])
            except Exception: pass
            try:
                ed = log.get("extra_data")
                if isinstance(ed, str): extra = _j.loads(ed)
            except Exception: pass
            return {
                "found":       True,
                "flow_id":     flow_id,
                "title":       log.get("title"),
                "location":    log.get("location"),
                "status":      log.get("status"),
                "started_at":  log.get("started_at", "")[:10],
                "candidates":  cands,
                "cleared_candidates": extra.get("cleared_candidates", []),
                "current_round":      extra.get("current_round", 1),
            }
    except Exception as e:
        return {"found": False, "error": str(e)}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return HTMLResponse(HTML_PAGE.replace("__REGISTRY__", REGISTRY_URL))



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
