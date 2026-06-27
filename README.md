📊 Meetwise: AI-Based Smart Meeting Analyzer

🚀 Overview
Meetwise is an AI-powered meeting analyzer built with FastAPI, Whisper AI, and Next.js. It transforms meeting audio into actionable insights by providing transcription, summaries, and analysis — all running locally without external databases or cloud deployment. The project is designed to be lightweight, developer-friendly, and easy to run on any machine.

✨ Features
🎙️ Whisper AI Transcription – Converts speech to text with high accuracy.

📝 Smart Summaries – Generates concise notes highlighting key points.

📌 Action Item Extraction – Detects tasks and responsibilities from discussions.

📊 Sentiment & Engagement Analysis – Evaluates tone and participation.

🌐 Next.js Dashboard – Interactive frontend for uploading audio and viewing results.

⚡ FastAPI Backend – Lightweight Python API for processing and analysis.

💾 Local Storage – Reports and transcripts saved directly to the file system.

🛠️ Tech Stack
Frontend: Next.js + Tailwind CSS

Backend: FastAPI (Python)

AI/ML: Whisper AI (OpenAI) + Hugging Face Transformers

Deployment: Local run with Node.js + Python

📂 Project Structure
Code
meetwise/
│── backend/
│   ├── app.py              # FastAPI entry point
│   ├── routes/             # API endpoints
│   ├── services/           # Whisper + NLP services
│   ├── requirements.txt    # Python dependencies
│
│── frontend/
│   ├── pages/              # Next.js pages
│   ├── components/         # UI components
│   ├── styles/             # Tailwind CSS styles
│   ├── package.json        # Node dependencies
│
│── data/                   # Sample meeting audio/text
│── reports/                # Generated summaries
│── README.md               # Documentation



📦 Installation
Backend (FastAPI + Whisper)
bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt

# Run FastAPI server
uvicorn app:app --reload
Frontend (Next.js)
bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
Backend runs at http://localhost:8000

Frontend runs at http://localhost:3000

⚙️ Usage
Start both backend and frontend servers.

Upload or record meeting audio via the Next.js UI.

FastAPI backend processes audio with Whisper AI.

Summaries, action items, and analytics are displayed in the dashboard.

Reports are saved locally in the reports/ folder.

📈 Roadmap
✅ MVP with transcription + summaries

🔜 Multi-language support

🔜 Advanced analytics dashboard

🔜 Export options (PDF/CSV)

🔜 Real-time streaming transcription

🤝 Contributing
We welcome contributions! Fork the repo and submit a pull request.
