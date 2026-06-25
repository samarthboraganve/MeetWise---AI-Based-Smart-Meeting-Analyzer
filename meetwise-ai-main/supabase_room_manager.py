"""
Supabase-backed state management for MeetWise AI.

If the backend database key is missing, the module falls back to in-memory
storage so the app can still run locally.
"""

import json
import os
import uuid
from datetime import datetime, timezone

import requests


SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_DB_KEY = (
    os.getenv("SUPABASE_SECRET_KEY", "").strip()
    or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
)
DB_ENABLED = bool(SUPABASE_URL and SUPABASE_DB_KEY)
LOCAL_STATE_FILE = os.getenv("MEETWISE_STATE_FILE", os.path.join("data", "meetwise_state.json"))


workspaces = {}
teams = {}
rooms = {}
summaries = {}


def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _load_memory_state() -> None:
    global workspaces, teams, rooms, summaries

    if DB_ENABLED or not os.path.exists(LOCAL_STATE_FILE):
        return

    try:
        with open(LOCAL_STATE_FILE, "r", encoding="utf-8") as handle:
            raw_state = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[state] Failed to load local state from {LOCAL_STATE_FILE}: {exc}")
        return

    workspaces = raw_state.get("workspaces", {})
    teams = raw_state.get("teams", {})
    rooms = raw_state.get("rooms", {})
    summaries = raw_state.get("summaries", {})


def _persist_memory_state() -> None:
    if DB_ENABLED:
        return

    try:
        state_dir = os.path.dirname(LOCAL_STATE_FILE)
        if state_dir:
            os.makedirs(state_dir, exist_ok=True)

        with open(LOCAL_STATE_FILE, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "workspaces": workspaces,
                    "teams": teams,
                    "rooms": rooms,
                    "summaries": summaries,
                },
                handle,
                ensure_ascii=True,
                indent=2,
            )
    except OSError as exc:
        print(f"[state] Failed to persist local state to {LOCAL_STATE_FILE}: {exc}")


def _db_headers(prefer_return: bool = False) -> dict:
    headers = {
        "apikey": SUPABASE_DB_KEY,
        "Authorization": f"Bearer {SUPABASE_DB_KEY}",
    }
    if prefer_return:
        headers["Prefer"] = "return=representation"
    return headers


def _db_request(method: str, table: str, params: dict | None = None, payload=None, prefer_return: bool = False):
    response = requests.request(
        method=method,
        url=f"{SUPABASE_URL}/rest/v1/{table}",
        headers=_db_headers(prefer_return=prefer_return),
        params=params,
        json=payload,
        timeout=20,
    )
    response.raise_for_status()

    if not response.text:
        return None
    return response.json()


def _db_select(table: str, params: dict) -> list[dict]:
    return _db_request("GET", table, params=params) or []


def _db_single(table: str, params: dict) -> dict | None:
    rows = _db_select(table, params)
    return rows[0] if rows else None


def _db_insert(table: str, payload: dict) -> dict:
    rows = _db_request("POST", table, payload=payload, prefer_return=True)
    return rows[0]


def _db_update(table: str, filters: dict, payload: dict) -> list[dict]:
    return _db_request("PATCH", table, params=filters, payload=payload, prefer_return=True) or []


def _db_count(table: str, params: dict) -> int:
    return len(_db_select(table, params))


def ensure_profile(user_id: str, email: str | None = None, full_name: str | None = None) -> dict | None:
    if not DB_ENABLED or not user_id:
        return None

    existing = _db_single(
        "profiles",
        {
            "id": f"eq.{user_id}",
            "select": "id,email,full_name",
        },
    )

    payload = {
        "id": user_id,
        "email": email,
        "full_name": full_name,
    }

    if existing is None:
        return _db_insert("profiles", payload)

    updates = {}
    if email and email != existing.get("email"):
        updates["email"] = email
    if full_name and full_name != existing.get("full_name"):
        updates["full_name"] = full_name

    if not updates:
        return existing

    rows = _db_update("profiles", {"id": f"eq.{user_id}"}, updates)
    return rows[0] if rows else existing


