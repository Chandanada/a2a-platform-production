"""
HR Ops Dashboard — A2A Client Agent
Discovers HR Ops Agent from registry and performs:
- Offer letter generation
- Contract review  
- Payroll processing
"""
import os, uuid, json, httpx, smtplib, hashlib, base64
from io import BytesIO
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, Response

load_dotenv()
REGISTRY_URL    = os.getenv("REGISTRY_URL", "http://localhost:8000")
HR_DASHBOARD_URL = os.getenv("HR_DASHBOARD_URL", "https://hr-dashboard-ttt2.onrender.com")
GMAIL_SENDER    = os.getenv("GMAIL_SENDER", "chandannov2291@gmail.com")
GMAIL_APP_PASS  = os.getenv("GMAIL_APP_PASS", "unkfnvhzezhpsycf")
OFFER_SECRET    = os.getenv("OFFER_SECRET", "hr-offer-secret-2026")
app = FastAPI(title="HR Ops Dashboard", version="1.0.0")


def _make_fallback_pdf(ol: dict, company: str) -> bytes:
    """Pure-Python minimal PDF — no dependencies, always works."""
    comp   = ol.get("compensation", {})
    name   = ol.get("candidate_name", "Candidate")
    role   = ol.get("role", "Software Engineer")
    ctc    = comp.get("annual_ctc_lpa", ol.get("ctc_lpa", ""))
    join   = ol.get("joining_date", "")
    loc    = ol.get("location", "")
    dept   = ol.get("department", "Engineering")
    prob   = ol.get("probation_period", "3 months")
    notice = ol.get("notice_period", "2 months")
    valid  = ol.get("offer_validity", "7 days from issue")
    sign   = ol.get("signatory", f"HR Manager, {company}")
    body   = ol.get("letter_body", f"We are delighted to offer you the position of {role} at {company}.")[:1200]
    bens   = ol.get("benefits", [])
    date   = ol.get("date", datetime.now().strftime("%B %d, %Y"))

    def esc(s): return str(s).replace("\\","\\\\").replace("(","\\(").replace(")","\\)")

    lines = [
        f"OFFER OF EMPLOYMENT",
        f"{company}",
        f"Date: {date}",
        f"",
        f"Dear {name},",
        f"",
    ]
    # word-wrap body
    import textwrap
    for para in body.split("\n"):
        for ln in textwrap.wrap(para, 90) or [""]:
            lines.append(ln)
    lines += [
        "", "=" * 60,
        "COMPENSATION & OFFER DETAILS",
        "=" * 60,
        f"Candidate Name  : {name}",
        f"Role            : {role}",
        f"Annual CTC      : INR {ctc} LPA",
        f"Department      : {dept}",
        f"Location        : {loc}",
        f"Joining Date    : {join}",
        f"Probation       : {prob}",
        f"Notice Period   : {notice}",
        f"Offer Valid For : {valid}",
        "", "=" * 60,
        "BENEFITS",
        "=" * 60,
    ]
    for b in bens:
        lines.append(f"  * {b}")
    lines += [
        "", "=" * 60,
        "E-SIGNATURE",
        "=" * 60,
        "By clicking the Accept Offer button in the email, you confirm that you",
        "have read, understood, and agree to all terms of this offer. Your",
        "acceptance constitutes a legally binding agreement.",
        "",
        f"Authorised Signatory: {sign}",
        "Candidate Acceptance: (via email acceptance link)",
        "",
        f"This is a system-generated offer letter from {company} | Confidential",
    ]

    # Build PDF streams per page (72 lines per page)
    page_size = 72
    pages = [lines[i:i+page_size] for i in range(0, len(lines), page_size)]
    if not pages:
        pages = [[""]]

    objects = []
    # obj 1: catalog, obj 2: pages, obj 3: font, then pairs (page, content) per page
    objects.append(None)  # placeholder index 0

    # Font object (will be obj 3)
    font_obj = b"<</Type /Font /Subtype /Type1 /BaseFont /Courier>>"

    # Build page content streams
    page_streams = []
    for pg in pages:
        ops = ["BT", "/F1 10 Tf", "50 780 Td", "12 TL"]
        for ln in pg:
            ops.append(f"({esc(ln)}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode()
        page_streams.append(stream)

    # Assign object numbers:
    # 1=catalog, 2=pages, 3=font
    # then for each page: 4+2i = page dict, 5+2i = content stream
    n_pages = len(page_streams)
    catalog_num = 1
    pages_num   = 2
    font_num    = 3
    first_page_num = 4

    def obj(num, content):
        return f"{num} 0 obj\n".encode() + content + b"\nendobj\n"

    buf = b"%PDF-1.4\n"
    offsets = {}

    # catalog
    offsets[catalog_num] = len(buf)
    buf += obj(catalog_num, f"<</Type /Catalog /Pages {pages_num} 0 R>>".encode())

    # pages
    kids = " ".join(f"{first_page_num + 2*i} 0 R" for i in range(n_pages))
    offsets[pages_num] = len(buf)
    buf += obj(pages_num, f"<</Type /Pages /Kids [{kids}] /Count {n_pages}>>".encode())

    # font
    offsets[font_num] = len(buf)
    buf += obj(font_num, font_obj)

    # page dicts + content streams
    for i, stream in enumerate(page_streams):
        pg_num      = first_page_num + 2 * i
        content_num = first_page_num + 2 * i + 1
        # content stream
        offsets[content_num] = len(buf)
        stream_obj = (f"<</Length {len(stream)}>>\nstream\n").encode() + stream + b"\nendstream"
        buf += obj(content_num, stream_obj)
        # page dict
        offsets[pg_num] = len(buf)
        buf += obj(pg_num, (
            f"<</Type /Page /Parent {pages_num} 0 R "
            f"/MediaBox [0 0 595 842] "
            f"/Contents {content_num} 0 R "
            f"/Resources <</Font <</F1 {font_num} 0 R>>>>>>"
        ).encode())

    # xref
    xref_pos = len(buf)
    total_obj = 1 + font_num + n_pages * 2
    buf += f"xref\n0 {total_obj + 1}\n0000000000 65535 f \n".encode()
    for i in range(1, total_obj + 1):
        off = offsets.get(i, 0)
        buf += f"{off:010d} 00000 n \n".encode()
    buf += (
        f"trailer\n<</Size {total_obj + 1} /Root {catalog_num} 0 R>>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    return buf


def generate_offer_pdf(ol: dict, company: str) -> bytes:
    """Generate offer letter PDF — uses fpdf2 if available, otherwise built-in."""
    try:
        from fpdf import FPDF
        comp = ol.get("compensation", {})
        pdf = FPDF()
        pdf.add_page()
        pdf.set_margins(20, 20, 20)
        pdf.set_fill_color(30, 20, 60)
        pdf.rect(0, 0, 210, 28, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_xy(20, 8)
        pdf.cell(0, 12, company, ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(20, 19)
        pdf.cell(0, 6, "OFFER OF EMPLOYMENT - CONFIDENTIAL", ln=True)
        pdf.set_text_color(30, 30, 30)
        pdf.set_y(36)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, f"Date: {ol.get('date', datetime.now().strftime('%B %d, %Y'))}", ln=True)
        pdf.ln(4)
        pdf.set_text_color(30, 30, 30)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, f"Dear {ol.get('candidate_name', 'Candidate')},", ln=True)
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 10)
        body = ol.get("letter_body", f"We are delighted to offer you the position of {ol.get('role','Software Engineer')} at {company}.")
        pdf.multi_cell(0, 6, body[:800])
        pdf.ln(6)
        pdf.set_fill_color(245, 240, 255)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(60, 30, 120)
        pdf.cell(0, 9, "COMPENSATION & BENEFITS", ln=True, fill=True)
        pdf.set_text_color(30, 30, 30)
        rows = [
            ("Annual CTC", f"INR {comp.get('annual_ctc_lpa', ol.get('ctc_lpa',''))} LPA"),
            ("Role", ol.get("role", "")),
            ("Department", ol.get("department", "Engineering")),
            ("Location", ol.get("location", "")),
            ("Joining Date", ol.get("joining_date", "")),
            ("Probation Period", ol.get("probation_period", "3 months")),
            ("Notice Period", ol.get("notice_period", "2 months")),
            ("Offer Valid Until", ol.get("offer_validity", "7 days")),
        ]
        for label, val in rows:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(70, 7, label, border="B")
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 7, str(val), border="B", ln=True)
        pdf.ln(5)
        pdf.set_fill_color(230, 255, 240)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(10, 100, 60)
        pdf.cell(0, 9, "BENEFITS", ln=True, fill=True)
        pdf.set_text_color(30, 30, 30)
        pdf.set_font("Helvetica", "", 10)
        for b in ol.get("benefits", []):
            pdf.cell(6, 6, "-")
            pdf.cell(0, 6, str(b), ln=True)
        pdf.ln(8)
        pdf.set_fill_color(255, 245, 230)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(150, 80, 0)
        pdf.cell(0, 9, "E-SIGNATURE REQUIRED", ln=True, fill=True)
        pdf.set_text_color(60, 60, 60)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, "By clicking Accept Offer in your email, you confirm agreement to all terms of this offer.")
        pdf.ln(8)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(80, 6, "Authorised Signatory:", border=0)
        pdf.cell(0, 6, "Candidate Acceptance:", border=0, ln=True)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(80, 8, ol.get("signatory", f"HR Manager, {company}"), border="T")
        pdf.cell(0, 8, "(via email acceptance link)", border="T", ln=True)
        pdf.set_y(-18)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 6, f"System-generated by A2A HR Platform | {company} | Confidential", align="C")
        return bytes(pdf.output())
    except Exception as e:
        print(f"[fpdf2 failed: {e}] — using built-in PDF generator")
        return _make_fallback_pdf(ol, company)

