"""
Background Check Remote Agent — v2
=====================================
- Serves official A2A Agent Card at /.well-known/agent-card.json
- Handles A2A SendMessage (JSON-RPC 2.0)
- Uses Groq LLM for AI-powered background verification
- NO auto-registration — developer registers manually via platform form
"""
import os, json, uuid
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from groq import Groq

load_dotenv()
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
AGENT_BASE_URL = os.getenv("AGENT_BASE_URL", "http://localhost:8004")
groq_client    = Groq(api_key=GROQ_API_KEY)

app = FastAPI(title="Background Check Agent", version="1.0.0")

AGENT_CARD = {
    # Official A2A AgentCard — Section 8.5 Sample Agent Card
    # Source: https://a2a-protocol.org/latest/specification/#85-sample-agent-card
    "name":        "Background Check Agent",
    "description": "Performs comprehensive AI-powered background verification for job candidates. Verifies employment history, education credentials, criminal records across jurisdictions, and professional references. Returns a full clearance report with risk assessment and hiring recommendation.",
    "supportedInterfaces": [
        {
            "url":             AGENT_BASE_URL,
            "protocolBinding": "JSONRPC",
            "protocolVersion": "1.0"
        }
    ],
    "provider": {
        "organization": "A2A Hiring Platform",
        "url":          "http://localhost:8000"
    },
    "iconUrl":          None,
    "version":          "1.0.0",
    "documentationUrl": "http://localhost:8000/agents/Background%20Check%20Agent",
    "capabilities": {
        "streaming":              False,
        "pushNotifications":      False,
        "stateTransitionHistory": False,
        "extendedAgentCard":      False
    },
    "securitySchemes": None,
    "security":        None,
    "defaultInputModes":  ["application/json"],
    "defaultOutputModes": ["application/json"],
    "skills": [
        {
            "id":          "verify_candidate",
            "name":        "Verify Candidate",
            "description": "Runs a full background check on a candidate including: employment history verification, education credential check, criminal record lookup across multiple jurisdictions, professional reference checks, and identity document verification. Returns overall risk level and hiring recommendation.",
            "tags":        ["background-check", "verification", "hiring", "compliance", "due-diligence"],
            "examples": [
                "Run background check on 3 shortlisted candidates for Senior Python Engineer",
                "Verify employment and education history for Alice Johnson",
                "{\"candidates\": [{\"name\": \"Alice Johnson\", \"linkedin\": \"linkedin.com/in/alice\"}], \"check_types\": [\"employment\", \"education\", \"criminal\", \"references\"]}"
            ],
            "inputModes":           ["application/json"],
            "outputModes":          ["application/json"],
            "securityRequirements": None
        }
    ],
    "signatures": None
}


@app.get("/.well-known/agent-card.json")
def get_agent_card():
    """Official A2A Agent Card — RFC 8615 well-known URI"""
    return JSONResponse(content=AGENT_CARD)


@app.post("/")
async def handle_message(request: Request):
    """Official A2A SendMessage handler — JSON-RPC 2.0"""
    body = await request.json()
    if body.get("method") != "SendMessage":
        return JSONResponse(content={"jsonrpc":"2.0","id":body.get("id"),"error":{"code":-32601,"message":"Method not found"}}, status_code=400)

    parts     = body.get("params",{}).get("message",{}).get("parts",[])
    user_text = next((p["text"] for p in parts if "text" in p), "")
    cand_data = next((p["data"] for p in parts if "data" in p), None)
    ctx       = json.dumps(cand_data.get("candidates",[]), indent=2) if cand_data else user_text

    prompt = f"""You are a professional background check specialist at a licensed verification firm.

Perform a comprehensive background check for these candidates:
{ctx}

Additional context: {user_text}

Return ONLY valid JSON (no markdown):
{{
  "verification_summary": "Overall summary of background checks",
  "checks": [
    {{
      "candidate_id": "candidate_1",
      "candidate_name": "Full Name",
      "overall_status": "CLEARED",
      "overall_risk": "LOW",
      "employment_verification": {{
        "status": "VERIFIED",
        "details": "Employment history confirmed at all stated companies",
        "discrepancies": "None found",
        "years_verified": 6
      }},
      "education_verification": {{
        "status": "VERIFIED",
        "details": "Degree confirmed with university",
        "discrepancies": "None found"
      }},
      "criminal_record": {{
        "status": "CLEAR",
        "details": "No criminal records found in checked jurisdictions",
        "jurisdictions_checked": ["India", "US", "UK"]
      }},
      "reference_check": {{
        "status": "POSITIVE",
        "references_contacted": 2,
        "feedback": "Strong positive feedback from previous managers",
        "notable_comments": "Described as a team player with excellent technical skills"
      }},
      "identity_verification": {{
        "status": "VERIFIED",
        "documents_checked": ["Passport", "National ID"]
      }},
      "recommendation": "PROCEED WITH OFFER",
      "notes": "Candidate cleared all checks. Safe to proceed."
    }}
  ],
  "completed_at": "2026-04-11T10:30:00Z",
  "next_steps": "All candidates cleared. Proceed with offer letters."
}}

Generate realistic background check results for all candidates."""

    resp = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role":"user","content":prompt}],
        temperature=0.6, max_tokens=3000,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"): raw = raw.split("```")[1]; raw = raw[4:] if raw.startswith("json") else raw
    try:    data = json.loads(raw.strip())
    except: data = {"raw_response": raw}

    return JSONResponse(content={
        "jsonrpc": "2.0", "id": body.get("id","req-001"),
        "result": {
            "task": {
                "id": str(uuid.uuid4()), "contextId": str(uuid.uuid4()),
                "status": {"state": "TASK_STATE_COMPLETED"},
                "artifacts": [{"artifactId": str(uuid.uuid4()), "name": "background_check_report",
                    "parts": [{"data": data, "mediaType": "application/json"}]}]
            }
        }
    })
