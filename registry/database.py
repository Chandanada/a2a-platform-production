"""
Registry Database — PostgreSQL production
Supports: agents, api_keys, audit_logs (hiring + travel + hr_ops)
"""
import os, json, hashlib
import psycopg2
import psycopg2.extras
from urllib.parse import urlparse

DATABASE_URL = os.getenv("DATABASE_URL", "")

def get_connection():
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require",
                                cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        raise RuntimeError("DATABASE_URL env var not set")
    return conn


def init_db():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id            SERIAL PRIMARY KEY,
            name          TEXT NOT NULL UNIQUE,
            description   TEXT NOT NULL,
            version       TEXT NOT NULL DEFAULT '1.0.0',
            agent_url     TEXT NOT NULL,
            skills        TEXT NOT NULL DEFAULT '[]',
            tags          TEXT NOT NULL DEFAULT '[]',
            input_modes   TEXT NOT NULL DEFAULT '["application/json"]',
            output_modes  TEXT NOT NULL DEFAULT '["application/json"]',
            status        TEXT NOT NULL DEFAULT 'active',
            registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id           SERIAL PRIMARY KEY,
            key_hash     TEXT NOT NULL UNIQUE,
            label        TEXT NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_used_at TIMESTAMPTZ,
            is_active    BOOLEAN NOT NULL DEFAULT TRUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id             SERIAL PRIMARY KEY,
            flow_id        TEXT NOT NULL,
            flow_type      TEXT NOT NULL DEFAULT 'hiring',
            title          TEXT NOT NULL,
            subtitle       TEXT,
            location       TEXT,
            status         TEXT NOT NULL DEFAULT 'in_progress',
            agents_used    TEXT,
            result_count   INTEGER DEFAULT 0,
            result_data    TEXT,
            secondary_data TEXT,
            tertiary_data  TEXT,
            emails_sent_to TEXT,
            extra_data     TEXT,
            experience_years INTEGER DEFAULT 0,
            started_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at   TIMESTAMPTZ,
            error_message  TEXT
        )
    """)

    # Default API key
    cur.execute("SELECT COUNT(*) AS cnt FROM api_keys")
    row = cur.fetchone()
    if (row["cnt"] if row else 0) == 0:
        default_key = "a2a-admin-key-changeme-in-production"
        key_hash = hashlib.sha256(default_key.encode()).hexdigest()
        cur.execute("INSERT INTO api_keys (key_hash, label) VALUES (%s, %s)",
                    (key_hash, "Default Admin Key"))
        print(f"[Registry] Default API key: {default_key}")

    conn.commit()
    cur.close()
    conn.close()
    print("[Registry] Database initialised ✅")


def verify_api_key(key: str) -> bool:
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("SELECT id FROM api_keys WHERE key_hash=%s AND is_active=TRUE", (key_hash,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE api_keys SET last_used_at=NOW() WHERE key_hash=%s", (key_hash,))
        conn.commit()
    cur.close(); conn.close()
    return row is not None


def register_agent(name, description, agent_url, skills, tags,
                   version="1.0.0", input_modes=None, output_modes=None) -> dict:
    input_modes  = input_modes  or ["application/json"]
    output_modes = output_modes or ["application/json"]
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO agents (name, description, agent_url, skills, tags,
                            version, input_modes, output_modes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (name) DO UPDATE SET
            description=EXCLUDED.description,
            agent_url=EXCLUDED.agent_url,
            skills=EXCLUDED.skills,
            tags=EXCLUDED.tags,
            version=EXCLUDED.version,
            updated_at=NOW()
        RETURNING *
    """, (name, description, agent_url,
          json.dumps(skills), json.dumps(tags),
          version, json.dumps(input_modes), json.dumps(output_modes)))
    row = dict(cur.fetchone())
    conn.commit(); cur.close(); conn.close()
    return row


def get_all_agents(status="active") -> list:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM agents WHERE status=%s ORDER BY registered_at DESC", (status,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    for r in rows:
        for f in ("skills","tags","input_modes","output_modes"):
            if r.get(f): r[f] = json.loads(r[f]) if isinstance(r[f],str) else r[f]
    return rows


def get_agent_by_name(name: str) -> dict | None:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM agents WHERE name=%s", (name,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row: return None
    r = dict(row)
    for f in ("skills","tags","input_modes","output_modes"):
        if r.get(f): r[f] = json.loads(r[f]) if isinstance(r[f],str) else r[f]
    return r


