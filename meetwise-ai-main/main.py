"""
main.py — FastAPI application with all API endpoints for MeetWise AI.

"""

import os
import random
import string

import requests
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

import audio_storage
import supabase_room_manager as rm
from gemini_service import process_meeting

app = FastAPI(title="MeetWise AI", description="Meetings end. Clarity begins.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUDIO_STORE = "audio_store"
SUMMARIES_DIR = "summaries"
os.makedirs(AUDIO_STORE, exist_ok=True)
os.makedirs(SUMMARIES_DIR, exist_ok=True)
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_PUBLISHABLE_KEY = (
    os.getenv("SUPABASE_PUBLISHABLE_KEY")
    or os.getenv("SUPABASE_ANON_KEY", "")
).strip()
SUPABASE_BACKEND_KEY = (
    os.getenv("SUPABASE_SECRET_KEY")
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
).strip()


# ──────────── Helpers ────────────

def _room_code(length: int = 6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def _summary_id() -> str:
    return rm._gen_id("sum")


def _extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header.removeprefix("Bearer ").strip() or None


def _verify_supabase_user(access_token: str) -> dict | None:
    if not access_token or not SUPABASE_URL or not (SUPABASE_BACKEND_KEY or SUPABASE_PUBLISHABLE_KEY):
        return None

    api_key = SUPABASE_BACKEND_KEY or SUPABASE_PUBLISHABLE_KEY
    try:
        response = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": api_key,
                "Authorization": f"Bearer {access_token}",
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        print(f"[auth] Failed to verify access token: {exc}")
        return None

    if response.status_code != 200:
        return None

    return response.json()


def require_authenticated_user(request: Request) -> dict:
    access_token = _extract_bearer_token(request)
    user = _verify_supabase_user(access_token) if access_token else None
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _ensure_workspace_access(user: dict, workspace_id: str) -> None:
    if not workspace_id:
        raise HTTPException(status_code=400, detail="Workspace ID is required")

    rm.ensure_profile(
        user["id"],
        email=user.get("email"),
        full_name=(user.get("user_metadata") or {}).get("full_name")
        or (user.get("user_metadata") or {}).get("name"),
    )
    rm.ensure_workspace_member(workspace_id, user["id"], role="member")


def _require_room_access(user: dict, room_code: str) -> dict:
    room = rm.get_room(room_code)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    workspace_id = room["workspace_id"]
    if not rm.is_workspace_member(workspace_id, user["id"]):
        raise HTTPException(status_code=403, detail="You do not have access to this room")

    return room


def _require_summary_access(user: dict, summary_id: str) -> None:
    workspace_id = rm.get_summary_workspace_id(summary_id)
    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Summary not found")

    if not rm.is_workspace_member(workspace_id, user["id"]):
        raise HTTPException(status_code=403, detail="You do not have access to this summary")


def _require_team_access(user: dict, team_id: str) -> None:
    workspace_id = rm.get_team_workspace_id(team_id)
    if workspace_id is None:
        raise HTTPException(status_code=404, detail="Team not found")

    if not rm.is_workspace_member(workspace_id, user["id"]):
        raise HTTPException(status_code=403, detail="You do not have access to this team")


# ──────────── Request Models ────────────

class WorkspaceCreate(BaseModel):
    name: str

class WorkspaceJoin(BaseModel):
    workspace_id: str
    user_name: str

class TeamCreate(BaseModel):
    workspace_id: str
    team_name: str

class RoomCreate(BaseModel):
    workspace_id: str
    team_id: str
    meeting_type: str  # standup | planning | review | general
    host_name: str

class RoomJoin(BaseModel):
    room_code: str
    participant_name: str


# ──────────── Workspace Endpoints ────────────

@app.post("/api/workspace/create")
def create_workspace(body: WorkspaceCreate, request: Request):
    user = _verify_supabase_user(_extract_bearer_token(request) or "")
    result = rm.create_workspace(body.name, user=user)
    print(f"[api] workspace created: {result}")
    return result


@app.post("/api/workspace/join")
def join_workspace(body: WorkspaceJoin, request: Request):
    user = _verify_supabase_user(_extract_bearer_token(request) or "")
    if user is not None:
        _ensure_workspace_access(user, body.workspace_id)
    result = rm.join_workspace(body.workspace_id, body.user_name)
    if result is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return result


# ──────────── Team Endpoints ────────────

@app.post("/api/teams/create")
def create_team(body: TeamCreate, request: Request):
    user = require_authenticated_user(request)
    _ensure_workspace_access(user, body.workspace_id)
    result = rm.create_team(body.workspace_id, body.team_name, user=user)
    if result is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return result


@app.get("/api/teams/{workspace_id}")
def get_teams(workspace_id: str, request: Request):
    user = require_authenticated_user(request)
    _ensure_workspace_access(user, workspace_id)
    teams_list = rm.get_teams_for_workspace(workspace_id)
    return {"teams": teams_list}


# ──────────── Room Endpoints ────────────

@app.post("/api/rooms/create")
def create_room(body: RoomCreate, request: Request):
    user = require_authenticated_user(request)
    _ensure_workspace_access(user, body.workspace_id)
    code = _room_code()
    result = rm.create_room(code, body.workspace_id, body.team_id,
                            body.meeting_type, body.host_name, user=user)
    if result is None:
        raise HTTPException(status_code=404, detail="Team not found")
    print(f"[api] room created: {code} by {body.host_name}")
    return result


@app.post("/api/rooms/join")
def join_room(body: RoomJoin, request: Request):
    user = require_authenticated_user(request)
    room = rm.get_room(body.room_code)
    if room is None or not room["is_active"]:
        raise HTTPException(status_code=404, detail="Room not found or inactive")

    _ensure_workspace_access(user, room["workspace_id"])
    result = rm.join_room(body.room_code, body.participant_name, user=user)
    if result is None:
        raise HTTPException(status_code=404, detail="Room not found or inactive")
    print(f"[api] {body.participant_name} joined room {body.room_code}")
    return result


@app.get("/api/rooms/{room_code}/status")
def room_status(room_code: str, request: Request):
    user = require_authenticated_user(request)
    _require_room_access(user, room_code)
    status = rm.get_room_status(room_code)
    if status is None:
        raise HTTPException(status_code=404, detail="Room not found")
    return status


# ──────────── Audio Upload ────────────

@app.post("/api/audio/upload")
async def upload_audio(
    request: Request,
    room_code: str = Form(...),
    participant_id: str = Form(...),
    audio: UploadFile = File(...),
):
    user = require_authenticated_user(request)
    room = _require_room_access(user, room_code)

    # Find participant name from ID
    participant = room["participants"].get(participant_id)
    if participant is None:
        raise HTTPException(status_code=404, detail="Participant not found in room")

    participant_name = participant["name"]

    contents = await audio.read()
    if audio_storage.STORAGE_ENABLED:
        extension = os.path.splitext(audio.filename or "")[1].lstrip(".") or "webm"
        save_path = audio_storage.upload_audio_bytes(
            room_code=room_code,
            participant_id=participant_id,
            participant_name=participant_name,
            contents=contents,
            content_type=audio.content_type or "audio/webm",
            extension=extension,
        )
    else:
        room_dir = os.path.join(AUDIO_STORE, room_code)
        os.makedirs(room_dir, exist_ok=True)
        save_path = os.path.join(room_dir, f"{participant_name}.webm")

        with open(save_path, "wb") as f:
            f.write(contents)

    # Track upload count
    count = rm.record_upload(room_code, participant_id=participant_id, audio_path=save_path)
    storage_target = "supabase-storage" if audio_storage.STORAGE_ENABLED else "local-disk"
    print(f"[api] audio uploaded: {participant_name} in room {room_code} ({len(contents)} bytes) -> {storage_target} ({count}/{len(room['participants'])})")

    return {
        "status": "uploaded",
        "filename": f"{participant_name}.webm",
    }


# ──────────── End Meeting + Summarization ────────────

@app.post("/api/rooms/{room_code}/end")
async def end_meeting(room_code: str, request: Request):
    user = require_authenticated_user(request)
    room = _require_room_access(user, room_code)

    # Mark room as ended
    rm.end_room(room_code)
    print(f"[api] room {room_code} ended, starting Gemini pipeline...")

    # Run the Gemini pipeline (blocking for hackathon)
    try:
        summary_data = await process_meeting(room_code, room)
    except Exception as e:
        print(f"[api] Gemini pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")

    # Save the summary
    sum_id = _summary_id()
    rm.save_summary(
        summary_id=sum_id,
        team_id=room["team_id"],
        workspace_id=room["workspace_id"],
        room_code=room_code,
        summary_data=summary_data,
    )

    print(f"[api] summary saved: {sum_id}")
    return {
        "status": "complete",
        "summary_id": sum_id,
        "summary": summary_data,
    }


# ──────────── Summary Endpoints ────────────

@app.get("/api/summaries/{summary_id}")
def get_summary(summary_id: str, request: Request):
    user = require_authenticated_user(request)
    _require_summary_access(user, summary_id)
    s = rm.get_summary(summary_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Summary not found")
    return s


@app.get("/api/summaries/team/{team_id}")
def get_team_summaries(team_id: str, request: Request):
    user = require_authenticated_user(request)
    _require_team_access(user, team_id)
    return rm.get_summaries_for_team(team_id)


@app.get("/api/summaries/workspace/{workspace_id}")
def get_workspace_summaries(workspace_id: str, request: Request):
    user = require_authenticated_user(request)
    _ensure_workspace_access(user, workspace_id)
    return rm.get_summaries_for_workspace(workspace_id)


@app.get("/api/summaries/{summary_id}/download")
def download_summary(summary_id: str, request: Request):
    user = require_authenticated_user(request)
    _require_summary_access(user, summary_id)
    md = rm.get_summary_as_markdown(summary_id)
    if md is None:
        raise HTTPException(status_code=404, detail="Summary not found")
    return PlainTextResponse(
        content=md,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="meeting-summary-{summary_id}.md"'
        },
    )


# ──────────── Serve Frontend ────────────

@app.get("/api/config/auth")
def auth_config():
    publishable_key = (
        os.getenv("SUPABASE_PUBLISHABLE_KEY")
        or os.getenv("SUPABASE_ANON_KEY", "")
    )
    return {
        "enabled": bool(os.getenv("SUPABASE_URL") and publishable_key),
        "url": os.getenv("SUPABASE_URL", ""),
        # Keep the response shape stable for the existing frontend code.
        "anon_key": publishable_key,
    }


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# Serve index.html at root
@app.get("/")
def serve_index():
    return FileResponse("static/index.html")
