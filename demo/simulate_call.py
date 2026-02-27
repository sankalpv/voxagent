#!/usr/bin/env python3
"""
Local Call Simulation Demo
==========================

Demonstrates the full AI Voice Agent pipeline without requiring
external service credentials (Telnyx, Google Cloud, etc.).

Simulates:
1. Creating an agent configuration
2. Initiating an outbound call
3. The real-time conversation loop (STT → LLM → TTS)
4. Tool invocation (meeting booking)
5. Post-call analysis

Run:
    python demo/simulate_call.py

No .env file or external services needed.
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator
from dataclasses import dataclass, field

# ─── Colors for terminal output ───────────────────────────────────────────────

class C:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    END = "\033[0m"


def banner(text: str):
    width = 70
    print(f"\n{C.BOLD}{C.CYAN}{'═' * width}{C.END}")
    print(f"{C.BOLD}{C.CYAN}  {text}{C.END}")
    print(f"{C.BOLD}{C.CYAN}{'═' * width}{C.END}\n")


def step(num: int, text: str):
    print(f"{C.BOLD}{C.GREEN}  [{num}] {text}{C.END}")


def agent_says(text: str, latency_ms: int):
    print(f"  {C.BOLD}{C.BLUE}🤖 Agent:{C.END} {text}")
    print(f"  {C.DIM}   ↳ latency: {latency_ms}ms | synthesized {len(text.split())} words{C.END}")


def caller_says(text: str):
    print(f"  {C.BOLD}{C.YELLOW}👤 Caller:{C.END} {text}")


def system_event(text: str):
    print(f"  {C.DIM}⚡ {text}{C.END}")


def tool_event(text: str):
    print(f"  {C.BOLD}{C.RED}🔧 Tool:{C.END} {text}")


# ─── Simulated Services ───────────────────────────────────────────────────────

# Simulated conversation script
CALL_SCRIPT = [
    {
        "caller": None,  # Opening — agent speaks first
        "agent": "Hi there! This is Alex from SolarBright Energy. Am I speaking with Sarah? I hope I'm not catching you at a bad time.",
        "latency_ms": 680,
    },
    {
        "caller": "Uh, hi. Yeah this is Sarah. What's this about?",
        "agent": "Great to connect with you, Sarah! I'm reaching out because I noticed your home in the Sunnyvale area could be a great fit for solar panels. Many of your neighbors have already switched and are saving around 40% on their electricity bills. Have you ever thought about going solar?",
        "latency_ms": 720,
    },
    {
        "caller": "Actually yeah, our electricity bill has been pretty crazy lately. Like over 300 bucks last month.",
        "agent": "Oh wow, 300 dollars a month — that's definitely on the higher side. The good news is that with solar, most homeowners in your area bring that down to around 80 to 100 dollars. And with the current federal tax credit, you'd get 30% back on the installation cost. Would you be open to a quick 15-minute assessment? We'd look at your roof, your usage, and give you an exact savings estimate — totally free, no obligation.",
        "latency_ms": 750,
    },
    {
        "caller": "Hmm, I don't know. These things always end up being way more expensive than they say.",
        "agent": "I totally hear you, Sarah. That's actually the most common concern we hear. Here's the thing though — we offer zero-down financing, so your monthly solar payment is usually less than what you're paying for electricity right now. So from day one, you're actually saving money. Plus the system pays for itself in about 6 to 8 years, and then it's basically free electricity for the next 20 years. Would it help if I had one of our energy consultants walk you through the actual numbers for your specific home?",
        "latency_ms": 710,
        "tool_call": None,  # No tool yet
    },
    {
        "caller": "Okay yeah, I guess that could be helpful. When would that be?",
        "agent": "Let me check that for you real quick.",
        "latency_ms": 350,
        "tool_call": {
            "name": "book_meeting",
            "args": {"invitee_name": "Sarah Johnson", "invitee_email": "sarah.j@email.com"},
            "result": {
                "success": True,
                "scheduling_link": "https://calendly.com/solarbright/assessment?name=Sarah+Johnson",
                "message": "Meeting link generated for Sarah Johnson",
            },
        },
        "agent_after_tool": "I've got some great availability this week. I'm going to send you a calendar link to sarah.j@email.com where you can pick the time that works best for you. You'll be meeting with one of our senior energy consultants — they'll have your home's satellite imagery pulled up and everything. Does that work for you?",
        "latency_ms_after_tool": 680,
    },
    {
        "caller": "Sure, sounds good. I'll take a look at the link.",
        "agent": "Awesome, Sarah! You should see that email come through in just a minute. And just so you know — the assessment is completely free, no pressure at all. If the numbers don't make sense for your situation, no hard feelings. But I think you'll be pleasantly surprised. Is there anything else I can help you with?",
        "latency_ms": 690,
    },
    {
        "caller": "No that's it. Thanks Alex.",
        "agent": "Thank you so much, Sarah! I really appreciate you taking the time. Enjoy the rest of your day, and I'll make sure that calendar invite gets to you right away. Take care!",
        "latency_ms": 620,
    },
]


# ─── Post-call analysis ───────────────────────────────────────────────────────

POST_CALL_ANALYSIS = {
    "summary": "Agent Alex from SolarBright Energy called Sarah Johnson about solar panel installation. "
               "Sarah expressed concern about her high electricity bills ($300/month). The agent addressed "
               "her pricing objections by explaining zero-down financing and the federal tax credit. "
               "Sarah agreed to a free solar assessment and a meeting booking was scheduled via Calendly.",
    "outcome": "meeting_booked",
    "sentiment": "positive",
    "objections_handled": [
        "Cost concern → explained zero-down financing",
        "Skepticism about savings claims → provided specific neighborhood data",
    ],
    "key_info_captured": {
        "monthly_bill": "$300",
        "location": "Sunnyvale area",
        "email": "sarah.j@email.com",
        "interest_level": "medium-high",
    },
}


# ─── Agent Configuration ──────────────────────────────────────────────────────

DEMO_AGENT_CONFIG = {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "name": "Alex — Solar Sales Agent",
    "system_prompt": """You are Alex, a solar energy sales representative for SolarBright Energy.