def send_offer_email(candidate_email: str, candidate_name: str, role: str,
                     company: str, pdf_bytes: bytes, accept_url: str, reject_url: str = "") -> bool:
    """Send offer letter PDF to candidate with acceptance link."""
    if not GMAIL_SENDER or not GMAIL_APP_PASS:
        return False
    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"Offer Letter — {role} at {company}"
        msg["From"]    = f"{company} HR <{GMAIL_SENDER}>"
        msg["To"]      = candidate_email

        html_body = f"""
<!DOCTYPE html><html>
<body style="font-family:'Segoe UI',sans-serif;background:#f8fafc;padding:20px">
<div style="max-width:600px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">
  <div style="background:linear-gradient(135deg,#1e0a3c,#3b1278);padding:28px 32px">
    <h1 style="color:#fff;margin:0;font-size:20px">🎉 Congratulations, {candidate_name}!</h1>
    <p style="color:#c4b5fd;margin:8px 0 0;font-size:13px">{company} — Offer of Employment</p>
  </div>
  <div style="padding:28px 32px">
    <p style="color:#1e293b;font-size:15px;line-height:1.7">
      We are thrilled to extend an offer of employment for the position of <strong>{role}</strong> at <strong>{company}</strong>.
    </p>
    <p style="color:#64748b;font-size:14px;line-height:1.7">
      Please find your detailed offer letter attached as a PDF. Kindly review all the terms and conditions carefully before accepting.
    </p>

    <div style="background:#f1f5f9;border-radius:12px;padding:20px;margin:20px 0;text-align:center">
      <p style="color:#1e293b;font-size:14px;font-weight:600;margin:0 0 6px">Please review the attached PDF offer letter, then respond:</p>
      <p style="color:#64748b;font-size:12px;margin:0 0 18px">You must respond within 7 days of receiving this offer.</p>
      <div style="display:flex;gap:14px;justify-content:center;flex-wrap:wrap">
        <a href="{accept_url}" style="display:inline-block;background:linear-gradient(135deg,#10b981,#059669);color:#fff;text-decoration:none;padding:14px 32px;border-radius:10px;font-weight:700;font-size:15px">
          ✅ Accept Offer
        </a>
        <a href="{reject_url}" style="display:inline-block;background:#fff;color:#ef4444;border:2px solid #ef4444;text-decoration:none;padding:14px 32px;border-radius:10px;font-weight:700;font-size:15px">
          ❌ Decline Offer
        </a>
      </div>
      <p style="color:#94a3b8;font-size:11px;margin:14px 0 0">By accepting, you confirm agreement to all terms in the attached PDF.</p>
    </div>

    <div style="border-top:1px solid #e2e8f0;padding-top:16px;margin-top:16px">
      <p style="color:#94a3b8;font-size:12px;margin:0">
        ⚠️ This offer is valid for <strong>7 days</strong> from the date of issue.<br/>
        For any queries, reply to this email.
      </p>
    </div>
  </div>
  <div style="background:#f1f5f9;padding:14px 32px;text-align:center">
    <p style="color:#94a3b8;font-size:11px;margin:0">Generated by A2A HR Platform · {company}</p>
  </div>
</div>
</body></html>"""

        msg.attach(MIMEText(html_body, "html"))

        # Attach PDF
        if pdf_bytes:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(pdf_bytes)
            encoders.encode_base64(part)
            safe_name = f"Offer_Letter_{candidate_name.replace(' ','_')}.pdf"
            part.add_header("Content-Disposition", f'attachment; filename="{safe_name}"')
            msg.attach(part)

        # Try port 587
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=25) as smtp:
                smtp.ehlo(); smtp.starttls(); smtp.ehlo()
                smtp.login(GMAIL_SENDER, GMAIL_APP_PASS)
                smtp.sendmail(GMAIL_SENDER, [candidate_email], msg.as_string())
            return True
        except Exception:
            pass
        # Try port 465
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=25) as smtp:
            smtp.login(GMAIL_SENDER, GMAIL_APP_PASS)
            smtp.sendmail(GMAIL_SENDER, [candidate_email], msg.as_string())
        return True
    except Exception as e:
        print(f"[offer email] error: {e}")
        return False


