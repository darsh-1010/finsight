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

The frontend is built with Next.js 15 (App Router), React 19, and Tailwind CSS v4.

### Install Dependencies
```bash
cd ../frontend
npm install
```

### Configuration (Environment Variables)
Create a `.env.local` file in the `frontend/` directory:
```ini
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

### Run the Frontend Development Server
```bash
npm run dev
```
The app will open at `http://localhost:3000`.

---

## 4. AI Engine Configuration (FreeLLMAPI)

Finsight utilizes **FreeLLMAPI** as its primary language model engine for chatbot functionality, query intelligence, and market insights. 

### Local Gateway Details
FreeLLMAPI runs as a local container gateway on port `3001` (or `3003` under custom configurations) and automatically routes requests to available free-tier providers.

### Model Selection & Configuration
Because FreeLLMAPI routes requests dynamically and features a custom model catalog, the Finsight environment is configured to use the `auto` routing model. This ensures that the engine automatically maps queries to the best available working model upstream (e.g. Mistral, Qwen, or Llama models) without manual key management.

To configure Finsight to use FreeLLMAPI, ensure your root `.env` file has the following configurations:

```ini
# LLM Provider Gateway
OPENAI_API_KEY=freellmapi-<your-key-here>
OPENAI_API_BASE=http://localhost:3001/v1
OPENAI_BASE_URL=http://localhost:3001/v1

# Target Models (set to auto-route)
OPENAI_MODEL_5_MINI=auto
GPT_4O_MINI=auto
GPT_4_1=auto
GPT_5_MINI=auto

# Tier-Specific Models
ML_TIER_0_MODEL=auto
ML_TIER_1_MODEL=auto
ML_TIER_2_MODEL=auto
ML_TIER_3_MODEL=auto
ML_TIER_4_MODEL=auto
ML_TIER_5_MODEL=auto
```

### Checking Available Catalog Models
To view a list of all models supported by the running FreeLLMAPI gateway:
```bash
curl -H "Authorization: Bearer <your-key>" http://localhost:3001/v1/models
```
Specific catalog models (such as `mistral-large-3` or `llama-3.3-70b`) can be supplied directly in `.env` if desired, though `auto` is recommended for general resilience.