PERSONA:
Warm, consultative, knowledgeable about solar energy. You use the caller's first name,
speak naturally, and never come across as pushy. You're genuinely enthusiastic about
helping people save money on electricity.

PRIMARY GOAL:
Qualify leads and book free solar assessments. Your success metric is booking a meeting
where an energy consultant can provide a detailed savings analysis.

CONSTRAINTS:
- Never promise specific savings without a proper assessment
- Always mention the free, no-obligation nature of the assessment
- If asked about pricing, explain zero-down financing and federal tax credit (30%)
- Never be deceptive about being an AI if directly asked
- Maximum 2 attempts to overcome objections; if still not interested, thank them and end

ESCALATION POLICY:
Transfer to human if: caller requests it, mentions legal/complaint issues, or
expresses frustration after 2 objection-handling attempts.""",
    "persona": "SolarBright Energy, Warm consultative solar sales representative",
    "primary_goal": "Book free solar assessment appointments",
    "voice_name": "en-US-Journey-D",
    "enabled_tools": ["book_meeting", "send_webhook", "end_call"],
}


# ─── Run the simulation ───────────────────────────────────────────────────────

async def simulate():
    call_start = time.time()

    banner("AI Voice Agent Platform — Call Simulation Demo")
    print(f"  {C.DIM}This demo simulates the full real-time pipeline:")
    print(f"  Phone → Telnyx WebSocket → STT → LLM (Gemini) → TTS → Phone{C.END}\n")

    # ─── Step 1: Show agent config ────────────────────────────────────────────
    step(1, "Loading Agent Configuration")
    print(f"  {C.DIM}Agent: {DEMO_AGENT_CONFIG['name']}")
    print(f"  Voice: {DEMO_AGENT_CONFIG['voice_name']}")
    print(f"  Tools: {', '.join(DEMO_AGENT_CONFIG['enabled_tools'])}")
    print(f"  Goal: {DEMO_AGENT_CONFIG['primary_goal']}{C.END}")
    await asyncio.sleep(0.5)

    # ─── Step 2: Initiate call ────────────────────────────────────────────────
    step(2, "Initiating Outbound Call")
    system_event("POST /api/v1/calls → Call record created (UUID: 7f8a9b0c-...)")
    system_event("Telnyx API: POST /v2/calls → dialing +14155551234")
    await asyncio.sleep(0.3)
    system_event("Webhook: call.initiated → status=ringing")
    await asyncio.sleep(0.5)

    print(f"\n  {C.DIM}📞 Ring... ring... ring...{C.END}")
    await asyncio.sleep(1.0)

    system_event("Webhook: call.answered → starting media stream")
    system_event("WebSocket: /ws/calls/7f8a9b0c → audio pipeline active")
    system_event("VoiceAgent started — STT → LLM → TTS loop running")

    # ─── Step 3: Conversation ─────────────────────────────────────────────────
    step(3, "Live Conversation (Real-Time Pipeline)")
    print()

    total_latency = 0
    turn_count = 0

    for i, turn in enumerate(CALL_SCRIPT):
        turn_count += 1
        turn_start = time.time()

        # Caller speaks
        if turn["caller"]:
            system_event(f"STT: transcribing audio... ({len(turn['caller'].split())} words)")
            await asyncio.sleep(0.2)
            caller_says(turn["caller"])
            print()
            await asyncio.sleep(0.3)

        # LLM + TTS
        latency = turn["latency_ms"]
        total_latency += latency

        system_event(f"LLM: Gemini 2.0 Flash processing (tier=fast)")
        await asyncio.sleep(0.2)

        # Tool call if present
        if turn.get("tool_call"):
            tc = turn["tool_call"]
            agent_says(turn["agent"], turn["latency_ms"])
            print()
            await asyncio.sleep(0.3)

            system_event(f"LLM requested tool: {tc['name']}")
            tool_event(f"{tc['name']}({json.dumps(tc['args'])})")
            await asyncio.sleep(0.4)
            tool_event(f"Result: {json.dumps(tc['result'], indent=2)}")
            print()
            await asyncio.sleep(0.3)

            system_event("LLM: incorporating tool results into response")
            agent_says(turn["agent_after_tool"], turn.get("latency_ms_after_tool", 700))
            total_latency += turn.get("latency_ms_after_tool", 700)
        else:
            system_event(f"TTS: synthesizing {len(turn['agent'].split())} words (sentence-by-sentence)")
            await asyncio.sleep(0.15)
            agent_says(turn["agent"], latency)

        print()
        await asyncio.sleep(0.4)

    # ─── Step 4: Call ends ────────────────────────────────────────────────────
    call_duration = round(time.time() - call_start)
    step(4, "Call Completed")
    system_event("Webhook: call.hangup → cleanup")
    system_event("VoiceAgent ended — building transcript")
    system_event(f"Call duration: {call_duration}s simulated (~3:20 real call)")
    system_event(f"Total turns: {turn_count * 2} ({turn_count} each side)")
    system_event(f"Average agent latency: {total_latency // turn_count}ms")
    print()

    # ─── Step 5: Post-call intelligence ───────────────────────────────────────
    step(5, "Post-Call AI Analysis (Async)")
    await asyncio.sleep(0.3)
    system_event("LLM: analyzing transcript for summary + outcome + sentiment")
    await asyncio.sleep(0.5)

    print(f"\n  {C.BOLD}📊 Call Analysis:{C.END}")
    print(f"  {C.DIM}┌────────────────────────────────────────────────────────────────┐{C.END}")
    print(f"  {C.DIM}│{C.END} {C.BOLD}Outcome:{C.END}    {C.GREEN}✅ meeting_booked{C.END}")
    print(f"  {C.DIM}│{C.END} {C.BOLD}Sentiment:{C.END}  {C.GREEN}positive{C.END}")
    print(f"  {C.DIM}│{C.END}")
    print(f"  {C.DIM}│{C.END} {C.BOLD}Summary:{C.END}")

    # Word-wrap the summary
    summary = POST_CALL_ANALYSIS["summary"]
    words = summary.split()
    line = "  │   "
    for word in words:
        if len(line) + len(word) > 68:
            print(f"  {C.DIM}│{C.END}   {line.strip()}")
            line = ""
        line += word + " "
    if line.strip():
        print(f"  {C.DIM}│{C.END}   {line.strip()}")

    print(f"  {C.DIM}│{C.END}")
    print(f"  {C.DIM}│{C.END} {C.BOLD}Objections Handled:{C.END}")
    for obj in POST_CALL_ANALYSIS["objections_handled"]:
        print(f"  {C.DIM}│{C.END}   • {obj}")

    print(f"  {C.DIM}│{C.END}")
    print(f"  {C.DIM}│{C.END} {C.BOLD}Key Info Captured:{C.END}")
    for k, v in POST_CALL_ANALYSIS["key_info_captured"].items():
        print(f"  {C.DIM}│{C.END}   {k}: {v}")

    print(f"  {C.DIM}└────────────────────────────────────────────────────────────────┘{C.END}")

    # ─── Step 6: Cost ─────────────────────────────────────────────────────────
    print()
    step(6, "Cost Breakdown (Standard Tier)")
    print(f"  {C.DIM}┌──────────────────────────────────────┐{C.END}")
    print(f"  {C.DIM}│{C.END}  Telephony (Telnyx, 3.3 min)  $0.033")
    print(f"  {C.DIM}│{C.END}  STT (Google Chirp 2)          $0.022")
    print(f"  {C.DIM}│{C.END}  LLM (Gemini 2.0 Flash, 7 turns) $0.0014")
    print(f"  {C.DIM}│{C.END}  TTS (Google Neural2)          $0.022")
    print(f"  {C.DIM}│{C.END}  Infrastructure                $0.005")
    print(f"  {C.DIM}│{C.END}  ─────────────────────────────────")
    print(f"  {C.DIM}│{C.END}  {C.BOLD}{C.GREEN}Total: $0.083{C.END}  (vs Nooks ~$0.40/call)")
    print(f"  {C.DIM}└──────────────────────────────────────┘{C.END}")

    # ─── Summary ──────────────────────────────────────────────────────────────
    banner("Demo Complete")
    print(f"  {C.BOLD}What you just saw:{C.END}")
    print(f"  • AI agent initiated an outbound call")
    print(f"  • Natural conversation with objection handling")
    print(f"  • Mid-call tool invocation (Calendly meeting booking)")
    print(f"  • Average ~680ms per-turn latency (target: <800ms)")
    print(f"  • Post-call AI analysis (summary, outcome, sentiment)")
    print(f"  • Total cost: $0.083/call (83% cheaper than competitors)")
    print()
    print(f"  {C.BOLD}To make real calls:{C.END}")
    print(f"  1. Sign up at https://telnyx.com (free tier available)")
    print(f"  2. Get a Gemini API key at https://aistudio.google.com")
    print(f"  3. Copy .env.example → .env and fill in credentials")
    print(f"  4. docker-compose up --build")
    print(f"  5. POST /api/v1/calls with agent_id and to_number")
    print()


if __name__ == "__main__":
    asyncio.run(simulate())