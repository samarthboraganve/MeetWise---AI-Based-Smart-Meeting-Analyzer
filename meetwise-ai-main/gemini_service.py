"""
gemini_service.py — All Gemini API calls (transcribe + summarize).
Uses Google Generative AI (Gemini 1.5 Flash).
"""

import os
import json
import google.generativeai as genai
from datetime import datetime, timezone
import asyncio

import audio_storage

# ──────────── Configure Gemini ────────────

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-2.5-flash")


# ──────────── Helpers ────────────

def parse_gemini_json(response_text: str) -> dict:
    """Strip markdown code blocks if present, then parse JSON."""
    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    # Also handle ```json prefix
    if text.startswith("json"):
        text = text[4:]
    return json.loads(text.strip())


# ──────────── Function 1: Transcribe Audio ────────────

async def transcribe_audio(audio_path: str, speaker_name: str) -> str:
    """
    Takes a path to an audio file and the speaker's name.
    Sends the audio to Gemini 1.5 Flash with a transcription prompt.
    Returns the transcribed text as a string.
    """
    prompt = f"""You are a meeting transcription engine optimized for Indian English speakers.

Transcribe the following audio. The speaker's name is {speaker_name}.

Rules:
- Transcribe exactly what is said
- If the speaker uses Hindi or Hinglish words, write them in Roman script
  and add an English translation in parentheses if the meaning is not obvious
  Example: "Accha (okay), so let's start the standup"
- Handle Indian English accents and pronunciations accurately
- Keep meaningful filler words like "accha", "haan", "theek hai"
- Remove pure noise, ums, uhs unless they indicate meaningful hesitation
- Do NOT add timestamps — just the text

Return ONLY the transcription. No headers, no labels, no explanations."""

    try:
        # Upload the audio file to Gemini, specifying the audio mime type
        audio_file = genai.upload_file(audio_path, mime_type="audio/webm")
        
        print(f"[gemini] Uploaded file {audio_file.name}. Waiting for ACTIVE state...")
        while audio_file.state.name == "PROCESSING":
            await asyncio.sleep(2)
            audio_file = genai.get_file(audio_file.name)
            
        if audio_file.state.name != "ACTIVE":
            raise Exception(f"File processing failed for {audio_file.name} (State: {audio_file.state.name})")
            
        response = model.generate_content([prompt, audio_file])
        
        return response.text.strip()
    except Exception as e:
        print(f"[gemini] Transcription error for {speaker_name}: {e}")
        return f"[Transcription failed for {speaker_name}: {str(e)}]"


# ──────────── Function 2: Merge Transcripts ────────────

def merge_transcripts(transcripts: dict[str, str]) -> str:
    """
    Takes a dict of { speaker_name: transcript_text }.
    Combines them into a single formatted transcript block.
    Returns a string.
    """
    parts = []
    for name, text in transcripts.items():
        parts.append(f"=== {name.upper()} ===")
        parts.append(text)
        parts.append("")
    return "\n".join(parts)


# ──────────── Function 3: Summarize Meeting ────────────

