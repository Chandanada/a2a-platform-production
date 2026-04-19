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
    .sbar{padding:12px 16px;border-radius:10px;margin-bottom:20px;font-size:13px;font-weight:600}
    .sbar.ok{background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);color:var(--green)}
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
    .cand-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin-top:12px}
    .cand-card{background:var(--card2);border:1px solid var(--border);border-radius:12px;padding:16px}
    .cand-name{font-size:14px;font-weight:700;margin-bottom:4px}
    .cand-score{display:inline-block;background:rgba(16,185,129,0.1);color:var(--green);border:1px solid rgba(16,185,129,0.25);border-radius:20px;padding:2px 10px;font-size:11px;font-weight:700;margin-bottom:8px}
    .cand-detail{font-size:12px;color:var(--muted);margin-bottom:3px}
    a.gh-link{color:var(--violet);text-decoration:none;font-size:12px;font-weight:600}
    .cand-check-list{margin-top:12px}
    .cand-check-item{display:flex;align-items:center;gap:12px;padding:10px 14px;background:var(--card2);border:2px solid var(--border);border-radius:10px;margin-bottom:8px;cursor:pointer;transition:border-color .15s}
    .cand-check-item:hover{border-color:#7c3aed}
    .cand-check-item.selected{border-color:var(--green);background:rgba(16,185,129,0.05)}
    .cand-check-item input[type=checkbox]{width:18px;height:18px;accent-color:var(--green);cursor:pointer;flex-shrink:0}
    .cand-check-info{flex:1}
    .cand-check-name{font-size:14px;font-weight:700}
    .cand-check-meta{font-size:12px;color:var(--muted);margin-top:2px}
    .sel-count{font-size:12px;color:var(--amber);font-weight:600;margin-top:8px}
    .resume-card{background:var(--card2);border:1px solid var(--border);border-radius:12px;padding:16px;margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
    .resume-info{flex:1;min-width:200px}
    .resume-title{font-size:14px;font-weight:700}
    .resume-meta{font-size:12px;color:var(--muted);margin-top:3px}
    .resume-status{font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;background:rgba(245,158,11,0.12);color:var(--amber);border:1px solid rgba(245,158,11,0.3);white-space:nowrap}
    .resume-btn{background:linear-gradient(135deg,#7c3aed,#ec4899);color:#fff;border:none;padding:8px 18px;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer}
  </style>
</head>
<body>
<nav>
  <div class="brand"><div class="logo">\U0001f916</div><span class="brand-name">Hiring Manager</span><span class="nav-badge">Google A2A Protocol</span></div>
  <div class="nav-links" style="display:flex;gap:2px">
    <a href="__REGISTRY__" target="_blank">Registry</a>
    <a href="__REGISTRY__/audit" target="_blank">Audit Logs</a>
    <a href="__REGISTRY__/analytics" target="_blank">Analytics</a>
  </div>
</nav>
<div class="container">
  <h1>Hiring Manager</h1>
  <p class="sub">A2A Client Agent — sequential hiring with candidate selection per round. Resume flows anytime.</p>
  <div id="regBar" class="sbar" style="display:none"></div>
  <div id="resumeSection" style="display:none">
    <div class="card">
      <div class="ct">Resume Active Hiring Flows</div>
      <p style="font-size:12px;color:var(--muted);margin-bottom:12px">Click Resume to continue where you left off — select who cleared each round.</p>
      <div id="resumeList"></div>
    </div>
  </div>
  <div class="card">
    <div class="ct">Start New Hiring Flow</div>
    <div class="g2">
      <div class="f"><label>Job Title</label><input id="jt" value="Senior Python Engineer"/></div>
      <div class="f"><label>Experience (Years)</label><input id="exp" type="number" value="5" min="0" max="20"/></div>
    </div>
    <div class="g3">
      <div class="f"><label>Location</label><select id="loc"><option>Remote</option><option>India (On-site)</option><option>Bangalore</option><option>Mumbai</option><option>Delhi</option><option>Hyderabad</option><option>Pune</option><option>USA</option><option>UK</option><option>Singapore</option><option>UAE</option></select></div>
      <div class="f"><label>No. of Candidates</label><select id="numcands"><option value="1">1 candidate</option><option value="2">2 candidates</option><option value="3">3 candidates</option><option value="5" selected>5 candidates</option><option value="8">8 candidates</option><option value="10">10 candidates</option></select></div>
      <div class="f"><label>Additional Notes</label><input id="notes" placeholder="e.g. Must know FastAPI, Docker"/></div>
    </div>
    <button class="rbtn" id="btn" onclick="startHiring()">Start Hiring Flow (Source + Round 1)</button>
  </div>
  <div id="result">
    <div class="rc"><div class="rct">A2A Flow Progress</div><div id="steps"></div></div>
    <div id="candidatesSection" style="display:none">
      <div class="rc"><div class="rct">Candidates Found</div><div id="candidatesGrid" class="cand-grid"></div></div>
    </div>
    <div id="round1Section" style="display:none">
      <div class="rc">
        <div class="rct">Round 1 — HR Screening</div>
        <div id="round1Content"></div>
        <div class="next-info">Round 1 email sent to HR. After interviews, <strong>check only candidates who cleared Round 1</strong>, then schedule Round 2 for them only:</div>
        <div class="cand-check-list" id="round1CheckList"></div>
        <div class="sel-count" id="round1SelCount"></div>
        <button class="adv-btn" id="round1Btn" onclick="advanceRound(2)">Schedule Round 2 (Technical) for Selected Candidates</button>
      </div>
    </div>
    <div id="round2Section" style="display:none">
      <div class="rc">
        <div class="rct">Round 2 — Technical Interview</div>
        <div id="round2Content"></div>
        <div class="next-info">Round 2 email sent. <strong>Check only candidates who cleared Round 2</strong>, then schedule Round 3:</div>
        <div class="cand-check-list" id="round2CheckList"></div>
        <div class="sel-count" id="round2SelCount"></div>
        <button class="adv-btn" id="round2Btn" onclick="advanceRound(3)">Schedule Round 3 (Final Round) for Selected Candidates</button>
      </div>
    </div>
    <div id="round3Section" style="display:none">
      <div class="rc">
        <div class="rct">Round 3 — Final Round</div>
        <div id="round3Content"></div>
        <div class="next-info">Round 3 email sent. <strong>Check only candidates who cleared Round 3</strong>, then run background verification:</div>
        <div class="cand-check-list" id="round3CheckList"></div>
        <div class="sel-count" id="round3SelCount"></div>
        <button class="bg-btn" id="round3Btn" onclick="runBgCheck()">Run Background Verification for Selected Candidates</button>
      </div>
    </div>
    <div id="bgSection" style="display:none">
      <div class="rc"><div class="rct">Background Verification</div><div id="bgContent"></div></div>
    </div>
  </div>
</div>
<script>
var REGISTRY = '__REGISTRY__';
var _flowData = {};
var _currentRoundCands = {};

window.addEventListener('DOMContentLoaded', function() {
  loadActiveFlows();
  fetch('/registry-status').then(function(r){return r.json();}).then(function(d){
    if (d.status==='ok' && d.registered_agents>0) {
      var bar=document.getElementById('regBar');
      bar.style.display='block'; bar.className='sbar ok';
      bar.innerHTML='Connected: '+d.registered_agents+' agents registered. <a href="'+REGISTRY+'" target="_blank" style="color:var(--green);margin-left:8px">Registry</a>';
    }
  }).catch(function(){});
});

function loadActiveFlows() {
  fetch('/active-flows').then(function(r){return r.json();}).then(function(d){
    var flows=d.flows||[];
    if (!flows.length) return;
    var lbl={'in_progress':'Waiting: select Round 1 cleared candidates','awaiting_round_2':'Waiting: select Round 2 cleared candidates','awaiting_round_3':'Waiting: select Round 3 cleared candidates','awaiting_bg_check':'Background check pending'};
    document.getElementById('resumeSection').style.display='block';
    document.getElementById('resumeList').innerHTML=flows.map(function(f){
      return '<div class="resume-card"><div class="resume-info"><div class="resume-title">'+(f.title||'Hiring Flow')+(f.location?' — '+f.location:'')+'</div><div class="resume-meta">Started: '+(f.started_at||'')+' &nbsp;·&nbsp; '+(f.all_candidates||[]).length+' candidates sourced</div></div><span class="resume-status">'+(lbl[f.status]||f.status)+'</span><button class="resume-btn" onclick="resumeFlow(''+f.flow_id+'')">Resume</button></div>';
    }).join('');
  }).catch(function(){});
}

function addStep(msg) {
  var el=document.getElementById('steps'),d=document.createElement('div');
  d.className=msg.indexOf('\u274c')>=0||msg.indexOf('Error')>=0?'step e':'step';
  d.textContent=msg; el.appendChild(d); el.scrollTop=el.scrollHeight;
}
function show(id){var e=document.getElementById(id);if(e)e.style.display='block';}
function hide(id){var e=document.getElementById(id);if(e)e.style.display='none';}

function renderSchedule(sched,cid){
  var el=document.getElementById(cid);
  if(!el||!sched||!sched.schedules)return;
  el.innerHTML=sched.schedules.map(function(s){
    var r=(s.interview_rounds||[])[0]||{};
    return '<div style="padding:10px 14px;border-bottom:1px solid var(--border);font-size:13px"><strong>'+(s.candidate_name||'Candidate')+'</strong><br/><span style="color:var(--muted);font-size:12px">'+( r.date||'TBD')+' at '+(r.time||'TBD')+' &nbsp;·&nbsp; '+(r.interviewer||'')+'</span></div>';
  }).join('');
}

function renderCheckboxes(candidates, roundNum) {
  _currentRoundCands[roundNum]=candidates;
  var listId='round'+roundNum+'CheckList', countId='round'+roundNum+'SelCount';
  document.getElementById(listId).innerHTML=candidates.map(function(c,i){
    var score=c.match_score||c.score||'?';
    return '<div class="cand-check-item selected" id="cci_'+roundNum+'_'+i+'" onclick="toggleCheck('+roundNum+','+i+')">' +
      '<input type="checkbox" id="chk_'+roundNum+'_'+i+'" checked onclick="event.stopPropagation();updateSelCount('+roundNum+')" />' +
      '<div class="cand-check-info"><div class="cand-check-name">'+(c.name||c.login||'Candidate')+'</div>' +
      '<div class="cand-check-meta">Score: '+score+'/10 &nbsp;·&nbsp; '+(c.location||'Unknown')+(c.github_url?' &nbsp;<a href="'+c.github_url+'" target="_blank" style="color:var(--violet)">GitHub</a>':'')+'</div></div>' +
      '</div>';
  }).join('');
  updateSelCount(roundNum);
  saveFlowState(roundNum, candidates, []);
}

function toggleCheck(roundNum,idx){
  var cb=document.getElementById('chk_'+roundNum+'_'+idx);
  var item=document.getElementById('cci_'+roundNum+'_'+idx);
  cb.checked=!cb.checked;
  item.className='cand-check-item'+(cb.checked?' selected':'');
  updateSelCount(roundNum);
}

function updateSelCount(roundNum){
  var cbs=document.querySelectorAll('#round'+roundNum+'CheckList input[type=checkbox]');
  var sel=Array.from(cbs).filter(function(c){return c.checked;}).length;
  var el=document.getElementById('round'+roundNum+'SelCount');
  if(el) el.textContent=sel+' of '+cbs.length+' candidates selected for next round';
}

function getSelectedCandidates(roundNum){
  var all=_currentRoundCands[roundNum]||[];
  return all.filter(function(c,i){
    var cb=document.getElementById('chk_'+roundNum+'_'+i);
    return cb&&cb.checked;
  });
}

function saveFlowState(roundNum, allCands, clearedCands){
  var flowId=_flowData.flow_id||'';
  var role=(_flowData.request&&_flowData.request.job_title)||'Software Engineer';
  if(!flowId) return;
  fetch('/save-flow-state',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({flow_id:flowId,round_number:roundNum,all_candidates:allCands,cleared_candidates:clearedCands,role:role})
  }).catch(function(){});
}

async function resumeFlow(flowId){
  var r=await fetch('/active-flows');
  var d=await r.json();
  var flow=(d.flows||[]).find(function(f){return f.flow_id===flowId;});
  if(!flow){alert('Could not load flow.');return;}
  _flowData={flow_id:flow.flow_id,request:{job_title:flow.role||flow.title},candidates:{candidates:flow.all_candidates||[]},status:flow.status};
  show('result');
  document.getElementById('steps').innerHTML='';
  ['candidatesSection','round1Section','round2Section','round3Section','bgSection'].forEach(hide);
  addStep('Resuming: '+flow.title+' (started '+flow.started_at+')');
  addStep((flow.all_candidates||[]).length+' candidates loaded from previous session');
  var cands=flow.all_candidates||[], cleared=flow.cleared_candidates||[];
  if(cands.length>0){
    show('candidatesSection');
    document.getElementById('candidatesGrid').innerHTML=cands.map(function(c){
      var score=c.match_score||c.score||'?';
      return '<div class="cand-card"><div class="cand-name">'+(c.name||c.login||'?')+'</div><span class="cand-score">Score: '+score+'/10</span><div class="cand-detail">'+(c.location||'Unknown')+'</div></div>';
    }).join('');
  }
  var roundNum=flow.current_round||1;
  var showCands=cleared.length?cleared:cands;
  var secId='round'+roundNum+'Section';
  show(secId);
  renderCheckboxes(showCands, roundNum);
  addStep('Select candidates who cleared Round '+roundNum+', then advance.');
  document.getElementById('result').scrollIntoView({behavior:'smooth'});
}

function startHiring(){
  var btn=document.getElementById('btn');
  btn.disabled=true; btn.textContent='Running...';
  show('result');
  document.getElementById('steps').innerHTML='';
  ['candidatesSection','round1Section','round2Section','round3Section','bgSection'].forEach(hide);
  fetch('/hire',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    job_title:document.getElementById('jt').value,
    experience_years:parseInt(document.getElementById('exp').value)||3,
    location:document.getElementById('loc').value,
    num_candidates:parseInt(document.getElementById('numcands').value)||5,
    notes:document.getElementById('notes').value
  })})
  .then(function(r){return r.json();})
  .then(function(data){
    _flowData=data;
    (data.steps||[]).forEach(addStep);
    var cands=(data.candidates&&data.candidates.candidates)?data.candidates.candidates:[];
    if(cands.length>0){
      show('candidatesSection');
      document.getElementById('candidatesGrid').innerHTML=cands.map(function(c){
        var score=c.match_score||c.score||'?';
        var col=score>=8?'var(--green)':score>=6?'var(--amber)':'var(--muted)';
        return '<div class="cand-card"><div class="cand-name">'+(c.name||c.login||'Unknown')+'</div><span class="cand-score" style="color:'+col+'">Score: '+score+'/10</span><div class="cand-detail">'+(c.location||'Unknown')+'</div>'+(c.github_url?'<a href="'+c.github_url+'" target="_blank" class="gh-link">GitHub</a>':'')+'</div>';
      }).join('');
    }
    show('round1Section');
    renderSchedule(data.schedule,'round1Content');
    renderCheckboxes(cands,1);
    document.getElementById('round1Section').scrollIntoView({behavior:'smooth'});
    loadActiveFlows();
  })
  .catch(function(e){addStep('Error: '+e.message);})
  .finally(function(){btn.disabled=false;btn.textContent='Start Hiring Flow (Source + Round 1)';});
}

