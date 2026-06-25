"""
room_manager.py — State management for MeetWise AI.
All data lives in in-memory dictionaries.
"""

import uuid
import os
from datetime import datetime, timezone


# ──────────── In-memory stores ────────────

workspaces = {}   # { workspace_id: { "name": str, "teams": [team_id, ...] } }
teams = {}        # { team_id: { "team_name": str, "workspace_id": str } }
rooms = {}        # { room_code: { ... room data ... } }
summaries = {}    # { summary_id: { ... summary data ... } }


# ──────────── ID generators ────────────

def _gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ──────────── Workspace operations ────────────

def create_workspace(name: str) -> dict:
    ws_id = _gen_id("ws")
    workspaces[ws_id] = {
        "workspace_id": ws_id,
        "name": name,
        "teams": [],
    }
    return {"workspace_id": ws_id, "name": name}


def join_workspace(workspace_id: str, user_name: str) -> dict | None:
    ws = workspaces.get(workspace_id)
    if ws is None:
        return None
    team_list = [get_team_info(tid) for tid in ws["teams"]]
    return {
        "workspace_id": workspace_id,
        "name": ws["name"],
        "teams": team_list,
    }


def get_workspace(workspace_id: str) -> dict | None:
    return workspaces.get(workspace_id)


# ──────────── Team operations ────────────

def create_team(workspace_id: str, team_name: str) -> dict | None:
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
    return {"team_id": team_id, "team_name": team_name}


def get_team_info(team_id: str) -> dict | None:
    t = teams.get(team_id)
    if t is None:
        return None
    # count summaries belonging to this team
    count = sum(1 for s in summaries.values() if s.get("team_id") == team_id)
    return {
        "team_id": team_id,
        "team_name": t["team_name"],
        "summary_count": count,
    }


def get_teams_for_workspace(workspace_id: str) -> list[dict]:
    ws = workspaces.get(workspace_id)
    if ws is None:
        return []
    return [get_team_info(tid) for tid in ws["teams"] if get_team_info(tid)]


# ──────────── Room operations ────────────

def create_room(room_code: str, workspace_id: str, team_id: str,
                meeting_type: str, host_name: str) -> dict | None:
    t = teams.get(team_id)
    if t is None:
        return None
    participant_id = _gen_id("p")
    rooms[room_code] = {
        "room_code": room_code,
        "workspace_id": workspace_id,
        "team_id": team_id,
        "team_name": t["team_name"],
        "meeting_type": meeting_type,
        "is_active": True,
        "host_id": participant_id,
        "participants": {
            participant_id: {
                "id": participant_id,
                "name": host_name,
                "is_host": True,
            }
        },
        "started_at": datetime.now(timezone.utc).isoformat(),
        "uploads_received": 0,
    }
    return {"room_code": room_code, "participant_id": participant_id}


def join_room(room_code: str, participant_name: str) -> dict | None:
    room = rooms.get(room_code)
    if room is None or not room["is_active"]:
        return None
    participant_id = _gen_id("p")
    room["participants"][participant_id] = {
        "id": participant_id,
        "name": participant_name,
        "is_host": False,
    }
    return {"room_code": room_code, "participant_id": participant_id}


def get_room(room_code: str) -> dict | None:
    return rooms.get(room_code)


def get_room_status(room_code: str) -> dict | None:
    room = rooms.get(room_code)
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
    room = rooms.get(room_code)
    if room is None:
        return False
    room["is_active"] = False
    return True


def record_upload(room_code: str) -> int:
    """Increment upload counter, return new count."""
    room = rooms.get(room_code)
    if room is None:
        return 0
    room["uploads_received"] = room.get("uploads_received", 0) + 1
    return room["uploads_received"]


def all_uploads_received(room_code: str) -> bool:
    room = rooms.get(room_code)
    if room is None:
        return False
    return room["uploads_received"] >= len(room["participants"])


# ──────────── Summary operations ────────────

def save_summary(summary_id: str, team_id: str, workspace_id: str,
                 room_code: str, summary_data: dict) -> dict:
    room = rooms.get(room_code, {})
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
    summaries[summary_id] = entry
    return entry


def get_summary(summary_id: str) -> dict | None:
    entry = summaries.get(summary_id)
    if entry is None:
        return None
    return entry["data"] | {"summary_id": summary_id}


def get_summaries_for_team(team_id: str) -> dict:
    t = teams.get(team_id)
    if t is None:
        return {"team_name": "Unknown", "summaries": []}
    team_summaries = []
    for s in summaries.values():
        if s["team_id"] == team_id:
            team_summaries.append({
                "summary_id": s["summary_id"],
                "meeting_title": s["meeting_title"],
                "meeting_type": s["meeting_type"],
                "date": s["date"],
                "duration": s["duration_estimate"],
                "participant_count": s["participant_count"],
            })
    return {"team_name": t["team_name"], "summaries": team_summaries}


def get_summaries_for_workspace(workspace_id: str) -> dict:
    ws = workspaces.get(workspace_id)
    if ws is None:
        return {"workspace_name": "Unknown", "teams": []}
    result_teams = []
    for tid in ws["teams"]:
        t = teams.get(tid)
        if t is None:
            continue
        team_data = get_summaries_for_team(tid)
        result_teams.append({
            "team_id": tid,
            "team_name": t["team_name"],
            "summaries": team_data["summaries"],
        })
    return {"workspace_name": ws["name"], "teams": result_teams}


def get_summary_as_markdown(summary_id: str) -> str | None:
    entry = summaries.get(summary_id)
    if entry is None:
        return None
    d = entry["data"]
    lines = []
    lines.append(f"# {d.get('meeting_title', 'Meeting Summary')}")
    lines.append("")
    lines.append(f"**Team:** {d.get('team', 'N/A')}")
    lines.append(f"**Type:** {d.get('meeting_type', 'N/A')}")
    lines.append(f"**Date:** {d.get('date', 'N/A')}")
    lines.append(f"**Duration:** {d.get('duration_estimate', 'N/A')}")
    lines.append(f"**Participants:** {', '.join(d.get('participants', []))}")
    lines.append("")

    lines.append("## Executive Summary")
    lines.append(d.get("executive_summary", "N/A"))
    lines.append("")

    if d.get("key_decisions"):
        lines.append("## Key Decisions")
        for kd in d["key_decisions"]:
            lines.append(f"- **{kd.get('decision', '')}** — {kd.get('context', '')} *(decided by {kd.get('decided_by', 'N/A')})*")
        lines.append("")

    if d.get("action_items"):
        lines.append("## Action Items")
        lines.append("| Task | Owner | Deadline | Priority |")
        lines.append("|------|-------|----------|----------|")
        for ai in d["action_items"]:
            lines.append(f"| {ai.get('task','')} | {ai.get('owner','')} | {ai.get('deadline','Not set')} | {ai.get('priority','medium')} |")
        lines.append("")

    if d.get("cross_team_dependencies"):
        lines.append("## Cross-Team Dependencies")
        for dep in d["cross_team_dependencies"]:
            lines.append(f"- **{dep.get('dependency', '')}** — Team needed: {dep.get('team_needed', 'N/A')} — Urgency: {dep.get('urgency', 'N/A')}")
        lines.append("")

    if d.get("unresolved_items"):
        lines.append("## Unresolved Items")
        for item in d["unresolved_items"]:
            lines.append(f"- {item}")
        lines.append("")

    if d.get("detailed_notes"):
        lines.append("## Detailed Notes")
        lines.append(d["detailed_notes"])
        lines.append("")

    return "\n".join(lines)
