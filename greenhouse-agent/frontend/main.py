"""Minimal FastAPI proxy for a deployed A2A agent (Agent Runtime, agents-cli 1.1.0+).

The browser talks ONLY to this proxy (same origin, no CORS, no GCP creds in the
browser). The proxy authenticates with Application Default Credentials and
forwards chat to the deployed agent over the A2A JSON-RPC protocol, returning replies as
structured parts the chat UI knows how to show:

  * {"kind": "text", "text": ...}  -> a normal chat bubble
  * {"kind": "a2ui", "data": ...}  -> one A2UI message (beginRendering /
    surfaceUpdate); static/index.html renders these as a card.
"""

import os
import uuid
import json
import logging
import google.auth
import google.auth.transport.requests
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("frontend_proxy")

RESOURCE = os.environ.get(
    "AGENT_ENGINE_RESOURCE_NAME",
    "projects/188939847350/locations/us-east1/reasoningEngines/6299188976947298304",
)
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")
LOCATION = RESOURCE.split("/locations/")[1].split("/")[0]

A2A_ENDPOINT = (
    f"https://{LOCATION}-aiplatform.googleapis.com/reasoningEngines/v1/"
    f"{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"
)

_A2UI_MIME = "application/json+a2ui"

_creds, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)

def _auth_headers() -> dict[str, str]:
    _creds.refresh(google.auth.transport.requests.Request())
    return {
        "Authorization": f"Bearer {_creds.token}",
        "Content-Type": "application/json",
    }

app = FastAPI()

@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    logger.exception("Error processing request: %s", exc)
    return JSONResponse(
        status_code=200,
        content={
            "parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}]
        },
    )

_contexts: dict[str, str] = {}

def _extract_parts(parts: list) -> list[dict]:
    out: list[dict] = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        # Plain text
        if "text" in p and p["text"]:
            out.append({"kind": "text", "text": p["text"]})
        # Data / A2UI
        elif "data" in p:
            val = p["data"]
            meta = p.get("metadata") or {}
            # Sometimes data itself is nested {"kind": "data", "data": {...}}
            if isinstance(val, dict) and "data" in val:
                meta = val.get("metadata") or meta
                val = val.get("data")
            mime = meta.get("mimeType") if isinstance(meta, dict) else None
            if mime == _A2UI_MIME or (isinstance(val, dict) and ("beginRendering" in val or "surfaceUpdate" in val)):
                out.append({"kind": "a2ui", "data": val})
        elif "file" in p and isinstance(p["file"], dict) and "uri" in p["file"]:
            out.append({"kind": "text", "text": p["file"]["uri"]})
    return out

@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"
    context_id = _contexts.get(user_id)

    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "messageId": str(uuid.uuid4()),
                "role": "user",
                "parts": [{"text": message}],
            }
        },
    }
    if context_id:
        payload["params"]["message"]["contextId"] = context_id

    async with httpx.AsyncClient(headers=_auth_headers(), timeout=120) as client:
        resp = await client.post(A2A_ENDPOINT, json=payload)
        resp.raise_for_status()
        res_json = resp.json()

    if "error" in res_json:
        err = res_json["error"]
        msg = err.get("message", str(err))
        return JSONResponse({"parts": [{"kind": "text", "text": f"Agent error: {msg}"}]})

    task = res_json.get("result", {})
    if getattr(task, "get", None) and task.get("contextId"):
        _contexts[user_id] = task["contextId"]

    parts: list[dict] = []
    # 1. Check artifacts first
    for art in task.get("artifacts", []):
        parts.extend(_extract_parts(art.get("parts", [])))

    # 2. Check history for agent replies if artifacts didn't have parts
    if not parts:
        for msg in task.get("history", []):
            if msg.get("role") == "agent":
                parts.extend(_extract_parts(msg.get("parts", [])))

    if not parts:
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]

    return JSONResponse({"parts": parts})

# Serve the chat UI
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