function advanceRound(toRound){
  var fromRound=toRound-1;
  var selected=getSelectedCandidates(fromRound);
  if(selected.length===0){alert('Please select at least one candidate who cleared Round '+fromRound);return;}
  var role=(_flowData.request&&_flowData.request.job_title)||'Software Engineer';
  var flowId=_flowData.flow_id||'';
  var btn=document.getElementById('round'+fromRound+'Btn');
  btn.disabled=true; btn.textContent='Scheduling Round '+toRound+' for '+selected.length+' candidate(s)...';
  addStep(selected.length+' candidate(s) cleared Round '+fromRound+': '+selected.map(function(c){return c.name||c.login||'?';}).join(', '));
  addStep('Scheduling Round '+toRound+'...');
  saveFlowState(fromRound,_currentRoundCands[fromRound]||[],selected);
  fetch('/schedule-round',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({round_number:toRound,candidates:selected,role:role,flow_id:flowId})})
  .then(function(r){return r.json();})
  .then(function(data){
    (data.steps||[]).forEach(addStep);
    if(!data.success){addStep('Error: '+(data.error||'Failed'));btn.disabled=false;btn.textContent='Retry';return;}
    var sec='round'+toRound+'Section';
    show(sec);
    renderSchedule(data.schedule,'round'+toRound+'Content');
    renderCheckboxes(selected,toRound);
    document.getElementById(sec).scrollIntoView({behavior:'smooth'});
    btn.textContent='Round '+fromRound+' Cleared ('+selected.length+' candidates)';
    btn.style.background='#374151';btn.style.cursor='not-allowed';
  })
  .catch(function(e){addStep('Error: '+e.message);btn.disabled=false;});
}

