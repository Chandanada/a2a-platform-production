"""
A2A Registry — Production
Full registry with PostgreSQL, audit logs, analytics, agent directory.
"""
import os, json, uuid, httpx
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from database import (init_db, verify_api_key, register_agent, get_all_agents,
                      get_agent_by_name, discover_agents_by_skill,
                      create_audit_log, update_audit_log,
                      get_audit_logs, get_audit_log, get_analytics)

app = FastAPI(title="A2A Registry", version="1.0.0")
templates = Jinja2Templates(directory="templates")

REGISTRY_URL = os.getenv("REGISTRY_URL", "http://localhost:8000")
API_KEY      = os.getenv("API_KEY", "a2a-admin-key-changeme-in-production")


@app.on_event("startup")
def startup():
    init_db()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/registry/health")
def health():
    agents = get_all_agents()
    return {"status": "ok", "registered_agents": len(agents),
            "timestamp": datetime.now().isoformat()}


@app.get("/health")
def health2():
    return health()


# ── Agent Registration ────────────────────────────────────────────────────────

@app.post("/registry/register")
async def api_register(request: Request,
                        x_api_key: str = Header(None, alias="X-API-Key")):
    key = x_api_key or request.headers.get("authorization","").replace("Bearer ","")
    if not verify_api_key(key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    body = await request.json()
    agent = register_agent(
        name         = body["name"],
        description  = body.get("description",""),
        agent_url    = body["agent_url"],
        skills       = body.get("skills",[]),
        tags         = body.get("tags",[]),
        version      = body.get("version","1.0.0"),
        input_modes  = body.get("input_modes",["application/json"]),
        output_modes = body.get("output_modes",["application/json"])
    )
    return {"status": "registered", "agent": agent}


@app.get("/registry/discover")
def discover(skill: str = None, tag: str = None):
    agents = discover_agents_by_skill(skill or tag or "")
    result = []
    for a in agents:
        result.append({
            "name":        a["name"],
            "description": a["description"],
            "agent_url":   a["agent_url"],
            "skills":      a["skills"],
            "supportedInterfaces": [{"url": a["agent_url"],
                                     "protocolBinding":"JSONRPC",
                                     "protocolVersion":"1.0"}]
        })
    return {"agents": result, "count": len(result)}


@app.get("/registry/agents")
def list_agents():
    return {"agents": get_all_agents(), "count": len(get_all_agents())}


# ── Audit API ─────────────────────────────────────────────────────────────────

@app.post("/registry/audit/create")
async def audit_create(request: Request):
    body = await request.json()
    create_audit_log(
        flow_id          = body["flow_id"],
        title            = body.get("title") or body.get("job_title",""),
        subtitle         = body.get("subtitle",""),
        location         = body.get("location",""),
        flow_type        = body.get("flow_type","hiring"),
        experience_years = body.get("experience_years",0)
    )
    return {"status": "created"}


@app.post("/registry/audit/save")
async def audit_save(request: Request):
    body    = await request.json()
    flow_id = body.pop("flow_id", None)
    if not flow_id:
        raise HTTPException(status_code=400, detail="flow_id required")
    if body.get("completed_at") == "now":
        body["completed_at"] = datetime.now().isoformat()
    # Serialize lists/dicts to JSON string for storage
    for f in ("agents_used","result_data","secondary_data","tertiary_data","emails_sent_to"):
        if f in body and not isinstance(body[f], str):
            body[f] = json.dumps(body[f])
    update_audit_log(flow_id, **body)
    return {"status": "saved"}


@app.get("/registry/audit")
def audit_api(limit: int = 50, flow_type: str = None):
    return {"logs": get_audit_logs(limit, flow_type)}


# ── Proxy for agent cards (CORS fix) ─────────────────────────────────────────

@app.get("/registry/proxy/agent-card")
async def proxy_agent_card(url: str):
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(url)
            return JSONResponse(r.json())
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))




# ── Agent Management ──────────────────────────────────────────────────────────

@app.post("/registry/agents/delete")
async def delete_agent(request: Request):
    body = await request.json()
    name = body.get("name", "")
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("DELETE FROM agents WHERE name=%s RETURNING id", (name,))
    row = cur.fetchone()
    conn.commit(); cur.close(); conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "deleted", "name": name}


@app.post("/registry/agents/set-status")
async def update_agent_status(request: Request):
    body   = await request.json()
    name   = body.get("name", "")
    status = body.get("status", "active")
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    if status not in ("active", "inactive"):
        raise HTTPException(status_code=400, detail="Status must be active or inactive")
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("UPDATE agents SET status=%s, updated_at=NOW() WHERE name=%s RETURNING id",
                (status, name))
    row = cur.fetchone()
    conn.commit(); cur.close(); conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "updated", "name": name, "new_status": status}

# ── UI Pages ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    agents = get_all_agents()
    return templates.TemplateResponse("index.html",
        {"request": request, "agents": agents,
         "registry_url": REGISTRY_URL})


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html",
        {"request": request, "registry_url": REGISTRY_URL,
         "api_key": API_KEY})


@app.post("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    form = await request.form()
    skills = [{"id": form.get("skill_id",""), "name": form.get("skill_name","")}]
    try:
        agent = register_agent(
            name        = form["name"],
            description = form.get("description",""),
            agent_url   = form["agent_url"],
            skills      = skills,
            tags        = [t.strip() for t in form.get("tags","").split(",") if t.strip()],
            version     = form.get("version","1.0.0")
        )
        agents = get_all_agents()
        return templates.TemplateResponse("register.html",
            {"request": request, "registry_url": REGISTRY_URL,
             "api_key": API_KEY, "success": True,
             "registered_agent": agent})
    except Exception as e:
        return templates.TemplateResponse("register.html",
            {"request": request, "registry_url": REGISTRY_URL,
             "api_key": API_KEY, "error": str(e)})


@app.get("/agents/{name}", response_class=HTMLResponse)
def agent_detail_page(request: Request, name: str):
    agent = get_agent_by_name(name.replace("%20"," "))
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return templates.TemplateResponse("agent_detail.html",
        {"request": request, "agent": agent,
         "registry_url": REGISTRY_URL})


@app.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request, flow_type: str = None):
    logs = get_audit_logs(100, flow_type)
    return templates.TemplateResponse("audit.html",
        {"request": request, "logs": logs,
         "flow_type": flow_type, "registry_url": REGISTRY_URL})


@app.get("/audit/{flow_id}", response_class=HTMLResponse)
def audit_detail_page(request: Request, flow_id: str):
    log = get_audit_log(flow_id)
    if not log:
        raise HTTPException(status_code=404, detail="Flow not found")
    return templates.TemplateResponse("audit_detail.html",
        {"request": request, "log": log,
         "registry_url": REGISTRY_URL})


@app.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request):
    data = get_analytics()
    return templates.TemplateResponse("analytics.html",
        {"request": request, "data": data,
         "registry_url": REGISTRY_URL})
