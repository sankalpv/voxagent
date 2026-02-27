# Getting Started — Real Calls Setup Guide

## 1. Telnyx (Telephony — $0.01/min)

### Sign Up
1. Go to https://telnyx.com/sign-up
2. Choose **Freemium** account (no credit card needed for testing)
3. Verify your email

### Get Your API Key
1. Log into https://portal.telnyx.com
2. Go to **Auth** → **API Keys** (left sidebar)
3. Click **Create API Key** → copy the `KEY_xxxxx` value
4. This goes in `.env` as `TELNYX_API_KEY`

### Buy a Phone Number
1. Go to **Numbers** → **Search & Buy**
2. Search for a number in your area (costs ~$1/month)
3. Buy it → note the number in E.164 format (e.g., `+14155551234`)
4. This goes in `.env` as `TELNYX_FROM_NUMBER`

### Create a SIP Connection
1. Go to **Voice** → **SIP Connections**
2. Click **Create SIP Connection**
3. Name it: `salescallagent`
4. Connection Type: **Credential-based**
5. Under **Inbound Settings**:
   - Webhook URL: `https://your-ngrok-url.ngrok.io/webhooks/telnyx`
   - Method: POST
6. Copy the **Connection ID** → this goes in `.env` as `TELNYX_CONNECTION_ID`
7. Assign your phone number to this connection

### Set Up ngrok (for local development)
```bash
# Install ngrok
brew install ngrok  # macOS

# Start tunnel
ngrok http 8000

# Copy the https URL (e.g., https://abc123.ngrok.io)
# Put it in .env as PUBLIC_BASE_URL
```

---

## 2. Gemini API Key (LLM — $0.0014/call)

1. Go to https://aistudio.google.com/apikey
2. Click **Create API Key**
3. Select or create a Google Cloud project
4. Copy the key → this goes in `.env` as `GEMINI_API_KEY`

---

## 3. Google Cloud (STT + TTS — $0.044/call)

### Option A: Application Default Credentials (recommended)
```bash
# Install gcloud CLI
brew install google-cloud-sdk

# Login and set project
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### Option B: Service Account Key
1. Go to https://console.cloud.google.com/iam-admin/serviceaccounts
2. Create a service account with roles:
   - Cloud Speech-to-Text User
   - Cloud Text-to-Speech User
3. Create a JSON key → download it
4. Set in `.env`: `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`

### Enable APIs
```bash
gcloud services enable speech.googleapis.com
gcloud services enable texttospeech.googleapis.com
```

---

## 4. Configure .env

```bash
cp .env.example .env
```

Fill in:
```
TELNYX_API_KEY=KEY_xxxxx
TELNYX_CONNECTION_ID=your-connection-id
TELNYX_FROM_NUMBER=+14155551234
PUBLIC_BASE_URL=https://abc123.ngrok.io
GEMINI_API_KEY=AIza...
GOOGLE_CLOUD_PROJECT=your-project-id
```

---

## 5. Start the Platform

```bash
# Start PostgreSQL + Redis + App
docker-compose up --build

# In another terminal, start ngrok
ngrok http 8000
```

---

## 6. Create an Agent & Make a Call

### Create an agent:
```bash
curl -X POST http://localhost:8000/api/v1/agents \
  -H "X-API-Key: dev-api-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alex — Solar Sales Agent",
    "system_prompt": "You are Alex, a solar energy sales representative for SolarBright Energy.\n\nPERSONA:\nWarm, consultative, knowledgeable about solar energy.\n\nPRIMARY GOAL:\nQualify leads and book free solar assessments.\n\nCONSTRAINTS:\n- Never promise specific savings without assessment\n- Always mention the free, no-obligation nature\n- If asked about pricing, explain zero-down financing\n- Never be deceptive about being an AI if directly asked\n- Maximum 2 attempts to overcome objections\n\nESCALATION POLICY:\nTransfer to human if caller requests it or expresses frustration after 2 attempts.",
    "persona": "SolarBright Energy, Warm consultative solar sales representative",
    "primary_goal": "Book free solar assessment appointments",
    "enabled_tools": ["book_meeting", "end_call"]
  }'
```

### Make a call:
```bash
curl -X POST http://localhost:8000/api/v1/calls \
  -H "X-API-Key: dev-api-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "AGENT_ID_FROM_ABOVE",
    "to_number": "+1YOURNUMBER",
    "contact_metadata": {
      "first_name": "Sarah",
      "last_name": "Johnson",
      "company": "Homeowner"
    }
  }'
```

### Check call status:
```bash
curl http://localhost:8000/api/v1/calls \
  -H "X-API-Key: dev-api-key-change-in-production"
```

---

## Cost Estimates

| Tier | 5-min Call | 50 calls/day × 250 days |
|------|-----------|------------------------|
| Standard | $0.078 | $975/year |
| Economy | $0.037 | $462/year |
| Premium | $0.331 | $4,138/year |
| **Nooks.ai** | **~$0.40** | **$5,000/year/seat** |