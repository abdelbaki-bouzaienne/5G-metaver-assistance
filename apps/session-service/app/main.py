"""session-service : seul point de coordination des sessions collaboratives (ADR 8).

- cree/rejoint une session liee a un site et une version du jumeau ;
- roles T (technicien), E (expert), A (admin) ;
- emet les identifiants TURN ephemeres (coturn use-auth-secret, HMAC time-limited)
  et, en option, un jeton Unity Relay (necessite un compte UGS - stub sinon) ;
- journal d'evenements + rapport de cloture (checklist, photos, annotations).
Une coupure du cloud ne coupe pas la session P2P en cours : ce service n'est sur le
chemin d'aucun flux temps reel.
"""
import base64
import hashlib
import hmac
import json
import os
import time
import uuid

import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
TURN_SECRET = os.environ.get("TURN_SECRET", "changeme-turn-secret")
TURN_URIS = os.environ.get("TURN_URIS", "turn:coturn:3478?transport=udp,turns:coturn:443?transport=tcp").split(",")
TURN_TTL = int(os.environ.get("TURN_TTL_SECONDS", "3600"))
RELAY_ENABLED = os.environ.get("UNITY_RELAY_ENABLED", "false").lower() == "true"

r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
app = FastAPI(title="session-service", version="1.0.0")


def turn_credentials(user: str) -> dict:
    """Identifiants ephemeres coturn (lifetime:username + HMAC-SHA1 du secret partage)."""
    expiry = int(time.time()) + TURN_TTL
    username = f"{expiry}:{user}"
    digest = hmac.new(TURN_SECRET.encode(), username.encode(), hashlib.sha1).digest()
    return {"uris": TURN_URIS, "username": username,
            "credential": base64.b64encode(digest).decode(), "ttl": TURN_TTL}


def relay_token() -> dict | None:
    if not RELAY_ENABLED:
        return None
    # Integration Unity Relay (UGS) : echange server-side du jeton d'allocation.
    return {"provider": "unity-relay", "note": "configurer UGS_PROJECT_ID / UGS_KEY"}


def skey(sid: str) -> str:
    return f"session:{sid}"


def log_event(sid: str, etype: str, payload: dict):
    r.rpush(f"{skey(sid)}:events", json.dumps(
        {"ts": time.time(), "type": etype, "payload": payload}))


class SessionIn(BaseModel):
    site_id: str
    twin_version_id: str
    user: str
    role: str  # T / E / A
    device: str = ""


class JoinIn(BaseModel):
    user: str
    role: str
    device: str = ""


@app.get("/healthz")
def healthz():
    try:
        r.ping()
    except Exception:
        raise HTTPException(503, "redis indisponible")
    return {"status": "ok", "service": "session-service"}


@app.post("/sessions", status_code=201)
def create_session(body: SessionIn):
    sid = uuid.uuid4().hex
    r.hset(skey(sid), mapping={
        "id": sid, "site_id": body.site_id, "twin_version_id": body.twin_version_id,
        "status": "open", "participants": json.dumps([body.model_dump()]),
    })
    log_event(sid, "session_created", body.model_dump())
    return {"id": sid, "status": "open",
            "turn": turn_credentials(body.user), "relay": relay_token(),
            "signaling_ws": f"/signaling/ws/{sid}"}


@app.post("/sessions/{sid}/join")
def join_session(sid: str, body: JoinIn):
    meta = r.hgetall(skey(sid))
    if not meta or meta.get("status") != "open":
        raise HTTPException(404, "session introuvable ou fermee")
    participants = json.loads(meta["participants"])
    participants.append(body.model_dump())
    r.hset(skey(sid), "participants", json.dumps(participants))
    log_event(sid, "participant_joined", body.model_dump())
    return {"id": sid, "twin_version_id": meta["twin_version_id"],
            "participants": participants,
            "turn": turn_credentials(body.user), "relay": relay_token(),
            "signaling_ws": f"/signaling/ws/{sid}"}


@app.get("/sessions/{sid}")
def get_session(sid: str):
    meta = r.hgetall(skey(sid))
    if not meta:
        raise HTTPException(404, "session introuvable")
    meta["participants"] = json.loads(meta["participants"])
    return meta


@app.post("/sessions/{sid}/events")
def push_event(sid: str, body: dict):
    if not r.exists(skey(sid)):
        raise HTTPException(404, "session introuvable")
    log_event(sid, body.get("type", "custom"), body.get("payload", {}))
    return {"ok": True}


@app.get("/sessions/{sid}/events")
def events(sid: str):
    return [json.loads(e) for e in r.lrange(f"{skey(sid)}:events", 0, -1)]


@app.post("/sessions/{sid}/report")
def close_with_report(sid: str, body: dict):
    """Phase D : rapport (checklist, captures, annotations, tests) puis fermeture.
    La validation du resultat reste explicite."""
    meta = r.hgetall(skey(sid))
    if not meta:
        raise HTTPException(404, "session introuvable")
    r.hset(skey(sid), mapping={"status": "closed", "report": json.dumps(body)})
    log_event(sid, "session_closed", {"report_keys": list(body.keys())})
    return {"id": sid, "status": "closed"}
