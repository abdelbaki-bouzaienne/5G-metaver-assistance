"""actuation-controller : controleur applicatif d'actuation au MEC (option URLLC).

Deux echanges distincts (doc 2, phase C) :
- l'expert envoie une instruction de SUPERVISION via le reseau longue distance
  (slice transport N6/N4, flux EF) -> POST /commands ;
- ce controleur pilote ensuite l'equipement via la BOUCLE DE CONTROLE
  (slice URLLC 2:791515, DNN actuation) -> appel de la passerelle actuateur.
L'UPF transporte les messages ; il n'execute pas la commande. La securite locale
(comportement sur en cas de perte reseau/MEC) reste assuree par l'equipement.
"""
import os
import time
import uuid

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

ACTUATOR_GATEWAY = os.environ.get("ACTUATOR_GATEWAY", "")  # vide = actuateur simule
COMMAND_EXPIRY_MS = int(os.environ.get("COMMAND_EXPIRY_MS", "500"))

app = FastAPI(title="actuation-controller", version="1.0.0")
journal: list[dict] = []


class Command(BaseModel):
    actuator_id: str
    action: str           # ex. "unlock", "led_on", "switch_port"
    issued_at_ms: int     # horodatage cote expert (detection de commande perimee)
    operator: str


@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "actuation-controller",
            "actuator_gateway": ACTUATOR_GATEWAY or "simulated"}


@app.post("/commands")
def supervise(cmd: Command):
    now_ms = int(time.time() * 1000)
    if now_ms - cmd.issued_at_ms > COMMAND_EXPIRY_MS:
        raise HTTPException(409, f"commande perimee (> {COMMAND_EXPIRY_MS} ms) : rejetee")
    cid = uuid.uuid4().hex
    t0 = time.perf_counter()
    if ACTUATOR_GATEWAY:
        try:
            resp = requests.post(f"{ACTUATOR_GATEWAY}/actuate",
                                 json={"id": cid, "actuator": cmd.actuator_id, "action": cmd.action},
                                 timeout=COMMAND_EXPIRY_MS / 1000)
            resp.raise_for_status()
            state = resp.json()
        except Exception as exc:
            journal.append({"id": cid, "cmd": cmd.model_dump(), "result": "failed", "error": str(exc)})
            raise HTTPException(502, f"actuateur injoignable (comportement sur local) : {exc}")
    else:
        state = {"actuator": cmd.actuator_id, "action": cmd.action, "result": "ok", "simulated": True}
    loop_ms = (time.perf_counter() - t0) * 1000
    entry = {"id": cid, "cmd": cmd.model_dump(), "state": state, "loop_ms": round(loop_ms, 2)}
    journal.append(entry)
    return entry


@app.get("/journal")
def get_journal():
    return journal[-100:]
