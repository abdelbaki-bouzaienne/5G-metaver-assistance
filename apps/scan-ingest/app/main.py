"""scan-ingest : upload fragmente et reprenable des scans (plan 1, asynchrone).

- chunks avec checksum SHA-256, idempotents (reprise sans tout recommencer) ;
- scan refuse si le marqueur image n'est pas detecte (echelle/origine obligatoires) ;
- a la completion, un job 3DGS est mis en file (Redis) pour gs-pipeline.
Stockage : S3/MinIO si S3_ENDPOINT est defini, sinon disque local (/data).
"""
import hashlib
import json
import os
import uuid

import redis
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT")
S3_BUCKET = os.environ.get("S3_BUCKET", "scans")
DATA_DIR = os.environ.get("DATA_DIR", "/data")

r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
app = FastAPI(title="scan-ingest", version="1.0.0")

s3 = None
if S3_ENDPOINT:
    import boto3

    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY", "minioadmin"),
    )
    try:
        s3.head_bucket(Bucket=S3_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=S3_BUCKET)


def put_blob(key: str, data: bytes):
    if s3:
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=data)
    else:
        path = os.path.join(DATA_DIR, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)


def scan_key(sid: str) -> str:
    return f"scan:{sid}"


class ScanIn(BaseModel):
    site_id: str
    marker_detected: bool
    total_chunks: int
    transform_marker: list | None = None


@app.get("/healthz")
def healthz():
    try:
        r.ping()
    except Exception:
        raise HTTPException(503, "redis indisponible")
    return {"status": "ok", "service": "scan-ingest"}


@app.post("/scans", status_code=201)
def create_scan(body: ScanIn):
    if not body.marker_detected:
        # US-1.2 : sans marqueur, pas d'echelle ni d'origine -> scan refuse
        raise HTTPException(422, "marqueur image non detecte : scan refuse (echelle/origine requises)")
    sid = uuid.uuid4().hex
    r.hset(scan_key(sid), mapping={
        "id": sid,
        "site_id": body.site_id,
        "total_chunks": body.total_chunks,
        "received": json.dumps([]),
        "status": "uploading",
        "transform_marker": json.dumps(body.transform_marker or []),
        "twin_version_id": "",
    })
    return {"id": sid, "status": "uploading"}


@app.put("/scans/{sid}/chunks/{n}")
async def upload_chunk(sid: str, n: int, request: Request,
                       x_chunk_sha256: str = Header(...)):
    meta = r.hgetall(scan_key(sid))
    if not meta:
        raise HTTPException(404, "scan introuvable")
    if n >= int(meta["total_chunks"]):
        raise HTTPException(400, "index de chunk hors limite")
    data = await request.body()
    digest = hashlib.sha256(data).hexdigest()
    if digest != x_chunk_sha256:
        raise HTTPException(422, "checksum invalide : renvoyer ce chunk")
    put_blob(f"raw/{sid}/chunk_{n:06d}", data)
    received = set(json.loads(meta["received"]))
    received.add(n)  # idempotent : rejouer un chunk deja recu est sans effet
    r.hset(scan_key(sid), "received", json.dumps(sorted(received)))
    return {"received": len(received), "total": int(meta["total_chunks"])}


@app.post("/scans/{sid}/complete")
def complete_scan(sid: str):
    meta = r.hgetall(scan_key(sid))
    if not meta:
        raise HTTPException(404, "scan introuvable")
    received = json.loads(meta["received"])
    total = int(meta["total_chunks"])
    if len(received) != total:
        missing = sorted(set(range(total)) - set(received))
        raise HTTPException(409, f"chunks manquants : {missing[:20]}")
    r.hset(scan_key(sid), "status", "queued")
    r.rpush("gs:jobs", json.dumps({"scan_id": sid, "site_id": meta["site_id"],
                                   "transform_marker": json.loads(meta["transform_marker"])}))
    return {"id": sid, "status": "queued"}


@app.get("/scans/{sid}")
def get_scan(sid: str):
    meta = r.hgetall(scan_key(sid))
    if not meta:
        raise HTTPException(404, "scan introuvable")
    return {"id": sid, "status": meta["status"], "site_id": meta["site_id"],
            "received": len(json.loads(meta["received"])), "total": int(meta["total_chunks"]),
            "twin_version_id": meta.get("twin_version_id") or None}
