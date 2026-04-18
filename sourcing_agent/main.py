"""
Candidate Sourcing Agent — v3 (GitHub-Powered)
================================================
- Fetches REAL developer profiles from GitHub public API
- Uses Groq LLM ONLY to enrich with match score and salary estimate
- Serves official A2A Agent Card at /.well-known/agent-card.json
- Handles A2A SendMessage (JSON-RPC 2.0)
- NO auto-registration — developer registers manually
- ZERO contact with real profiles — read only
"""
import os, json, uuid, httpx, re
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from groq import Groq

load_dotenv()
GROQ_API_KEY    = os.getenv("GROQ_API_KEY")
GITHUB_TOKEN    = os.getenv("GITHUB_TOKEN")
AGENT_BASE_URL  = os.getenv("AGENT_BASE_URL", "http://localhost:8001")

groq_client = Groq(api_key=GROQ_API_KEY)

app = FastAPI(title="Candidate Sourcing Agent", version="3.0.0")

AGENT_CARD = {
    "name":        "Candidate Sourcing Agent",
    "description": "Finds real developer profiles from GitHub public API based on role requirements. Uses AI to assess match quality. Returns real public profiles enriched with AI-generated match scores.",
    "supportedInterfaces": [{"url": AGENT_BASE_URL, "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}],
    "provider":    {"organization": "A2A Hiring Platform", "url": os.getenv("REGISTRY_URL", "")},
    "iconUrl":     None,
    "version":     "3.0.0",
    "documentationUrl": os.getenv("REGISTRY_URL","") + "/agents/agents/Candidate%20Sourcing%20Agent",
    "capabilities": {
        "streaming": False, "pushNotifications": False,
        "stateTransitionHistory": False, "extendedAgentCard": False
    },
    "securitySchemes": None, "security": None,
    "defaultInputModes":  ["text/plain", "application/json"],
    "defaultOutputModes": ["application/json"],
    "skills": [{
        "id":          "find_candidates",
        "name":        "Find Candidates",
        "description": "Searches GitHub public API for real developers matching job requirements. Returns real public profiles with AI-enriched match analysis.",
        "tags":        ["hiring", "recruitment", "sourcing", "github", "developers"],
        "examples":    [
            "Find 3 Senior Python Engineers with 5 years experience",
            "Source React frontend developers in Bangalore"
        ],
        "inputModes":  ["text/plain", "application/json"],
        "outputModes": ["application/json"],
        "securityRequirements": None
    }],
    "signatures": None
}


@app.get("/.well-known/agent-card.json")
def get_agent_card():
    return JSONResponse(content=AGENT_CARD)


async def search_github_developers(language: str, min_followers: int = 10, count: int = 3) -> list:
    """
    Search real GitHub developers by programming language.
    Uses GitHub public search API — read only, no contact made.
    """
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    query = f"language:{language} followers:>{min_followers} repos:>5"

    async with httpx.AsyncClient() as client:
        # Search users
        search_resp = await client.get(
            "https://api.github.com/search/users",
            params={"q": query, "sort": "followers", "order": "desc", "per_page": 10},
            headers=headers,
            timeout=15.0
        )
        search_data = search_resp.json()
        users = search_data.get("items", [])[:count * 2]  # fetch extra in case some have no details

        profiles = []
        for user in users:
            if len(profiles) >= count:
                break
            try:
                # Fetch full profile for each user
                profile_resp = await client.get(
                    f"https://api.github.com/users/{user['login']}",
                    headers=headers,
                    timeout=10.0
                )
                profile = profile_resp.json()

                # Fetch their top repos to understand skills
                repos_resp = await client.get(
                    f"https://api.github.com/users/{user['login']}/repos",
                    params={"sort": "stars", "per_page": 5},
                    headers=headers,
                    timeout=10.0
                )
                repos = repos_resp.json()

                # Extract real languages from repos
                languages = list(set(
                    r.get("language") for r in repos
                    if r.get("language")
                ))[:5]

                profiles.append({
                    "login":       profile.get("login"),
                    "name":        profile.get("name") or profile.get("login"),
                    "bio":         profile.get("bio") or "No bio provided",
                    "location":    profile.get("location") or "Not specified",
                    "company":     profile.get("company") or "Not specified",
                    "github_url":  profile.get("html_url"),
                    "avatar_url":  profile.get("avatar_url"),
                    "public_repos": profile.get("public_repos", 0),
                    "followers":   profile.get("followers", 0),
                    "languages":   languages,
                    "top_repos":   [
                        {
                            "name":  r.get("name"),
                            "stars": r.get("stargazers_count"),
                            "description": r.get("description") or ""
                        }
                        for r in repos[:3]
                    ],
                    "data_source": "GitHub Public API — read only"
                })
            except Exception:
                continue

    return profiles


async def enrich_with_ai(profiles: list, job_title: str, experience: int, location: str) -> list:
    """
    Use Groq LLM ONLY to add match score and salary estimate.
    All profile data remains from GitHub — LLM only adds analysis.
    """
    prompt = f"""You are an expert tech recruiter. 

Job requirement: {job_title}, {experience} years experience, location: {location}

Here are real GitHub developer profiles. For each, provide ONLY a match assessment.
Do NOT invent or change any profile details.

Profiles:
{json.dumps(profiles, indent=2)}

Return ONLY valid JSON (no markdown):
{{
  "enriched_candidates": [
    {{
      "github_login": "their_login",
      "match_score": 85,
      "match_reason": "Why they match the role based on their real GitHub data",
      "estimated_experience_years": 5,
      "estimated_salary_range": "$90,000 - $120,000",
      "availability": "Unknown — contact via GitHub",
      "ai_enriched": true,
      "ai_disclaimer": "Match score and salary are AI estimates only. Profile data is from GitHub public API."
    }}
  ]
}}"""

    resp = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2000,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        raw = raw[4:] if raw.startswith("json") else raw
    try:
        enriched = json.loads(raw.strip())
        return enriched.get("enriched_candidates", [])
    except Exception:
        return []


@app.post("/")
async def handle_message(request: Request):
    body = await request.json()
    if body.get("method") != "SendMessage":
        return JSONResponse(content={
            "jsonrpc": "2.0", "id": body.get("id"),
            "error": {"code": -32601, "message": "Method not found"}
        }, status_code=400)

    parts     = body.get("params", {}).get("message", {}).get("parts", [])
    user_text = next((p["text"] for p in parts if "text" in p), "")

    # Extract job details from request
    data_part = next((p["data"] for p in parts if "data" in p), {})
    job_title  = data_part.get("job_title", "Software Engineer")
    experience = data_part.get("experience_years", 3)
    location   = data_part.get("location", "Remote")

    # Detect programming language from job title
    language_map = {
        "python": "python", "javascript": "javascript", "js": "javascript",
        "react": "javascript", "node": "javascript", "java": "java",
        "golang": "go", "go": "go", "rust": "rust", "ruby": "ruby",
        "php": "php", "swift": "swift", "kotlin": "kotlin",
        "typescript": "typescript", "ts": "typescript",
        "data scientist": "python", "ml engineer": "python",
        "machine learning": "python", "ai engineer": "python",
    }
    detected_language = "python"  # default
    job_lower = job_title.lower()
    for keyword, lang in language_map.items():
        if keyword in job_lower:
            detected_language = lang
            break

    # Step 1 — Fetch real GitHub profiles
    github_profiles = await search_github_developers(
        language=detected_language,
        min_followers=10,
        count=3
    )

    if not github_profiles:
        return JSONResponse(content={
            "jsonrpc": "2.0", "id": body.get("id", "req-001"),
            "error": {"code": -32000, "message": "No GitHub profiles found. Check GitHub token."}
        })

    # Step 2 — AI enrichment (match score + salary only)
    enriched = await enrich_with_ai(github_profiles, job_title, experience, location)

    # Step 3 — Merge real data with AI analysis
    candidates = []
    for i, profile in enumerate(github_profiles):
        ai_data = next(
            (e for e in enriched if e.get("github_login") == profile["login"]),
            {}
        )
        candidates.append({
            # Real data from GitHub
            "id":           f"candidate_{i+1}",
            "name":         profile["name"],
            "github_login": profile["login"],
            "github_url":   profile["github_url"],
            "location":     profile["location"],
            "company":      profile["company"],
            "bio":          profile["bio"],
            "languages":    profile["languages"],
            "public_repos": profile["public_repos"],
            "followers":    profile["followers"],
            "top_repos":    profile["top_repos"],
            "data_source":  "GitHub Public API",

            # AI estimates — clearly labeled
            "match_score":              ai_data.get("match_score", 0),
            "match_reason":             ai_data.get("match_reason", ""),
            "estimated_experience":     ai_data.get("estimated_experience_years", "Unknown"),
            "estimated_salary":         ai_data.get("estimated_salary_range", "Unknown"),
            "availability":             "Unknown — contact via GitHub",
            "ai_enriched":              True,
            "ai_disclaimer":            "Match score and salary are AI estimates only. Profile data is from GitHub public API."
        })

    result = {
        "job_analysis": {
            "role":             job_title,
            "detected_language": detected_language,
            "experience_required": experience,
            "location":         location,
            "data_source":      "GitHub Public API (real profiles)"
        },
        "candidates":     candidates,
        "total_found":    len(candidates),
        "sourcing_note":  "All profiles are real GitHub users with public profiles. AI estimates are for match scoring only. No candidates were contacted."
    }

    return JSONResponse(content={
        "jsonrpc": "2.0", "id": body.get("id", "req-001"),
        "result": {
            "task": {
                "id": str(uuid.uuid4()), "contextId": str(uuid.uuid4()),
                "status": {"state": "TASK_STATE_COMPLETED"},
                "artifacts": [{
                    "artifactId": str(uuid.uuid4()),
                    "name": "sourced_candidates",
                    "parts": [{"data": result, "mediaType": "application/json"}]
                }]
            }
        }
    })