def make_accept_token(candidate_name: str, role: str, company: str) -> str:
    raw = f"{candidate_name}|{role}|{company}|{OFFER_SECRET}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


@app.post("/send-offer-email")
async def send_offer_email_endpoint(request: Request):
  try:
    body           = await request.json()
    offer_data     = body.get("offer_data", {})
    candidate_email = body.get("candidate_email", "")
    ol = offer_data.get("offer_letter", offer_data)

    if not candidate_email:
        return JSONResponse({"success": False, "error": "candidate_email required"})

    candidate_name = ol.get("candidate_name", "Candidate")
    role           = ol.get("role", "Software Engineer")
    company        = ol.get("company_name") or body.get("company_name", "TechCorp India Pvt. Ltd.")

    token      = make_accept_token(candidate_name, role, company)
    accept_url = f"{HR_DASHBOARD_URL}/accept-offer?token={token}&name={candidate_name.replace(' ','%20')}&role={role.replace(' ','%20')}&company={company.replace(' ','%20')}"
    reject_url = f"{HR_DASHBOARD_URL}/reject-offer?token={token}&name={candidate_name.replace(' ','%20')}&role={role.replace(' ','%20')}&company={company.replace(' ','%20')}"

    try:
        pdf_bytes = generate_offer_pdf(ol, company)
    except Exception as e:
        print(f"[PDF gen] error: {e}")
        pdf_bytes = b""

    try:
        sent = send_offer_email(candidate_email, candidate_name, role, company, pdf_bytes, accept_url, reject_url)
    except Exception as e:
        return JSONResponse({"success": False, "error": f"Email failed: {str(e)[:200]}", "accept_url": accept_url})

    return JSONResponse({
        "success": sent,
        "email_sent_to": candidate_email,
        "accept_url": accept_url,
        "pdf_generated": len(pdf_bytes) > 0,
        "message": f"Offer letter emailed to {candidate_email} with PDF and acceptance link" if sent else "Email failed — check GMAIL_SENDER/GMAIL_APP_PASS env vars on Render"
    })
  except Exception as e:
    return JSONResponse({"success": False, "error": f"Server error: {str(e)[:200]}"})


