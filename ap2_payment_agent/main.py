"""
Payment Agent — AP2 Protocol (Fixed)
Simplified and robust version that won't silently crash.
"""
import os, json, uuid, hmac, hashlib, smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

load_dotenv()
GMAIL_SENDER        = os.getenv("GMAIL_SENDER", "chandannov2291@gmail.com")
GMAIL_APP_PASS      = os.getenv("GMAIL_APP_PASS", "unkfnvhzezhpsycf")
AGENT_BASE_URL      = os.getenv("AGENT_BASE_URL", "http://localhost:8009")
REGISTRY_URL        = os.getenv("REGISTRY_URL", "http://localhost:8000")
DEMO_SIGNING_SECRET = os.getenv("DEMO_SIGNING_SECRET", "ap2-demo-signing-secret-2026")
NOTIFY_EMAILS       = os.getenv("INTERVIEW_NOTIFY_EMAILS",
                                 "chandannov2291@gmail.com,dubeyneha1191@gmail.com").split(",")

AP2_EXTENSION_URI = "https://github.com/google-agentic-commerce/ap2/tree/v0.1"

app = FastAPI(title="AP2 Payment Agent", version="0.1.0")
@app.get("/health")
def health():
    return {"status": "ok", "service": "ap2_payment_agent"}

# In-memory cart store
_pending_carts: dict = {}