async def summarize_meeting(
    merged_transcript: str,
    meeting_type: str,
    team_name: str,
    participants: list[str]
) -> dict:
    """
    Takes the merged transcript and meeting metadata.
    Sends to Gemini with a summarization prompt.
    Returns a structured dictionary (the Master Summary).
    """
    participants_str = ", ".join(participants)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prompt = f"""You are a meeting summarization engine for Indian tech teams.

Below is a transcript from a {meeting_type} meeting held by the {team_name} team.
Participants: {participants_str}

This summary will be shared with OTHER teams in the organization who were NOT
in this meeting. Write it so that someone reading this for the first time can
fully understand what was discussed and decided — without needing to ask anyone.

Be specific:
- Don't say "discussed the design" → say "decided on card-based layout inspired by Stripe"
- Don't say "someone will handle it" → say "Sneha will handle mobile responsiveness"
- Include context for WHY decisions were made, not just WHAT was decided

Pay special attention to cross-team dependencies — anything that requires input
from or affects another team. These are the most valuable part of the summary.

Meeting type context:
- standup: focus on blockers, today's priorities, help needed
- planning: focus on scope, ownership, timelines
- review: focus on feedback, approvals, changes requested
- general: balanced coverage of all topics

Use today's date: {today}

Respond ONLY with valid JSON in this exact format (no markdown, no backticks):

{{
    "meeting_title": "Auto-generated descriptive title for this meeting",
    "team": "{team_name}",
    "meeting_type": "{meeting_type}",
    "date": "{today}",
    "duration_estimate": "Estimated duration based on transcript length",
    "participants": {json.dumps(participants)},

    "executive_summary": "3-5 sentences. A busy person reads ONLY this and gets the full picture.",

    "key_decisions": [
        {{
            "decision": "What was decided",
            "context": "Brief context on why or what alternatives were discussed",
            "decided_by": "Who made or proposed the decision"
        }}
    ],

    "action_items": [
        {{
            "task": "Specific, actionable task description",
            "owner": "Name of the person responsible",
            "deadline": "If mentioned in transcript, else 'Not set'",
            "priority": "high / medium / low"
        }}
    ],

    "cross_team_dependencies": [
        {{
            "dependency": "What is needed from or affects another team",
            "team_needed": "Which team (if identifiable from context)",
            "urgency": "blocking / needed soon / nice to have"
        }}
    ],

    "unresolved_items": [
        "Topics that were raised but not concluded — need follow-up"
    ],

    "detailed_notes": "A longer narrative summary for those who want full depth"
}}

TRANSCRIPT:
{merged_transcript}"""

    try:
        response = model.generate_content(prompt)
        summary = parse_gemini_json(response.text)
        return summary
    except json.JSONDecodeError as e:
        print(f"[gemini] JSON parse error: {e}")
        print(f"[gemini] Raw response: {response.text[:500]}")
        # Return a fallback summary
        return _fallback_summary(team_name, meeting_type, participants, today, merged_transcript)
    except Exception as e:
        print(f"[gemini] Summarization error: {e}")
        return _fallback_summary(team_name, meeting_type, participants, today, merged_transcript)


def _fallback_summary(team_name, meeting_type, participants, date, transcript) -> dict:
    """Fallback if Gemini fails to produce valid JSON."""
    return {
        "meeting_title": f"{team_name} {meeting_type.title()} Meeting",
        "team": team_name,
        "meeting_type": meeting_type,
        "date": date,
        "duration_estimate": "Unknown",
        "participants": participants,
        "executive_summary": "Summary generation encountered an issue. Please review the detailed notes.",
        "key_decisions": [],
        "action_items": [],
        "cross_team_dependencies": [],
        "unresolved_items": ["Summary needs to be regenerated"],
        "detailed_notes": transcript[:2000] if transcript else "No transcript available.",
    }


# ──────────── Full Pipeline ────────────

async def process_meeting(room_code: str, room_data: dict) -> dict:
    """
    Called by the /api/rooms/{code}/end endpoint.
    Orchestrates the full pipeline:
    1. Transcribe each participant's audio
    2. Merge transcripts
    3. Generate Master Summary
    """
    print(f"[gemini] Starting pipeline for room {room_code}")

    # Step 1: Transcribe each participant's audio
    transcripts = {}
    for pid, pinfo in room_data["participants"].items():
        audio_reference = pinfo.get("audio_path") or os.path.join("audio_store", room_code, f"{pinfo['name']}.webm")
        temp_audio_path = None

        try:
            if audio_reference and os.path.exists(audio_reference):
                audio_path = audio_reference
            elif pinfo.get("audio_path") and audio_storage.STORAGE_ENABLED:
                print(f"[gemini] Downloading audio for {pinfo['name']} from Supabase Storage...")
                audio_path = audio_storage.download_audio_to_temp(pinfo["audio_path"])
                temp_audio_path = audio_path
            else:
                audio_path = audio_reference

            if audio_path and os.path.exists(audio_path):
                print(f"[gemini] Transcribing audio for {pinfo['name']}...")
                transcript = await transcribe_audio(audio_path, pinfo["name"])
                transcripts[pinfo["name"]] = transcript
            else:
                print(f"[gemini] No audio file found for {pinfo['name']} at {audio_reference}")
                transcripts[pinfo["name"]] = f"[No audio recorded for {pinfo['name']}]"
        finally:
            audio_storage.cleanup_temp_file(temp_audio_path)

    # Step 2: Merge all transcripts
    merged = merge_transcripts(transcripts)
    print(f"[gemini] Merged transcript ({len(merged)} chars)")

    # Step 3: Generate Master Summary
    print(f"[gemini] Generating summary...")
    summary = await summarize_meeting(
        merged_transcript=merged,
        meeting_type=room_data.get("meeting_type", "general"),
        team_name=room_data.get("team_name", "Unknown"),
        participants=list(transcripts.keys()),
    )

    print(f"[gemini] Pipeline complete for room {room_code}")
    return summary