def _offer_page_style():
    return """<style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:'Segoe UI',sans-serif;background:linear-gradient(135deg,#0a0f1e,#1a0a3c);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}.card{background:#fff;border-radius:20px;padding:48px;max-width:580px;width:100%;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,0.3)}.icon{font-size:64px;margin-bottom:20px}.title{font-size:28px;font-weight:800;color:#1e293b;margin-bottom:8px}.sub{color:#64748b;font-size:15px;line-height:1.7;margin-bottom:24px}.badge{display:inline-flex;align-items:center;gap:8px;padding:10px 24px;border-radius:30px;font-size:14px;font-weight:700;margin-bottom:24px}.info{background:#f8fafc;border-radius:12px;padding:20px;text-align:left;margin-bottom:16px}.info-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #e2e8f0;font-size:14px}.info-row:last-child{border:none}.info-label{color:#64748b}.info-val{font-weight:600;color:#1e293b}textarea{width:100%;border:1px solid #e2e8f0;border-radius:10px;padding:12px;font-size:14px;font-family:inherit;resize:vertical;min-height:100px;margin-bottom:16px}.reject-btn{width:100%;background:#ef4444;color:#fff;border:none;padding:14px;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer}.ts{font-size:12px;color:#94a3b8;margin-top:12px}</style>"""


