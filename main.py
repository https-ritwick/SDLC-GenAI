"""
DevMind Studio — FastAPI Backend
Orchestrates chat, Gemini AI, file management, WebSocket, and preview serving.
"""

import os
import uuid
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from file_manager import FileManager
from gemini_service import GeminiService

# ─── Boot ───────────────────────────────────────────────────────
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s │ %(name)s │ %(message)s")
logger = logging.getLogger("devmind")

# ─── App ────────────────────────────────────────────────────────
app = FastAPI(title="DevMind Studio", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Services ───────────────────────────────────────────────────
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
gemini = GeminiService(GEMINI_KEY)

# ─── State ──────────────────────────────────────────────────────
# project_id → {name, created, description}
projects_meta: Dict[str, Dict] = {}
# project_id → WebSocket
connections: Dict[str, WebSocket] = {}

# ─── Static files ────────────────────────────────────────────────
# All files are flat next to main.py — frontend IS the same directory
FRONTEND_DIR = Path(__file__).parent

PROJECTS_DIR = Path(__file__).parent / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)

if (FRONTEND_DIR / "css").exists():
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
if (FRONTEND_DIR / "js").exists():
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")


# ═══════════════════════════════════════════════════════════════
#  Frontend
# ═══════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    fp = FRONTEND_DIR / "index.html"
    if fp.exists():
        return HTMLResponse(fp.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Frontend not found — run from repo root.</h1>", status_code=503)


# ═══════════════════════════════════════════════════════════════
#  Preview — serve generated project files inside sandboxed iframe
# ═══════════════════════════════════════════════════════════════

@app.get("/preview/{project_id}", response_class=HTMLResponse)
async def preview_root(project_id: str):
    fm = FileManager(project_id)
    index = fm.project_dir / "index.html"
    if index.exists():
        html = index.read_text(encoding="utf-8")

        # Inject <base> tag so ALL relative CSS/JS/image URLs resolve correctly
        # from /preview/{project_id}/ instead of /preview/
        base_tag = f'<base href="/preview/{project_id}/">'

        if "<head>" in html:
            html = html.replace("<head>", f"<head>\n  {base_tag}", 1)
        elif "<HEAD>" in html:
            html = html.replace("<HEAD>", f"<HEAD>\n  {base_tag}", 1)
        else:
            # No <head> tag — prepend base tag at the very top
            html = base_tag + "\n" + html

        return HTMLResponse(content=html, status_code=200)

    # Friendly placeholder
    return HTMLResponse(
        """<!DOCTYPE html><html><head><style>
        body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;
        height:100vh;margin:0;background:#0f1117;color:#64748b;flex-direction:column;gap:12px;}
        h3{color:#e2e8f0;margin:0;}p{margin:0;font-size:14px;}</style></head>
        <body><h3>No index.html yet</h3>
        <p>Ask DevMind to build your app — the preview will appear here.</p></body></html>""",
        status_code=200,
    )


@app.get("/preview/{project_id}/{file_path:path}")
async def preview_file(project_id: str, file_path: str):
    fm = FileManager(project_id)
    fp = fm._resolve(file_path)
    if fp and fp.exists() and fp.is_file():
        return FileResponse(str(fp))
    # Try with common extensions as fallback (Gemini sometimes omits extension)
    for ext in [".css", ".js", ".html", ".json"]:
        fp_ext = fm._resolve(file_path + ext)
        if fp_ext and fp_ext.exists() and fp_ext.is_file():
            fp = fp_ext
            break

    if fp and fp.exists() and fp.is_file():
        # Inject <base> tag into HTML sub-pages too, so their relative CSS/JS links work
        if fp.suffix.lower() == ".html":
            html = fp.read_text(encoding="utf-8")
            base_tag = f'<base href="/preview/{project_id}/">'
            if "<head>" in html:
                html = html.replace("<head>", f"<head>\n  {base_tag}", 1)
            elif "<HEAD>" in html:
                html = html.replace("<HEAD>", f"<HEAD>\n  {base_tag}", 1)
            else:
                html = base_tag + "\n" + html
            return HTMLResponse(content=html, status_code=200)
        return FileResponse(str(fp))

    raise HTTPException(status_code=404, detail=f"File not found: {file_path}")


# ═══════════════════════════════════════════════════════════════
#  REST API
# ═══════════════════════════════════════════════════════════════

# ── Projects ──────────────────────────────────────────────────

@app.get("/api/projects")
async def list_projects():
    result = []
    for pid, meta in projects_meta.items():
        fm = FileManager(pid)
        result.append({
            "id": pid,
            "name": meta.get("name", f"Project {pid}"),
            "description": meta.get("description", ""),
            "created": meta.get("created", 0),
            "file_count": len(fm.list_files()),
        })
    result.sort(key=lambda x: x["created"], reverse=True)
    return {"projects": result}


@app.post("/api/projects")
async def create_project(body: dict = Body(...)):
    pid = str(uuid.uuid4())[:8]
    name = body.get("name", f"Project {pid}")
    projects_meta[pid] = {
        "name": name,
        "description": body.get("description", ""),
        "created": time.time(),
    }
    FileManager(pid)  # Creates the directory
    logger.info("Created project %s — %s", pid, name)
    return {"id": pid, "name": name}


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    import shutil
    if project_id in projects_meta:
        del projects_meta[project_id]
    fm = FileManager(project_id)
    shutil.rmtree(str(fm.project_dir), ignore_errors=True)
    gemini.clear_session(project_id)
    return {"status": "deleted"}


# ── Files ─────────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/files")
async def get_files(project_id: str):
    fm = FileManager(project_id)
    return {"files": fm.list_files()}


@app.get("/api/projects/{project_id}/files/{file_path:path}")
async def get_file(project_id: str, file_path: str):
    fm = FileManager(project_id)
    content = fm.get_file(file_path)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": file_path, "content": content}


@app.put("/api/projects/{project_id}/files/{file_path:path}")
async def update_file(project_id: str, file_path: str, body: dict = Body(...)):
    fm = FileManager(project_id)
    fm.write_file(file_path, body.get("content", ""))
    return {"status": "ok", "path": file_path}


@app.delete("/api/projects/{project_id}/files/{file_path:path}")
async def delete_file(project_id: str, file_path: str):
    fm = FileManager(project_id)
    deleted = fm.delete_file(file_path)
    return {"status": "ok" if deleted else "not_found"}


# ── Settings ──────────────────────────────────────────────────

@app.post("/api/settings/api-key")
async def set_api_key(body: dict = Body(...)):
    key = body.get("key", "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")
    gemini.update_api_key(key)
    return {"status": "ok", "configured": gemini.is_configured()}


@app.get("/api/settings/status")
async def settings_status():
    return {"gemini_configured": gemini.is_configured()}


# ═══════════════════════════════════════════════════════════════
#  WebSocket — Main real-time channel
# ═══════════════════════════════════════════════════════════════

@app.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await websocket.accept()
    connections[project_id] = websocket
    logger.info("WebSocket connected: %s", project_id)

    # Register project if new
    if project_id not in projects_meta:
        projects_meta[project_id] = {
            "name": f"Project {project_id}",
            "description": "",
            "created": time.time(),
        }

    fm = FileManager(project_id)

    # Send initial handshake
    await _send(websocket, {
        "type": "init",
        "project_id": project_id,
        "project_name": projects_meta[project_id]["name"],
        "files": fm.list_files(),
        "gemini_configured": gemini.is_configured(),
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await _send(websocket, {"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = data.get("type", "")

            # ── Chat message ─────────────────────────────────────
            if msg_type == "chat":
                user_message = (data.get("message") or "").strip()
                if not user_message:
                    continue

                await _send(websocket, {
                    "type": "status",
                    "status": "thinking",
                    "label": "DevMind is thinking…",
                })

                await _log(websocket, "info", "🤖 Routing request to Gemini AI…")

                # Build project context
                context = fm.get_project_context()

                # Call Gemini
                result = await gemini.generate(project_id, user_message, context)
                if not result.get("actions"):
                    await _log(websocket, "warning", "⚠️ Gemini returned no executable file actions")

                if result.get("status") == "error":
                    for entry in result.get("logs", []):
                        await _log(websocket, "error", entry)
                # Process file actions
                actions: List[Dict] = result.get("actions", [])
                created, updated, deleted = 0, 0, 0

                for action in actions:
                    atype = action.get("type", "")
                    path  = action.get("path", "").strip("/")
                    content = action.get("content", "")

                    if not path:
                        continue

                    if atype in ("create_file", "update_file"):
                        fm.write_file(path, content)
                        await _send(websocket, {
                            "type": "file_update",
                            "action": atype,
                            "path": path,
                            "content": content,
                        })
                        if atype == "create_file":
                            await _log(websocket, "success", f"✨ Created  → {path}")
                            created += 1
                        else:
                            await _log(websocket, "success", f"✏️  Updated → {path}")
                            updated += 1

                    elif atype == "delete_file":
                        fm.delete_file(path)
                        await _send(websocket, {"type": "file_delete", "path": path})
                        await _log(websocket, "warning", f"🗑️  Deleted → {path}")
                        deleted += 1

                # Emit Gemini logs
                for entry in result.get("logs", []):
                    await _log(websocket, "info", entry)

                # Summary log
                if created or updated or deleted:
                    summary = []
                    if created: summary.append(f"{created} created")
                    if updated: summary.append(f"{updated} updated")
                    if deleted: summary.append(f"{deleted} deleted")
                    await _log(websocket, "success", f"✅ Done — {', '.join(summary)}")

                # Send AI message to chat
                await _send(websocket, {
                    "type": "message",
                    "role": "assistant",
                    "content": result.get("message", "Done."),
                    "status": result.get("status", "complete"),
                    "files_updated": len(actions),
                })

                # Refresh file list
                await _send(websocket, {
                    "type": "files_list",
                    "files": fm.list_files(),
                })

                await _send(websocket, {
                    "type": "status",
                    "status": result.get("status", "complete"),
                    "label": "Ready",
                })

            # ── Get file content ──────────────────────────────────
            elif msg_type == "get_file":
                path = data.get("path", "")
                content = fm.get_file(path)
                await _send(websocket, {
                    "type": "file_content",
                    "path": path,
                    "content": content or "",
                })

            # ── Save file (manual edit) ───────────────────────────
            elif msg_type == "save_file":
                path    = data.get("path", "")
                content = data.get("content", "")
                if path:
                    fm.write_file(path, content)
                    await _log(websocket, "success", f"💾 Saved → {path}")
                    await _send(websocket, {
                        "type": "file_update",
                        "action": "update_file",
                        "path": path,
                        "content": content,
                    })

            # ── Rename project ────────────────────────────────────
            elif msg_type == "rename_project":
                new_name = data.get("name", "").strip()
                if new_name and project_id in projects_meta:
                    projects_meta[project_id]["name"] = new_name
                    await _send(websocket, {
                        "type": "project_renamed",
                        "name": new_name,
                    })

            # ── Clear chat / reset session ────────────────────────
            elif msg_type == "clear_session":
                gemini.clear_session(project_id)
                await _log(websocket, "info", "🔄 Conversation context cleared")

            else:
                logger.warning("Unknown WS message type: %s", msg_type)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", project_id)
        connections.pop(project_id, None)
    except Exception as exc:
        logger.exception("WebSocket error for %s", project_id)
        try:
            await _send(websocket, {"type": "error", "message": str(exc)})
        except Exception:
            pass
        connections.pop(project_id, None)


# ─── Helpers ────────────────────────────────────────────────────

async def _send(ws: WebSocket, data: Dict):
    try:
        await ws.send_json(data)
    except Exception:
        pass


async def _log(ws: WebSocket, level: str, message: str):
    await _send(ws, {"type": "log", "level": level, "message": message})


# ─── Catch-all static file server (MUST be last) ────────────────

@app.get("/{filename:path}")
async def serve_static(filename: str):
    """Serve flat static files (style.css, app.js, etc.) — registered LAST so it never shadows other routes."""
    fp = FRONTEND_DIR / filename
    if fp.exists() and fp.is_file():
        return FileResponse(str(fp))
    raise HTTPException(status_code=404, detail=f"Not found: {filename}")


# ─── Entry point ────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        reload_dirs=["."],
    )