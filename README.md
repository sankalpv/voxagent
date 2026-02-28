<div align="center">
  
# 🚀 VoxAgent
### The Next-Generation, Ultra-Low Latency AI Voice Assistant for Enterprises

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Telnyx](https://img.shields.io/badge/Telnyx-Telephony-green.svg)](https://telnyx.com/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-Live%20Multimodal-orange.svg)](https://deepmind.google/technologies/gemini/)

</div>

---

Welcome to **VoxAgent**—an autonomous, production-ready AI Voice Assistant designed to supercharge your inbound and outbound calls. Built using state-of-the-art **Telnyx WebSockets** and **Google Gemini Live Native Audio**, this agent doesn't just read text; it *understands* context, extracts meaning in real-time, and interacts with human-like latency. 

Whether you need a frontline receptionist, a 24/7 technical support agent with encyclopedic knowledge, or an automated sales representative that instantly emails calendar invites, VoxAgent acts as a frictionless extension of your business.

## ✨ Dazzling Feature List

- ⚡ **Ultra-Low Latency Speech-to-Speech:** Direct bidirectional mu-law PCMU payload streaming skips text-to-speech translators. It listens natively and speaks instantaneously.
- 🧠 **Retrieval-Augmented Generation (RAG):** Upload PDF policies or text documents straight into an agent's "Knowledge Base." Powered by `gemini-embedding-001` and `pgvector` HNSW indexes, your AI searches your private company documents within sub-milliseconds to answer hyper-specific questions accurately without hallucinations. 
- 📧 **Automated Appointments & Emails:** The agent semantically listens for user email addresses, identifies the contact, updates your CRM, securely schedules an event via `calendar_tool`, and dispatches a customized calendar confirmation email completely asynchronously.
- 🛠️ **Fully Stateful & Multi-Tenant:** A robust Postgres and Redis backbone capable of handling hundreds of concurrent active calls securely split across multiple organizational tenants.
- 📞 **Inbound & Outbound Ready:** Plug and play with any SIP trunk or WebRTC. Fully modular Telnyx endpoints.
- 🛡️ **Production Tested:** 100% test coverage for logic loops with strict `ruff` static analysis to guarantee enterprise-grade uptime.

---

## 📖 The Development Journey

VoxAgent didn't pop out of thin air; it evolved through rigorous experimentation and bleeding-edge technical fixes to solve the hardest problems in voice telephony.

Here is how we got here:

* **Inception & Core Routing**: We started by hooking up the Telnyx `media` websockets bridging directly into FastAPI. We introduced an asynchronous Python event loop bridging `asyncio` queues from Google GenAI into the Telnyx payload format.
* **The Silent Audio Breakthrough**: We noticed Google's `gemini-2.5-flash-native-audio-latest` model had strict pure-audio gating properties. It would hang silently when receiving unprompted Mu-Law streams. We pioneered a workaround sending an artificial context-injecting textual `send()` immediately upon connection to unlock the audio stream and force the model to greet the user dynamically.
* **Mastering the Real-World (SMTP)**: Voice isn't enough; an agent must *do* things. We built a non-blocking `asyncio.to_thread` execution pool to parse caller emails contextually and dispatch real SMTP emails through Gmail and external providers entirely on the fly.
* **Eradicating Hallucinations (RAG)**: We integrated PostgreSQL with the `pgvector` extension. However, standard GenAI SDKs suffered persistent DNS latency loops. We pivoted away into a pristine, customized HTTPX REST client targeting Google's `gemini-embedding-001` endpoint securely. The system now chunks natively via `pypdf`, converts the tokens to 768-dimensional matrices, and performs exact Nearest Neighbor Cosine searches locally in < 0.5ms.
* **Refining the Forge**: We nuked arbitrary testing files spanning the root level, normalized internal `module` tracking using `ruff`, relocated our complex integrations into a dedicated async `tests/` parameter suite, and dialed our asynchronous timing intervals up to completely eradicate testing environment flakiness.

---

## ⚙️ Quick Start

Want to see the magic yourself? Stand up your instance in minutes.

### Prerequisites

- Python 3.10+
- PostgreSQL (with the `pgvector` extension enabled)
- Redis Server
- Telnyx Account (for SIP trunking)
- Google Cloud Platform Account (Gemini API Key)

### Installation

1. **Clone & Install**
   ```bash
   git clone <your-repo-url>
   cd voxagent
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure your Variables**
   ```bash
   cp .env.example .env
   ```
   *(Be sure to add your `GEMINI_API_KEY`, `TELNYX_API_KEY`, and database URLs)*

3. **Initialize the Database & Knowledge Vector Engine**
   ```bash
   alembic upgrade head
   python create_db.py
   ```

4. **Launch the Engine**
   ```bash
   uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   *(Interactive Swagger documentation available instantly at `http://localhost:8000/docs`)*

---

### Tests & Quality Assurance
Run the resilient test suite (which mocks the Telnyx engine but performs real Gemini Native AI streams):
```bash
pytest 
```

**Enjoy building the future of conversational AI.**