@app.get("/accept-offer")
async def accept_offer_page(token: str = "", name: str = "", role: str = "", company: str = ""):
    expected = make_accept_token(name, role, company)
    valid    = token == expected
    timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    if not valid:
        return HTMLResponse("""<!DOCTYPE html><html><body style="font-family:sans-serif;text-align:center;padding:60px">
<h1>❌ Invalid or Expired Link</h1><p>Please contact HR for assistance.</p></body></html>""")

    # Notify HR of acceptance via email
    try:
        _notify_hr_decision(name, role, company, "ACCEPTED", "", timestamp)
    except Exception:
        pass

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"/><title>Offer Accepted</title>{_offer_page_style()}</head><body>
<div class="card">
  <div class="icon">🎉</div>
  <h1 class="title">Offer Accepted!</h1>
  <p class="sub">Congratulations, <strong>{name}</strong>! Your e-signature has been recorded. HR will contact you shortly with onboarding details.</p>
  <div class="badge" style="background:#ecfdf5;border:1px solid #6ee7b7;color:#047857">✅ E-Signature Confirmed</div>
  <div class="info">
    <div class="info-row"><span class="info-label">Candidate</span><span class="info-val">{name}</span></div>
    <div class="info-row"><span class="info-label">Role</span><span class="info-val">{role}</span></div>
    <div class="info-row"><span class="info-label">Company</span><span class="info-val">{company}</span></div>
    <div class="info-row"><span class="info-label">Accepted On</span><span class="info-val">{timestamp}</span></div>
  </div>
  <p class="ts">HR has been notified. Reference: {token[:12].upper()}</p>
</div></body></html>"""
    return HTMLResponse(html)


@app.get("/reject-offer")
async def reject_offer_page(token: str = "", name: str = "", role: str = "", company: str = ""):
    expected = make_accept_token(name, role, company)
    valid    = token == expected
    if not valid:
        return HTMLResponse("""<!DOCTYPE html><html><body style="font-family:sans-serif;text-align:center;padding:60px">