def ensure_workspace_member(workspace_id: str, user_id: str, role: str = "member") -> dict | None:
    if not DB_ENABLED or not workspace_id or not user_id:
        return None

    existing = _db_single(
        "workspace_members",
        {
            "workspace_id": f"eq.{workspace_id}",
            "user_id": f"eq.{user_id}",
            "select": "workspace_id,user_id,role,joined_at",
        },
    )
    if existing is not None:
        return existing

    assigned_role = role
    if role != "owner":
        current_member_count = _db_count(
            "workspace_members",
            {
                "workspace_id": f"eq.{workspace_id}",
                "select": "user_id",
            },
        )
        if current_member_count == 0:
            assigned_role = "owner"

    return _db_insert(
        "workspace_members",
        {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "role": assigned_role,
        },
    )


def is_workspace_member(workspace_id: str, user_id: str) -> bool:
    if not DB_ENABLED:
        return True

    if not workspace_id or not user_id:
        return False

    return _db_single(
        "workspace_members",
        {
            "workspace_id": f"eq.{workspace_id}",
            "user_id": f"eq.{user_id}",
            "select": "workspace_id",
        },
    ) is not None


def _room_from_rows(room_row: dict, team_row: dict | None, participant_rows: list[dict]) -> dict:
    participants = {
        row["participant_id"]: {
            "id": row["participant_id"],
            "name": row["participant_name"],
            "is_host": row.get("is_host", False),
            "audio_path": row.get("audio_path"),
            "upload_received": row.get("upload_received", False),
        }
        for row in participant_rows
    }
    uploads_received = sum(1 for row in participant_rows if row.get("upload_received"))
    host_row = next((row for row in participant_rows if row.get("is_host")), None)

    return {
        "room_code": room_row["room_code"],
        "workspace_id": room_row["workspace_id"],
        "team_id": room_row["team_id"],
        "team_name": team_row["team_name"] if team_row else "Unknown",
        "meeting_type": room_row["meeting_type"],
        "is_active": room_row["status"] == "active",
        "host_id": host_row["participant_id"] if host_row else None,
        "participants": participants,
        "started_at": room_row["started_at"],
        "uploads_received": uploads_received,
    }


def _memory_get_team_info(team_id: str) -> dict | None:
    team = teams.get(team_id)
    if team is None:
        return None
    count = sum(1 for summary in summaries.values() if summary.get("team_id") == team_id)
    return {
        "team_id": team_id,
        "team_name": team["team_name"],
        "summary_count": count,
    }


def create_workspace(name: str, user: dict | None = None) -> dict:
    if not DB_ENABLED:
        ws_id = _gen_id("ws")
        workspaces[ws_id] = {
            "workspace_id": ws_id,
            "name": name,
            "teams": [],
        }
        _persist_memory_state()
        return {"workspace_id": ws_id, "name": name}

    user_id = user.get("id") if user else None
    email = user.get("email") if user else None
    full_name = ((user.get("user_metadata") or {}).get("full_name") if user else None) or ((user.get("user_metadata") or {}).get("name") if user else None)

    if user_id:
        ensure_profile(user_id, email=email, full_name=full_name)

    payload = {"name": name}
    if user_id:
        payload["created_by"] = user_id

    row = _db_insert("workspaces", payload)
    if user_id:
        ensure_workspace_member(row["workspace_id"], user_id, role="owner")
    return {"workspace_id": row["workspace_id"], "name": row["name"]}


def join_workspace(workspace_id: str, user_name: str) -> dict | None:
    if not DB_ENABLED:
        ws = workspaces.get(workspace_id)
        if ws is None:
            return None
        return {
            "workspace_id": workspace_id,
            "name": ws["name"],
            "teams": [team for team in (_memory_get_team_info(tid) for tid in ws["teams"]) if team],
        }

    ws = get_workspace(workspace_id)
    if ws is None:
        return None
    return {
        "workspace_id": workspace_id,
        "name": ws["name"],
        "teams": get_teams_for_workspace(workspace_id),
    }


def get_workspace(workspace_id: str) -> dict | None:
    if not DB_ENABLED:
        return workspaces.get(workspace_id)

    return _db_single(
        "workspaces",
        {
            "workspace_id": f"eq.{workspace_id}",
            "select": "workspace_id,name,created_at,updated_at",
        },
    )