def discover_agents_by_skill(skill: str) -> list:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        SELECT * FROM agents
        WHERE status='active' AND skills::text ILIKE %s
        ORDER BY registered_at DESC
    """, (f'%{skill}%',))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    for r in rows:
        for f in ("skills","tags","input_modes","output_modes"):
            if r.get(f): r[f] = json.loads(r[f]) if isinstance(r[f],str) else r[f]
    return rows


def create_audit_log(flow_id, title, subtitle="", location="",
                     flow_type="hiring", experience_years=0):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO audit_logs (flow_id, flow_type, title, subtitle, location, experience_years)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (flow_id, flow_type, title, subtitle, location, experience_years))
    conn.commit(); cur.close(); conn.close()


def update_audit_log(flow_id: str, **kwargs):
    if not kwargs: return
    conn = get_connection(); cur = conn.cursor()
    sets = ", ".join(f"{k}=%s" for k in kwargs)
    vals = list(kwargs.values()) + [flow_id]
    cur.execute(f"UPDATE audit_logs SET {sets} WHERE flow_id=%s", vals)
    conn.commit(); cur.close(); conn.close()


def get_audit_logs(limit=100, flow_type=None) -> list:
    conn = get_connection(); cur = conn.cursor()
    if flow_type:
        cur.execute("SELECT * FROM audit_logs WHERE flow_type=%s ORDER BY started_at DESC LIMIT %s",
                    (flow_type, limit))
    else:
        cur.execute("SELECT * FROM audit_logs ORDER BY started_at DESC LIMIT %s", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    for r in rows:
        for f in ("agents_used","result_data","secondary_data","tertiary_data","emails_sent_to"):
            if r.get(f):
                try: r[f] = json.loads(r[f])
                except: pass
        # Serialize timestamps
        for f in ("started_at","completed_at"):
            if r.get(f): r[f] = str(r[f])
    return rows


def get_audit_log(flow_id: str) -> dict | None:
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT * FROM audit_logs WHERE flow_id=%s", (flow_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row: return None
    r = dict(row)
    for f in ("agents_used","result_data","secondary_data","tertiary_data","emails_sent_to"):
        if r.get(f):
            try: r[f] = json.loads(r[f])
            except: pass
    for f in ("started_at","completed_at"):
        if r.get(f): r[f] = str(r[f])
    return r


def get_analytics() -> dict:
    conn = get_connection(); cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS c FROM audit_logs")
    total_flows = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM audit_logs WHERE status='completed'")
    completed = cur.fetchone()["c"]

    cur.execute("SELECT COALESCE(SUM(result_count),0) AS c FROM audit_logs WHERE flow_type='hiring'")
    total_candidates = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) AS c FROM agents WHERE status='active'")
    total_agents = cur.fetchone()["c"]

    cur.execute("""
        SELECT DATE(started_at) AS day, COUNT(*) AS count
        FROM audit_logs WHERE started_at >= NOW() - INTERVAL '14 days'
        GROUP BY DATE(started_at) ORDER BY day
    """)
    flows_per_day = [{"day": str(r["day"]), "count": r["count"]} for r in cur.fetchall()]

    cur.execute("""
        SELECT DATE(started_at) AS day, COALESCE(SUM(result_count),0) AS count
        FROM audit_logs WHERE flow_type='hiring' AND started_at >= NOW() - INTERVAL '14 days'
        GROUP BY DATE(started_at) ORDER BY day
    """)
    candidates_per_day = [{"day": str(r["day"]), "count": r["count"]} for r in cur.fetchall()]

    cur.execute("SELECT status, COUNT(*) AS count FROM audit_logs GROUP BY status")
    status_bd = [{"status": r["status"], "count": r["count"]} for r in cur.fetchall()]

    cur.execute("SELECT flow_type, COUNT(*) AS count FROM audit_logs GROUP BY flow_type")
    type_bd = [{"type": r["flow_type"], "count": r["count"]} for r in cur.fetchall()]

    cur.execute("""
        SELECT title AS job_title, COUNT(*) AS count FROM audit_logs
        WHERE flow_type='hiring' GROUP BY title ORDER BY count DESC LIMIT 8
    """)
    top_jobs = [{"job": r["job_title"], "count": r["count"]} for r in cur.fetchall()]

    cur.execute("""
        SELECT COALESCE(location,'Remote') AS location, COUNT(*) AS count
        FROM audit_logs GROUP BY location ORDER BY count DESC LIMIT 6
    """)
    top_locations = [{"location": r["location"], "count": r["count"]} for r in cur.fetchall()]

    cur.execute("""
        SELECT flow_id, flow_type, title, subtitle, location, result_count, status,
               started_at::text AS started_at
        FROM audit_logs ORDER BY started_at DESC LIMIT 10
    """)
    recent = [dict(r) for r in cur.fetchall()]

    cur.close(); conn.close()

    return {
        "kpis": {
            "total_flows":      total_flows,
            "completed_flows":  completed,
            "total_candidates": total_candidates,
            "total_agents":     total_agents,
            "success_rate":     round(completed/total_flows*100 if total_flows else 0, 1),
            "avg_candidates":   round(total_candidates/max(completed,1), 1),
        },
        "flows_per_day":       flows_per_day,
        "candidates_per_day":  candidates_per_day,
        "status_breakdown":    status_bd,
        "flow_type_breakdown": type_bd,
        "top_jobs":            top_jobs,
        "top_locations":       top_locations,
        "recent_flows":        recent,
    }
