"""
HR Ops Agent — A2A Remote Agent
Skills: review_contract, process_payroll, generate_offer_letter
Uses Groq LLM to simulate HR operations.
In production: connects to Zoho Payroll / Darwinbox / Leegality APIs.
"""
import os, json, uuid
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from groq import Groq

load_dotenv()
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
AGENT_BASE_URL = os.getenv("AGENT_BASE_URL", "http://localhost:8006")

groq_client = Groq(api_key=GROQ_API_KEY)
app = FastAPI(title="HR Ops Agent", version="1.0.0")
@app.get("/health")
def health():
    return {"status": "ok", "service": "hr_ops_agent"}

AGENT_CARD = {
    "name":        "HR Ops Agent",
    "description": "Handles HR operations: generates offer letters, reviews contracts for red flags, processes payroll summaries. Powered by AI with Zoho/Darwinbox integration in production.",
    "supportedInterfaces": [{"url": AGENT_BASE_URL, "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}],
    "provider":    {"organization": "A2A Platform", "url": os.getenv("REGISTRY_URL", "")},
    "iconUrl":     None, "version": "1.0.0",
    "documentationUrl": os.getenv("REGISTRY_URL","") + "/agents/agents/HR%20Ops%20Agent",
    "capabilities": {"streaming": False, "pushNotifications": False,
                     "stateTransitionHistory": False, "extendedAgentCard": False},
    "securitySchemes": None, "security": None,
    "defaultInputModes":  ["application/json"],
    "defaultOutputModes": ["application/json"],
    "skills": [
        {
            "id": "generate_offer_letter", "name": "Generate Offer Letter",
            "description": "Generates a professional offer letter for a selected candidate with salary, role, joining date.",
            "tags": ["hr", "offer", "hiring", "onboarding"],
            "examples": ["Generate offer letter for Rajesh Kumar, Senior Python Engineer, ₹18 LPA, joining May 1"],
            "inputModes": ["application/json"], "outputModes": ["application/json"],
            "securityRequirements": None
        },
        {
            "id": "review_contract", "name": "Review Contract",
            "description": "Reviews vendor or employment contracts for red flags, unusual clauses, missing sections.",
            "tags": ["legal", "contract", "compliance", "review"],
            "examples": ["Review this vendor contract for red flags", "Check NDA for missing clauses"],
            "inputModes": ["application/json"], "outputModes": ["application/json"],
            "securityRequirements": None
        },
        {
            "id": "process_payroll", "name": "Process Payroll Summary",
            "description": "Generates payroll summary for a team with CTC breakdown, deductions, take-home.",
            "tags": ["payroll", "salary", "finance", "hr"],
            "examples": ["Process payroll for 5 engineers this month", "Calculate take-home for CTC of 18 LPA"],
            "inputModes": ["application/json"], "outputModes": ["application/json"],
            "securityRequirements": None
        }
    ],
    "signatures": None
}


@app.get("/.well-known/agent-card.json")
def agent_card():
    return JSONResponse(content=AGENT_CARD)


async def call_groq(prompt: str) -> dict:
    resp = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3, max_tokens=2000,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        raw = raw[4:] if raw.startswith("json") else raw
    try:
        return json.loads(raw.strip())
    except Exception:
        return {"raw_response": raw}


@app.post("/")
async def handle(request: Request):
    body = await request.json()
    if body.get("method") != "SendMessage":
        return JSONResponse({"jsonrpc":"2.0","id":body.get("id"),
            "error":{"code":-32601,"message":"Method not found"}}, status_code=400)

    parts = body.get("params",{}).get("message",{}).get("parts",[])
    data  = next((p["data"] for p in parts if "data" in p), {})
    task  = data.get("task", "generate_offer_letter")
    today = datetime.now().strftime("%B %d, %Y")

    # ── OFFER LETTER ──────────────────────────────────────────────────────────
    if task == "generate_offer_letter":
        candidate  = data.get("candidate_name", "Candidate Name")
        role       = data.get("role", "Software Engineer")
        ctc_lpa    = data.get("ctc_lpa", 15)
        joining    = data.get("joining_date", "May 1, 2026")
        company    = data.get("company_name", "TechCorp India Pvt. Ltd.")
        location   = data.get("location", "Bangalore, Karnataka")

        prompt = f"""You are an experienced HR manager at an Indian tech company. Today is {today}.

Generate a complete, professional offer letter for:
- Candidate: {candidate}
- Role: {role}
- CTC: ₹{ctc_lpa} LPA
- Joining Date: {joining}
- Company: {company}
- Location: {location}

Return ONLY valid JSON (no markdown):
{{
  "offer_letter": {{
    "date": "{today}",
    "candidate_name": "{candidate}",
    "role": "{role}",
    "department": "Engineering",
    "reporting_to": "Engineering Manager",
    "location": "{location}",
    "joining_date": "{joining}",
    "compensation": {{
      "annual_ctc_inr": {int(ctc_lpa * 100000)},
      "annual_ctc_lpa": {ctc_lpa},
      "basic_salary_monthly": 0,
      "hra_monthly": 0,
      "special_allowance_monthly": 0,
      "pf_employer_monthly": 0,
      "take_home_approx_monthly": 0
    }},
    "benefits": ["Health insurance (self + family)", "21 days paid leave", "Work from home 2 days/week", "Annual performance bonus", "Learning & development budget ₹50,000/year"],
    "probation_period": "3 months",
    "notice_period": "2 months after confirmation",
    "offer_validity": "7 days from date of issue",
    "letter_body": "Full formal offer letter text here — 3-4 professional paragraphs",
    "signatory": "HR Manager, {company}"
  }},
  "status": "generated",
  "next_steps": ["Send to candidate for e-signature", "Update ATS status to Offered", "Initiate background verification", "Prepare onboarding kit"],
  "production_note": "In production, this integrates with Leegality for e-signature and Darwinbox for HRMS auto-update."
}}"""

    # ── CONTRACT REVIEW ──────────────────────────────────────────────────────
    elif task == "review_contract":
        contract_type = data.get("contract_type", "Vendor Agreement")
        vendor        = data.get("vendor_name", "Vendor Company")
        value         = data.get("contract_value", "₹5,00,000")

        prompt = f"""You are an experienced corporate lawyer reviewing an Indian business contract.

Contract details:
- Type: {contract_type}
- Vendor: {vendor}
- Value: {value}
- Review date: {today}

Simulate a thorough contract review. Return ONLY valid JSON (no markdown):
{{
  "review_summary": {{
    "contract_type": "{contract_type}",
    "vendor": "{vendor}",
    "value": "{value}",
    "review_date": "{today}",
    "overall_risk": "Medium",
    "recommendation": "Approve with modifications"
  }},
  "red_flags": [
    {{"clause": "Clause name", "issue": "What the issue is", "severity": "High/Medium/Low", "recommendation": "What to do"}}
  ],
  "missing_clauses": ["List of important clauses that should be added"],
  "favorable_clauses": ["Clauses that are good for your company"],
  "suggested_changes": [
    {{"original": "Original clause text", "suggested": "Suggested replacement", "reason": "Why this change"}}
  ],
  "legal_compliance": {{
    "companies_act_2013": "Compliant / Non-compliant / Partial",
    "it_act_2000": "Compliant",
    "gst_clauses": "Present / Missing",
    "arbitration_clause": "Present / Missing"
  }},
  "production_note": "In production, this integrates with Leegality contract management and flags to your legal team via Slack."
}}"""

    # ── PAYROLL ───────────────────────────────────────────────────────────────
    else:
        employees = data.get("employees", [])
        month     = data.get("month", datetime.now().strftime("%B %Y"))

        if not employees:
            employees = [
                {"name": "Rajesh Kumar",    "role": "Senior Engineer",   "ctc_lpa": 18},
                {"name": "Priya Sharma",    "role": "Product Manager",   "ctc_lpa": 22},
                {"name": "Ankit Verma",     "role": "Junior Engineer",   "ctc_lpa": 8},
                {"name": "Meera Nair",      "role": "UX Designer",       "ctc_lpa": 14},
                {"name": "Rohit Agarwal",   "role": "DevOps Engineer",   "ctc_lpa": 16},
            ]

        prompt = f"""You are a payroll specialist in India. Process payroll for {month}.

Employees:
{json.dumps(employees, indent=2)}

Return ONLY valid JSON (no markdown):
{{
  "payroll_month": "{month}",
  "processed_on": "{today}",
  "summary": {{
    "total_employees": {len(employees)},
    "total_gross_payroll_inr": 0,
    "total_deductions_inr": 0,
    "total_net_payroll_inr": 0,
    "total_employer_pf_inr": 0,
    "total_cost_to_company_inr": 0
  }},
  "employee_payslips": [
    {{
      "name": "employee name",
      "role": "role",
      "ctc_lpa": 0,
      "monthly_gross_inr": 0,
      "basic_inr": 0,
      "hra_inr": 0,
      "special_allowance_inr": 0,
      "deductions": {{
        "pf_employee_inr": 0,
        "professional_tax_inr": 200,
        "income_tax_tds_inr": 0,
        "total_deductions_inr": 0
      }},
      "net_take_home_inr": 0,
      "employer_pf_inr": 0,
      "status": "Processed"
    }}
  ],
  "bank_transfer_file": "bank_transfer_{month.replace(' ','_')}.csv",
  "compliance": {{
    "pf_challan_due": "15th of next month",
    "pt_challan_due": "Last day of month",
    "tds_payment_due": "7th of next month"
  }},
  "production_note": "In production, this integrates with Zoho Payroll / Darwinbox for automated salary disbursement."
}}"""

    result = await call_groq(prompt)

    return JSONResponse({"jsonrpc":"2.0","id":body.get("id","req-001"),
        "result":{"task":{"id":str(uuid.uuid4()),"contextId":str(uuid.uuid4()),
            "status":{"state":"TASK_STATE_COMPLETED"},
            "artifacts":[{"artifactId":str(uuid.uuid4()),"name":"hr_ops_result",
                "parts":[{"data":result,"mediaType":"application/json"}]}]}}})
