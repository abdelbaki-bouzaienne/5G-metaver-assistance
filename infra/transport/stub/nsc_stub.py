#!/usr/bin/env python3
"""Stub du controleur de transport (NSC IETF) - TRANSPORT_CONTROLLER=none.

Implemente la meme API que le controleur du banc (POST/GET/DELETE /network-slices)
mais ne configure aucun PE : il tient un INVENTAIRE JSON des slices demandes
(etat ESTABLISHED immediat). Objectifs :
- debloquer la chaine OpenSlice -> RFS_Transport_InterSite -> controleur de ressource
  generique -> NSC (la ressource passe AVAILABLE) ;
- conserver l'intention exacte (network_slice_id, sdps, connectivity_type, SLO) pour
  la rejouer telle quelle sur le vrai controleur V3.

Lancement :  python3 nsc_stub.py [--port 8079] [--inventory /var/lib/nsc/inventory.json]
"""
import argparse
import json
import os
import threading
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
import uvicorn

app = FastAPI(title="nsc-stub (inventaire)", version="0.3.0")
_lock = threading.Lock()
INVENTORY_PATH = os.environ.get("NSC_INVENTORY", "/tmp/nsc-inventory.json")


def load() -> dict:
    if os.path.exists(INVENTORY_PATH):
        with open(INVENTORY_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save(inv: dict):
    os.makedirs(os.path.dirname(INVENTORY_PATH) or ".", exist_ok=True)
    with open(INVENTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(inv, f, indent=2, ensure_ascii=False)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "nsc-stub", "inventory": INVENTORY_PATH,
            "note": "stub inventaire - aucun PE configure (TRANSPORT_CONTROLLER=none)"}


@app.post("/network-slices", status_code=201)
def create_slice(body: dict):
    sid = body.get("network_slice_id")
    if not sid:
        raise HTTPException(400, "network_slice_id requis")
    if not body.get("sdps") or len(body["sdps"]) != 2:
        raise HTTPException(400, "sdps doit contenir exactement 2 points de demarcation")
    with _lock:
        inv = load()
        body["state"] = "ESTABLISHED"          # stub : etabli immediatement
        body["stub"] = True
        body["created_at"] = datetime.now(timezone.utc).isoformat()
        inv[sid] = body
        save(inv)
    return body


@app.get("/network-slices")
def list_slices():
    return list(load().values())


@app.get("/network-slices/{sid}")
def get_slice(sid: str):
    inv = load()
    if sid not in inv:
        raise HTTPException(404, "slice inconnu")
    return inv[sid]


@app.delete("/network-slices/{sid}", status_code=204)
def delete_slice(sid: str):
    with _lock:
        inv = load()
        if sid not in inv:
            raise HTTPException(404, "slice inconnu")
        del inv[sid]
        save(inv)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8079)
    ap.add_argument("--inventory", default=INVENTORY_PATH)
    args = ap.parse_args()
    INVENTORY_PATH = args.inventory
    uvicorn.run(app, host="0.0.0.0", port=args.port)