def create_team(workspace_id: str, team_name: str, user: dict | None = None) -> dict | None:
    if not DB_ENABLED:
        ws = workspaces.get(workspace_id)
        if ws is None:
            return None
        team_id = _gen_id("tm")
        teams[team_id] = {
            "team_id": team_id,
            "team_name": team_name,
            "workspace_id": workspace_id,
        }
        ws["teams"].append(team_id)
        _persist_memory_state()
        return {"team_id": team_id, "team_name": team_name}

    ws = get_workspace(workspace_id)
    if ws is None:
        return None

    payload = {"workspace_id": workspace_id, "team_name": team_name}
    if user and user.get("id"):
        ensure_profile(
            user["id"],
            email=user.get("email"),
            full_name=((user.get("user_metadata") or {}).get("full_name") or (user.get("user_metadata") or {}).get("name")),
        )
        payload["created_by"] = user["id"]

    row = _db_insert("teams", payload)
    return {"team_id": row["team_id"], "team_name": row["team_name"]}


def get_team_info(team_id: str) -> dict | None:
    if not DB_ENABLED:
        return _memory_get_team_info(team_id)

    team_row = _db_single(
        "teams",
        {
            "team_id": f"eq.{team_id}",
            "select": "team_id,team_name,workspace_id",
        },
    )
    if team_row is None:
        return None

    return {
        "team_id": team_row["team_id"],
        "team_name": team_row["team_name"],
        "summary_count": _db_count(
            "summaries",
            {
                "team_id": f"eq.{team_id}",
                "select": "summary_id",
            },
        ),
    }


def get_team_workspace_id(team_id: str) -> str | None:
    if not DB_ENABLED:
        team = teams.get(team_id)
        return team["workspace_id"] if team else None

    row = _db_single(
        "teams",
        {
            "team_id": f"eq.{team_id}",
            "select": "workspace_id",
        },
    )
    return row["workspace_id"] if row else None


def get_teams_for_workspace(workspace_id: str) -> list[dict]:
    if not DB_ENABLED:
        ws = workspaces.get(workspace_id)
        if ws is None:
            return []
        return [team for team in (_memory_get_team_info(tid) for tid in ws["teams"]) if team]

    team_rows = _db_select(
        "teams",
        {
            "workspace_id": f"eq.{workspace_id}",
            "select": "team_id,team_name",
            "order": "created_at.asc",
        },
    )
    return [get_team_info(row["team_id"]) for row in team_rows]


def create_room(room_code: str, workspace_id: str, team_id: str, meeting_type: str, host_name: str, user: dict | None = None) -> dict | None:
    if not DB_ENABLED:
        team = teams.get(team_id)
        if team is None:
            return None
        participant_id = _gen_id("p")
        rooms[room_code] = {
            "room_code": room_code,
            "workspace_id": workspace_id,
            "team_id": team_id,
            "team_name": team["team_name"],
            "meeting_type": meeting_type,
            "is_active": True,
            "host_id": participant_id,
            "participants": {
                participant_id: {
                    "id": participant_id,
                    "name": host_name,
                    "is_host": True,
                    "audio_path": None,
                    "upload_received": False,
                }
            },
            "started_at": datetime.now(timezone.utc).isoformat(),
            "uploads_received": 0,
        }
        _persist_memory_state()
        return {"room_code": room_code, "participant_id": participant_id}

    team_row = _db_single(
        "teams",
        {
            "team_id": f"eq.{team_id}",
            "workspace_id": f"eq.{workspace_id}",
            "select": "team_id,team_name",
        },
    )
    if team_row is None:
        return None

    host_user_id = user.get("id") if user else None
    if host_user_id:
        ensure_profile(
            host_user_id,
            email=user.get("email"),
            full_name=((user.get("user_metadata") or {}).get("full_name") or (user.get("user_metadata") or {}).get("name")),
        )

    _db_insert(
        "rooms",
        {
            "room_code": room_code,
            "workspace_id": workspace_id,
            "team_id": team_id,
            "meeting_type": meeting_type,
            "host_user_id": host_user_id,
            "host_name": host_name,
            "status": "active",
        },
    )
    participant = _db_insert(
        "room_participants",
        {
            "room_code": room_code,
            "user_id": host_user_id,
            "participant_name": host_name,
            "is_host": True,
        },
    )
    return {"room_code": room_code, "participant_id": participant["participant_id"]}