<h1>❌ Invalid Link</h1><p>Please contact HR for assistance.</p></body></html>""")

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"/><title>Decline Offer</title>{_offer_page_style()}</head><body>
<div class="card">
  <div class="icon">😔</div>
  <h1 class="title">Decline Offer</h1>
  <p class="sub">We are sorry to see you go, <strong>{name}</strong>. Please let us know your reason so we can improve our process.</p>
  <div class="info">
    <div class="info-row"><span class="info-label">Role</span><span class="info-val">{role}</span></div>
    <div class="info-row"><span class="info-label">Company</span><span class="info-val">{company}</span></div>
  </div>
  <textarea id="reason" placeholder="Please share your reason for declining (e.g. salary, location, competing offer, personal reasons...)"></textarea>
  <button class="reject-btn" onclick="submitReject()">❌ Confirm Decline &amp; Notify HR</button>
  <p class="ts" id="msg"></p>
</div>
<script>
async function submitReject() {{
  const reason = document.getElementById('reason').value.trim();
  if (!reason) {{ document.getElementById('msg').textContent = 'Please enter a reason before submitting.'; return; }}
  document.querySelector('.reject-btn').disabled = true;
  document.querySelector('.reject-btn').textContent = '⏳ Submitting...';
  const r = await fetch('/submit-rejection', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{token: '{token}', name: '{name}', role: '{role}', company: '{company}', reason}})
  }});
  const d = await r.json();
  if (d.success) {{
    document.querySelector('.card').innerHTML = '<div class="icon">📨</div><h1 class="title">Response Recorded</h1><p class="sub">Thank you for letting us know, <strong>{name}</strong>. Your response and reason have been sent to the HR team.</p><div class="badge" style="background:#fef2f2;border:1px solid #fca5a5;color:#dc2626">❌ Offer Declined</div>';
  }} else {{
    document.getElementById('msg').textContent = 'Submission failed. Please try again.';
    document.querySelector('.reject-btn').disabled = false;
    document.querySelector('.reject-btn').textContent = '❌ Confirm Decline & Notify HR';
  }}
}}
</script></body></html>"""
    return HTMLResponse(html)


@app.post("/submit-rejection")
async def submit_rejection(request: Request):
    try:
        body    = await request.json()
        token   = body.get("token", "")
        name    = body.get("name", "")
        role    = body.get("role", "")
        company = body.get("company", "")
        reason  = body.get("reason", "No reason given")
        expected = make_accept_token(name, role, company)
        if token != expected:
            return JSONResponse({"success": False, "error": "Invalid token"})
        timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        _notify_hr_decision(name, role, company, "DECLINED", reason, timestamp)
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


def _notify_hr_decision(name: str, role: str, company: str, decision: str, reason: str, timestamp: str):
    """Send email to HR when candidate accepts or declines."""
    if not GMAIL_SENDER or not GMAIL_APP_PASS:
        return
    is_accept = decision == "ACCEPTED"
    color  = "#10b981" if is_accept else "#ef4444"
    emoji  = "🎉" if is_accept else "😔"
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"{emoji} Offer {decision}: {name} — {role}"
    msg["From"]    = f"A2A HR Platform <{GMAIL_SENDER}>"
    msg["To"]      = GMAIL_SENDER
    reason_html = f"""<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:10px;padding:16px;margin-top:16px">
      <p style="font-weight:700;color:#dc2626;margin:0 0 8px">Reason for declining:</p>
      <p style="color:#1e293b;font-size:14px;margin:0">{reason}</p>
    </div>""" if not is_accept else ""
    html = f"""<!DOCTYPE html><html><body style="font-family:'Segoe UI',sans-serif;background:#f8fafc;padding:20px">
<div style="max-width:560px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">
  <div style="background:{color};padding:24px 32px">
    <h1 style="color:#fff;margin:0;font-size:18px">{emoji} Offer {decision.title()}: {name}</h1>
    <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:13px">{role} at {company}</p>
  </div>
  <div style="padding:24px 32px">
    <table style="width:100%;font-size:14px;border-collapse:collapse">
      <tr><td style="padding:8px 0;color:#64748b;width:120px">Candidate</td><td style="font-weight:600">{name}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b">Role</td><td style="font-weight:600">{role}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b">Company</td><td style="font-weight:600">{company}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b">Decision</td><td style="font-weight:700;color:{color}">{decision}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b">Timestamp</td><td>{timestamp}</td></tr>
    </table>
    {reason_html}
  </div>
  <div style="background:#f1f5f9;padding:14px 32px;text-align:center">
    <p style="color:#94a3b8;font-size:11px;margin:0">A2A HR Platform — Automated Notification</p>
  </div>
</div></body></html>"""
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=25) as smtp:
            smtp.ehlo(); smtp.starttls(); smtp.ehlo()
            smtp.login(GMAIL_SENDER, GMAIL_APP_PASS)
            smtp.sendmail(GMAIL_SENDER, [GMAIL_SENDER], msg.as_string())
    except Exception:
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=25) as smtp:
                smtp.login(GMAIL_SENDER, GMAIL_APP_PASS)
                smtp.sendmail(GMAIL_SENDER, [GMAIL_SENDER], msg.as_string())
        except Exception as e:
            print(f"[HR notify] error: {e}")


