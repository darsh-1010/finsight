# Finsight Installation & Setup Guide

This document describes how to install, configure, and run Finsight locally for development and testing.

---

## Prerequisites

Before starting, ensure you have the following software installed on your system:

- **Python 3.11+**
- **Node.js v18+ & npm v9+**
- **Git**
- **SQLite** (built-in with Python)

---

## 1. Backend Setup

The backend is built with FastAPI and runs on Python 3.11+.

### Clone the Repository
```bash
git clone <repository-url>
cd finsight
```

### Create and Activate Virtual Environment
```bash
# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Configuration (Environment Variables)
Create a `.env` file in the `backend/` directory:
```ini
PROJECT_NAME="FinSight API"
DATABASE_URL="sqlite:///./test.db"
SECRET_KEY="your-super-secret-jwt-key"
STRIPE_SECRET_KEY="sk_test_..."
STRIPE_WEBHOOK_SECRET="whsec_..."
OPENAI_API_KEY="sk-proj-..."
TAVILY_API_KEY="tvly-..."
AWS_ACCESS_KEY_ID="minioadmin"
AWS_SECRET_ACCESS_KEY="minioadmin"
AWS_REGION="us-east-1"
SES_SENDER_EMAIL="briefings@finsight.com"
```

### Seeding Tiers and Users
Initialize the local SQLite database and populate standard subscription tiers and local test users:
```bash
python -m app.seeds.seed_tiers
python -m app.seeds.seed_local_test_users
```

### Run the Backend Server
```bash
uvicorn app.main:app --reload --port 8000
```
The API documentation will be available at `http://localhost:8000/docs`.

---

## 2. ML Service Setup

The ML processing service (reasoning engine & RAG) runs within the `ml/` directory.

### Install Dependencies
Ensure you have activated the virtual environment:
```bash
cd ../ml
pip install -r requirements.txt
```

### Run the ML Tests
Ensure your python path is configured, then execute `pytest`:
```bash
pytest tests/ -v --tb=short
```

---

## 3. Frontend Setup

The frontend is built with React, Vite, and Tailwind CSS v4.

### Install Dependencies
```bash
cd ../frontend
npm install
```

### Configuration (Environment Variables)
Create a `.env` file in the `frontend/` directory:
```ini
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

### Run the Frontend Development Server
```bash
npm run dev
```
The app will open at `http://localhost:5173`.
