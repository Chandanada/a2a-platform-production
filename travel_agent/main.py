"""
Travel Agent — A2A Remote Agent
Skills: search_flights, book_hotel, plan_trip
Uses Groq LLM to simulate realistic travel planning responses.
In production: replace Groq calls with Goibibo / MakeMyTrip / Amadeus API.
"""
import os, json, uuid
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from groq import Groq

load_dotenv()
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
AGENT_BASE_URL = os.getenv("AGENT_BASE_URL", "http://localhost:8005")

groq_client = Groq(api_key=GROQ_API_KEY)
app = FastAPI(title="Travel Agent", version="1.0.0")

AGENT_CARD = {
    "name":        "Travel Agent",
    "description": "Plans complete business trips — searches flights, books hotels, estimates expenses. Powered by AI with real Goibibo/MakeMyTrip API integration in production.",
    "supportedInterfaces": [{"url": AGENT_BASE_URL, "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}],
    "provider":    {"organization": "A2A Platform", "url": os.getenv("REGISTRY_URL", "")},
    "iconUrl":     None, "version": "1.0.0",
    "documentationUrl": os.getenv("REGISTRY_URL","") + "/agents/agents/Travel%20Agent",
    "capabilities": {"streaming": False, "pushNotifications": False,
                     "stateTransitionHistory": False, "extendedAgentCard": False},
    "securitySchemes": None, "security": None,
    "defaultInputModes":  ["application/json"],
    "defaultOutputModes": ["application/json"],
    "skills": [
        {
            "id": "plan_trip", "name": "Plan Business Trip",
            "description": "End-to-end business trip planning: flights, hotel, ground transport, expense estimate.",
            "tags": ["travel", "flight", "hotel", "business-trip", "expense"],
            "examples": ["Plan a 3-day business trip from Bangalore to Mumbai next week",
                         "Book flights and hotel for Delhi conference on April 20"],
            "inputModes": ["application/json"], "outputModes": ["application/json"],
            "securityRequirements": None
        },
        {
            "id": "search_flights", "name": "Search Flights",
            "description": "Search available flights between cities with pricing and timing options.",
            "tags": ["flight", "travel", "goibibo"],
            "examples": ["Find flights Bangalore to Delhi on April 15"],
            "inputModes": ["application/json"], "outputModes": ["application/json"],
            "securityRequirements": None
        },
        {
            "id": "book_hotel", "name": "Book Hotel",
            "description": "Find and book hotels near the meeting location within budget.",
            "tags": ["hotel", "accommodation", "makemytrip"],
            "examples": ["Find 4-star hotel in Connaught Place Delhi under 5000/night"],
            "inputModes": ["application/json"], "outputModes": ["application/json"],
            "securityRequirements": None
        }
    ],
    "signatures": None
}


@app.get("/.well-known/agent-card.json")
def agent_card():
    return JSONResponse(content=AGENT_CARD)

@app.get("/health")
def health():
    return {"status": "ok", "service": "Travel Agent"}

async def call_groq(prompt: str) -> dict:
    resp = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4, max_tokens=2000,
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

    parts     = body.get("params",{}).get("message",{}).get("parts",[])
    user_text = next((p["text"] for p in parts if "text" in p), "")
    data      = next((p["data"] for p in parts if "data" in p), {})

    origin      = data.get("origin", "Bangalore")
    destination = data.get("destination", "Mumbai")
    travel_date = data.get("travel_date", "next Monday")
    return_date = data.get("return_date", "3 days later")
    purpose     = data.get("purpose", "business meeting")
    budget      = data.get("budget_inr", "50000")
    travelers   = data.get("travelers", 1)
    today       = datetime.now().strftime("%B %d, %Y")

    prompt = f"""You are a corporate travel planner. Today is {today}.

Plan a complete business trip:
- Origin: {origin}
- Destination: {destination}  
- Travel date: {travel_date}
- Return date: {return_date}
- Purpose: {purpose}
- Budget: ₹{budget} total
- Travelers: {travelers}

Note: This is a demo. Use realistic Indian pricing. Simulate Goibibo/MakeMyTrip style results.

Return ONLY valid JSON (no markdown):
{{
  "trip_summary": {{
    "origin": "{origin}",
    "destination": "{destination}",
    "travel_date": "actual date",
    "return_date": "actual date",
    "purpose": "{purpose}",
    "total_travelers": {travelers},
    "estimated_total_cost_inr": 32000
  }},
  "flights": [
    {{
      "option": 1,
      "airline": "IndiGo",
      "flight_number": "6E-204",
      "departure": "07:15 AM",
      "arrival": "09:05 AM",
      "duration": "1h 50m",
      "class": "Economy",
      "price_per_person_inr": 6500,
      "total_price_inr": 13000,
      "booking_note": "Demo — would book via Goibibo API in production"
    }},
    {{
      "option": 2,
      "airline": "Air India",
      "flight_number": "AI-501",
      "departure": "10:30 AM",
      "arrival": "12:25 PM",
      "duration": "1h 55m",
      "class": "Economy",
      "price_per_person_inr": 7200,
      "total_price_inr": 14400,
      "booking_note": "Demo — would book via Goibibo API in production"
    }}
  ],
  "hotels": [
    {{
      "option": 1,
      "name": "Hotel name near meeting area",
      "rating": 4,
      "location": "area name, {destination}",
      "price_per_night_inr": 4500,
      "total_nights": 2,
      "total_cost_inr": 9000,
      "amenities": ["WiFi", "Breakfast", "Airport pickup"],
      "booking_note": "Demo — would book via MakeMyTrip API in production"
    }}
  ],
  "ground_transport": {{
    "airport_to_hotel": "Ola/Uber — approx ₹400-600",
    "local_travel": "Ola daily pass — ₹800/day",
    "estimated_total_inr": 2000
  }},
  "expense_estimate": {{
    "flights_inr": 13000,
    "hotel_inr": 9000,
    "ground_transport_inr": 2000,
    "meals_inr": 2500,
    "miscellaneous_inr": 1000,
    "total_inr": 27500,
    "within_budget": true,
    "budget_remaining_inr": 22500
  }},
  "itinerary": [
    {{
      "day": 1,
      "date": "travel date",
      "schedule": ["07:15 Depart {origin}", "09:05 Arrive {destination}", "10:00 Check-in hotel", "14:00 {purpose}", "19:00 Dinner with team"]
    }}
  ],
  "recommended_option": {{
    "flight": "IndiGo 6E-204 — best value",
    "hotel": "first hotel option",
    "reason": "Best combination of cost and convenience"
  }},
  "production_note": "In production, this agent connects to Goibibo API for live flight prices and MakeMyTrip API for hotel inventory with real booking."
}}"""

    result = await call_groq(prompt)

    return JSONResponse({"jsonrpc":"2.0","id":body.get("id","req-001"),
        "result":{"task":{"id":str(uuid.uuid4()),"contextId":str(uuid.uuid4()),
            "status":{"state":"TASK_STATE_COMPLETED"},
            "artifacts":[{"artifactId":str(uuid.uuid4()),"name":"trip_plan",
                "parts":[{"data":result,"mediaType":"application/json"}]}]}}})
