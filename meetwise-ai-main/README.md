# MeetWise AI

> **Meetings end. Clarity begins.**

MeetWise AI is a browser-based meeting tool where team members join a room, talk, and when the meeting ends, **Gemini AI automatically generates a structured Master Summary** of everything that was discussed. Summaries are organized by teams inside a shared workspace — so any team can read any other team's meeting outcomes without scheduling a sync call.

## 🎯 How It Works

1. **Create a Workspace** — Set up your organization (e.g., "Acme Corp")
2. **Create Teams** — Add teams like Frontend, Backend, Design
3. **Start a Meeting** — Host creates a room and gets a 6-digit code
4. **Join & Talk** — Participants join via code; each person's mic is recorded
5. **End Meeting** — Audio is sent to Gemini AI for transcription + summarization
6. **Read Summaries** — Structured summaries with decisions, action items, and cross-team dependencies appear on the dashboard

### Why This Architecture Is Smart

Traditional meeting AI tools use one microphone and try to figure out who said what (speaker diarization). Our approach: **each person's browser records ONLY their voice**. We already know who's speaking from their login. No diarization needed — the problem is solved by design, not by AI.

## 🏗️ Architecture

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

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python + FastAPI |
| AI | Google Gemini 1.5 Flash |
| Frontend | Vanilla HTML/CSS/JS |
| Audio Capture | MediaRecorder API |
| Server | Uvicorn (ASGI) |

## 🚀 How to Run Locally

### Prerequisites
- Python 3.11+
- Google Gemini API key ([Get one here](https://makersuite.google.com/app/apikey))

### Setup

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/meetwise-ai.git
cd meetwise-ai

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Mac/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
echo "GEMINI_API_KEY=your_key_here" > .env
# Then add:
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_ANON_KEY=your_supabase_anon_key

# Create required directories
mkdir audio_store summaries

# Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in Chrome.

### Important Notes
- **Mic access requires HTTPS or localhost** — don't test on `http://192.168.x.x`
- **Chrome only** — MediaRecorder with webm/opus is best supported in Chrome
- **Audio files are never committed** — `audio_store/` is gitignored

## 🤖 How Gemini Is Used

Gemini 1.5 Flash is used in **two stages**:

1. **Multimodal Audio Transcription** — Each participant's audio file is sent to Gemini with speaker identification, handling Indian English accents and Hinglish code-switching
2. **Structured Summarization** — The merged transcript is processed by Gemini to extract decisions, action items with owners, cross-team dependencies, and unresolved items into a structured JSON format

## 📁 Project Structure

```
meetwise-ai/
├── main.py                 # FastAPI application — all API endpoints
├── room_manager.py         # Room, team, workspace state management
├── gemini_service.py       # All Gemini API calls (transcribe + summarize)
├── requirements.txt        # Python dependencies
├── .env                    # GEMINI_API_KEY (DO NOT COMMIT)
├── audio_store/            # Temp storage for uploaded audio files
├── summaries/              # Saved summary JSON files
└── static/                 # Frontend files
    ├── index.html          # Landing page
    ├── dashboard.html      # Workspace dashboard
    ├── create-room.html    # Create meeting room
    ├── room.html           # Meeting room (audio capture)
    ├── summary.html        # View meeting summary
    ├── style.css           # Dark theme styles
    └── app.js              # Shared frontend utilities
```

## 👥 Built By

Team MeetWise — Built for Hack Days NIET 2026

---

*MeetWise AI — "Meetings end. Clarity begins."*
