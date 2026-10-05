"""signaling : relais WebSocket de signalisation WebRTC (SDP offer/answer, ICE candidates).

Une room par session ; les messages sont retransmis aux autres participants tels quels.
Les flux media eux-memes passent en P2P (SRTP) ou via coturn - jamais par ce service.
"""
import json
import os
from collections import defaultdict

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
app = FastAPI(title="signaling", version="1.0.0")
rooms: dict[str, set[WebSocket]] = defaultdict(set)


@app.get("/healthz")
async def healthz():
    try:
        r = aioredis.from_url(REDIS_URL)
        await r.ping()
        await r.aclose()
    except Exception:
        raise HTTPException(503, "redis indisponible")
    return {"status": "ok", "service": "signaling"}


@app.websocket("/ws/{session_id}")
async def ws_room(ws: WebSocket, session_id: str):
    await ws.accept()
    rooms[session_id].add(ws)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                json.loads(raw)  # SDP / ICE / controle - valide JSON uniquement
            except ValueError:
                continue
            for peer in list(rooms[session_id]):
                if peer is not ws:
                    try:
                        await peer.send_text(raw)
                    except Exception:
                        rooms[session_id].discard(peer)
    except WebSocketDisconnect:
        rooms[session_id].discard(ws)
        if not rooms[session_id]:
            rooms.pop(session_id, None)
