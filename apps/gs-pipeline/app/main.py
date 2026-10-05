"""gs-pipeline : pipeline 3D Gaussian Splatting asynchrone.

File de jobs Redis (gs:jobs) alimentee par scan-ingest. Pour chaque job :
poses -> entrainement -> compression -> tuiles/LOD, puis creation d'une TwinVersion
dans twin-service. Reprises automatiques (GS_MAX_RETRIES), statut visible cote app.

Deux modes (GS_MODE) :
- mock (defaut) : produit un splat factice + manifeste de tuiles -> demontre toute la
  chaine sans GPU (PoC reseau) ;
- gpu : execute GS_TRAIN_CMD (ex. script nerfstudio/gsplat sur noeud GPU du MEC) qui
  doit deposer splat.spz et tiles/ dans le repertoire de travail.
"""
import json
import os
import subprocess
import threading
import time

import redis
import requests
from fastapi import FastAPI, HTTPException

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
TWIN_URL = os.environ.get("TWIN_URL", "http://twin-service:8001")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT")
S3_BUCKET = os.environ.get("S3_BUCKET", "scans")
GS_MODE = os.environ.get("GS_MODE", "mock")
GS_TRAIN_CMD = os.environ.get("GS_TRAIN_CMD", "")
MAX_RETRIES = int(os.environ.get("GS_MAX_RETRIES", "2"))
MOCK_TRAIN_SECONDS = float(os.environ.get("GS_MOCK_SECONDS", "5"))
DATA_DIR = os.environ.get("DATA_DIR", "/data")

r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
app = FastAPI(title="gs-pipeline", version="1.0.0")

s3 = None
if S3_ENDPOINT:
    import boto3

    s3 = boto3.client("s3", endpoint_url=S3_ENDPOINT,
                      aws_access_key_id=os.environ.get("S3_ACCESS_KEY", "minioadmin"),
                      aws_secret_access_key=os.environ.get("S3_SECRET_KEY", "minioadmin"))


def put_blob(key: str, data: bytes):
    if s3:
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=data)
    else:
        path = os.path.join(DATA_DIR, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)


def set_status(scan_id: str, status: str, **extra):
    r.hset(f"scan:{scan_id}", mapping={"status": status, **extra})


def train(job: dict) -> list[dict]:
    """Retourne la liste des assets produits (type, lod, uri, taille)."""
    scan_id = job["scan_id"]
    if GS_MODE == "gpu" and GS_TRAIN_CMD:
        workdir = f"/tmp/gs/{scan_id}"
        os.makedirs(workdir, exist_ok=True)
        subprocess.run(GS_TRAIN_CMD, shell=True, check=True,
                       env={**os.environ, "SCAN_ID": scan_id, "WORKDIR": workdir})
        assets = []
        for root, _, files in os.walk(workdir):
            for f in files:
                p = os.path.join(root, f)
                key = f"splat/{scan_id}/{os.path.relpath(p, workdir)}"
                with open(p, "rb") as fh:
                    put_blob(key, fh.read())
                kind = "splat" if f.endswith((".spz", ".ply")) else "tile"
                assets.append({"asset_type": kind, "lod": 0, "uri": f"s3://{S3_BUCKET}/{key}",
                               "size_bytes": os.path.getsize(p)})
        return assets
    # Mode mock : entrainement simule, splat compresse + 3 niveaux de detail
    time.sleep(MOCK_TRAIN_SECONDS)
    assets = []
    splat = f"splat/{scan_id}/scene.spz".encode() * 64
    put_blob(f"splat/{scan_id}/scene.spz", splat)
    assets.append({"asset_type": "splat", "lod": 0,
                   "uri": f"s3://{S3_BUCKET}/splat/{scan_id}/scene.spz", "size_bytes": len(splat)})
    for lod in (0, 1, 2):
        manifest = json.dumps({"scan": scan_id, "lod": lod,
                               "tiles": [f"tile_{lod}_{i}.bin" for i in range(4 >> lod or 1)]}).encode()
        key = f"tiles/{scan_id}/lod{lod}/manifest.json"
        put_blob(key, manifest)
        assets.append({"asset_type": "tile", "lod": lod,
                       "uri": f"s3://{S3_BUCKET}/{key}", "size_bytes": len(manifest)})
    return assets


def process(job: dict):
    scan_id = job["scan_id"]
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            set_status(scan_id, "running")
            assets = train(job)
            resp = requests.post(f"{TWIN_URL}/twin-versions", json={
                "site_id": job["site_id"],
                "transform_marker": job.get("transform_marker") or None,
                "quality_score": 0.9,
                "coverage": 0.85,
                "assets": assets,
            }, timeout=30)
            resp.raise_for_status()
            set_status(scan_id, "done", twin_version_id=resp.json()["id"])
            return
        except Exception as exc:  # reprise automatique (US-1.4)
            if attempt > MAX_RETRIES:
                set_status(scan_id, "failed", error=str(exc))
                r.rpush("gs:jobs:dead", json.dumps(job))
                return
            time.sleep(2 * attempt)


def worker():
    while True:
        item = r.blpop("gs:jobs", timeout=5)
        if item:
            process(json.loads(item[1]))


threading.Thread(target=worker, daemon=True).start()


@app.get("/healthz")
def healthz():
    try:
        r.ping()
    except Exception:
        raise HTTPException(503, "redis indisponible")
    return {"status": "ok", "service": "gs-pipeline", "mode": GS_MODE}


@app.get("/jobs/{scan_id}")
def job_status(scan_id: str):
    meta = r.hgetall(f"scan:{scan_id}")
    if not meta:
        raise HTTPException(404, "job introuvable")
    return {"scan_id": scan_id, "status": meta.get("status"),
            "twin_version_id": meta.get("twin_version_id") or None,
            "error": meta.get("error")}