AGENT_CARD = {
    "name": "AP2 Payment Agent",
    "description": "Implements Agent Payments Protocol (AP2) v0.1. Roles: merchant + payment-processor. Produces CartMandate artifacts. Accepts PaymentMandate messages.",
    "supportedInterfaces": [{"url": AGENT_BASE_URL, "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}],
    "provider": {"organization": "A2A Platform", "url": REGISTRY_URL},
    "iconUrl": None, "version": "0.1.0",
    "documentationUrl": f"{REGISTRY_URL}/agents/AP2%20Payment%20Agent",
    "capabilities": {
        "streaming": False, "pushNotifications": False,
        "stateTransitionHistory": True, "extendedAgentCard": False,
        "extensions": [{
            "uri": AP2_EXTENSION_URI,
            "description": "AP2 v0.1 merchant + payment-processor roles",
            "params": {"roles": ["merchant", "payment-processor"]},
            "required": True
        }]
    },
    "securitySchemes": None, "security": None,
    "defaultInputModes": ["application/json"],
    "defaultOutputModes": ["application/json"],
    "skills": [{
        "id": "process_payment", "name": "Process AP2 Payment",
        "description": "AP2 human-present payment: IntentMandate → CartMandate → PaymentMandate",
        "tags": ["payment", "ap2", "booking", "cart-mandate", "payment-mandate"],
        "examples": ["Book trip Bangalore→Mumbai via AP2 CartMandate"],
        "inputModes": ["application/json"], "outputModes": ["application/json"],
        "securityRequirements": None
    }],
    "signatures": None
}


def sign_mandate(payload: dict) -> str:
    payload_bytes = json.dumps(payload, sort_keys=True).encode()
    sig = hmac.new(DEMO_SIGNING_SECRET.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return f"demo-hmac-sha256:{sig}"


def verify_user_authorization(payment_mandate: dict) -> bool:
    user_auth = payment_mandate.get("user_authorization", "")
    contents  = payment_mandate.get("payment_mandate_contents", {})
    expected  = sign_mandate(contents)
    return hmac.compare_digest(user_auth, expected)


def send_booking_email(booking_ref: str, amount: dict) -> bool:
    try:
        html = f"""<html><body style="font-family:sans-serif;padding:20px">
<div style="max-width:500px;margin:0 auto;background:#fff;border-radius:12px;border:1px solid #e2e8f0;padding:24px">
  <h2 style="color:#065f46">🎉 AP2 Booking Confirmed</h2>
  <p>Booking Reference: <strong>{booking_ref}</strong></p>
  <p>Amount: <strong>{amount.get('currency','')} {amount.get('value',0):,}</strong></p>
  <p>Protocol: Agent Payments Protocol (AP2) v0.1</p>
  <p style="color:#92400e;font-size:12px">⚠️ Demo — no real charge made.</p>
</div></body></html>"""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"✈️ AP2 Booking Confirmed #{booking_ref}"
        msg["From"]    = f"A2A Travel Platform <{GMAIL_SENDER}>"
        msg["To"]      = ", ".join(NOTIFY_EMAILS)
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(GMAIL_SENDER, GMAIL_APP_PASS)
            s.sendmail(GMAIL_SENDER, NOTIFY_EMAILS, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


def wrap(body: dict, task_id: str, context_id: str,
         data: dict, state: str = "TASK_STATE_COMPLETED") -> JSONResponse:
    return JSONResponse({
        "jsonrpc": "2.0", "id": body.get("id", "req-001"),
        "result": {
            "task": {
                "id": task_id, "contextId": context_id,
                "status": {"state": state},
                "artifacts": [{
                    "artifactId": str(uuid.uuid4()),
                    "name": "ap2_result",
                    "parts": [{"kind": "data", "data": data, "mediaType": "application/json"}]
                }]
            }
        }
    })


@app.get("/.well-known/agent-card.json")
def agent_card():
    return JSONResponse(content=AGENT_CARD)


@app.post("/")
async def handle(request: Request):
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse({"jsonrpc": "2.0", "id": None,
            "error": {"code": -32700, "message": f"Parse error: {e}"}}, status_code=400)

    if body.get("method") != "SendMessage":
        return JSONResponse({"jsonrpc": "2.0", "id": body.get("id"),
            "error": {"code": -32601, "message": "Method not found"}}, status_code=400)

    parts      = body.get("params", {}).get("message", {}).get("parts", [])
    context_id = body.get("params", {}).get("message", {}).get("contextId", str(uuid.uuid4()))
    task_id    = body.get("params", {}).get("message", {}).get("taskId",    str(uuid.uuid4()))

    print(f"\n[AP2] Received message with {len(parts)} parts")
    for i, p in enumerate(parts):
        print(f"  Part {i}: keys={list(p.keys())}")

    # Check for PaymentMandate
    pay_part = next(
        (p for p in parts if "ap2.mandates.PaymentMandate" in p.get("data", {})), None
    )
    if pay_part:
        print("[AP2] Processing PaymentMandate...")
        return handle_payment(body, pay_part, context_id, task_id)

    # Check for IntentMandate (AP2 format)
    intent_part = next(
        (p for p in parts if "ap2.mandates.IntentMandate" in p.get("data", {})), None
    )
    if intent_part:
        print("[AP2] Processing IntentMandate...")
        return handle_intent(body, intent_part, context_id, task_id)

    # Fallback: any data part (for backward compat)
    data_part = next((p for p in parts if "data" in p and p.get("data")), None)
    if data_part:
        print("[AP2] Fallback: treating data part as IntentMandate...")
        d = data_part["data"]
        fake_intent = {
            "data": {
                "ap2.mandates.IntentMandate": {
                    "natural_language_description": str(d),
                    "cart_items":   d.get("cart_items", []),
                    "total_amount": d.get("total_amount",
                                          {"currency": "INR",
                                           "value": d.get("expense_estimate", {}).get("total_inr", 0)}),
                    "user_cart_confirmation_required": True,
                    "intent_expiry": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
                }
            }
        }
        return handle_intent(body, fake_intent, context_id, task_id)

    print("[AP2] ERROR: No recognizable mandate found")
    return JSONResponse({"jsonrpc": "2.0", "id": body.get("id"),
        "error": {"code": -32602,
                  "message": "Expected ap2.mandates.IntentMandate or ap2.mandates.PaymentMandate"}},
        status_code=400)


def handle_intent(body: dict, intent_part: dict,
                  context_id: str, task_id: str) -> JSONResponse:
    try:
        intent = intent_part["data"]["ap2.mandates.IntentMandate"]
        cart_items   = intent.get("cart_items", [])
        total_amount = intent.get("total_amount", {"currency": "INR", "value": 0})

        cart_id  = f"cart_{uuid.uuid4().hex[:8]}"
        order_id = f"order_{uuid.uuid4().hex[:8]}"
        now_iso  = datetime.now(timezone.utc).isoformat()

        # Build CartMandate per AP2 spec
        cart_contents = {
            "id": cart_id,
            "user_signature_required": True,
            "payment_request": {
                "method_data": [{
                    "supported_methods": "CARD",
                    "data": {"payment_processor_url": AGENT_BASE_URL,
                             "supported_networks": ["Visa", "Mastercard", "RuPay"]}
                }],
                "details": {
                    "id": order_id,
                    "displayItems": cart_items if cart_items else [{
                        "label": intent.get("natural_language_description", "Trip booking"),
                        "amount": total_amount, "pending": None
                    }],
                    "total": {"label": "Total", "amount": total_amount, "pending": None}
                },
                "options": {
                    "requestPayerName": True, "requestPayerEmail": True,
                    "requestPayerPhone": False, "requestShipping": False
                }
            }
        }

        merchant_signature = sign_mandate(cart_contents)
        cart_mandate = {
            "contents": cart_contents,
            "merchant_signature": merchant_signature,
            "timestamp": now_iso
        }

        # Store for verification
        _pending_carts[cart_id] = {
            "cart_mandate": cart_mandate,
            "order_id": order_id,
            "total": total_amount,
            "created_at": now_iso
        }

        print(f"[AP2] CartMandate created: cart_id={cart_id}")

        return JSONResponse({
            "jsonrpc": "2.0", "id": body.get("id", "req-001"),
            "result": {
                "task": {
                    "id": task_id, "contextId": context_id,
                    "status": {"state": "TASK_STATE_INPUT_REQUIRED"},
                    "artifacts": [{
                        "artifactId": str(uuid.uuid4()),
                        "name": "AP2 CartMandate",
                        "parts": [
                            {"kind": "data", "data": {"ap2.mandates.CartMandate": cart_mandate}},
                            {"kind": "data", "data": {
                                "ap2_extension_uri": AP2_EXTENSION_URI,
                                "ap2_agent_roles": ["merchant", "payment-processor"],
                                "next_step": "Send ap2.mandates.PaymentMandate to complete"
                            }}
                        ]
                    }]
                }
            }
        })
    except Exception as e:
        print(f"[AP2] ERROR in handle_intent: {e}")
        import traceback; traceback.print_exc()
        return wrap(body, task_id, context_id,
                    {"status": "ERROR", "error": str(e)}, "TASK_STATE_FAILED")


def handle_payment(body: dict, pay_part: dict,
                   context_id: str, task_id: str) -> JSONResponse:
    try:
        pm       = pay_part["data"]["ap2.mandates.PaymentMandate"]
        contents = pm.get("payment_mandate_contents", {})
        cart_id  = contents.get("cart_id", "")
        total    = contents.get("payment_details_total", {})

        # Verify signature
        if not verify_user_authorization(pm):
            return wrap(body, task_id, context_id,
                {"status": "MANDATE_INVALID",
                 "error": "user_authorization signature verification failed."
                }, "TASK_STATE_FAILED")

        # Find cart
        pending = _pending_carts.get(cart_id)
        if not pending:
            return wrap(body, task_id, context_id,
                {"status": "CART_NOT_FOUND",
                 "error": f"CartMandate {cart_id} not found or expired."
                }, "TASK_STATE_FAILED")

        booking_ref  = f"BKG{uuid.uuid4().hex[:8].upper()}"
        amount       = total.get("amount", pending["total"])
        email_sent   = send_booking_email(booking_ref, amount)
        del _pending_carts[cart_id]

        print(f"[AP2] Payment SUCCESS: booking_ref={booking_ref}")

        return wrap(body, task_id, context_id, {
            "status":          "PAYMENT_SUCCESS",
            "booking_ref":     booking_ref,
            "order_id":        contents.get("payment_details_id", ""),
            "amount_charged":  amount,
            "timestamp":       datetime.now(timezone.utc).isoformat(),
            "email_sent":      email_sent,
            "ap2_protocol":    "Agent Payments Protocol v0.1",
            "mandate_chain": {
                "intent_mandate":  "Received ✓",
                "cart_mandate":    "Produced + merchant_signature ✓",
                "payment_mandate": "Verified user_authorization ✓"
            },
            "next_steps": [
                "Add trip to calendar using the .ics download",
                "Web check-in opens 48 hours before departure",
                "Booking confirmation email sent"
            ]
        })
    except Exception as e:
        print(f"[AP2] ERROR in handle_payment: {e}")
        import traceback; traceback.print_exc()
        return wrap(body, task_id, context_id,
                    {"status": "ERROR", "error": str(e)}, "TASK_STATE_FAILED")