function runBgCheck(){
  var selected=getSelectedCandidates(3);
  if(selected.length===0){alert('Please select at least one candidate who cleared Round 3');return;}
  var role=(_flowData.request&&_flowData.request.job_title)||'Software Engineer';
  var flowId=_flowData.flow_id||'';
  var btn=document.getElementById('round3Btn');
  btn.disabled=true; btn.textContent='Running background checks for '+selected.length+' candidate(s)...';
  addStep(selected.length+' candidate(s) cleared Round 3: '+selected.map(function(c){return c.name||c.login||'?';}).join(', '));
  addStep('Running background verification...');
  saveFlowState(3,_currentRoundCands[3]||[],selected);
  fetch('/run-background-check',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({candidates:selected,role:role,flow_id:flowId})})
  .then(function(r){return r.json();})
  .then(function(data){
    (data.steps||[]).forEach(addStep);
    if(!data.success){addStep('Error: '+(data.error||'Failed'));btn.disabled=false;return;}
    show('bgSection');
    var checks=(data.background_checks&&(data.background_checks.results||data.background_checks.verification_results))||[];
    document.getElementById('bgContent').innerHTML=checks.length>0
      ?checks.map(function(c){
        var pass=c.overall_status==='PASS'||c.status==='verified';
        return '<div style="padding:10px 14px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;font-size:13px"><strong>'+(c.candidate_name||c.name||'Candidate')+'</strong><span style="color:'+(pass?'var(--green)':'var(--amber)')+'">'+( c.overall_status||c.status||'Checked')+'</span></div>';
      }).join('')
      :'<pre style="font-size:11px;color:var(--muted);white-space:pre-wrap">'+JSON.stringify(data.background_checks,null,2)+'</pre>';
    document.getElementById('bgSection').scrollIntoView({behavior:'smooth'});
    addStep('Done! Source → R1 → R2 → R3 → Background Check complete!');
    btn.textContent='Done';btn.style.background='#374151';btn.style.cursor='not-allowed';
  })
  .catch(function(e){addStep('Error: '+e.message);btn.disabled=false;});
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


