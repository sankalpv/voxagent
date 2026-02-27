"""
Customer Onboarding Page — Interactive guide for new customers.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("", response_class=HTMLResponse)
async def onboarding():
    return ONBOARDING_HTML


ONBOARDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Get Started - AI Voice Agent Platform</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0f;color:#e0e0e0;line-height:1.6}
.hero{background:linear-gradient(135deg,#0d1b2a 0%,#1b2838 50%,#162447 100%);padding:60px 30px;text-align:center;border-bottom:2px solid #00d4ff33}
.hero h1{font-size:42px;color:#fff;margin-bottom:10px}
.hero h1 span{color:#00d4ff}
.hero .subtitle{font-size:18px;color:#8899aa;max-width:700px;margin:0 auto 25px}
.hero .badges{display:flex;gap:15px;justify-content:center;flex-wrap:wrap}
.hero .badge{background:#1a2a3a;border:1px solid #2a3a4a;padding:6px 16px;border-radius:20px;font-size:13px;color:#aaa}
.hero .badge strong{color:#00ff88}
.nav{display:flex;gap:20px;justify-content:center;margin-top:20px}
.nav a{color:#00d4ff;text-decoration:none;font-size:14px;padding:6px 14px;border-radius:6px;border:1px solid #2a3a4a;transition:all 0.2s}
.nav a:hover{background:#1a2a3a;border-color:#00d4ff}
.container{max-width:1100px;margin:0 auto;padding:40px 20px}
.section-title{font-size:28px;color:#fff;margin-bottom:8px;text-align:center}
.section-sub{font-size:15px;color:#666;text-align:center;margin-bottom:40px}
.flowchart{display:flex;flex-direction:column;align-items:center;gap:0;margin:40px auto;max-width:800px}
.flow-step{display:flex;align-items:center;gap:20px;width:100%;max-width:700px}
.flow-node{background:linear-gradient(135deg,#1a1a2e,#16213e);border:2px solid #2a3a5a;border-radius:16px;padding:24px;flex:1;min-width:280px;cursor:pointer;transition:all 0.3s;position:relative}
.flow-node:hover{border-color:#00d4ff;transform:translateY(-2px);box-shadow:0 8px 25px rgba(0,212,255,0.15)}
.flow-node.active{border-color:#00d4ff;box-shadow:0 0 20px rgba(0,212,255,0.2)}
.flow-number{position:absolute;top:-12px;left:20px;background:#00d4ff;color:#000;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:14px}
.flow-node .icon{font-size:28px;margin-bottom:8px}
.flow-node h3{font-size:17px;color:#fff;margin-bottom:4px}
.flow-node p{font-size:13px;color:#888}
.flow-node .time{font-size:11px;color:#00d4ff;margin-top:6px;font-weight:600}
.flow-arrow{display:flex;flex-direction:column;align-items:center;padding:5px 0}
.flow-arrow svg{width:30px;height:40px}
.flow-arrow path{stroke:#00d4ff;stroke-width:2;fill:none;opacity:0.5}
.flow-arrow polygon{fill:#00d4ff;opacity:0.5}
.flow-detail{background:#0d0d1a;border:1px solid #1a1a3a;border-radius:12px;padding:20px 24px;width:100%;max-width:700px;margin-top:-5px;margin-bottom:5px;display:none}
.flow-detail.active{display:block;animation:fadeIn 0.3s}
.flow-detail h4{color:#00d4ff;font-size:14px;margin-bottom:10px}
.flow-detail code{background:#1a1a2e;padding:12px 16px;border-radius:8px;display:block;font-size:12px;color:#ccc;overflow-x:auto;white-space:pre;font-family:'SF Mono','Fira Code',Consolas,monospace;line-height:1.5}
@keyframes fadeIn{from{opacity:0;transform:translateY(-5px)}to{opacity:1;transform:translateY(0)}}
.templates{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;margin-top:30px}
.template-card{background:#1a1a2e;border:2px solid #2a2a4a;border-radius:12px;padding:20px;cursor:pointer;transition:all 0.3s;text-align:center}
.template-card:hover{border-color:#00d4ff;transform:translateY(-3px)}
.template-card.selected{border-color:#00ff88;background:#1a2a2e}
.template-card .emoji{font-size:36px;margin-bottom:8px}
.template-card h4{font-size:14px;color:#fff;margin-bottom:4px}
.template-card p{font-size:11px;color:#666}
.cost-table{width:100%;border-collapse:collapse;margin-top:20px}
.cost-table th{text-align:left;padding:12px 16px;background:#1a1a2e;color:#888;font-size:12px;text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid #2a2a4a}
.cost-table td{padding:12px 16px;border-bottom:1px solid #1a1a2e;font-size:14px}
.cost-table tr:hover{background:#1a1a2e}
.cost-table .us{color:#00ff88;font-weight:700}
.cost-table .them{color:#888}
.cost-table .savings{color:#00d4ff;font-size:12px}
.try-section{background:linear-gradient(135deg,#1a1a2e,#0d1b2a);border:2px solid #2a3a5a;border-radius:16px;padding:30px;margin-top:40px}
.try-section h3{color:#00d4ff;font-size:20px;margin-bottom:15px}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:15px}
.form-group{display:flex;flex-direction:column}
.form-group label{font-size:12px;color:#888;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px}
.form-group input,.form-group textarea,.form-group select{background:#0a0a0f;border:1px solid #2a2a4a;border-radius:8px;padding:10px 14px;color:#ddd;font-size:14px;font-family:inherit}
.form-group input:focus,.form-group textarea:focus{border-color:#00d4ff;outline:none}
.form-group textarea{min-height:80px;resize:vertical}
.form-group.full{grid-column:1/-1}
.btn{background:#00d4ff;color:#000;border:none;padding:12px 28px;border-radius:8px;font-size:15px;font-weight:700;cursor:pointer;transition:all 0.2s;margin-top:15px}
.btn:hover{background:#00b8e0;transform:translateY(-1px)}
.btn.large{font-size:17px;padding:14px 40px}
.btn:disabled{background:#333;color:#666;cursor:not-allowed}
.result-box{background:#0a0a0f;border:1px solid #1a3a2e;border-radius:8px;padding:15px;margin-top:15px;display:none;font-family:monospace;font-size:13px;white-space:pre-wrap}
.result-box.show{display:block;animation:fadeIn 0.3s}
.result-box.success{border-color:#00ff88;color:#00ff88}
.result-box.error{border-color:#ff4444;color:#ff6666}
.footer{text-align:center;padding:40px 20px;color:#444;font-size:13px;border-top:1px solid #1a1a2e;margin-top:60px}
.footer a{color:#00d4ff;text-decoration:none}
</style>
</head>
<body>
<div class="hero">
<h1>&#x1F916; <span>AI Voice Agent</span> Platform</h1>
<p class="subtitle">Deploy autonomous AI calling agents for any industry. Configured entirely through natural language. No code changes. No flowcharts. Just describe what you want.</p>
<div class="badges">
<span class="badge">&#x1F4B0; <strong>$0.078</strong>/call (83% cheaper)</span>
<span class="badge">&#x1F680; <strong>15 min</strong> to first call</span>
<span class="badge">&#x1F30D; <strong>Any industry</strong> - zero code changes</span>
<span class="badge">&#x1F916; <strong>Fully autonomous</strong> - no human needed</span>
</div>
<div class="nav">
<a href="/dashboard">Dashboard</a>
<a href="/docs">API Docs</a>
<a href="/onboarding">Get Started</a>
</div>
</div>
<div class="container">
<h2 class="section-title">How It Works</h2>
<p class="section-sub">5 steps from sign-up to your first AI phone call</p>
<div class="flowchart">
<div class="flow-step"><div class="flow-node" onclick="toggleStep(1)"><span class="flow-number">1</span><div class="icon">&#x1F511;</div><h3>Get Your API Key</h3><p>Sign up and receive your tenant API key for platform access</p><div class="time">30 seconds</div></div></div>
<div class="flow-detail" id="step-detail-1"><h4>Your API Key</h4><code>X-API-Key: your-api-key-here

Each key is scoped to your tenant.
Complete data isolation via PostgreSQL Row-Level Security.</code></div>
<div class="flow-arrow"><svg viewBox="0 0 30 40"><path d="M15 0 L15 30"/><polygon points="9,28 15,38 21,28"/></svg></div>
<div class="flow-step"><div class="flow-node" onclick="toggleStep(2)"><span class="flow-number">2</span><div class="icon">&#x1F916;</div><h3>Create Your AI Agent</h3><p>Describe your agent in natural language - persona, goal, constraints, tools</p><div class="time">10-15 minutes</div></div></div>
<div class="flow-detail" id="step-detail-2"><h4>Create Agent via API</h4><code>POST /api/v1/agents
{
  "name": "Your Agent Name",
  "system_prompt": "You are [Name], a [role] at [Company]...",
  "persona": "Warm, consultative, uses first names",
  "primary_goal": "Book meetings / qualify leads / schedule appointments",
  "constraints": "Rules and boundaries in natural language",
  "escalation_policy": "When to transfer to human",
  "enabled_tools": ["book_meeting", "end_call"],
  "voice_name": "en-US-Journey-D"
}</code></div>
<div class="flow-arrow"><svg viewBox="0 0 30 40"><path d="M15 0 L15 30"/><polygon points="9,28 15,38 21,28"/></svg></div>
<div class="flow-step"><div class="flow-node" onclick="toggleStep(3)"><span class="flow-number">3</span><div class="icon">&#x1F4DE;</div><h3>Make Your First Call</h3><p>Trigger an outbound call - your AI agent dials, speaks, and handles the conversation</p><div class="time">1 minute</div></div></div>
<div class="flow-detail" id="step-detail-3"><h4>Initiate a Call</h4><code>POST /api/v1/calls
{
  "agent_id": "your-agent-id",
  "to_number": "+14155551234",
  "contact_metadata": {
    "first_name": "Sarah",
    "company": "Acme Corp"
  }
}</code></div>
<div class="flow-arrow"><svg viewBox="0 0 30 40"><path d="M15 0 L15 30"/><polygon points="9,28 15,38 21,28"/></svg></div>
<div class="flow-step"><div class="flow-node" onclick="toggleStep(4)"><span class="flow-number">4</span><div class="icon">&#x1F4CA;</div><h3>Monitor on Dashboard</h3><p>Watch calls in real-time - status, duration, outcomes, transcripts, AI summaries</p><div class="time">Real-time</div></div></div>
<div class="flow-detail" id="step-detail-4"><h4>Dashboard Features</h4><code>Stats:     Total calls, meetings booked, completed, failed, active
Call List:  Status badges, click for full detail  
Detail:    Timestamps, transcript, AI summary, sentiment, outcome
Agents:    All configured agents with tools and voice settings
Refresh:   Auto-updates every 5 seconds

Open: http://localhost:8000/dashboard</code></div>
<div class="flow-arrow"><svg viewBox="0 0 30 40"><path d="M15 0 L15 30"/><polygon points="9,28 15,38 21,28"/></svg></div>
<div class="flow-step"><div class="flow-node" onclick="toggleStep(5)"><span class="flow-number">5</span><div class="icon">&#x1F504;</div><h3>Iterate and Improve</h3><p>Update your agent's prompts based on results - no code, no deployment, instant effect</p><div class="time">2 minutes per change</div></div></div>
<div class="flow-detail" id="step-detail-5"><h4>Update Agent (Hot Reload)</h4><code>PATCH /api/v1/agents/{agent_id}
{
  "constraints": "Be more empathetic about budget concerns. Offer callback instead of pushing."
}

Changes take effect on the NEXT call. No restart needed.</code></div>
</div>

<h2 class="section-title" style="margin-top:60px">Industry Templates</h2>
<p class="section-sub">Click a template to auto-fill the form below - ready to deploy in 5 minutes</p>
<div class="templates">
<div class="template-card" onclick="showTemplate('realestate')"><div class="emoji">&#x1F3E0;</div><h4>Real Estate</h4><p>Buyer outreach and property viewing scheduling</p></div>
<div class="template-card" onclick="showTemplate('saas')"><div class="emoji">&#x1F4BB;</div><h4>SaaS Sales</h4><p>Demo booking and lead qualification</p></div>
<div class="template-card" onclick="showTemplate('solar')"><div class="emoji">&#x2600;</div><h4>Solar Energy</h4><p>Free assessment scheduling</p></div>
<div class="template-card" onclick="showTemplate('insurance')"><div class="emoji">&#x1F6E1;</div><h4>Insurance</h4><p>Coverage review appointments</p></div>
<div class="template-card" onclick="showTemplate('healthcare')"><div class="emoji">&#x1F3E5;</div><h4>Healthcare</h4><p>Appointment scheduling and follow-ups</p></div>
</div>

<h2 class="section-title" style="margin-top:60px">Cost Comparison</h2>
<p class="section-sub">Per 5-minute call - 83% cheaper than the closest competitor</p>
<table class="cost-table">
<thead><tr><th>Platform</th><th>Cost/Call</th><th>Annual (50/day)</th><th>vs Us</th></tr></thead>
<tbody>
<tr><td class="us">Our Platform (Standard)</td><td class="us">$0.078</td><td class="us">$975/yr</td><td class="us">-</td></tr>
<tr><td class="us">Our Platform (Economy)</td><td class="us">$0.037</td><td class="us">$462/yr</td><td class="us">-</td></tr>
<tr><td class="them">Nooks.ai</td><td class="them">~$0.40</td><td class="them">$5,000/yr</td><td class="savings">81% cheaper</td></tr>
<tr><td class="them">Bland.ai</td><td class="them">$0.45</td><td class="them">$5,625/yr</td><td class="savings">83% cheaper</td></tr>
<tr><td class="them">Retell AI</td><td class="them">$0.35-0.55</td><td class="them">$4,375-6,875/yr</td><td class="savings">78-86% cheaper</td></tr>
<tr><td class="them">Air.ai</td><td class="them">$0.55</td><td class="them">$6,875/yr</td><td class="savings">86% cheaper</td></tr>
</tbody></table>

<div class="try-section">
<h3>Try It Now - Create an Agent and Make a Call</h3>
<p style="color:#888;font-size:14px;margin-bottom:20px">Pick a template above to auto-fill, or type your own. Then Create Agent and Make Call.</p>
<div class="form-grid">
<div class="form-group"><label>Agent Name</label><input type="text" id="f-name" placeholder="e.g., Alex - Solar Sales Agent"></div>
<div class="form-group"><label>Voice</label><select id="f-voice"><option value="en-US-Journey-D">Journey-D (Male, warm)</option><option value="en-US-Journey-F">Journey-F (Female, warm)</option><option value="en-US-Neural2-A">Neural2-A (Male)</option><option value="en-US-Neural2-C">Neural2-C (Female)</option></select></div>
<div class="form-group full"><label>Primary Goal</label><input type="text" id="f-goal" placeholder="e.g., Book free solar assessments with homeowners"></div>
<div class="form-group full"><label>System Prompt (the complete call logic in natural language)</label><textarea id="f-prompt" rows="5" placeholder="You are Alex, a solar energy sales representative..."></textarea></div>
<div class="form-group full"><label>Constraints</label><textarea id="f-constraints" rows="2" placeholder="Never promise specific savings. Max 2 objection attempts."></textarea></div>
<div class="form-group"><label>Phone Number to Call</label><input type="text" id="f-phone" placeholder="+14155551234"></div>
<div class="form-group"><label>Tools</label><select id="f-tools" multiple size="3"><option value="book_meeting" selected>Book Meeting</option><option value="send_webhook">Send Webhook</option><option value="end_call" selected>End Call</option><option value="transfer_call">Transfer Call</option><option value="lookup_contact">Lookup Contact</option></select></div>
</div>
<div style="display:flex;gap:10px;margin-top:15px">
<button class="btn large" onclick="createAgent()">1. Create Agent</button>
<button class="btn large" id="btn-call" onclick="makeCall()" disabled>2. Make Call</button>
</div>
<div class="result-box" id="result"></div>
</div>
</div>
<div class="footer">
<p>AI Voice Agent Platform v0.1.0 | <a href="/dashboard">Dashboard</a> | <a href="/docs">API Docs</a> | <a href="/onboarding">Get Started</a></p>
<p style="margin-top:8px">GenAI Native | Multi-Tenant | $0.078/call | Any Industry</p>
</div>
<script>
const API_KEY='dev-api-key-change-in-production';
const headers={'X-API-Key':API_KEY,'Content-Type':'application/json'};
let createdAgentId=null;

function toggleStep(n){
  const el=document.getElementById('step-detail-'+n);
  const active=el.classList.contains('active');
  document.querySelectorAll('.flow-detail').forEach(d=>d.classList.remove('active'));
  document.querySelectorAll('.flow-node').forEach(d=>d.classList.remove('active'));
  if(!active){el.classList.add('active');el.previousElementSibling.querySelector('.flow-node').classList.add('active')}
}

const templates={
  realestate:{name:"Sarah - Real Estate Buyer Outreach",voice:"en-US-Journey-F",goal:"Schedule property viewings with qualified home buyers",prompt:"You are Sarah, a real estate agent at Prestige Homes. You call potential buyers who expressed interest in properties.\\n\\nPERSONA: Friendly, knowledgeable about local market, uses first names.\\n\\nPRIMARY GOAL: Schedule in-person or virtual property viewings. Qualify buyers by budget, neighborhoods, timeline.\\n\\nCONSTRAINTS:\\n- Never discuss exact prices on phone - invite to viewing\\n- Do not pressure\\n- Respect existing agent relationships\\n- Max 2 objection attempts\\n\\nESCALATION: Transfer if buyer has financing questions.",constraints:"Never discuss exact prices. No pressure. Max 2 objection attempts."},
  saas:{name:"Jordan - SaaS Demo Booker",voice:"en-US-Journey-D",goal:"Book product demos with decision-makers at 50+ employee companies",prompt:"You are Jordan, a BDR at CloudSync, a B2B project management platform.\\n\\nPERSONA: Professional, concise, value-focused.\\n\\nPRIMARY GOAL: Book 30-min demos with VPs/Directors/C-suite at 50+ employee companies.\\n\\nCONSTRAINTS:\\n- Only book decision-makers\\n- Never discuss pricing on call\\n- Under 50 employees = suggest self-serve\\n- Keep calls under 3 minutes\\n\\nESCALATION: Transfer for enterprise pricing questions.",constraints:"Only book decision-makers. Never discuss pricing. Keep under 3 min."},
  solar:{name:"Alex - Solar Sales Agent",voice:"en-US-Journey-D",goal:"Book free solar assessments with homeowners",prompt:"You are Alex, a solar energy sales rep for SolarBright Energy.\\n\\nPERSONA: Warm, consultative, knowledgeable. Uses first names, never pushy.\\n\\nPRIMARY GOAL: Qualify leads and book free solar assessments.\\n\\nCONSTRAINTS:\\n- Never promise specific savings without assessment\\n- Always mention free, no-obligation\\n- Explain zero-down financing and 30% federal tax credit\\n- Never lie about being AI if asked\\n- Max 2 objection attempts\\n\\nESCALATION: Transfer if caller requests human or is frustrated after 2 attempts.",constraints:"Never promise specific savings. Free no-obligation. Max 2 objection attempts."},
  insurance:{name:"Maya - Insurance Review Specialist",voice:"en-US-Journey-F",goal:"Schedule insurance coverage review meetings",prompt:"You are Maya, a specialist at SafeGuard Insurance.\\n\\nPERSONA: Reassuring, patient, simplifies insurance.\\n\\nPRIMARY GOAL: Schedule free coverage reviews. Most people are over-insured or under-insured.\\n\\nCONSTRAINTS:\\n- Never quote premiums on phone\\n- Always emphasize free review\\n- Do not disparage current insurance\\n- Max 2 objection attempts\\n\\nESCALATION: Transfer for claims or existing policy issues.",constraints:"Never quote premiums. Free review. Max 2 objection attempts."},
  healthcare:{name:"Dr. Kim - Patient Appointment Scheduler",voice:"en-US-Neural2-C",goal:"Schedule patient appointments and follow-ups",prompt:"You are Kim, a patient coordinator at Wellness Medical Group.\\n\\nPERSONA: Caring, professional, HIPAA-aware.\\n\\nPRIMARY GOAL: Schedule appointments for patients due for checkups or follow-ups.\\n\\nCONSTRAINTS:\\n- Never discuss diagnoses or test results on phone\\n- Only confirm appointment availability\\n- Be sensitive to health anxiety\\n- Max 1 follow-up if they decline\\n\\nESCALATION: Transfer immediately for urgent medical concerns.",constraints:"Never discuss diagnoses. HIPAA compliant. Max 1 follow-up."}
};

function showTemplate(key){
  const t=templates[key];
  document.querySelectorAll('.template-card').forEach(c=>c.classList.remove('selected'));
  event.currentTarget.classList.add('selected');
  document.getElementById('f-name').value=t.name;
  document.getElementById('f-voice').value=t.voice;
  document.getElementById('f-goal').value=t.goal;
  document.getElementById('f-prompt').value=t.prompt.replace(/\\n/g,'\\n');
  document.getElementById('f-constraints').value=t.constraints;
}

async function createAgent(){
  const name=document.getElementById('f-name').value;
  const goal=document.getElementById('f-goal').value;
  const prompt=document.getElementById('f-prompt').value;
  const constraints=document.getElementById('f-constraints').value;
  const voice=document.getElementById('f-voice').value;
  const toolSelect=document.getElementById('f-tools');
  const tools=Array.from(toolSelect.selectedOptions).map(o=>o.value);
  if(!name||!prompt){showResult('Please fill in Agent Name and System Prompt','error');return}
  try{
    const resp=await fetch('/api/v1/agents',{method:'POST',headers,body:JSON.stringify({name,system_prompt:prompt,primary_goal:goal,constraints,enabled_tools:tools,voice_name:voice})});
    const data=await resp.json();
    if(resp.ok){
      createdAgentId=data.id;
      document.getElementById('btn-call').disabled=false;
      showResult('Agent created!\\nID: '+data.id+'\\nName: '+data.name+'\\nTools: '+JSON.stringify(data.enabled_tools),'success');
    }else{showResult('Error: '+JSON.stringify(data),'error')}
  }catch(e){showResult('Error: '+e.message,'error')}
}

async function makeCall(){
  const phone=document.getElementById('f-phone').value;
  if(!createdAgentId){showResult('Create an agent first','error');return}
  if(!phone||!phone.startsWith('+')){showResult('Enter a valid E.164 phone number (e.g., +14155551234)','error');return}
  try{
    const resp=await fetch('/api/v1/calls',{method:'POST',headers,body:JSON.stringify({agent_id:createdAgentId,to_number:phone,contact_metadata:{source:'onboarding_page'}})});
    const data=await resp.json();
    if(resp.ok){showResult('Call initiated!\\nCall ID: '+data.id+'\\nTo: '+data.to_number+'\\nStatus: '+data.status+'\\n\\nCheck the dashboard: /dashboard','success')}
    else{showResult('Error: '+JSON.stringify(data),'error')}
  }catch(e){showResult('Error: '+e.message,'error')}
}

function showResult(msg,type){
  const el=document.getElementById('result');
  el.textContent=msg;
  el.className='result-box show '+type;
}
</script>
</body>
</html>"""