def join_room(room_code: str, participant_name: str, user: dict | None = None) -> dict | None:
    if not DB_ENABLED:
        room = rooms.get(room_code)
        if room is None or not room["is_active"]:
            return None
        participant_id = _gen_id("p")
        room["participants"][participant_id] = {
            "id": participant_id,
            "name": participant_name,
            "is_host": False,
            "audio_path": None,
            "upload_received": False,
        }
        _persist_memory_state()
        return {"room_code": room_code, "participant_id": participant_id}

    room_row = _db_single(
        "rooms",
        {
            "room_code": f"eq.{room_code}",
            "select": "room_code,status",
        },
    )
    if room_row is None or room_row["status"] != "active":
        return None

    user_id = user.get("id") if user else None
    if user_id:
        ensure_profile(
            user_id,
            email=user.get("email"),
            full_name=((user.get("user_metadata") or {}).get("full_name") or (user.get("user_metadata") or {}).get("name")),
        )

    participant = _db_insert(
        "room_participants",
        {
            "room_code": room_code,
            "user_id": user_id,
            "participant_name": participant_name,
            "is_host": False,
        },
    )
    return {"room_code": room_code, "participant_id": participant["participant_id"]}


def get_room(room_code: str) -> dict | None:
    if not DB_ENABLED:
        return rooms.get(room_code)

    room_row = _db_single(
        "rooms",
        {
            "room_code": f"eq.{room_code}",
            "select": "room_code,workspace_id,team_id,meeting_type,status,started_at",
        },
    )
    if room_row is None:
        return None

    team_row = _db_single(
        "teams",
        {
            "team_id": f"eq.{room_row['team_id']}",
            "select": "team_name",
        },
    )
    participant_rows = _db_select(
        "room_participants",
        {
            "room_code": f"eq.{room_code}",
            "select": "participant_id,participant_name,is_host,upload_received,audio_path",
            "order": "joined_at.asc",
        },
    )
    return _room_from_rows(room_row, team_row, participant_rows)


def get_room_workspace_id(room_code: str) -> str | None:
    if not DB_ENABLED:
        room = rooms.get(room_code)
        return room["workspace_id"] if room else None

    room_row = _db_single(
        "rooms",
        {
            "room_code": f"eq.{room_code}",
            "select": "workspace_id",
        },
    )
    return room_row["workspace_id"] if room_row else None


def get_room_status(room_code: str) -> dict | None:
    room = get_room(room_code)
    if room is None:
        return None
    return {
        "room_code": room["room_code"],
        "team_name": room["team_name"],
        "meeting_type": room["meeting_type"],
        "is_active": room["is_active"],
        "participants": list(room["participants"].values()),
        "started_at": room["started_at"],
    }


def end_room(room_code: str) -> bool:
    if not DB_ENABLED:
        room = rooms.get(room_code)
        if room is None:
            return False
        room["is_active"] = False
        _persist_memory_state()
        return True

    return bool(
        _db_update(
            "rooms",
            {"room_code": f"eq.{room_code}"},
            {"status": "ended", "ended_at": datetime.now(timezone.utc).isoformat()},
        )
    )


def record_upload(room_code: str, participant_id: str | None = None, audio_path: str | None = None) -> int:
    if not DB_ENABLED:
        room = rooms.get(room_code)
        if room is None:
            return 0
        if participant_id and participant_id in room["participants"]:
            room["participants"][participant_id]["upload_received"] = True
            if audio_path:
                room["participants"][participant_id]["audio_path"] = audio_path
        room["uploads_received"] = sum(
            1 for participant in room["participants"].values()
            if participant.get("upload_received")
        )
        _persist_memory_state()
        return room["uploads_received"]

    if participant_id:
        payload = {"upload_received": True}
        if audio_path:
            payload["audio_path"] = audio_path
        _db_update(
            "room_participants",
            {
                "room_code": f"eq.{room_code}",
                "participant_id": f"eq.{participant_id}",
            },
            payload,
        )

    return len(
        _db_select(
            "room_participants",
            {
                "room_code": f"eq.{room_code}",
                "upload_received": "eq.true",
                "select": "participant_id",
            },
        )
    )


