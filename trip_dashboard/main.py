"""
Business Trip Dashboard — AP2 Protocol Implementation
Full flow using official AP2 mandates:
  IntentMandate → CartMandate → PaymentMandate
"""
import os, uuid, json, hmac, hashlib, smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, Response

load_dotenv()
REGISTRY_URL       = os.getenv("REGISTRY_URL", "http://localhost:8000")
GMAIL_SENDER       = os.getenv("GMAIL_SENDER", "chandannov2291@gmail.com")
GMAIL_APP_PASS     = os.getenv("GMAIL_APP_PASS", "unkfnvhzezhpsycf")
NOTIFY_EMAILS      = os.getenv("INTERVIEW_NOTIFY_EMAILS",
                                "chandannov2291@gmail.com,dubeyneha1191@gmail.com").split(",")
DEMO_SIGNING_SECRET = os.getenv("DEMO_SIGNING_SECRET", "ap2-demo-signing-secret-2026")
AP2_EXTENSION_URI  = "https://github.com/google-agentic-commerce/ap2/tree/v0.1"

app = FastAPI(title="Business Trip Dashboard", version="3.0.0")
confirmed_trips: dict = {}


# ── AP2 signing (matches payment agent) ───────────────────────────────────────
def sign_mandate(payload: dict) -> str:
    """Demo HMAC-SHA256 — production: hardware-backed ECDSA."""
    payload_bytes = json.dumps(payload, sort_keys=True).encode()
    sig = hmac.new(DEMO_SIGNING_SECRET.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return f"demo-hmac-sha256:{sig}"


# ── Helpers ───────────────────────────────────────────────────────────────────
import httpx

async def discover_agent(skill: str) -> dict | None:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{REGISTRY_URL}/registry/discover",
                             params={"skill": skill}, timeout=10.0)
        return (r.json().get("agents") or [None])[0]


async def send_a2a(agent_url: str, parts: list,
                   context_id: str = None, task_id: str = None) -> dict:
    """Send A2A message with AP2 extension header."""
    payload = {
        "jsonrpc": "2.0",
        "id":      f"req-{uuid.uuid4().hex[:8]}",
        "method":  "SendMessage",
        "params":  {
            "message": {
                "role":      "user",
                "messageId": str(uuid.uuid4()),
                "contextId": context_id or str(uuid.uuid4()),
                "taskId":    task_id    or str(uuid.uuid4()),
                "parts":     parts
            }
        }
    }
    headers = {
        "Content-Type":      "application/json",
        # AP2 extension header — marks this as an AP2 transaction
        "X-A2A-Extensions":  AP2_EXTENSION_URI
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(agent_url, json=payload, headers=headers)
        return r.json()


def extract(resp: dict) -> dict:
    try:
        return next((p["data"] for p in
                     resp["result"]["task"]["artifacts"][0]["parts"]
                     if "data" in p), {})
    except Exception:
        return {}


def extract_cart_mandate(resp: dict) -> dict:
    """Extract ap2.mandates.CartMandate from artifact parts."""
    try:
        for part in resp["result"]["task"]["artifacts"][0]["parts"]:
            data = part.get("data", {})
            if "ap2.mandates.CartMandate" in data:
                return data["ap2.mandates.CartMandate"]
    except Exception:
        pass
    return {}


def build_ics(trip: dict) -> str:
    ts = trip.get("trip_summary", {})
    f  = trip.get("selected_flight", {})
    h  = trip.get("selected_hotel", {})
    try:
        dt = datetime.strptime(ts.get("travel_date", ""), "%A, %B %d, %Y")
    except Exception:
        dt = datetime.now()
    uid = str(uuid.uuid4())
    desc = (f"Purpose: {ts.get('purpose','')}\\n"
            f"Flight: {f.get('airline','')} {f.get('flight_number','')}\\n"
            f"Hotel: {h.get('name','')}\\nBooked via AP2 Protocol")
    return (f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//A2A AP2 Travel//EN\r\n"
            f"BEGIN:VEVENT\r\nUID:{uid}\r\n"
            f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}\r\n"
            f"DTSTART:{dt.strftime('%Y%m%dT070000')}\r\n"
            f"DTEND:{dt.strftime('%Y%m%dT230000')}\r\n"
            f"SUMMARY:Business Trip: {ts.get('origin','')} → {ts.get('destination','')}\r\n"
            f"DESCRIPTION:{desc}\r\nSTATUS:CONFIRMED\r\nEND:VEVENT\r\nEND:VCALENDAR")


@app.get("/registry-status")
async def registry_status():
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{REGISTRY_URL}/registry/health", timeout=5.0)
            return r.json()
    except Exception:
        return {"status": "error", "registered_agents": 0}


# ── STEP 1: Plan trip via Travel Agent ────────────────────────────────────────
@app.post("/plan-trip")
async def plan_trip(request: Request):
    body   = await request.json()
    report = {"flow_id": str(uuid.uuid4()), "steps": [], "trip_plan": {}, "status": "in_progress"}
    def step(msg): report["steps"].append(msg)

    step("🔍 Step 1: Querying registry for Travel Agent...")
    agent = await discover_agent("plan_trip")
    if not agent:
        report["status"] = "failed"
        report["error"]  = "Travel Agent not registered. Go to localhost:8000/register."
        return JSONResponse(report, status_code=404)
    url = agent["supportedInterfaces"][0]["url"]
    step(f"✅ Found: {agent['name']} at {url}")
    step("📋 Step 2: Fetching Travel Agent Card...")
    async with httpx.AsyncClient() as client:
        card = (await client.get(f"{url}/.well-known/agent-card.json", timeout=8.0)).json()
    step(f"✅ Skills: {[s['id'] for s in card.get('skills',[])]}")
    step("📤 Step 3: Sending trip request via A2A SendMessage...")
    resp = await send_a2a(url, [
        {"kind": "text", "text": f"Plan trip {body.get('origin')} to {body.get('destination')}",
         "mediaType": "text/plain"},
        {"kind": "data", "data": body, "mediaType": "application/json"}
    ])
    from typing import Any
    def _extract_any(r: dict) -> dict:
        try:
            for part in r["result"]["task"]["artifacts"][0]["parts"]:
                if "data" in part: return part["data"]
        except Exception:
            pass
        return {}
    trip = _extract_any(resp)
    report["trip_plan"] = trip
    report["status"]    = "completed"
    step("✅ Trip options ready — select flight and hotel below.")
    return JSONResponse(report)


