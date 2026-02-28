# SalesCallAgent: AI Voice Assistant

A production-ready artificial intelligence voice agent built using **FastAPI**, **Telnyx** for telephony, and **Google Gemini Live API** for real-time, low-latency multimodal voice interactions. It integrates advanced business workflows including automated meeting scheduler emails and Retrieval-Augmented Generation (RAG) for factual knowledge access.

## Features

1. **Real-time Voice Telephony**
   - Integrates with Telnyx via WebSockets for bidirectional mu-law audio streaming.
   - Connects to Google's Native Audio Gemini Live models (`gemini-2.5-flash-native-audio-latest`) for instantaneous speech-to-speech interaction.
   
2. **AI Knowledge Base (RAG)**
   - Businesses can upload PDF or Text documents to an Agent's Knowledge Base.
   - Documents are chunked (using `pypdf`) and embedded using `gemini-embedding-001`.
   - Embeddings are stored and indexed in PostgreSQL using the `pgvector` extension for sub-millisecond approximate nearest neighbor (HNSW) search.
   - The AI dynamically queries this context during calls to answer specific factual questions accurately.

3. **Email Confirmations & Calendar Scheduling**
   - The agent securely collects caller emails via contextual extraction.
   - Uses an asynchronous SMTP pipeline to dispatch calendar invites and booking confirmations without pausing the conversation.

4. **Production-Ready Architecture**
   - **Backend**: FastAPI with asynchronous endpoints.
   - **Database**: PostgreSQL (Asyncpg + SQLAlchemy 2.0 ORM) with Alembic migrations.
   - **State Management**: Redis for call session caching.
   - **Code Quality**: Enforced via `pytest` suites and `ruff` linting.

## Prerequisites

- Python 3.10+
- PostgreSQL (with `pgvector` extension installed)
- Redis Server
- Telnyx Account (for SIP trunking and WebRTC)
- Google Cloud Platform Account (Gemini API Key)
- An SMTP provider (e.g., SendGrid, Mailgun, or standard Gmail) 

## Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone <your-repo-url>
   cd salescallagent
   ```

2. **Set up the Environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**
   Copy `.env.example` to `.env` and fill in the required keys:
   ```bash
   cp .env.example .env
   ```
   **Required Keys**: 
   - `GEMINI_API_KEY`: Your Google Gemini API Key.
   - `TELNYX_API_KEY`: Your Telnyx API Key.
   - Database URIs (`DATABASE_URL`, `ASYNC_DATABASE_URL`), Redis URL.
   - SMTP details for email triggers.

4. **Initialize Database**
   Ensure Postgres and Redis are running. The startup script handles creating the tenant defaults and the `pgvector` extension.
   ```bash
   alembic upgrade head
   python create_db.py
   ```

## Running the Application

**Run locally for development:**
```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```
*The API documentation will be automatically accessible at `http://localhost:8000/docs`.*

## Testing

The application maintains a comprehensive `pytest` test suite covering core components, tool integrations, and real-time asynchronous multi-modal connections.

```bash
# Run the entire test suite
pytest

# Run tests excluding integration modules (which require an active Gemini API key)
pytest -m "not integration"
```

## Contributing
We use `ruff` to maintain code standards. Please run `ruff check --fix .` prior to committing modifications.