@app.post("/save-flow-state")
async def save_flow_state(request: Request):
    """Persist which candidates are in a round so HR can resume days later."""
    import json as _j
    body          = await request.json()
    flow_id       = body.get("flow_id", "")
    round_number  = int(body.get("round_number", 1))
    all_cands     = body.get("all_candidates", [])
    cleared_cands = body.get("cleared_candidates", [])
    role          = body.get("role", "")
    status        = f"awaiting_round_{round_number + 1}" if round_number < 3 else "awaiting_bg_check"
    if not flow_id:
        return JSONResponse({"success": False, "error": "flow_id required"})
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{REGISTRY_URL}/registry/audit/save", json={
                "flow_id": flow_id,
                "status":  status,
                "extra_data": _j.dumps({
                    "current_round":      round_number,
                    "all_candidates":     all_cands,
                    "cleared_candidates": cleared_cands,
                    "role":               role
                })
            })
        return JSONResponse({"success": True, "status": status})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@app.get("/active-flows")
async def get_active_flows():
    """Return all in-progress hiring flows so HR can resume from any session."""
    import json as _j
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{REGISTRY_URL}/registry/audit",
                                 params={"flow_type": "hiring", "limit": 30})
            logs = r.json().get("logs", [])
        active = []
        for log in logs:
            if log.get("status") not in ("in_progress", "awaiting_round_2",
                                          "awaiting_round_3", "awaiting_bg_check"):
                continue
            extra, all_cands, cleared = {}, [], []
            try:
                ed = log.get("extra_data")
                if isinstance(ed, str): extra = _j.loads(ed)
                all_cands = extra.get("all_candidates", [])
                cleared   = extra.get("cleared_candidates", [])
            except Exception: pass
            if not all_cands:
                try:
                    rd = log.get("result_data")
                    if isinstance(rd, str): rd = _j.loads(rd)
                    if isinstance(rd, dict): all_cands = rd.get("candidates", [])
                except Exception: pass
            round_map = {"in_progress": 1, "awaiting_round_2": 2,
                         "awaiting_round_3": 3, "awaiting_bg_check": 4}
            active.append({
                "flow_id":     log.get("flow_id"),
                "title":       log.get("title", "Hiring Flow"),
                "location":    log.get("location", ""),
                "status":      log.get("status"),
                "current_round": round_map.get(log.get("status",""), 1),
                "started_at":  (log.get("started_at") or "")[:10],
                "all_candidates":     all_cands,
                "cleared_candidates": cleared,
                "role":        extra.get("role", log.get("title", "Software Engineer")),
            })
        return JSONResponse({"flows": active})
    except Exception as e:
        return JSONResponse({"flows": [], "error": str(e)})


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
