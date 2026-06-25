# MeetWise AI — Team Kickoff Document

> **Read this fully before writing any code.**
> This is our single source of truth. If something here conflicts with a WhatsApp message, this document wins.

---

## Table of Contents

1. [What Are We Building](#1-what-are-we-building)
2. [How It Works — End to End](#2-how-it-works--end-to-end)
3. [Tech Stack](#3-tech-stack)
4. [Project Structure](#4-project-structure)
5. [The API Contract](#5-the-api-contract)
6. [The Gemini Pipeline](#6-the-gemini-pipeline)
7. [Frontend Pages](#7-frontend-pages)
8. [Audio Capture — How It Works in the Browser](#8-audio-capture--how-it-works-in-the-browser)
9. [Who Does What](#9-who-does-what)
10. [Setup Instructions](#10-setup-instructions)
11. [Git Workflow](#11-git-workflow)
12. [Timeline](#12-timeline)
13. [Integration Checklist](#13-integration-checklist)
14. [Deployment](#14-deployment)
15. [Demo Script](#15-demo-script)
16. [Devpost Submission](#16-devpost-submission)
17. [Known Constraints and Gotchas](#17-known-constraints-and-gotchas)

---

## 1. What Are We Building

**MeetWise AI** is a browser-based meeting tool where team members join a room, talk, and when the meeting ends, Gemini AI automatically generates a structured Master Summary of everything that was discussed.

These summaries are organized by teams inside a shared workspace — so Team Backend can read Team Frontend's meeting summary without scheduling a sync call.

### What It Is

- A meeting room you join in the browser
- Each person's mic is recorded silently in the background
- When the meeting ends, all audio is sent to the server
- Gemini transcribes each person's audio (we know who's speaking because each person is on their own machine)
- All transcripts are merged and Gemini generates one Master Summary
- The summary shows up on a shared dashboard, organized by team
- Any team in the workspace can read any other team's summaries

### What It Is NOT

- Not a video calling tool (people use Meet/Zoom/in-person separately — we just capture audio)
- Not a live transcription tool (nobody sees text during the meeting)
- Not a notes app (the AI generates everything — no manual input)
- Not a translation tool (cool idea, out of scope)

### Why This Architecture Is Smart

Traditional meeting AI tools use one microphone and try to figure out who said what (speaker diarization). This is unreliable, especially with similar voices or crosstalk.

Our approach: each person's browser records ONLY their voice. We already know who's speaking from their login. No diarization needed. The problem is solved by design, not by AI.

---

## 2. How It Works — End to End

### Before the Meeting

```
1. Someone creates a Workspace (e.g., "Acme Corp")
2. Teams are created inside the workspace (e.g., "Frontend", "Backend", "Design")
3. A host starts a new meeting → picks their team + meeting type → gets a 6-digit room code
4. Host shares the room code with teammates (WhatsApp, verbally, whatever)
```

### During the Meeting

```
5. Each participant opens MeetWise in their browser
6. They enter the room code + their name → click Join
7. Browser asks for mic permission → they click Allow
8. The browser starts recording their mic audio silently
9. The meeting page shows: participant list + timer + "Recording" indicator
10. People just talk normally. Nothing else happens on screen.
```

### Ending the Meeting

```
11. Host clicks "End Meeting"
12. Each participant's browser stops recording
13. Each browser uploads the full audio file to the server via HTTP POST
14. Server now has one audio file per participant, labeled with their name
```

### AI Processing (server-side, automatic)

```
15. Server sends each audio file to Gemini separately:
    "Transcribe this audio. The speaker is Pratham."
    "Transcribe this audio. The speaker is Rahul."
    "Transcribe this audio. The speaker is Sneha."

16. Server gets back three transcripts, each labeled with the speaker name

17. Server combines all transcripts into one unified text block

18. Server sends the combined transcript to Gemini one more time:
    "Here is a full meeting transcript. Generate a Master Summary with
     decisions, action items, owners, and cross-team dependencies."

19. Gemini returns structured summary JSON

20. Server saves the summary under the team in the workspace
```

### After the Meeting

```
21. Anyone in the workspace opens the dashboard
22. They see all teams and their meeting summaries
23. They click on a summary to read it
24. They can download it as markdown
25. No sync meeting needed — the summary tells them everything
```

### Visual Flow

```
  PARTICIPANT BROWSERS                    SERVER                         GEMINI
  ┌──────────────┐
  │ Pratham's mic │──record──►┐
  └──────────────┘           │
  ┌──────────────┐           │  upload    ┌──────────┐  transcribe   ┌──────────┐
  │ Rahul's mic  │──record──►├──────────►│  FastAPI  │─────────────►│  Gemini  │
  └──────────────┘           │           │  Server   │◄─────────────│  1.5     │
  ┌──────────────┐           │           │           │  summarize   │  Flash   │
  │ Sneha's mic  │──record──►┘           │           │─────────────►│          │
  └──────────────┘                       │           │◄─────────────│          │
                                         └─────┬─────┘              └──────────┘
                                               │
                                         ┌─────▼─────┐
                                         │ Dashboard  │
                                         │ Team A: ✓  │
                                         │ Team B: ✓  │
                                         └───────────┘
```

---

## 3. Tech Stack

| What             | Tool                       | Version / Notes                         |
|------------------|----------------------------|-----------------------------------------|
| Language         | Python                     | 3.11 or higher                          |
| Web framework    | FastAPI                    | Latest (`pip install fastapi`)          |
| Server           | Uvicorn                    | ASGI server for FastAPI                 |
| AI               | google-generativeai        | Gemini 1.5 Flash, free tier             |
| Frontend         | Vanilla HTML + CSS + JS    | No React, no build step                 |
| Audio capture    | MediaRecorder API          | Browser-native, outputs .webm           |
| File uploads     | python-multipart           | Required by FastAPI for file handling   |
| Templating       | Jinja2                     | Optional, for dynamic HTML pages        |
| Deployment       | Render                     | Free tier, HTTPS included               |
| Version control  | Git + GitHub               | Single repo, everyone pushes to main    |

### requirements.txt

```
fastapi
uvicorn[standard]
google-generativeai
python-multipart
jinja2
python-dotenv
```

### Why These Choices

- **FastAPI over Flask:** async support out of the box, which matters when making multiple Gemini API calls
- **Vanilla HTML over React:** no build step, no npm, no node_modules — just files that work
- **In-memory dict over a database:** hackathon lasts hours, not months — no need for PostgreSQL
- **Gemini Flash over Pro:** faster responses, higher free tier limits, good enough quality
- **Render over Railway:** simpler Python deployment, free HTTPS

---

## 4. Project Structure

```
meetwise-ai/
│
├── main.py                     # FastAPI application — all API endpoints
├── room_manager.py             # Room, team, workspace state management
├── gemini_service.py           # All Gemini API calls (transcribe + summarize)
├── requirements.txt            # Python dependencies
├── .env                        # GEMINI_API_KEY=your_key_here (DO NOT COMMIT)
├── .gitignore                  # .env, audio_store/, __pycache__/, .venv/
├── README.md                   # Project overview for GitHub + Devpost
│
├── audio_store/                # Temp storage for uploaded audio files (gitignored)
│   └── ROOM_CODE/
│       ├── pratham.webm
│       ├── rahul.webm
│       └── sneha.webm
│
├── summaries/                  # Saved summary JSON files (gitignored)
│   └── summary_abc123.json
│
└── static/                     # All frontend files (served by FastAPI)
    ├── index.html              # Landing page — create/join workspace
    ├── dashboard.html          # Workspace dashboard — all teams + summaries
    ├── create-room.html        # Create a new meeting room
    ├── room.html               # Meeting room — participants + timer + recording
    ├── summary.html            # View a single meeting summary
    ├── style.css               # Shared styles (dark theme)
    └── app.js                  # Audio capture + API calls + UI logic
```

### Who Touches What

```
Person 1 (Backend):     main.py, room_manager.py
Person 2 (AI/Gemini):   gemini_service.py, test_gemini.py (their own test script)
Person 3 (Frontend):    static/* (all files in the static folder)
Person 4 (Demo/QA):     README.md, test audio files, screenshots, demo video
```

**No two people edit the same file.** This means almost zero merge conflicts.

---

## 5. The API Contract

This is the most important section. Person 1 builds these endpoints. Person 3 calls them from the frontend. Person 2 builds the functions that Person 1 calls internally.

**Everyone must agree on this before writing code. If you change an endpoint, tell the group chat immediately.**

### Workspace Endpoints

```
POST /api/workspace/create
  Request:  { "name": "Acme Corp" }
  Response: { "workspace_id": "ws_a1b2c3", "name": "Acme Corp" }

POST /api/workspace/join
  Request:  { "workspace_id": "ws_a1b2c3", "user_name": "Pratham" }
  Response: { "workspace_id": "ws_a1b2c3", "name": "Acme Corp", "teams": [...] }
```

### Team Endpoints

```
POST /api/teams/create
  Request:  { "workspace_id": "ws_a1b2c3", "team_name": "Frontend" }
  Response: { "team_id": "tm_xyz", "team_name": "Frontend" }

GET /api/teams/{workspace_id}
  Response: {
    "teams": [
      { "team_id": "tm_xyz", "team_name": "Frontend", "summary_count": 3 },
      { "team_id": "tm_abc", "team_name": "Backend", "summary_count": 1 }
    ]
  }
```

### Room (Meeting) Endpoints

```
POST /api/rooms/create
  Request:  {
    "workspace_id": "ws_a1b2c3",
    "team_id": "tm_xyz",
    "meeting_type": "standup",     # options: standup, planning, review, general
    "host_name": "Pratham"
  }
  Response: { "room_code": "FE2041", "participant_id": "p_001" }

POST /api/rooms/join
  Request:  { "room_code": "FE2041", "participant_name": "Rahul" }
  Response: { "room_code": "FE2041", "participant_id": "p_002" }

GET /api/rooms/{room_code}/status
  Response: {
    "room_code": "FE2041",
    "team_name": "Frontend",
    "meeting_type": "standup",
    "is_active": true,
    "participants": [
      { "id": "p_001", "name": "Pratham", "is_host": true },
      { "id": "p_002", "name": "Rahul", "is_host": false }
    ],
    "started_at": "2026-04-01T14:30:00Z"
  }
```

### Audio Upload Endpoint

```
POST /api/audio/upload
  Content-Type: multipart/form-data
  Fields:
    - room_code: "FE2041"
    - participant_id: "p_001"
    - audio: <file.webm>
  Response: { "status": "uploaded", "filename": "pratham.webm" }
```

### End Meeting + Summarization

```
POST /api/rooms/{room_code}/end
  Response: { "status": "processing", "summary_id": "sum_12345" }

  NOTE: This triggers the Gemini pipeline internally.
  The frontend should poll GET /api/summaries/{summary_id} until it's ready,
  or this endpoint can block until processing is complete (simpler for hackathon).
  
  DECISION: For the hackathon, this endpoint BLOCKS until the summary is ready
  and returns:
  {
    "status": "complete",
    "summary_id": "sum_12345",
    "summary": { ...full summary object... }
  }
  
  The frontend shows a loading spinner while waiting.
```

### Summary Endpoints

```
GET /api/summaries/{summary_id}
  Response: { ...full summary JSON, see section 6 for the exact shape... }

GET /api/summaries/team/{team_id}
  Response: {
    "team_name": "Frontend",
    "summaries": [
      {
        "summary_id": "sum_12345",
        "meeting_title": "Landing Page Design Discussion",
        "meeting_type": "review",
        "date": "2026-04-01",
        "duration": "12 min",
        "participant_count": 4
      },
      ...
    ]
  }

GET /api/summaries/workspace/{workspace_id}
  Response: {
    "workspace_name": "Acme Corp",
    "teams": [
      {
        "team_id": "tm_xyz",
        "team_name": "Frontend",
        "summaries": [ ...same shape as above... ]
      },
      {
        "team_id": "tm_abc",
        "team_name": "Backend",
        "summaries": [ ... ]
      }
    ]
  }

GET /api/summaries/{summary_id}/download
  Response: returns a .md file as a download
  Content-Type: text/markdown
  Content-Disposition: attachment; filename="meeting-summary-FE2041.md"
```

---

## 6. The Gemini Pipeline

This is Person 2's entire job. Everything here lives in `gemini_service.py`.

### Function 1: transcribe_audio

```python
async def transcribe_audio(audio_path: str, speaker_name: str) -> str:
    """
    Takes a path to an audio file and the speaker's name.
    Sends the audio to Gemini 1.5 Flash with a transcription prompt.
    Returns the transcribed text as a string.
    """
```

**Prompt to use (iterate on this):**

```
You are a meeting transcription engine optimized for Indian English speakers.

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

Return ONLY the transcription. No headers, no labels, no explanations.
```

**Output example:**

```
So I've been working on the landing page design. I think we should go with a
card-based layout, something clean like what Stripe does. The hero section
needs to be bold but not cluttered. I'll have the mockup ready by tomorrow.
Accha (okay), one more thing — we need the brand colors from the design team
before I can finalize anything.
```

### Function 2: merge_transcripts

```python
def merge_transcripts(transcripts: dict[str, str]) -> str:
    """
    Takes a dict of { speaker_name: transcript_text }.
    Combines them into a single formatted transcript block.
    Returns a string.
    
    NOTE: Since we don't have precise per-sentence timestamps,
    we just concatenate each speaker's full transcript with their name label.
    Gemini is smart enough to understand the conversational context.
    """
```

**Output example:**

```
=== PRATHAM ===
So I've been working on the landing page design. I think we should go with a
card-based layout, something clean like what Stripe does. The hero section
needs to be bold but not cluttered. I'll have the mockup ready by tomorrow.
Accha, one more thing — we need the brand colors from the design team before
I can finalize anything.

=== RAHUL ===
Yeah the card layout makes sense. I was thinking Tailwind for styling, it'll
speed things up. For the API integration on the pricing cards, I need to know
the response format from the backend team. Can someone check with them?
Also, I can do the hero section prototype by day after tomorrow.

=== SNEHA ===
I'll handle mobile responsiveness. I've done this before with the last project
so it shouldn't take long. Regarding the animation library — are we going with
Framer Motion or just CSS transitions? We should decide that before Arjun starts
the component library.
```

### Function 3: summarize_meeting

```python
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
```

**Prompt to use (iterate on this):**

```
You are a meeting summarization engine for Indian tech teams.

Below is a transcript from a {meeting_type} meeting held by the {team_name} team.
Participants: {participants}

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

Respond ONLY with valid JSON in this exact format (no markdown, no backticks):

{
    "meeting_title": "Auto-generated descriptive title for this meeting",
    "team": "The team name",
    "meeting_type": "standup/planning/review/general",
    "date": "YYYY-MM-DD",
    "duration_estimate": "Estimated duration based on transcript length",
    "participants": ["name1", "name2"],

    "executive_summary": "3-5 sentences. A busy person reads ONLY this and gets the full picture.",

    "key_decisions": [
        {
            "decision": "What was decided",
            "context": "Brief context on why or what alternatives were discussed",
            "decided_by": "Who made or proposed the decision"
        }
    ],

    "action_items": [
        {
            "task": "Specific, actionable task description",
            "owner": "Name of the person responsible",
            "deadline": "If mentioned in transcript, else 'Not set'",
            "priority": "high / medium / low"
        }
    ],

    "cross_team_dependencies": [
        {
            "dependency": "What is needed from or affects another team",
            "team_needed": "Which team (if identifiable from context)",
            "urgency": "blocking / needed soon / nice to have"
        }
    ],

    "unresolved_items": [
        "Topics that were raised but not concluded — need follow-up"
    ],

    "detailed_notes": "A longer narrative summary for those who want full depth"
}
```

### The Full Pipeline (called when a meeting ends)

```python
async def process_meeting(room_code: str, room_data: dict) -> dict:
    """
    Called by the /api/rooms/{code}/end endpoint.
    Orchestrates the full pipeline.
    """
    
    # Step 1: Transcribe each participant's audio
    transcripts = {}
    for participant_id, participant_info in room_data["participants"].items():
        audio_path = f"audio_store/{room_code}/{participant_info['name']}.webm"
        transcript = await transcribe_audio(audio_path, participant_info["name"])
        transcripts[participant_info["name"]] = transcript
    
    # Step 2: Merge all transcripts
    merged = merge_transcripts(transcripts)
    
    # Step 3: Generate Master Summary
    summary = await summarize_meeting(
        merged_transcript=merged,
        meeting_type=room_data["meeting_type"],
        team_name=room_data["team_name"],
        participants=list(transcripts.keys())
    )
    
    return summary
```

### Testing Independently (IMPORTANT)

Person 2 should create a `test_gemini.py` file (not part of the main app) to test everything without needing the server:

```python
# test_gemini.py — Person 2's testing script
# Run this standalone: python test_gemini.py

import asyncio
from gemini_service import transcribe_audio, merge_transcripts, summarize_meeting

async def main():
    # Test with a sample audio file
    transcript = await transcribe_audio("test_audio/sample.webm", "Pratham")
    print("=== TRANSCRIPTION ===")
    print(transcript)
    
    # Test merge with fake data
    transcripts = {
        "Pratham": transcript,
        "Rahul": "I agree with the card layout. I'll handle the Tailwind setup.",
    }
    merged = merge_transcripts(transcripts)
    print("\n=== MERGED ===")
    print(merged)
    
    # Test summarization
    summary = await summarize_meeting(merged, "review", "Frontend", ["Pratham", "Rahul"])
    print("\n=== SUMMARY ===")
    print(summary)

asyncio.run(main())
```

**Person 2 should have this working with real audio BEFORE Person 1 finishes the backend.**

---

## 7. Frontend Pages

Person 3 owns all of this. Below is the page-by-page spec.

### Page 1: Landing (`index.html`)

**Purpose:** Entry point. Create a workspace or join an existing one.

**Elements:**
- App title + tagline: "Meetings end. Clarity begins."
- "Create Workspace" button → shows input for workspace name → calls `POST /api/workspace/create` → redirects to dashboard.html
- "Join Workspace" form → input for workspace ID + user name → calls `POST /api/workspace/join` → redirects to dashboard.html

**State to save (in sessionStorage):**
- `workspace_id`
- `user_name`

### Page 2: Dashboard (`dashboard.html`)

**Purpose:** See all teams and their meeting summaries. Start new meetings.

**Elements:**
- Header: workspace name + "Create Team" button + "New Meeting" button
- Team list (collapsible sections), each showing their meeting summaries
- Each summary entry shows: title, date, duration, participant count → clickable to summary.html
- "Create Team" → modal with team name input → calls `POST /api/teams/create`
- "New Meeting" → redirects to create-room.html

**Data source:** `GET /api/summaries/workspace/{workspace_id}`

### Page 3: Create Room (`create-room.html`)

**Purpose:** Host creates a new meeting.

**Elements:**
- Team selector (dropdown populated from `GET /api/teams/{workspace_id}`)
- Meeting type selector (standup / planning / review / general)
- "Create Meeting" button → calls `POST /api/rooms/create` → redirects to room.html with room_code in URL

### Page 4: Meeting Room (`room.html`)

**Purpose:** The actual meeting room. Minimal UI. Audio recording happens here.

**URL:** `room.html?code=FE2041&pid=p_001`

**Elements:**
- Room code displayed prominently (so people can share it)
- Meeting type label
- Timer (starts from 0:00, counts up using JS setInterval)
- Participant list (poll `GET /api/rooms/{code}/status` every 5 seconds to update)
- Recording indicator: red dot + "Recording from your mic"
- "Join this meeting" form (if arriving via shared room code without a participant_id)
- "End Meeting" button (visible only to host / or visible to everyone for simplicity)

**Audio behavior:**
- On page load (if participant): request mic → start MediaRecorder → save to blob
- On "End Meeting" click: stop recording → upload audio → show loading spinner → redirect to summary when ready

**This page MUST work on both Chrome desktop and Chrome mobile (for the demo).**

### Page 5: Summary View (`summary.html`)

**Purpose:** Display a single meeting's Master Summary beautifully.

**URL:** `summary.html?id=sum_12345`

**Elements:**
- Back button → returns to dashboard
- Meeting title (large)
- Meta info: team name, date, duration, participant list
- Download button (markdown) → calls `GET /api/summaries/{id}/download`
- Copy link button
- Executive Summary section (highlighted, prominent)
- Key Decisions section (list with checkmarks)
- Action Items section (table: task / owner / deadline / priority)
- Cross-Team Dependencies section (highlighted differently — this is the killer feature)
- Unresolved Items section
- Detailed Notes (collapsible)

**Data source:** `GET /api/summaries/{summary_id}`

### Design Notes

- **Dark theme.** Looks good in demos, hides imperfections.
- **Keep it minimal.** No animations, no gradients, no fancy stuff. Clean cards with clear typography.
- **Use system fonts:** `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- **Color palette suggestion:**
  - Background: `#0a0a0a`
  - Cards: `#1a1a1a`
  - Primary text: `#ffffff`
  - Secondary text: `#888888`
  - Accent (buttons, highlights): `#4f8ff7`
  - Cross-team dependency highlight: `#f59e0b` (amber/warning color)
  - Success/decisions: `#10b981` (green)

---

## 8. Audio Capture — How It Works in the Browser

This is the trickiest frontend piece. Here's exactly how it works.

### Starting the Recording

```javascript
// Request microphone access
const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

// Create MediaRecorder — it will record the entire meeting as one file
const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });

// Collect audio data into chunks (these are combined into one file at the end)
const audioChunks = [];
mediaRecorder.ondataavailable = (event) => {
    if (event.data.size > 0) {
        audioChunks.push(event.data);
    }
};

// Start recording
mediaRecorder.start();
```

### Stopping and Uploading

```javascript
// When "End Meeting" is clicked:
mediaRecorder.stop();

mediaRecorder.onstop = async () => {
    // Combine all chunks into one file
    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
    
    // Upload to server
    const formData = new FormData();
    formData.append('room_code', roomCode);
    formData.append('participant_id', participantId);
    formData.append('audio', audioBlob, 'recording.webm');
    
    // Show loading spinner
    showLoadingState("Processing your meeting...");
    
    const response = await fetch('/api/audio/upload', {
        method: 'POST',
        body: formData
    });
    
    // After upload, call end meeting (only host does this)
    if (isHost) {
        const endResponse = await fetch(`/api/rooms/${roomCode}/end`, {
            method: 'POST'
        });
        const result = await endResponse.json();
        
        // Redirect to summary page
        window.location.href = `summary.html?id=${result.summary_id}`;
    }
};
```

### Important Notes

- `mimeType: 'audio/webm;codecs=opus'` — this is what Chrome supports. Don't try mp3 or wav.
- The recording is ONE continuous file, not chunks. `audioChunks` array is just how the browser buffers data internally — they get combined into one blob at the end.
- Mic access requires HTTPS or localhost. On `http://192.168.x.x` it WILL NOT WORK. Test on `localhost:8000`.
- Chrome allows two tabs to share the mic (e.g., Google Meet + MeetWise). Firefox does not. Our target is Chrome only.

### Handling the "End Meeting" Flow for Non-Host Participants

The host clicks "End Meeting", but ALL participants need to stop recording and upload their audio. Two approaches:

**Approach A (simpler, recommended for hackathon):**
- Everyone has an "End Meeting" button, not just the host
- When anyone clicks it, their browser stops recording and uploads
- The LAST person to upload triggers the processing
- Problem: need to know when all uploads are done

**Approach B (actually simplest):**
- Polling. Every participant's browser polls `GET /api/rooms/{code}/status` every 5 seconds
- When the host clicks "End Meeting", the server sets `is_active: false`
- All other browsers detect this on next poll → stop recording → upload automatically
- After uploading, redirect to a "waiting for summary" page
- The backend waits until all expected audio files are received, then processes

**Go with Approach B.** It avoids any WebSocket complexity and the polling is already there for the participant list.

---

## 9. Who Does What

### Person 1 — Backend Lead

**Files:** `main.py`, `room_manager.py`

**Your job:** Build all the API endpoints listed in Section 5. Store everything in Python dictionaries (no database). Handle file uploads and save audio files to `audio_store/`. When "End Meeting" is called, call Person 2's functions from `gemini_service.py`. Handle deployment to Render at the end.

**Day-of checklist:**
1. Set up FastAPI project with static file serving
2. Build workspace + team endpoints (CRUD on dictionaries)
3. Build room create/join/status endpoints
4. Build audio upload endpoint (save files to `audio_store/{room_code}/`)
5. Build end-meeting endpoint (calls `process_meeting()` from gemini_service)
6. Build summary retrieval endpoints
7. Build markdown download endpoint
8. Test all endpoints with curl or Postman
9. Integrate with Person 2's gemini_service
10. Deploy to Render

**You can test everything without Person 2 or Person 3.** Just return dummy JSON from the summary endpoints initially. Replace with real Gemini output when Person 2's code is ready.

**Critical detail:** The end-meeting endpoint needs to wait for all participants to upload their audio before processing. The simplest way: when `/api/rooms/{code}/end` is called, the server marks the room as ended. Each participant's browser detects this via polling, uploads their audio, and calls `POST /api/audio/upload`. The server counts uploads. When `uploads_received == participant_count`, trigger processing.

### Person 2 — AI / Gemini Lead

**Files:** `gemini_service.py`, `test_gemini.py` (your personal test script)

**Your job:** Make Gemini transcribe audio accurately and generate high-quality summaries. This is the most important job because the summary quality IS the product. A good summary makes judges go "wow." A mediocre summary makes the whole project feel like a toy.

**Day-of checklist:**
1. Get Gemini API key from Google AI Studio (https://makersuite.google.com)
2. Test basic audio transcription with a sample .webm file
3. Iterate on the transcription prompt until Indian English is handled well
4. Test merge_transcripts with sample data
5. Write and iterate on the summarization prompt — this is where you spend most of your time
6. Test with multiple fake transcripts to ensure the summary structure is consistent
7. Make sure the output is VALID JSON every time (add parsing + retry logic)
8. Hand off working functions to Person 1

**You do NOT need the server running. Test everything standalone.**

**Critical detail:** Gemini sometimes returns JSON with markdown backticks (```json ... ```). You need to strip those before parsing. Add error handling:

```python
import json

def parse_gemini_json(response_text: str) -> dict:
    # Strip markdown code blocks if present
    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]  # remove first line
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]  # remove last line
    return json.loads(text.strip())
```

### Person 3 — Frontend Lead

**Files:** Everything in `static/`

**Your job:** Build all 5 HTML pages, the CSS, and the JavaScript. Make the audio capture work. Make it look good enough for a demo video.

**Day-of checklist:**
1. Build index.html (landing page)
2. Build dashboard.html with hardcoded dummy data first
3. Build create-room.html
4. Build room.html — get audio recording working on this page
5. Build summary.html — render the summary JSON beautifully
6. Style everything with a clean dark theme
7. Wire up all `fetch()` calls to Person 1's endpoints
8. Test audio recording → upload → end meeting flow end-to-end
9. Make sure it works on Chrome desktop AND Chrome mobile

**You can build and test everything without the backend.** Use hardcoded dummy data initially. When Person 1's endpoints are ready, just swap the data source.

**Example dummy summary for testing your summary.html:**

```javascript
const dummySummary = {
    meeting_title: "Landing Page Design Discussion",
    team: "Frontend",
    meeting_type: "review",
    date: "2026-04-01",
    duration_estimate: "12 minutes",
    participants: ["Pratham", "Rahul", "Sneha"],
    executive_summary: "Team decided on a card-based layout inspired by Stripe for the landing page. Sneha will handle mobile responsiveness. Rahul will prototype the hero section by April 3. The team needs brand colors from the Design team and API response format from the Backend team before finalizing.",
    key_decisions: [
        { decision: "Card-based layout for landing page", context: "Compared grid vs card vs single-scroll. Cards won for modularity.", decided_by: "Pratham" },
        { decision: "Tailwind CSS for styling", context: "Faster than writing custom CSS from scratch", decided_by: "Rahul" }
    ],
    action_items: [
        { task: "Create hero section prototype", owner: "Rahul", deadline: "April 3", priority: "high" },
        { task: "Handle mobile breakpoints", owner: "Sneha", deadline: "April 5", priority: "high" },
        { task: "Set up component library", owner: "Arjun", deadline: "April 5", priority: "medium" }
    ],
    cross_team_dependencies: [
        { dependency: "Need API response format for pricing cards", team_needed: "Backend", urgency: "blocking" },
        { dependency: "Need finalized brand colors", team_needed: "Design", urgency: "needed soon" }
    ],
    unresolved_items: [
        "Animation library choice: Framer Motion vs CSS transitions"
    ],
    detailed_notes: "The meeting opened with Pratham presenting two layout options for the landing page..."
};
```

### Person 4 — Demo, QA, and Delivery Lead

**Files:** `README.md`, test audio files, screenshots, demo video, Devpost submission

**Your job:** Everything that's not code but wins the hackathon. You are the quality gate — you test the full flow, find bugs, and make sure the submission is complete.

**Day-of checklist:**
1. Record 2-3 test audio clips:
   - Have the team do a mock 2-minute standup (each person records on their phone)
   - Convert to .webm if needed (use online converter or ffmpeg)
   - These clips will be used for testing AND the demo video
2. Write README.md:
   - Project overview (2-3 paragraphs)
   - Architecture diagram (use the ASCII art from this doc)
   - How to run locally (step by step)
   - How Gemini is used
   - Screenshots
3. Take screenshots at each stage of development
4. Once the app is working end-to-end, do a full test:
   - Create workspace → create team → create room → join from 2+ browsers → talk → end → check summary
5. Record the demo video (2-5 minutes) — see Section 15 for the script
6. Fill out the Devpost submission — see Section 16 for the checklist
7. Do a final check: GitHub repo is public, live link works, video is uploaded

**You are the most important person in the last 4 hours.** While others are fixing bugs, you're producing the deliverables that judges actually see.

---

## 10. Setup Instructions

Every team member runs these steps on their machine.

### Step 1: Clone the Repo

```bash
git clone https://github.com/YOUR_USERNAME/meetwise-ai.git
cd meetwise-ai
```

### Step 2: Create Virtual Environment

```bash
python -m venv .venv

# On Mac/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Set Up Environment Variables

```bash
# Create .env file
echo "GEMINI_API_KEY=your_key_here" > .env
```

Get your Gemini API key from: https://makersuite.google.com/app/apikey

### Step 5: Create Required Directories

```bash
mkdir -p audio_store summaries
```

### Step 6: Run the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

App will be at: http://localhost:8000

### Step 7: Test Audio (Person 3)

Open http://localhost:8000/static/room.html in Chrome.
Click "Allow" when asked for mic permission.
You should see the recording indicator.

---

## 11. Git Workflow

**Keep it dead simple. No branches, no PRs, no code reviews.**

```bash
# Before you start working:
git pull origin main

# After you've made changes:
git add .
git commit -m "brief description of what you did"
git push origin main

# If push fails (someone else pushed first):
git pull --rebase origin main
git push origin main
```

### Rules

1. **Pull before you start working.** Every time.
2. **Commit often.** Small commits are easier to fix if something breaks.
3. **Don't touch other people's files.** If you need to, tell the group chat first.
4. **If you break something, tell the group chat immediately.** Don't try to fix it silently.
5. **Commit messages should say what you did:** "add audio upload endpoint" not "update main.py"

### .gitignore (set this up first thing)

```
.env
.venv/
__pycache__/
audio_store/
summaries/
*.pyc
.DS_Store
```

---

## 12. Timeline

Adjust based on when you actually start.

### Phase 1: Foundation (Hours 0-2)

```
ALL:       Clone repo, set up environment, get Gemini API key
Person 1:  FastAPI skeleton + workspace/team/room CRUD endpoints
Person 2:  Test Gemini transcription with sample audio in test_gemini.py
Person 3:  Landing page + dashboard page with hardcoded data
Person 4:  Record mock standup audio clips with the team
```

**Checkpoint: Person 1 has endpoints returning dummy JSON. Person 2 can transcribe audio.**

### Phase 2: Core Features (Hours 2-6)

```
Person 1:  Audio upload endpoint + end-meeting flow + summary storage
Person 2:  Summarization prompt engineering — iterate until output is clean
Person 3:  Room page with audio capture (MediaRecorder) + summary display page
Person 4:  Test Person 2's pipeline with recorded audio clips
```

**Checkpoint: Person 2 can produce a clean summary from audio. Person 3 can record and upload audio.**

### Phase 3: Integration (Hours 6-9)

```
Person 1:  Connect gemini_service to end-meeting endpoint
Person 3:  Wire frontend fetch() calls to real backend endpoints  
Person 2:  Help Person 1 with Gemini integration, fix edge cases
Person 4:  End-to-end testing — find and report bugs
```

**Checkpoint: Full flow works — create room → join → talk → end → see summary on dashboard.**

### Phase 4: Polish (Hours 9-12)

```
Person 1:  Markdown download endpoint, error handling, CORS
Person 2:  Refine summary quality based on real test runs
Person 3:  CSS polish, loading states, error messages, mobile check
Person 4:  Take screenshots, start README, prepare demo script
```

### Phase 5: Ship (Hours 12-16)

```
Person 1:  Deploy to Render, test live URL
Person 2:  Final summary quality check on deployed version
Person 3:  Final frontend bugs on deployed version
Person 4:  Record demo video, write Devpost submission, submit
```

---

## 13. Integration Checklist

Use this when connecting the pieces together.

```
[ ] Person 3's landing page calls Person 1's workspace/create endpoint
[ ] Person 3's dashboard calls Person 1's workspace summaries endpoint
[ ] Person 3's create-room page calls Person 1's room/create endpoint
[ ] Person 3's room page calls Person 1's room/join and room/status endpoints
[ ] Person 3's room page uploads audio to Person 1's audio/upload endpoint
[ ] Person 3's room page calls Person 1's rooms/{code}/end endpoint
[ ] Person 1's end-meeting endpoint calls Person 2's process_meeting function
[ ] Person 2's functions return valid JSON that matches the contract in Section 6
[ ] Person 3's summary page renders the JSON returned by Person 1's summary endpoint
[ ] The dashboard shows summaries from multiple teams
[ ] Markdown download works
[ ] Everything works on the deployed Render URL (not just localhost)
```

---

## 14. Deployment

Person 1 handles this.

### Render (recommended)

1. Push code to GitHub (should already be there)
2. Go to https://render.com → sign in with GitHub
3. New → Web Service → connect your repo
4. Settings:
   - Runtime: Python 3
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variable: `GEMINI_API_KEY` = your key
6. Deploy

Render gives you a URL like `https://meetwise-ai.onrender.com` — this is your live link.

### Important

- Render free tier sleeps after 15 min of inactivity. The first request after sleep takes ~30 seconds. Open the URL before the demo to wake it up.
- Audio files stored on Render's filesystem will be lost on redeploy. This is fine for a hackathon.

---

## 15. Demo Script

Person 4 records this. 2-5 minutes total.

### Part 1: The Problem (30 seconds)

```
"In every company, teams have meetings. Frontend has a design review.
Backend has a planning session. And then they need ANOTHER meeting 
just to sync with each other about what happened.

Meetings keep creating more meetings. MeetWise AI breaks this cycle."
```

### Part 2: Live Demo (2-2.5 minutes)

```
Show: Create workspace "Acme Corp"
Show: Create teams — "Frontend" and "Backend"

Show: Team Frontend starts a meeting (create room, get code)
Show: 2-3 people join the room (open multiple browser tabs/windows)
[Play pre-recorded audio OR do a live 30-second mock standup]
Show: Host clicks "End Meeting" → loading spinner → summary appears

Highlight: Executive summary — "this is what a busy manager reads"
Highlight: Action items with owners — "everyone knows who's doing what"
Highlight: Cross-team dependencies — "this is the game changer"

Show: Go back to dashboard → start a Backend team meeting
[Quick 20-second mock discussion]
Show: End → summary appears under Backend team

Show: Dashboard now has both teams' summaries
"Team Backend can now see that Frontend needs the API response format.
No sync meeting needed. Problem solved."
```

### Part 3: How Gemini Is Used (30 seconds)

```
"We use Gemini 1.5 Flash in two stages. First, each participant's audio
is sent to Gemini for speaker-labeled transcription — we don't need
diarization because each person records from their own device.
Then, the merged transcript goes through a second Gemini call that
generates a structured summary with decisions, action items, 
and cross-team dependencies."
```

### Part 4: Impact + Future (30 seconds)

```
"A team of 50 people having 3 meetings a day saves 150+ meeting-hours 
per week. MeetWise AI turns every meeting into a searchable, shareable 
document — so the next meeting doesn't need to happen.

Future scope: Slack integration, automated follow-ups, and trend analysis
across meeting summaries to surface recurring blockers."
```

---

## 16. Devpost Submission

### Required Fields

- **Project title:** MeetWise AI
- **Tagline:** "Meetings end. Clarity begins."
- **Problem statement:** Teams waste hours in sync meetings because meeting outcomes aren't documented and shared. When Team A finishes a planning call, Team B has no idea what was discussed — so they schedule another meeting to find out. This cycle repeats daily across every organization.
- **Solution:** MeetWise AI is a browser-based meeting room that captures each participant's audio, uses Gemini to generate a structured Master Summary, and shares it across teams — eliminating the need for sync meetings entirely.
- **How Google Gemini was used:** Gemini 1.5 Flash is used in two stages: (1) Multimodal audio transcription — each participant's audio file is sent to Gemini with speaker identification, handling Indian English accents and Hinglish code-switching. (2) Structured summarization — the merged transcript is processed by Gemini to extract decisions, action items with owners, cross-team dependencies, and unresolved items into a structured JSON format.
- **Built with:** Python, FastAPI, Google Gemini 1.5 Flash, Vanilla HTML/CSS/JS, MediaRecorder API
- **GitHub:** (your repo link)
- **Demo video:** (upload)
- **Screenshots:** Landing page, meeting room, summary view, dashboard with multiple teams
- **Live link:** (your Render URL)

---

## 17. Known Constraints and Gotchas

### Things That WILL Bite You If You're Not Careful

1. **Mic requires HTTPS or localhost.** Don't test on `http://192.168.x.x`. Use `localhost:8000`.

2. **MediaRecorder mimeType.** Use `audio/webm;codecs=opus`. If you try `audio/mp3`, Chrome will throw an error.

3. **Gemini returns JSON with backticks sometimes.** Always strip ` ```json ` and ` ``` ` before parsing.

4. **Gemini might return slightly different JSON structure.** Add validation. If a field is missing, use a default.

5. **Render free tier sleeps after 15 minutes.** Wake it up before the demo.

6. **Audio files are big for Git.** NEVER commit audio files. Make sure `audio_store/` is in `.gitignore`.

7. **Browser MediaRecorder might not fire `onstop` if the page is closed.** The "End Meeting" button should stop recording AND upload in the same flow — don't rely on page unload events.

8. **Multiple participants uploading at once.** Person 1 needs to handle concurrent uploads. Use unique filenames: `{room_code}/{participant_name}.webm`.

9. **The meeting end flow is the hardest part.** The host clicks end → server marks room as ended → other browsers detect via polling → they stop recording and upload → server waits for all uploads → then processes. Get this flow right early.

10. **Test with real human voice, not text-to-speech.** Gemini handles real speech differently. Record yourselves talking.

---

## Final Note

The hackathon is won in the demo, not in the code. A working demo with a clean summary output and a good video will beat a technically superior project with a bad presentation every time.

**Priority order: Working demo > Summary quality > UI polish > Code quality**

Now stop reading and start building.

---

*MeetWise AI — "Meetings end. Clarity begins."*
*Built for Hack Days NIET 2026*