# ── STEP 2: Confirm trip + send approval email ────────────────────────────────
@app.post("/confirm-trip")
async def confirm_trip(request: Request):
    body    = await request.json()
    trip_id = str(uuid.uuid4())
    confirmed_trips[trip_id] = {
        "trip_id":          trip_id,
        "confirmed_at":     datetime.now().isoformat(),
        "trip_summary":     body.get("trip_summary", {}),
        "selected_flight":  body.get("selected_flight", {}),
        "selected_hotel":   body.get("selected_hotel", {}),
        "expense_estimate": body.get("expense_estimate", {}),
        "status":           "pending_payment"
    }
    return JSONResponse({"trip_id": trip_id, "status": "pending_payment"})


# ── STEP 3: Send AP2 IntentMandate → get CartMandate ─────────────────────────
@app.post("/ap2-intent")
async def ap2_intent(request: Request):
    """
    Shopping Agent sends IntentMandate to Payment Agent.
    Per AP2 spec: IntentMandate describes what user wants to purchase.
    """
    body   = await request.json()
    report = {"steps": [], "status": "in_progress"}
    def step(msg): report["steps"].append(msg)

    step("🔍 Querying registry for AP2 Payment Agent...")
    agent = await discover_agent("process_payment")
    if not agent:
        report["status"] = "failed"
        report["error"]  = "AP2 Payment Agent not registered. Go to your Registry and register it with skill: process_payment"
        return JSONResponse(report, status_code=404)

    url = agent["supportedInterfaces"][0]["url"]
    step(f"✅ Found: {agent['name']} at {url}")

    # Check AP2 extension in AgentCard
    step("📋 Fetching AP2 Payment Agent Card...")
    async with httpx.AsyncClient() as client:
        card = (await client.get(f"{url}/.well-known/agent-card.json", timeout=8.0)).json()

    extensions = card.get("capabilities", {}).get("extensions", [])
    ap2_ext    = next((e for e in extensions if AP2_EXTENSION_URI in e.get("uri", "")), None)
    if ap2_ext:
        roles = ap2_ext.get("params", {}).get("roles", [])
        step(f"✅ AP2 Extension confirmed · Roles: {roles}")
    else:
        step("⚠️ AP2 extension not declared in AgentCard — proceeding anyway")

    # Build IntentMandate per AP2 spec section 4.1.2
    ts    = body.get("trip_summary", {})
    exp   = body.get("expense_estimate", {})
    items = body.get("cart_items", [])
    total = {"currency": "INR", "value": exp.get("total_inr", 0)}

    context_id = str(uuid.uuid4())
    task_id    = str(uuid.uuid4())

    intent_mandate = {
        "user_cart_confirmation_required": True,   # human-present
        "natural_language_description":    (
            f"Book business trip: {ts.get('origin','')} → {ts.get('destination','')} "
            f"on {ts.get('travel_date','')}. Purpose: {ts.get('purpose','')}."
        ),
        "merchants":           [{"name": "A2A Travel Platform", "url": REGISTRY_URL}],
        "skus":                None,
        "requires_refundability": False,
        "intent_expiry":       (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        # Extra context for the merchant
        "cart_items":          items,
        "total_amount":        total
    }

    step(f"📤 Sending AP2 IntentMandate via A2A SendMessage...")
    step(f"   → Extension header: X-A2A-Extensions: {AP2_EXTENSION_URI}")
    step(f"   → Mandate key: ap2.mandates.IntentMandate")

    resp = await send_a2a(url, [
        {
            "kind": "data",
            "data": {"ap2.mandates.IntentMandate": intent_mandate}
        }
    ], context_id=context_id, task_id=task_id)

    # Extract CartMandate from response
    cart_mandate = extract_cart_mandate(resp)
    task_state   = resp.get("result", {}).get("task", {}).get("status", {}).get("state", "")
    step(f"📨 A2A Task State: {task_state}")

    if cart_mandate:
        cart_contents = cart_mandate.get("contents", {})
        cart_id       = cart_contents.get("id", "")
        order_id      = cart_contents.get("payment_request", {}).get("details", {}).get("id", "")
        step(f"✅ CartMandate received · Cart ID: {cart_id}")
        step(f"   → merchant_signature: {cart_mandate.get('merchant_signature','')[:30]}...")
        step(f"   → user_signature_required: {cart_contents.get('user_signature_required', True)}")
        step("⏳ Waiting for user confirmation (human-present step)...")
        report["status"]        = "awaiting_user_confirmation"
        report["cart_mandate"]  = cart_mandate
        report["cart_id"]       = cart_id
        report["order_id"]      = order_id
        report["context_id"]    = context_id
        report["task_id"]       = task_id
        report["agent_url"]     = url
        report["total"]         = total
    else:
        report["status"] = "error"
        report["error"]  = "No CartMandate received from Payment Agent"
        step("❌ CartMandate not found in response")

    report["steps"] = report["steps"]
    return JSONResponse(report)


# ── STEP 4: User confirmed → send AP2 PaymentMandate ─────────────────────────
@app.post("/ap2-pay")
async def ap2_pay(request: Request):
    """
    User confirmed cart → Shopping Agent sends PaymentMandate.
    Per AP2 spec section 4.1.3.
    user_authorization = demo HMAC-SHA256 (production: hardware ECDSA).
    """
    body       = await request.json()
    agent_url  = body.get("agent_url", "")
    cart_id    = body.get("cart_id", "")
    order_id   = body.get("order_id", "")
    total      = body.get("total", {})
    context_id = body.get("context_id", str(uuid.uuid4()))
    task_id    = body.get("task_id",    str(uuid.uuid4()))
    card_last4 = body.get("card_last4", "****")

    report = {"steps": [], "status": "in_progress"}
    def step(msg): report["steps"].append(msg)

    # Build PaymentMandate contents
    pm_id = f"pm_{uuid.uuid4().hex[:12]}"
    payment_mandate_contents = {
        "payment_mandate_id":    pm_id,
        "payment_details_id":    order_id,
        "cart_id":               cart_id,
        "payment_details_total": {
            "label":         "Total",
            "amount":        total,
            "pending":       None,
            "refund_period": 30
        },
        "payment_response": {
            "request_id":  order_id,
            "method_name": "CARD",
            "details": {
                "token": {
                    "value": f"demo_token_card_{card_last4}",
                    "note":  "Production: real payment token from Credential Provider"
                }
            },
            "shipping_address": None,
            "payer_name":       "Demo User",
            "payer_email":      GMAIL_SENDER
        },
        "merchant_agent": "AP2 Payment Agent",
        "timestamp":      datetime.now(timezone.utc).isoformat()
    }

    # User signs the PaymentMandate (demo HMAC, production ECDSA)
    user_authorization = sign_mandate(payment_mandate_contents)

    # Full PaymentMandate per AP2 A2A extension spec
    payment_mandate = {
        "payment_mandate_contents": payment_mandate_contents,
        "user_authorization":       user_authorization
    }

    step("📤 Sending AP2 PaymentMandate via A2A SendMessage...")
    step(f"   → Mandate key: ap2.mandates.PaymentMandate")
    step(f"   → user_authorization: {user_authorization[:40]}...")
    step(f"   → Payment method: CARD (last 4: {card_last4})")

    resp   = await send_a2a(agent_url, [
        {
            "kind": "data",
            "data": {"ap2.mandates.PaymentMandate": payment_mandate}
        }
    ], context_id=context_id, task_id=task_id)

    result     = extract(resp)
    task_state = resp.get("result", {}).get("task", {}).get("status", {}).get("state", "")
    step(f"📨 A2A Task State: {task_state}")

    if result.get("status") == "PAYMENT_SUCCESS":
        report["status"]       = "success"
        report["booking_ref"]  = result.get("booking_ref")
        report["amount_charged"] = result.get("amount_charged")
        report["mandate_chain"]  = result.get("mandate_chain", {})
        report["next_steps"]     = result.get("next_steps", [])
        report["email_sent"]     = result.get("email_sent", False)
        step(f"✅ AP2 PaymentMandate verified by merchant")
        step(f"✅ Booking confirmed · Ref: {result.get('booking_ref')}")
        step(f"✅ Mandate chain complete: IntentMandate → CartMandate → PaymentMandate")
    elif result.get("status") == "MANDATE_INVALID":
        report["status"] = "error"
        report["error"]  = result.get("error", "Mandate signature invalid")
        step(f"❌ {report['error']}")
    else:
        report["status"] = "error"
        report["error"]  = result.get("error", "Payment failed")
        step(f"❌ {report['error']}")

    report["raw_result"] = result
    return JSONResponse(report)


@app.get("/calendar/{trip_id}")
async def calendar(trip_id: str):
    trip = confirmed_trips.get(trip_id)
    if not trip:
        return Response("Not found", status_code=404)
    ts = trip.get("trip_summary", {})
    fn = f"trip_{ts.get('origin','X')}_to_{ts.get('destination','X')}.ics".replace(" ", "_")
    return Response(content=build_ics(trip), media_type="text/calendar",
                    headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse(open("/tmp/trip_ui.html").read()
                        if os.path.exists("/tmp/trip_ui.html")
                        else _build_ui())


def _build_ui() -> str:
    return """<!DOCTYPE html>
<html>
<head>
  <title>Business Trip Planner — AP2 Protocol</title>
  <style>
    :root{--bg:#0a0f1e;--card:#111827;--card2:#1a2235;--border:#1e2d45;--amber:#f59e0b;--amber2:#fbbf24;--text:#e2e8f0;--muted:#64748b;--green:#10b981;--red:#f87171;--blue:#3b82f6;--violet:#7c3aed}
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding:32px 20px}
    .wrap{max-width:920px;margin:0 auto}
    nav{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px}
    .brand{display:flex;align-items:center;gap:10px}
    .logo{width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#f59e0b,#ef4444);display:flex;align-items:center;justify-content:center;font-size:18px}
    .brand-name{font-size:16px;font-weight:800}
    .nav-links{display:flex;gap:8px;flex-wrap:wrap}
    .nav-links a{color:var(--amber);font-size:12px;text-decoration:none;font-weight:600;padding:6px 10px;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);border-radius:8px}
    h1{font-size:22px;font-weight:900;margin-bottom:4px}
    .sub{color:var(--muted);font-size:13px;margin-bottom:18px}
    .sbar{padding:11px 14px;border-radius:10px;margin-bottom:16px;font-size:12px;font-weight:600}
    .sbar.checking{background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);color:var(--amber)}
    .sbar.ok{background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);color:var(--green)}
    .sbar.error{background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.25);color:var(--red)}
    /* AP2 Protocol Banner */
    .ap2-banner{background:linear-gradient(135deg,rgba(124,58,237,0.1),rgba(59,130,246,0.08));border:1px solid rgba(124,58,237,0.25);border-radius:12px;padding:12px 16px;margin-bottom:16px;font-size:12px}
    .ap2-title{font-weight:700;color:var(--violet);margin-bottom:4px}
    .ap2-flow{display:flex;align-items:center;gap:6px;flex-wrap:wrap;color:var(--muted);font-size:11px}
    .ap2-node{background:rgba(124,58,237,0.12);color:#a78bfa;border:1px solid rgba(124,58,237,0.2);border-radius:20px;padding:3px 10px;font-weight:600;white-space:nowrap}
    .ap2-arrow{color:var(--muted2)}
    /* Stepper */
    .stepper{display:flex;align-items:flex-start;margin-bottom:20px;overflow-x:auto;gap:0}
    .sw{display:flex;flex-direction:column;align-items:center;min-width:60px}
    .sd{width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;flex-shrink:0;border:2px solid var(--border);background:var(--card);color:var(--muted);transition:all .3s}
    .sd.done{background:var(--green);border-color:var(--green);color:#fff}
    .sd.active{background:var(--amber);border-color:var(--amber);color:#000}
    .sl{width:48px;height:2px;background:var(--border);flex-shrink:0;transition:background .3s;margin-top:14px}
    .sl.done{background:var(--green)}
    .sl-wrap{display:flex;align-items:flex-start}
    .sl-label{font-size:9px;color:var(--muted);text-align:center;margin-top:4px;max-width:60px;line-height:1.3}
    .card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:22px;margin-bottom:16px}
    .ct{font-size:11px;font-weight:700;color:var(--amber);text-transform:uppercase;letter-spacing:1px;margin-bottom:12px}
    .g2{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}
    .g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:10px}
    .f{display:flex;flex-direction:column;gap:4px}
    label{font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
    input,select{background:#080c1a;border:1px solid var(--border);color:var(--text);padding:9px 11px;border-radius:8px;font-size:12px;outline:none;width:100%;font-family:inherit}
    input:focus,select:focus{border-color:var(--amber)}
    select option{background:#111827}
    .rbtn{width:100%;background:linear-gradient(135deg,#f59e0b,#ef4444);color:#fff;border:none;padding:12px;border-radius:10px;font-size:13px;font-weight:700;cursor:pointer;margin-top:8px;transition:opacity .2s}
    .rbtn:hover{opacity:.88}.rbtn:disabled{opacity:.4;cursor:not-allowed}
    #result{display:none}
    .rc{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:12px}
    .rct{font-size:11px;font-weight:700;color:var(--amber);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px}
    .step{padding:4px 0;font-size:12px;border-bottom:1px solid var(--border);color:var(--green)}
    .step:last-child{border:none}.step.e{color:var(--red)}.step.i{color:var(--blue)}.step.m{color:#a78bfa}
    .tbar{background:#080c1a;border:1px solid var(--border);border-radius:10px;padding:12px;margin-bottom:12px;display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
    .tbar .l{font-size:10px;color:var(--muted)}.tbar .v{font-size:12px;font-weight:700}.tbar .v.c{color:var(--amber2)}
    .og{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
    .oh{font-size:11px;font-weight:700;color:var(--amber);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}
    .oc{background:#080c1a;border:1px solid var(--border);border-radius:10px;padding:11px;cursor:pointer;transition:all .2s;margin-bottom:7px;position:relative}
    .oc:hover{border-color:var(--amber)}.oc.sel{border-color:var(--amber);background:rgba(245,158,11,0.06)}
    .oc.sel::after{content:'✓';position:absolute;top:9px;right:11px;font-size:12px;font-weight:700;color:var(--amber)}
    .ot{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px}
    .on{font-weight:700;font-size:12px}.op{color:var(--amber2);font-weight:700;font-size:13px}
    .od{font-size:11px;color:var(--muted)}
    .rc2{font-size:9px;background:rgba(245,158,11,0.15);color:var(--amber);border:1px solid rgba(245,158,11,0.3);border-radius:20px;padding:2px 6px;font-weight:700;margin-left:4px}
    .er{display:flex;justify-content:space-between;padding:5px 0;font-size:12px;border-bottom:1px solid var(--border)}
    .er:last-child{border:none;font-weight:800;color:var(--amber2)}
    .cs{background:rgba(16,185,129,0.06);border:1px solid rgba(16,185,129,0.2);border-radius:10px;padding:14px;margin-top:12px;display:none}
    .cbtn{background:linear-gradient(135deg,#10b981,#059669);color:#fff;border:none;padding:11px 20px;border-radius:8px;font-size:12px;font-weight:700;cursor:pointer;margin-right:8px;transition:opacity .2s}
    .cbtn:hover{opacity:.88}.cbtn:disabled{opacity:.4;cursor:not-allowed}
    /* AP2 Payment section */
    .ap2-pay{display:none}
    .mandate-flow{background:rgba(124,58,237,0.06);border:1px solid rgba(124,58,237,0.2);border-radius:10px;padding:14px;margin-bottom:14px}
    .mf-title{font-size:11px;font-weight:700;color:#a78bfa;margin-bottom:10px}
    .mf-step{display:flex;align-items:flex-start;gap:8px;margin-bottom:8px;font-size:11px}
    .mf-step:last-child{margin-bottom:0}
    .mf-dot{width:20px;height:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;flex-shrink:0}
    .mf-dot.done{background:var(--green);color:#fff}
    .mf-dot.active{background:var(--amber);color:#000}
    .mf-dot.pending{background:var(--card2);color:var(--muted);border:1px solid var(--border)}
    .mf-text .mf-label{font-weight:700;color:var(--text)}
    .mf-text .mf-sub{color:var(--muted);margin-top:1px}
    .cart-mandate-box{background:#080c1a;border:1px solid rgba(124,58,237,0.25);border-radius:10px;padding:14px;margin-bottom:12px}
    .cmb-title{font-size:11px;font-weight:700;color:#a78bfa;margin-bottom:8px}
    .cmb-row{display:flex;justify-content:space-between;padding:4px 0;font-size:12px;border-bottom:1px solid var(--border)}
    .cmb-row:last-child{border:none}
    .paybtn{width:100%;background:linear-gradient(135deg,#7c3aed,#4f46e5);color:#fff;border:none;padding:12px;border-radius:10px;font-size:13px;font-weight:700;cursor:pointer;margin-top:8px;transition:opacity .2s}
    .paybtn:hover{opacity:.88}.paybtn:disabled{opacity:.4;cursor:not-allowed}
    /* Success */
    .success-sec{display:none}
    .bk-card{background:linear-gradient(135deg,#0a2318,#065f46);border:1px solid rgba(16,185,129,0.3);border-radius:14px;padding:22px;margin-bottom:12px;text-align:center}
    .bk-icon{font-size:44px;margin-bottom:10px}
    .bk-title{font-size:18px;font-weight:800;color:var(--green);margin-bottom:4px}
    .bk-ref{font-size:13px;color:#a7f3d0;font-family:monospace;font-weight:700;margin-bottom:14px;letter-spacing:2px}
    .chain-badge{display:inline-flex;align-items:center;gap:6px;background:rgba(16,185,129,0.1);border:1px solid rgba(16,185,129,0.25);border-radius:20px;padding:5px 14px;font-size:11px;color:var(--green);font-weight:600}
    .ac{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}
    .acard{background:var(--card2);border:1px solid var(--border);border-radius:10px;padding:14px;text-align:center;text-decoration:none;color:var(--text);transition:all .2s;display:block}
    .acard:hover{border-color:var(--amber);transform:translateY(-2px)}
    .acard .ico{font-size:20px;margin-bottom:6px}
    .acard .at{font-size:11px;font-weight:700;margin-bottom:2px}
    .acard .asu{font-size:10px;color:var(--muted)}
  </style>
</head>
<body>
<div class="wrap">
  <nav>
    <div class="brand"><div class="logo">✈️</div><span class="brand-name">Business Trip Planner</span></div>
    <div class="nav-links">
      <a href="http://localhost:8000" target="_blank">Registry</a>
      <a href="http://localhost:8003" target="_blank">Hiring</a>
      <a href="http://localhost:8008" target="_blank">HR Ops</a>
    </div>
  </nav>

  <h1>Plan a Business Trip</h1>
  <p class="sub">A2A Client Agent · Payment via <strong>AP2 (Agent Payments Protocol) v0.1</strong> · IntentMandate → CartMandate → PaymentMandate</p>

  <!-- AP2 Protocol Banner -->
  <div class="ap2-banner">
    <div class="ap2-title">🔐 AP2 Protocol Flow</div>
    <div class="ap2-flow">
      <span class="ap2-node">Shopping Agent</span>
      <span class="ap2-arrow">→ IntentMandate →</span>
      <span class="ap2-node">Merchant Agent</span>
      <span class="ap2-arrow">→ CartMandate →</span>
      <span class="ap2-node">User Confirms</span>
      <span class="ap2-arrow">→ PaymentMandate →</span>
      <span class="ap2-node">Payment Processor</span>
      <span class="ap2-arrow">→ Booking Confirmed</span>
    </div>
  </div>

  <div id="regBar" class="sbar checking">⏳ Checking registry...</div>

  <!-- Progress stepper -->
  <div class="stepper" id="stepper">
    <div class="sl-wrap"><div class="sw"><div class="sd active" id="sd1">1</div><div class="sl-label">Plan</div></div></div>
    <div class="sl" id="sl1"></div>
    <div class="sl-wrap"><div class="sw"><div class="sd" id="sd2">2</div><div class="sl-label">Select</div></div></div>
    <div class="sl" id="sl2"></div>
    <div class="sl-wrap"><div class="sw"><div class="sd" id="sd3">3</div><div class="sl-label">Intent<br>Mandate</div></div></div>
    <div class="sl" id="sl3"></div>
    <div class="sl-wrap"><div class="sw"><div class="sd" id="sd4">4</div><div class="sl-label">Cart<br>Mandate</div></div></div>
    <div class="sl" id="sl4"></div>
    <div class="sl-wrap"><div class="sw"><div class="sd" id="sd5">5</div><div class="sl-label">Payment<br>Mandate</div></div></div>
    <div class="sl" id="sl5"></div>
    <div class="sl-wrap"><div class="sw"><div class="sd" id="sd6">✓</div><div class="sl-label">Booked</div></div></div>
  </div>

  <!-- FORM -->
  <div class="card">
    <div class="ct">✈️ Trip Details</div>
    <div class="g2">
      <div class="f"><label>From City</label><input id="orig" value="Bangalore"/></div>
      <div class="f"><label>To City</label><input id="dest" value="Mumbai"/></div>
    </div>
    <div class="g3">
      <div class="f"><label>Travel Date</label><input id="td" value="Monday, April 20, 2026"/></div>
      <div class="f"><label>Return Date</label><input id="rd" value="Wednesday, April 22, 2026"/></div>
      <div class="f"><label>Travelers</label><input id="tv" type="number" value="1" min="1"/></div>
    </div>
    <div class="g2">
      <div class="f"><label>Purpose</label><input id="pur" value="Client meeting and product demo"/></div>
      <div class="f"><label>Budget (₹)</label><input id="bud" type="number" value="50000"/></div>
    </div>
    <button class="rbtn" id="planBtn" onclick="plan()">✈️ Find Flights & Hotels</button>
  </div>

  <div id="result">
    <div class="rc"><div class="rct">📊 A2A + AP2 Flow Log</div><div id="steps"></div></div>

    <!-- Options -->
    <div class="rc" id="optCard" style="display:none">
      <div class="rct">🗺️ Select Preferences</div>
      <div class="tbar" id="tbar"></div>
      <div class="og">
        <div><div class="oh">✈️ Flights</div><div id="flts"></div></div>
        <div><div class="oh">🏨 Hotels</div><div id="htls"></div></div>
      </div>
      <div style="font-size:11px;font-weight:700;color:var(--amber);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">💰 Expense</div>
      <div id="expb"></div>
      <div class="cs" id="cs">
        <div style="font-size:12px;font-weight:700;color:var(--green);margin-bottom:8px">✅ Send AP2 IntentMandate</div>
        <div id="csum" style="font-size:12px;color:var(--muted);margin-bottom:10px"></div>
        <button class="cbtn" id="confirmBtn" onclick="sendIntent()">🔐 Send IntentMandate to Payment Agent</button>
        <span style="font-size:11px;color:var(--muted)">Agent will return a CartMandate</span>
      </div>
    </div>

    <!-- AP2 Payment -->
    <div class="ap2-pay" id="paySection">
      <div class="rc">
        <div class="rct">🔐 AP2 Payment Flow</div>

        <!-- Mandate flow tracker -->
        <div class="mandate-flow">
          <div class="mf-title">AP2 Mandate Chain Progress</div>
          <div class="mf-step">
            <div class="mf-dot done" id="mf1">✓</div>
            <div class="mf-text"><div class="mf-label">IntentMandate sent</div><div class="mf-sub">Shopping Agent → Merchant Agent</div></div>
          </div>
          <div class="mf-step">
            <div class="mf-dot done" id="mf2">✓</div>
            <div class="mf-text"><div class="mf-label">CartMandate received</div><div class="mf-sub">Merchant Agent → Shopping Agent (signed)</div></div>
          </div>
          <div class="mf-step">
            <div class="mf-dot active" id="mf3">3</div>
            <div class="mf-text"><div class="mf-label">User confirms cart ← YOU ARE HERE</div><div class="mf-sub">Human-present: review and confirm</div></div>
          </div>
          <div class="mf-step">
            <div class="mf-dot pending" id="mf4">4</div>
            <div class="mf-text"><div class="mf-label">PaymentMandate sent</div><div class="mf-sub">Shopping Agent → Payment Processor (signed)</div></div>
          </div>
        </div>

        <!-- Cart Mandate display -->
        <div class="cart-mandate-box" id="cartMandateBox">
          <div class="cmb-title">📋 CartMandate (from Merchant Agent)</div>
          <div id="cartItems"></div>
          <div class="cmb-row" style="font-weight:800;color:var(--amber2)"><span>Total</span><span id="cartTotal"></span></div>
          <div style="font-size:10px;color:var(--muted);margin-top:8px">
            merchant_signature: <span id="sigDisplay" style="font-family:monospace;color:#a78bfa"></span>
          </div>
        </div>

        <!-- Card input for PaymentMandate -->
        <div class="g2">
          <div class="f"><label>Card Last 4 Digits</label><input id="cardLast4" maxlength="4" placeholder="4567" style="font-size:18px;font-family:monospace;letter-spacing:4px"/></div>
          <div class="f"><label>Spend Limit (₹)</label><input id="spendLimit" type="number" value="50000"/></div>
        </div>
        <div style="background:rgba(124,58,237,0.06);border:1px solid rgba(124,58,237,0.2);border-radius:8px;padding:10px;margin-top:8px;font-size:11px;color:#a78bfa">
          🔐 <strong>AP2 user_authorization</strong> will be generated as HMAC-SHA256 over CartMandate contents.
          Production: hardware-backed ECDSA per W3C Verifiable Credentials.
        </div>
        <button class="paybtn" id="payBtn" onclick="sendPayment()">🔐 Sign & Send PaymentMandate</button>
      </div>
    </div>

    <!-- Success -->
    <div class="success-sec" id="successSec">
      <div class="bk-card">
        <div class="bk-icon">🎉</div>
        <div class="bk-title">Booking Confirmed!</div>
        <div class="bk-ref" id="bkRef">BKG--------</div>
        <div class="chain-badge">✅ IntentMandate → CartMandate → PaymentMandate · AP2 v0.1</div>
      </div>
      <div class="rc">
        <div class="rct">🎯 Next Steps</div>
        <div id="nextSteps"></div>
        <div class="ac" id="actionCards"></div>
      </div>
    </div>
  </div>
</div>

<script>
let tripData=null, sf=null, sh=null, apData=null, confirmedId=null;

function setStep(n){
  for(let i=1;i<=6;i++){
    const dot=document.getElementById(`sd${i}`);
    const line=document.getElementById(`sl${i}`);
    if(i<n){dot.className='sd done';if(line)line.className='sl done';}
    else if(i===n){dot.className='sd active';}
    else{dot.className='sd';if(line)line.className='sl';}
  }
}

async function checkReg(){
  const b=document.getElementById('regBar');
  try{
    const r=await fetch('/registry-status'); const d=await r.json();
    if(d.status==='ok'&&d.registered_agents>0){
      b.className='sbar ok';
      b.innerHTML=`✅ <strong>${d.registered_agents} agents registered.</strong>
        <a href="http://localhost:8000" target="_blank" style="color:var(--amber2);margin-left:8px;font-weight:600">→ Registry</a>`;
    }else{
      b.className='sbar error';
      b.innerHTML=`❌ No agents. <a href="http://localhost:8000/register" target="_blank" style="color:var(--amber2);margin-left:8px">→ Register Travel Agent + AP2 Payment Agent</a>`;
    }
  }catch(e){b.className='sbar error';b.innerHTML='❌ Registry not reachable.';}
}
window.addEventListener('DOMContentLoaded',()=>{checkReg();setStep(1);});

function addStep(text, cls=''){
  const el=document.getElementById('steps');
  const d=document.createElement('div');
  d.className='step '+(text.includes('❌')?' e':cls);
  d.textContent=text; el.appendChild(d);
  el.scrollTop=el.scrollHeight;
}

async function plan(){
  const btn=document.getElementById('planBtn');
  btn.disabled=true; btn.textContent='⏳ Finding options...';
  document.getElementById('result').style.display='block';
  document.getElementById('steps').innerHTML='';
  document.getElementById('optCard').style.display='none';
  document.getElementById('paySection').style.display='none';
  sf=null; sh=null; setStep(1);
  try{
    const res=await fetch('/plan-trip',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({origin:document.getElementById('orig').value,destination:document.getElementById('dest').value,
        travel_date:document.getElementById('td').value,return_date:document.getElementById('rd').value,
        travelers:parseInt(document.getElementById('tv').value),purpose:document.getElementById('pur').value,
        budget_inr:document.getElementById('bud').value})});
    const data=await res.json();
    (data.steps||[]).forEach(s=>addStep(s));
    if(data.error){addStep(`❌ ${data.error}`);}
    else if(data.trip_plan&&Object.keys(data.trip_plan).length>0){
      tripData=data.trip_plan; renderOpts(tripData);
      document.getElementById('optCard').style.display='block'; setStep(2);
    }
  }catch(e){addStep(`Error: ${e.message}`);}
  btn.disabled=false; btn.textContent='✈️ Find Flights & Hotels';
}

function renderOpts(p){
  const ts=p.trip_summary||{}; const exp=p.expense_estimate||{};
  document.getElementById('tbar').innerHTML=`<div><div class="l">Route</div><div class="v">${ts.origin||''}→${ts.destination||''}</div></div><div><div class="l">Dates</div><div class="v">${ts.travel_date||''}–${ts.return_date||''}</div></div><div><div class="l">Total</div><div class="v c">₹${(ts.estimated_total_cost_inr||0).toLocaleString('en-IN')}</div></div>`;
  const fc=document.getElementById('flts'); fc.innerHTML='';
  (p.flights||[]).forEach((f,i)=>{const rec=(p.recommended_option?.flight||'').includes(f.airline);const d=document.createElement('div');d.className='oc'+(rec?' sel':'');d.onclick=()=>selF(i,d);d.innerHTML=`<div class="ot"><div><div class="on">${f.airline} ${f.flight_number||''}${rec?'<span class="rc2">Rec</span>':''}</div><div class="od">${f.departure||''}→${f.arrival||''}·${f.duration||''}</div><div class="od">₹${(f.total_price_inr||0).toLocaleString('en-IN')}</div></div><div class="op">₹${(f.price_per_person_inr||0).toLocaleString('en-IN')}/pp</div></div>`;fc.appendChild(d);if(rec&&!sf){sf=p.flights[i];chk();}});
  const hc=document.getElementById('htls'); hc.innerHTML='';
  (p.hotels||[]).forEach((h,i)=>{const rec=(p.recommended_option?.hotel||'').includes((h.name||'').split(' ')[0]);const d=document.createElement('div');d.className='oc'+(rec?' sel':'');d.onclick=()=>selH(i,d);d.innerHTML=`<div class="ot"><div><div class="on">${h.name||''} ${'⭐'.repeat(h.rating||0)}</div><div class="od">${h.location||''}</div><div class="od">${h.total_nights||0}n · ₹${(h.total_cost_inr||0).toLocaleString('en-IN')}</div></div><div class="op">₹${(h.price_per_night_inr||0).toLocaleString('en-IN')}/n</div></div>`;hc.appendChild(d);if(rec&&!sh){sh=p.hotels[i];chk();}});
  const exp2=p.expense_estimate||{};
  document.getElementById('expb').innerHTML=`<div class="er"><span>Flights</span><span>₹${(exp2.flights_inr||0).toLocaleString('en-IN')}</span></div><div class="er"><span>Hotel</span><span>₹${(exp2.hotel_inr||0).toLocaleString('en-IN')}</span></div><div class="er"><span>Transport+Meals</span><span>₹${((exp2.ground_transport_inr||0)+(exp2.meals_inr||0)).toLocaleString('en-IN')}</span></div><div class="er"><span>TOTAL</span><span>₹${(exp2.total_inr||0).toLocaleString('en-IN')}</span></div>`;
}

function selF(i,el){document.querySelectorAll('#flts .oc').forEach(c=>c.classList.remove('sel'));el.classList.add('sel');sf=tripData.flights[i];chk();}
function selH(i,el){document.querySelectorAll('#htls .oc').forEach(c=>c.classList.remove('sel'));el.classList.add('sel');sh=tripData.hotels[i];chk();}
function chk(){
  if(sf&&sh){
    document.getElementById('cs').style.display='block';
    const t=(tripData.expense_estimate?.total_inr||0);
    document.getElementById('csum').innerHTML=`<strong>${sf.airline} ${sf.flight_number||''}</strong> + <strong>${sh.name||''}</strong><br><span style="color:var(--amber2);font-weight:700">Total: ₹${t.toLocaleString('en-IN')}</span>`;
  }else{document.getElementById('cs').style.display='none';}
}

async function sendIntent(){
  const btn=document.getElementById('confirmBtn');
  btn.disabled=true; btn.textContent='⏳ Sending IntentMandate...';
  setStep(3);

  // Build cart items for IntentMandate
  const exp=tripData.expense_estimate||{};
  const ts=tripData.trip_summary||{};
  const cart_items=[
    {label:`Flight: ${sf.airline} ${sf.flight_number||''}`,amount:{currency:'INR',value:sf.total_price_inr||0},pending:null},
    {label:`Hotel: ${sh.name||''} (${sh.total_nights||0} nights)`,amount:{currency:'INR',value:sh.total_cost_inr||0},pending:null},
    {label:'Transport + Meals',amount:{currency:'INR',value:(exp.ground_transport_inr||0)+(exp.meals_inr||0)},pending:null}
  ];

  try{
    const res=await fetch('/ap2-intent',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({trip_summary:ts,expense_estimate:exp,selected_flight:sf,selected_hotel:sh,cart_items})});
    const data=await res.json();
    (data.steps||[]).forEach(s=>addStep(s,s.includes('ap2.')||s.includes('Mandate')?'m':'i'));

    if(data.status==='awaiting_user_confirmation'){
      apData=data; setStep(4);
      // Show cart mandate
      const cm=data.cart_mandate||{};
      const contents=cm.contents||{};
      const items=contents.payment_request?.details?.displayItems||[];
      document.getElementById('cartItems').innerHTML=items.map(it=>`<div class="cmb-row"><span>${it.label}</span><span>₹${(it.amount?.value||0).toLocaleString('en-IN')}</span></div>`).join('');
      const total=contents.payment_request?.details?.total?.amount||data.total||{};
      document.getElementById('cartTotal').textContent=`₹${(total.value||0).toLocaleString('en-IN')}`;
      const sig=cm.merchant_signature||'';
      document.getElementById('sigDisplay').textContent=sig.substring(0,35)+'...';
      document.getElementById('paySection').style.display='block';
      document.getElementById('paySection').scrollIntoView({behavior:'smooth',block:'start'});
    }else if(data.error){
      addStep(`❌ ${data.error}`);
    }
  }catch(e){addStep(`Error: ${e.message}`);}
  btn.disabled=false; btn.textContent='🔐 Send IntentMandate to Payment Agent';
}

async function sendPayment(){
  const btn=document.getElementById('payBtn');
  const last4=document.getElementById('cardLast4').value;
  if(last4.length!==4){alert('Enter 4-digit card number');return;}
  btn.disabled=true; btn.textContent='⏳ Signing & Sending PaymentMandate...';
  setStep(5);
  document.getElementById('mf3').className='mf-dot done'; document.getElementById('mf3').textContent='✓';
  document.getElementById('mf4').className='mf-dot active'; document.getElementById('mf4').textContent='4';

  try{
    const res=await fetch('/ap2-pay',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({agent_url:apData.agent_url,cart_id:apData.cart_id,
        order_id:apData.order_id,total:apData.total,
        context_id:apData.context_id,task_id:apData.task_id,card_last4:last4})});
    const data=await res.json();
    (data.steps||[]).forEach(s=>addStep(s,s.includes('Mandate')?'m':'i'));

    if(data.status==='success'){
      setStep(6);
      document.getElementById('mf4').className='mf-dot done'; document.getElementById('mf4').textContent='✓';
      document.getElementById('successSec').style.display='block';
      document.getElementById('bkRef').textContent=data.booking_ref||'BKG------';
      const ns=data.next_steps||[];
      document.getElementById('nextSteps').innerHTML=ns.map(s=>`<div class="step" style="color:var(--muted)">→ ${s}</div>`).join('');
      document.getElementById('actionCards').innerHTML=`<a class="acard" href="/calendar/${confirmedId||'none'}" download><div class="ico">📅</div><div class="at">Calendar (.ics)</div><div class="asu">Google Cal/Outlook</div></a><a class="acard" href="http://localhost:8000/audit" target="_blank"><div class="ico">📋</div><div class="at">Audit Log</div><div class="asu">Full flow record</div></a><a class="acard" href="http://localhost:8000/analytics" target="_blank"><div class="ico">📊</div><div class="at">Analytics</div><div class="asu">Platform stats</div></a>`;
      document.getElementById('successSec').scrollIntoView({behavior:'smooth',block:'start'});
    }else{addStep(`❌ ${data.error||'Payment failed'}`);}
  }catch(e){addStep(`Error: ${e.message}`);}
  btn.disabled=false; btn.textContent='🔐 Sign & Send PaymentMandate';
}
</script>
</body>
</html>"""


# ── Audit logging helper ──────────────────────────────────────────────────────
import httpx as _httpx_audit
import json as _json_audit

async def _log_trip_audit(flow_id, ts, sf, sh, exp, status="completed"):
    try:
        reg = os.getenv("REGISTRY_URL", "http://localhost:8000")
        agents = ["Travel Agent", "AP2 Payment Agent"]
        async with _httpx_audit.AsyncClient(timeout=5.0) as client:
            await client.post(f"{reg}/registry/audit/create", json={
                "flow_id": flow_id, "flow_type": "travel",
                "title": f"Business Trip: {ts.get('origin','')} → {ts.get('destination','')}",
                "subtitle": ts.get("purpose", ""),
                "location": ts.get("destination", "")
            })
            await client.post(f"{reg}/registry/audit/save", json={
                "flow_id": flow_id, "status": status,
                "agents_used": _json_audit.dumps(agents),
                "result_count": 1,
                "result_data": _json_audit.dumps({
                    "flight": f"{sf.get('airline','')} {sf.get('flight_number','')}",
                    "hotel":  sh.get("name", ""),
                    "total_inr": exp.get("total_inr", 0)
                }),
                "completed_at": "now"
            })
    except Exception as e:
        print(f"[Audit] travel log error: {e}")