async def discover_agent(skill: str) -> dict | None:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{REGISTRY_URL}/registry/discover",
                                 params={"skill": skill}, timeout=10.0)
            agents = r.json().get("agents", [])
            return agents[0] if agents else None
    except Exception as e:
        print(f"[discover_agent] skill={skill} error: {e}")
        return None


async def send_message(agent_url: str, text: str, data: dict = None) -> dict:
    parts = [{"text": text, "mediaType": "text/plain"}]
    if data:
        parts.append({"data": data, "mediaType": "application/json"})
    payload = {"jsonrpc": "2.0", "id": f"req-{str(uuid.uuid4())[:8]}",
               "method": "SendMessage",
               "params": {"message": {"role": "user", "messageId": str(uuid.uuid4()), "parts": parts}}}
    import asyncio
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(agent_url, json=payload)
                if r.status_code >= 500:
                    if attempt < 2: await asyncio.sleep(15); continue
                    return {"error": f"HTTP {r.status_code} after retries"}
                try:
                    return r.json()
                except Exception:
                    if r.text and attempt == 2:
                        return {"error": f"Non-JSON (HTTP {r.status_code}): {r.text[:200]}"}
                    if attempt < 2: await asyncio.sleep(15); continue
        except Exception as e:
            if attempt < 2: await asyncio.sleep(15); continue
            return {"error": str(e)}
    return {"error": "All retries failed"}

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
  try:
    body    = await request.json()
    task    = body.get("task", "generate_offer_letter")
    flow_id = str(uuid.uuid4())
    report  = {"flow_id": flow_id, "steps": [], "result": {}, "status": "in_progress", "task": task}
    def step(msg): report["steps"].append(msg)

    # All 3 tasks use the same hr_ops skill — that's what the agent is registered with
    skill = "hr_ops"

    step("🔍 Querying registry for HR Ops Agent...")
    agent = await discover_agent(skill)
    if not agent:
        report["status"] = "failed"
        report["error"]  = "No HR Ops Agent found in registry. Register it with skill: hr_ops"
        return JSONResponse(report)

    url = agent["supportedInterfaces"][0]["url"]
    step(f"✅ Found: {agent['name']} at {url}")

    # Wake up Render — free tier cold starts return 502
    step("🔔 Waking up HR Ops Agent (Render cold start may take 30s)...")
    import asyncio
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                ping = await client.get(f"{url}/health")
                if ping.status_code < 500:
                    step("✅ HR Ops Agent is awake")
                    break
                if attempt < 2:
                    step(f"⏳ Still starting, waiting... (attempt {attempt+1}/3)")
                    await asyncio.sleep(15)
        except Exception:
            if attempt < 2:
                await asyncio.sleep(15)

    step(f"📤 Sending {task} request via A2A SendMessage...")
    try:
        resp = await send_message(url, f"HR Ops task: {task}", data=body)
        if resp.get("error") and "result" not in resp:
            report["status"] = "failed"
            report["error"]  = resp.get("error", "Agent error")[:120]
            step(f"❌ {report['error']}")
            return JSONResponse(report)
        result = extract_artifact(resp)
        report["result"] = result
        report["status"] = "completed"
        step("✅ HR Ops task completed!")
        # Log to audit trail
        try:
            await _log_hr_audit(flow_id, task, "completed")
        except Exception:
            pass
    except Exception as e:
        report["status"] = "failed"
        report["error"]  = str(e)[:120]
        step(f"❌ {report['error']}")

    return JSONResponse(report)

  except Exception as e:
    return JSONResponse({"steps": [f"❌ Server error: {str(e)}"], "status": "failed", "result": {}})


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
      <a href="https://a2a-platform-production-production.up.railway.app" target="_blank">Registry</a>
      <a href="https://hiring-dashboard-cpcp.onrender.com" target="_blank">Hiring</a>
      <a href="https://trip-dashboard-xav2.onrender.com" target="_blank">Travel</a>
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
        <div class="field"><label>Candidate Email *</label><input id="o-email" type="email" value="chandannov2291@gmail.com" placeholder="candidate@email.com"/></div>
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
        <a href="https://a2a-platform-production-production.up.railway.app" target="_blank" style="color:#f9a8d4;margin-left:10px;font-weight:600">→ Registry</a>`;
    } else {
      bar.className = 'status-bar error';
      bar.innerHTML = `❌ No agents registered. <a href="https://a2a-platform-production-production.up.railway.app/register" target="_blank" style="color:#f9a8d4;margin-left:8px;font-weight:600">→ Register HR Ops Agent</a>`;
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
      d.innerHTML = `❌ ${data.error} <a href="https://a2a-platform-production-production.up.railway.app/register" target="_blank" style="color:#f9a8d4;margin-left:6px">→ Register HR Ops Agent</a>`;
      el.appendChild(d);
    }
    if (data.result && Object.keys(data.result).length > 0) {
      document.getElementById('resultCard').style.display = 'block';
      renderResult(t, data.result);
      if (t === 'offer') window._lastOfferData = data.result;
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
      <div class="result-section">
        <h3>📧 Send to Candidate</h3>
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <input id="send-email-addr" type="email" placeholder="candidate@email.com"
            value="${document.getElementById('o-email')?.value||''}"
            style="flex:1;min-width:200px;background:#080c1a;border:1px solid var(--border);color:var(--text);padding:10px 12px;border-radius:8px;font-size:13px;outline:none"/>
          <button onclick="sendOfferEmail()" style="background:linear-gradient(135deg,#7c3aed,#ec4899);color:#fff;border:none;padding:11px 22px;border-radius:8px;font-weight:700;font-size:13px;cursor:pointer;white-space:nowrap">
            📧 Email PDF + Acceptance Link
          </button>
        </div>
        <div id="email-status" style="margin-top:10px;font-size:13px"></div>
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
async function sendOfferEmail() {
  const email = document.getElementById('send-email-addr')?.value?.trim();
  const statusEl = document.getElementById('email-status');
  if (!email) { statusEl.innerHTML = '<span style="color:#f87171">Please enter candidate email</span>'; return; }
  if (!window._lastOfferData) { statusEl.innerHTML = '<span style="color:#f87171">Generate offer letter first</span>'; return; }

  statusEl.innerHTML = '<span style="color:#a78bfa">⏳ Generating PDF and sending email...</span>';

  try {
    const res = await fetch('/send-offer-email', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        offer_data: window._lastOfferData,
        candidate_email: email,
        company_name: document.getElementById('o-company')?.value || 'TechCorp India Pvt. Ltd.'
      })
    });
    const data = await res.json();
    if (data.success) {
      statusEl.innerHTML = `<span style="color:#10b981">✅ ${data.message}</span><br/>
        <span style="font-size:11px;color:#64748b">Acceptance link: <a href="${data.accept_url}" target="_blank" style="color:#a78bfa">${data.accept_url.substring(0,60)}...</a></span>`;
    } else {
      statusEl.innerHTML = `<span style="color:#f87171">❌ ${data.error || data.message}</span>`;
    }
  } catch(e) {
    statusEl.innerHTML = `<span style="color:#f87171">❌ Error: ${e.message}</span>`;
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
        labels = {
            "generate_offer_letter": "Offer Letter Generated",
            "review_contract":       "Contract Reviewed",
            "process_payroll":       "Payroll Processed"
        }
        async with _httpx_hr.AsyncClient(timeout=5.0) as client:
            await client.post(f"{REGISTRY_URL}/registry/audit/create", json={
                "flow_id": flow_id, "flow_type": "hr_ops",
                "title":   labels.get(task, task),
                "subtitle": task, "location": "HR Operations"
            })
            await client.post(f"{REGISTRY_URL}/registry/audit/save", json={
                "flow_id": flow_id, "status": status,
                "agents_used": _json_hr.dumps(["HR Ops Agent"]),
                "result_count": 1, "completed_at": "now"
            })
    except Exception as e:
        print(f"[Audit] hr log error: {e}")
