"""
Call Dashboard — Single-page HTML dashboard served by FastAPI.
Shows call history, agent configs, and live call status.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Voice Agent Platform — Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0f; color: #e0e0e0; }
        
        .header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 20px 30px; border-bottom: 1px solid #2a2a4a; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 22px; color: #00d4ff; }
        .header .status { display: flex; gap: 15px; align-items: center; }
        .header .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
        .header .dot.green { background: #00ff88; box-shadow: 0 0 6px #00ff88; }
        
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        
        .stats { display: grid; grid-template-columns: repeat(5, 1fr); gap: 15px; margin-bottom: 25px; }
        .stat-card { background: #1a1a2e; border: 1px solid #2a2a4a; border-radius: 10px; padding: 18px; }
        .stat-card .label { font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 1px; }
        .stat-card .value { font-size: 28px; font-weight: 700; color: #fff; margin-top: 5px; }
        .stat-card .sub { font-size: 12px; color: #666; margin-top: 3px; }
        .stat-card.highlight .value { color: #00ff88; }
        .stat-card.warn .value { color: #ffaa00; }
        
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        
        .panel { background: #1a1a2e; border: 1px solid #2a2a4a; border-radius: 10px; overflow: hidden; }
        .panel-header { padding: 15px 20px; border-bottom: 1px solid #2a2a4a; display: flex; justify-content: space-between; align-items: center; }
        .panel-header h2 { font-size: 16px; color: #00d4ff; }
        .panel-header .badge { background: #2a2a4a; color: #aaa; padding: 3px 10px; border-radius: 12px; font-size: 12px; }
        .panel-body { padding: 0; max-height: 500px; overflow-y: auto; }
        
        .call-row { padding: 12px 20px; border-bottom: 1px solid #1a1a2e; display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: background 0.2s; }
        .call-row:hover { background: #22223a; }
        .call-row .left { display: flex; flex-direction: column; gap: 3px; }
        .call-row .phone { font-size: 14px; font-weight: 600; color: #fff; }
        .call-row .meta { font-size: 12px; color: #666; }
        .call-row .right { text-align: right; }
        .call-row .status-badge { padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }
        .status-pending { background: #333; color: #aaa; }
        .status-initiated { background: #1a3a5c; color: #4da6ff; }
        .status-answered { background: #1a4a2e; color: #00ff88; animation: pulse 1.5s infinite; }
        .status-completed { background: #1a3a2e; color: #00cc66; }
        .status-failed { background: #4a1a1a; color: #ff4444; }
        .status-voicemail { background: #4a3a1a; color: #ffaa00; }
        
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.6; } }
        
        .outcome-badge { padding: 2px 8px; border-radius: 8px; font-size: 10px; margin-top: 3px; display: inline-block; }
        .outcome-meeting_booked { background: #1a4a2e; color: #00ff88; }
        .outcome-not_interested { background: #4a1a1a; color: #ff6666; }
        .outcome-callback_requested { background: #4a3a1a; color: #ffaa00; }
        .outcome-unknown { background: #333; color: #888; }
        
        .agent-card { padding: 15px 20px; border-bottom: 1px solid #1a1a2e; }
        .agent-card .name { font-size: 15px; font-weight: 600; color: #fff; }
        .agent-card .goal { font-size: 12px; color: #888; margin-top: 3px; }
        .agent-card .tools { margin-top: 8px; display: flex; gap: 5px; flex-wrap: wrap; }
        .agent-card .tool-tag { background: #2a2a4a; color: #00d4ff; padding: 2px 8px; border-radius: 8px; font-size: 10px; }
        
        .detail-panel { background: #1a1a2e; border: 1px solid #2a2a4a; border-radius: 10px; margin-top: 20px; display: none; }
        .detail-panel.active { display: block; }
        .detail-header { padding: 15px 20px; border-bottom: 1px solid #2a2a4a; }
        .detail-body { padding: 20px; }
        .detail-field { margin-bottom: 12px; }
        .detail-field .label { font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 1px; }
        .detail-field .value { font-size: 14px; color: #e0e0e0; margin-top: 2px; }
        
        .transcript { background: #0a0a0f; border-radius: 8px; padding: 15px; margin-top: 15px; max-height: 300px; overflow-y: auto; }
        .transcript-line { margin-bottom: 8px; font-size: 13px; line-height: 1.5; }
        .transcript-line .role { font-weight: 700; }
        .transcript-line .role-agent { color: #00d4ff; }
        .transcript-line .role-user { color: #ffaa00; }
        .transcript-line .role-system { color: #666; }
        
        .btn { background: #00d4ff; color: #000; border: none; padding: 8px 18px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s; }
        .btn:hover { background: #00b8e0; transform: translateY(-1px); }
        .btn.danger { background: #ff4444; color: #fff; }
        .btn.secondary { background: #2a2a4a; color: #ddd; }
        
        .actions { display: flex; gap: 10px; padding: 15px 20px; }
        
        .empty { padding: 40px; text-align: center; color: #555; }
        
        .refresh-timer { font-size: 11px; color: #555; }
        
        .cost { font-family: 'SF Mono', 'Fira Code', monospace; color: #00ff88; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 AI Voice Agent Platform</h1>
        <div class="status">
            <span class="refresh-timer" id="timer">Refreshing in 5s</span>
            <span><span class="dot green"></span> Live</span>
        </div>
    </div>
    
    <div class="container">
        <!-- Stats -->
        <div class="stats" id="stats">
            <div class="stat-card"><div class="label">Total Calls</div><div class="value" id="stat-total">-</div></div>
            <div class="stat-card highlight"><div class="label">Meetings Booked</div><div class="value" id="stat-meetings">-</div></div>
            <div class="stat-card"><div class="label">Completed</div><div class="value" id="stat-completed">-</div></div>
            <div class="stat-card warn"><div class="label">Failed</div><div class="value" id="stat-failed">-</div></div>
            <div class="stat-card"><div class="label">Active Now</div><div class="value" id="stat-active">-</div><div class="sub">live calls</div></div>
        </div>
        
        <!-- Grid -->
        <div class="grid">
            <!-- Calls Panel -->
            <div class="panel">
                <div class="panel-header">
                    <h2>📞 Recent Calls</h2>
                    <span class="badge" id="call-count">0</span>
                </div>
                <div class="panel-body" id="calls-list">
                    <div class="empty">Loading calls...</div>
                </div>
            </div>
            
            <!-- Agents Panel -->
            <div class="panel">
                <div class="panel-header">
                    <h2>🤖 Agents</h2>
                    <span class="badge" id="agent-count">0</span>
                </div>
                <div class="panel-body" id="agents-list">
                    <div class="empty">Loading agents...</div>
                </div>
            </div>
        </div>
        
        <!-- Call Detail -->
        <div class="detail-panel" id="call-detail">
            <div class="panel-header">
                <h2>📋 Call Details</h2>
                <button class="btn secondary" onclick="closeDetail()">✕ Close</button>
            </div>
            <div class="detail-body" id="detail-body"></div>
        </div>
    </div>
    
    <script>
        const API_KEY = 'dev-api-key-change-in-production';
        const headers = { 'X-API-Key': API_KEY, 'Content-Type': 'application/json' };
        let refreshInterval;
        let countdown = 5;
        
        async function fetchCalls() {
            try {
                const resp = await fetch('/api/v1/calls?page_size=50', { headers });
                const data = await resp.json();
                return data;
            } catch (e) {
                console.error('Error fetching calls:', e);
                return { calls: [], total: 0 };
            }
        }
        
        async function fetchAgents() {
            try {
                const resp = await fetch('/api/v1/agents', { headers });
                return await resp.json();
            } catch (e) {
                console.error('Error fetching agents:', e);
                return [];
            }
        }
        
        async function fetchCallDetail(callId) {
            try {
                const resp = await fetch(`/api/v1/calls/${callId}`, { headers });
                return await resp.json();
            } catch (e) {
                console.error('Error fetching call detail:', e);
                return null;
            }
        }
        
        function renderCalls(data) {
            const list = document.getElementById('calls-list');
            const calls = data.calls || [];
            document.getElementById('call-count').textContent = data.total || calls.length;
            
            // Stats
            const total = data.total || calls.length;
            const meetings = calls.filter(c => c.outcome === 'meeting_booked').length;
            const completed = calls.filter(c => c.status === 'completed').length;
            const failed = calls.filter(c => c.status === 'failed').length;
            const active = calls.filter(c => ['initiated','answered','ringing'].includes(c.status)).length;
            
            document.getElementById('stat-total').textContent = total;
            document.getElementById('stat-meetings').textContent = meetings;
            document.getElementById('stat-completed').textContent = completed;
            document.getElementById('stat-failed').textContent = failed;
            document.getElementById('stat-active').textContent = active;
            
            if (calls.length === 0) {
                list.innerHTML = '<div class="empty">No calls yet. Use the API to initiate a call.</div>';
                return;
            }
            
            list.innerHTML = calls.map(c => {
                const time = c.created_at ? new Date(c.created_at).toLocaleString() : '';
                const duration = c.duration_seconds ? `${c.duration_seconds}s` : (c.answered_at && c.ended_at ? 
                    Math.round((new Date(c.ended_at) - new Date(c.answered_at)) / 1000) + 's' : '-');
                const outcome = c.outcome ? `<span class="outcome-badge outcome-${c.outcome}">${c.outcome.replace(/_/g, ' ')}</span>` : '';
                const cost = c.cost_usd ? `<span class="cost">$${c.cost_usd.toFixed(4)}</span>` : '';
                const sentiment = c.sentiment ? `<span style="font-size:11px;color:${c.sentiment==='positive'?'#00ff88':c.sentiment==='negative'?'#ff4444':'#888'}">${c.sentiment}</span>` : '';
                
                return `
                    <div class="call-row" onclick="showDetail('${c.id}')">
                        <div class="left">
                            <span class="phone">${c.to_number}</span>
                            <span class="meta">${c.direction} · ${time} · ${duration} ${sentiment}</span>
                            ${outcome}
                        </div>
                        <div class="right">
                            <span class="status-badge status-${c.status}">${c.status}</span>
                            ${cost}
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        function renderAgents(agents) {
            const list = document.getElementById('agents-list');
            document.getElementById('agent-count').textContent = agents.length;
            
            if (agents.length === 0) {
                list.innerHTML = '<div class="empty">No agents configured.</div>';
                return;
            }
            
            list.innerHTML = agents.map(a => `
                <div class="agent-card">
                    <div class="name">${a.name}</div>
                    <div class="goal">${a.primary_goal || 'No goal set'}</div>
                    <div style="font-size:11px;color:#666;margin-top:3px;">Voice: ${a.voice_name} · Max: ${a.max_call_duration_seconds}s</div>
                    <div class="tools">
                        ${(a.enabled_tools || []).map(t => `<span class="tool-tag">${t}</span>`).join('')}
                    </div>
                </div>
            `).join('');
        }
        
        async function showDetail(callId) {
            const detail = await fetchCallDetail(callId);
            if (!detail) return;
            
            const panel = document.getElementById('call-detail');
            const body = document.getElementById('detail-body');
            
            const fields = [
                ['Call ID', detail.id],
                ['Direction', detail.direction],
                ['To', detail.to_number],
                ['From', detail.from_number],
                ['Status', `<span class="status-badge status-${detail.status}">${detail.status}</span>`],
                ['Outcome', detail.outcome || '-'],
                ['Sentiment', detail.sentiment || '-'],
                ['Started', detail.started_at ? new Date(detail.started_at).toLocaleString() : '-'],
                ['Answered', detail.answered_at ? new Date(detail.answered_at).toLocaleString() : '-'],
                ['Ended', detail.ended_at ? new Date(detail.ended_at).toLocaleString() : '-'],
                ['Duration', detail.duration_seconds ? `${detail.duration_seconds}s` : (detail.answered_at && detail.ended_at ? Math.round((new Date(detail.ended_at) - new Date(detail.answered_at)) / 1000) + 's' : '-')],
                ['Cost', detail.cost_usd ? `$${detail.cost_usd.toFixed(4)}` : '-'],
                ['Recording', detail.recording_url ? `<a href="${detail.recording_url}" style="color:#00d4ff" target="_blank">Listen</a>` : '-'],
            ];
            
            let html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">';
            fields.forEach(([label, value]) => {
                html += `<div class="detail-field"><div class="label">${label}</div><div class="value">${value}</div></div>`;
            });
            html += '</div>';
            
            // AI Summary
            if (detail.ai_summary) {
                html += `<div class="detail-field" style="margin-top:15px;"><div class="label">AI Summary</div><div class="value">${detail.ai_summary}</div></div>`;
            }
            
            // Transcript
            if (detail.transcript) {
                html += '<div class="detail-field" style="margin-top:15px;"><div class="label">Transcript</div></div>';
                html += '<div class="transcript">';
                detail.transcript.split('\\n').forEach(line => {
                    const match = line.match(/^\[(\w+)\]:\s*(.*)/);
                    if (match) {
                        const role = match[1].toLowerCase();
                        html += `<div class="transcript-line"><span class="role role-${role}">[${match[1]}]</span> ${match[2]}</div>`;
                    } else if (line.trim()) {
                        html += `<div class="transcript-line">${line}</div>`;
                    }
                });
                html += '</div>';
            }
            
            // Events
            if (detail.events && detail.events.length > 0) {
                html += '<div class="detail-field" style="margin-top:15px;"><div class="label">Conversation Events</div></div>';
                html += '<div class="transcript">';
                detail.events.forEach(e => {
                    const latency = e.latency_ms ? `<span style="color:#555;font-size:10px;">(${e.latency_ms}ms)</span>` : '';
                    html += `<div class="transcript-line"><span class="role role-${e.role}">[${e.role.toUpperCase()}]</span> ${e.content} ${latency}</div>`;
                });
                html += '</div>';
            }
            
            body.innerHTML = html;
            panel.classList.add('active');
            panel.scrollIntoView({ behavior: 'smooth' });
        }
        
        function closeDetail() {
            document.getElementById('call-detail').classList.remove('active');
        }
        
        async function refresh() {
            const [calls, agents] = await Promise.all([fetchCalls(), fetchAgents()]);
            renderCalls(calls);
            renderAgents(agents);
        }
        
        function startTimer() {
            countdown = 5;
            clearInterval(refreshInterval);
            refreshInterval = setInterval(() => {
                countdown--;
                document.getElementById('timer').textContent = `Refreshing in ${countdown}s`;
                if (countdown <= 0) {
                    refresh();
                    countdown = 5;
                }
            }, 1000);
        }
        
        // Initial load
        refresh();
        startTimer();
    </script>
</body>
</html>
"""


@router.get("", response_class=HTMLResponse)
async def dashboard():
    """Serve the call dashboard."""
    return DASHBOARD_HTML