def all_uploads_received(room_code: str) -> bool:
    room = get_room(room_code)
    if room is None:
        return False
    return room["uploads_received"] >= len(room["participants"])


def save_summary(summary_id: str, team_id: str, workspace_id: str, room_code: str, summary_data: dict) -> dict:
    room = get_room(room_code) or {}
    entry = {
        "summary_id": summary_id,
        "team_id": team_id,
        "workspace_id": workspace_id,
        "room_code": room_code,
        "meeting_title": summary_data.get("meeting_title", "Untitled Meeting"),
        "meeting_type": summary_data.get("meeting_type", "general"),
        "date": summary_data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        "duration_estimate": summary_data.get("duration_estimate", "Unknown"),
        "participant_count": len(room.get("participants", {})),
        "participants": summary_data.get("participants", []),
        "data": summary_data,
    }

    if not DB_ENABLED:
        summaries[summary_id] = entry
        _persist_memory_state()
        return entry

    row = _db_insert(
        "summaries",
        {
            "summary_id": summary_id,
            "workspace_id": workspace_id,
            "team_id": team_id,
            "room_code": room_code,
            "meeting_title": entry["meeting_title"],
            "meeting_type": entry["meeting_type"],
            "meeting_date": entry["date"],
            "duration_estimate": entry["duration_estimate"],
            "participant_count": entry["participant_count"],
            "participants": entry["participants"],
            "summary_data": summary_data,
        },
    )
    return {
        "summary_id": row["summary_id"],
        "team_id": row["team_id"],
        "workspace_id": row["workspace_id"],
        "room_code": row["room_code"],
        "meeting_title": row["meeting_title"],
        "meeting_type": row["meeting_type"],
        "date": row["meeting_date"],
        "duration_estimate": row["duration_estimate"],
        "participant_count": row["participant_count"],
        "participants": row["participants"],
        "data": row["summary_data"],
    }


def get_summary(summary_id: str) -> dict | None:
    if not DB_ENABLED:
        entry = summaries.get(summary_id)
        if entry is None:
            return None
        return entry["data"] | {"summary_id": summary_id}

    row = _db_single(
        "summaries",
        {
            "summary_id": f"eq.{summary_id}",
            "select": "summary_id,summary_data",
        },
    )
    if row is None:
        return None
    return row["summary_data"] | {"summary_id": row["summary_id"]}


def get_summary_workspace_id(summary_id: str) -> str | None:
    if not DB_ENABLED:
        entry = summaries.get(summary_id)
        return entry["workspace_id"] if entry else None

    row = _db_single(
        "summaries",
        {
            "summary_id": f"eq.{summary_id}",
            "select": "workspace_id",
        },
    )
    return row["workspace_id"] if row else None


def get_summaries_for_team(team_id: str) -> dict:
    if not DB_ENABLED:
        team = teams.get(team_id)
        if team is None:
            return {"team_name": "Unknown", "summaries": []}
        return {
            "team_name": team["team_name"],
            "summaries": [
                {
                    "summary_id": summary["summary_id"],
                    "meeting_title": summary["meeting_title"],
                    "meeting_type": summary["meeting_type"],
                    "date": summary["date"],
                    "duration": summary["duration_estimate"],
                    "participant_count": summary["participant_count"],
                }
                for summary in summaries.values()
                if summary["team_id"] == team_id
            ],
        }

    team_row = _db_single(
        "teams",
        {
            "team_id": f"eq.{team_id}",
            "select": "team_name",
        },
    )
    if team_row is None:
        return {"team_name": "Unknown", "summaries": []}

    summary_rows = _db_select(
        "summaries",
        {
            "team_id": f"eq.{team_id}",
            "select": "summary_id,meeting_title,meeting_type,meeting_date,duration_estimate,participant_count",
            "order": "created_at.desc",
        },
    )
    return {
        "team_name": team_row["team_name"],
        "summaries": [
            {
                "summary_id": row["summary_id"],
                "meeting_title": row["meeting_title"],
                "meeting_type": row["meeting_type"],
                "date": row["meeting_date"],
                "duration": row["duration_estimate"],
                "participant_count": row["participant_count"],
            }
            for row in summary_rows
        ],
    }


def get_summaries_for_workspace(workspace_id: str) -> dict:
    if not DB_ENABLED:
        ws = workspaces.get(workspace_id)
        if ws is None:
            return {"workspace_name": "Unknown", "teams": []}
        result_teams = []
        for team_id in ws["teams"]:
            team = teams.get(team_id)
            if team is None:
                continue
            team_data = get_summaries_for_team(team_id)
            result_teams.append(
                {
                    "team_id": team_id,
                    "team_name": team["team_name"],
                    "summaries": team_data["summaries"],
                }
            )
        return {"workspace_name": ws["name"], "teams": result_teams}

    ws = get_workspace(workspace_id)
    if ws is None:
        return {"workspace_name": "Unknown", "teams": []}

    team_rows = _db_select(
        "teams",
        {
            "workspace_id": f"eq.{workspace_id}",
            "select": "team_id,team_name",
            "order": "created_at.asc",
        },
    )
    summary_rows = _db_select(
        "summaries",
        {
            "workspace_id": f"eq.{workspace_id}",
            "select": "summary_id,team_id,meeting_title,meeting_type,meeting_date,duration_estimate,participant_count",
            "order": "created_at.desc",
        },
    )

    summaries_by_team = {}
    for row in summary_rows:
        summaries_by_team.setdefault(row["team_id"], []).append(
            {
                "summary_id": row["summary_id"],
                "meeting_title": row["meeting_title"],
                "meeting_type": row["meeting_type"],
                "date": row["meeting_date"],
                "duration": row["duration_estimate"],
                "participant_count": row["participant_count"],
            }
        )

    return {
        "workspace_name": ws["name"],
        "teams": [
            {
                "team_id": row["team_id"],
                "team_name": row["team_name"],
                "summaries": summaries_by_team.get(row["team_id"], []),
            }
            for row in team_rows
        ],
    }


def get_summary_as_markdown(summary_id: str) -> str | None:
    summary = get_summary(summary_id)
    if summary is None:
        return None

    lines = []
    lines.append(f"# {summary.get('meeting_title', 'Meeting Summary')}")
    lines.append("")
    lines.append(f"**Team:** {summary.get('team', 'N/A')}")
    lines.append(f"**Type:** {summary.get('meeting_type', 'N/A')}")
    lines.append(f"**Date:** {summary.get('date', 'N/A')}")
    lines.append(f"**Duration:** {summary.get('duration_estimate', 'N/A')}")
    lines.append(f"**Participants:** {', '.join(summary.get('participants', []))}")
    lines.append("")

    lines.append("## Executive Summary")
    lines.append(summary.get("executive_summary", "N/A"))
    lines.append("")

    if summary.get("key_decisions"):
        lines.append("## Key Decisions")
        for item in summary["key_decisions"]:
            lines.append(f"- **{item.get('decision', '')}** - {item.get('context', '')} *(decided by {item.get('decided_by', 'N/A')})*")
        lines.append("")

    if summary.get("action_items"):
        lines.append("## Action Items")
        lines.append("| Task | Owner | Deadline | Priority |")
        lines.append("|------|-------|----------|----------|")
        for item in summary["action_items"]:
            lines.append(f"| {item.get('task', '')} | {item.get('owner', '')} | {item.get('deadline', 'Not set')} | {item.get('priority', 'medium')} |")
        lines.append("")

    if summary.get("cross_team_dependencies"):
        lines.append("## Cross-Team Dependencies")
        for item in summary["cross_team_dependencies"]:
            lines.append(f"- **{item.get('dependency', '')}** - Team needed: {item.get('team_needed', 'N/A')} - Urgency: {item.get('urgency', 'N/A')}")
        lines.append("")

    if summary.get("unresolved_items"):
        lines.append("## Unresolved Items")
        for item in summary["unresolved_items"]:
            lines.append(f"- {item}")
        lines.append("")

    if summary.get("detailed_notes"):
        lines.append("## Detailed Notes")
        lines.append(summary["detailed_notes"])
        lines.append("")

    return "\n".join(lines)


_load_memory_state()
