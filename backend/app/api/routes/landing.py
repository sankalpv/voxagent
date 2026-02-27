"""
VoxAgent Landing Page — Premium SaaS landing page.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("", response_class=HTMLResponse)
async def landing():
    return LANDING_HTML


LANDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VoxAgent — AI Agents That Call For You</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
:root{--cyan:#00d4ff;--green:#00ff88;--purple:#7b61ff;--pink:#ff6b9d;--dark:#050510;--card:#0a0a1a;--border:#1a1a3a;--text:#b0b0c0;--white:#f0f0ff}
body{font-family:'Inter',sans-serif;background:var(--dark);color:var(--text);overflow-x:hidden;-webkit-font-smoothing:antialiased}
a{color:var(--cyan);text-decoration:none}

/* ═══ ANIMATED BACKGROUND ═══ */
.bg-glow{position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0}
.bg-glow .orb{position:absolute;border-radius:50%;filter:blur(120px);opacity:0.12;animation:float 20s ease-in-out infinite}
.bg-glow .orb:nth-child(1){width:600px;height:600px;background:var(--cyan);top:-200px;left:-100px;animation-delay:0s}
.bg-glow .orb:nth-child(2){width:500px;height:500px;background:var(--purple);top:30%;right:-150px;animation-delay:-7s}
.bg-glow .orb:nth-child(3){width:400px;height:400px;background:var(--pink);bottom:-100px;left:30%;animation-delay:-14s}
@keyframes float{0%,100%{transform:translate(0,0) scale(1)}33%{transform:translate(30px,-40px) scale(1.05)}66%{transform:translate(-20px,30px) scale(0.95)}}

/* ═══ NAV ═══ */
nav{position:fixed;top:0;width:100%;z-index:100;padding:16px 40px;display:flex;justify-content:space-between;align-items:center;backdrop-filter:blur(20px);background:rgba(5,5,16,0.7);border-bottom:1px solid rgba(255,255,255,0.05);transition:all 0.3s}
.logo{font-size:22px;font-weight:800;color:var(--white);letter-spacing:-0.5px}
.logo span{background:linear-gradient(135deg,var(--cyan),var(--purple));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.nav-links{display:flex;gap:32px;align-items:center}
.nav-links a{color:var(--text);font-size:14px;font-weight:500;transition:color 0.2s}
.nav-links a:hover{color:var(--white)}
.nav-cta{background:var(--cyan);color:#000;padding:8px 20px;border-radius:8px;font-weight:600;font-size:14px;transition:all 0.2s}
.nav-cta:hover{background:#00e8ff;transform:translateY(-1px);box-shadow:0 4px 15px rgba(0,212,255,0.3)}

/* ═══ HERO ═══ */
.hero{position:relative;z-index:1;min-height:100vh;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:120px 20px 80px}
.hero-badge{display:inline-flex;align-items:center;gap:8px;background:rgba(0,212,255,0.08);border:1px solid rgba(0,212,255,0.2);padding:6px 18px;border-radius:100px;font-size:13px;color:var(--cyan);margin-bottom:30px;animation:fadeUp 0.8s ease-out}
.hero-badge .dot{width:6px;height:6px;background:var(--green);border-radius:50%;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
.hero h1{font-size:clamp(48px,7vw,84px);font-weight:900;color:var(--white);line-height:1.05;letter-spacing:-2px;max-width:900px;margin-bottom:24px;animation:fadeUp 0.8s ease-out 0.1s both}
.hero h1 .gradient{background:linear-gradient(135deg,var(--cyan) 0%,var(--purple) 50%,var(--pink) 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-size:200% 200%;animation:gradientShift 5s ease infinite}
@keyframes gradientShift{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
.hero .sub{font-size:clamp(16px,2vw,20px);color:var(--text);max-width:600px;line-height:1.6;margin-bottom:40px;animation:fadeUp 0.8s ease-out 0.2s both}
.hero-buttons{display:flex;gap:16px;animation:fadeUp 0.8s ease-out 0.3s both}
.btn-primary{background:linear-gradient(135deg,var(--cyan),#0099cc);color:#000;padding:14px 36px;border-radius:12px;font-weight:700;font-size:16px;border:none;cursor:pointer;transition:all 0.3s;box-shadow:0 4px 20px rgba(0,212,255,0.25)}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(0,212,255,0.4)}
.btn-secondary{background:transparent;color:var(--white);padding:14px 36px;border-radius:12px;font-weight:600;font-size:16px;border:1px solid var(--border);cursor:pointer;transition:all 0.3s}
.btn-secondary:hover{border-color:var(--cyan);background:rgba(0,212,255,0.05)}
@keyframes fadeUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}

/* ═══ STATS BAR ═══ */
.stats-bar{position:relative;z-index:1;display:flex;justify-content:center;gap:60px;padding:40px 20px;border-top:1px solid rgba(255,255,255,0.05);border-bottom:1px solid rgba(255,255,255,0.05);background:rgba(10,10,26,0.5);backdrop-filter:blur(10px)}
.stat{text-align:center}
.stat .number{font-size:36px;font-weight:800;color:var(--white);letter-spacing:-1px}
.stat .number span{color:var(--cyan)}
.stat .label{font-size:13px;color:var(--text);margin-top:4px}

/* ═══ SECTIONS ═══ */
section{position:relative;z-index:1;padding:100px 20px}
.section-inner{max-width:1100px;margin:0 auto}
.section-label{font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:2px;color:var(--cyan);margin-bottom:12px}
.section-title{font-size:clamp(32px,4vw,48px);font-weight:800;color:var(--white);letter-spacing:-1px;line-height:1.15;margin-bottom:16px}
.section-desc{font-size:17px;color:var(--text);max-width:600px;line-height:1.7}

/* ═══ HOW IT WORKS ═══ */
.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;margin-top:60px}
.step{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:36px 28px;transition:all 0.4s;position:relative;overflow:hidden}
.step::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--cyan),var(--purple));opacity:0;transition:opacity 0.3s}
.step:hover{border-color:rgba(0,212,255,0.3);transform:translateY(-4px);box-shadow:0 20px 40px rgba(0,0,0,0.3)}
.step:hover::before{opacity:1}
.step-num{width:40px;height:40px;border-radius:12px;background:linear-gradient(135deg,rgba(0,212,255,0.15),rgba(123,97,255,0.15));display:flex;align-items:center;justify-content:center;font-weight:800;font-size:16px;color:var(--cyan);margin-bottom:20px}
.step h3{font-size:20px;font-weight:700;color:var(--white);margin-bottom:10px}
.step p{font-size:14px;color:var(--text);line-height:1.6}
.step .tag{display:inline-block;margin-top:14px;padding:4px 12px;border-radius:6px;font-size:11px;font-weight:600;background:rgba(0,255,136,0.1);color:var(--green)}

/* ═══ INDUSTRIES ═══ */
.industries{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;margin-top:50px}
.industry{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:28px 16px;text-align:center;transition:all 0.3s;cursor:pointer}
.industry:hover{border-color:var(--cyan);transform:translateY(-4px);box-shadow:0 12px 30px rgba(0,0,0,0.3)}
.industry .icon{font-size:40px;margin-bottom:12px}
.industry h4{font-size:14px;font-weight:600;color:var(--white);margin-bottom:4px}
.industry p{font-size:11px;color:var(--text)}

/* ═══ COMPARISON ═══ */
.comparison{display:grid;grid-template-columns:1fr 1fr;gap:30px;margin-top:50px}
.comp-card{border-radius:20px;padding:40px;position:relative;overflow:hidden}
.comp-card.them{background:var(--card);border:1px solid var(--border)}
.comp-card.us{background:linear-gradient(135deg,rgba(0,212,255,0.08),rgba(123,97,255,0.08));border:1px solid rgba(0,212,255,0.25)}
.comp-card.us::before{content:'RECOMMENDED';position:absolute;top:16px;right:16px;background:var(--cyan);color:#000;padding:4px 12px;border-radius:6px;font-size:10px;font-weight:700;letter-spacing:1px}
.comp-card h3{font-size:24px;font-weight:700;color:var(--white);margin-bottom:6px}
.comp-card .price{font-size:42px;font-weight:900;color:var(--white);margin:16px 0 4px}
.comp-card .price span{font-size:16px;font-weight:400;color:var(--text)}
.comp-card .price-note{font-size:13px;color:var(--text);margin-bottom:24px}
.comp-card ul{list-style:none;display:flex;flex-direction:column;gap:12px}
.comp-card li{font-size:14px;display:flex;align-items:center;gap:10px}
.comp-card.us li::before{content:'\2713';color:var(--green);font-weight:700;font-size:16px}
.comp-card.them li::before{content:'\2717';color:#ff4466;font-weight:700;font-size:16px}
.comp-card.them li{color:#888}

/* ═══ FEATURES ═══ */
.features-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:20px;margin-top:50px}
.feature{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:28px;transition:all 0.3s}
.feature:hover{border-color:rgba(0,212,255,0.2)}
.feature .f-icon{font-size:24px;margin-bottom:12px}
.feature h4{font-size:16px;font-weight:700;color:var(--white);margin-bottom:6px}
.feature p{font-size:13px;color:var(--text);line-height:1.6}

/* ═══ CTA ═══ */
.cta-section{text-align:center;padding:120px 20px;position:relative;z-index:1}
.cta-section h2{font-size:clamp(36px,5vw,56px);font-weight:900;color:var(--white);letter-spacing:-1.5px;margin-bottom:16px}
.cta-section h2 .gradient{background:linear-gradient(135deg,var(--cyan),var(--purple));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.cta-section p{font-size:18px;color:var(--text);margin-bottom:40px;max-width:500px;margin-left:auto;margin-right:auto}
.cta-buttons{display:flex;gap:16px;justify-content:center}

/* ═══ FOOTER ═══ */
footer{border-top:1px solid var(--border);padding:40px 20px;text-align:center;font-size:13px;color:#555;position:relative;z-index:1}
footer .links{display:flex;gap:24px;justify-content:center;margin-bottom:16px}
footer a{color:var(--text);transition:color 0.2s}
footer a:hover{color:var(--cyan)}

/* ═══ RESPONSIVE ═══ */
@media(max-width:768px){
.steps{grid-template-columns:1fr}
.industries{grid-template-columns:repeat(2,1fr)}
.comparison{grid-template-columns:1fr}
.features-grid{grid-template-columns:1fr}
.stats-bar{flex-wrap:wrap;gap:30px}
nav{padding:12px 20px}
.nav-links{display:none}
}
</style>
</head>
<body>

<div class="bg-glow">
<div class="orb"></div>
<div class="orb"></div>
<div class="orb"></div>
</div>

<nav>
<div class="logo">Vox<span>Agent</span></div>
<div class="nav-links">
<a href="#how">How It Works</a>
<a href="#industries">Industries</a>
<a href="#pricing">Pricing</a>
<a href="#features">Features</a>
<a href="/onboarding" class="nav-cta">Get Started</a>
</div>
</nav>

<div class="hero">
<div class="hero-badge"><span class="dot"></span> Now in Public Beta</div>
<h1>AI Agents That <span class="gradient">Call For You</span></h1>
<p class="sub">Deploy autonomous voice agents for any industry in 15 minutes. Configured through natural language. No code. No flowcharts. 83% cheaper than competitors.</p>
<div class="hero-buttons">
<a href="/onboarding" class="btn-primary">Start Building Free</a>
<a href="/dashboard" class="btn-secondary">View Live Dashboard</a>
</div>
</div>

<div class="stats-bar">
<div class="stat"><div class="number"><span>$0.078</span></div><div class="label">Per 5-min call</div></div>
<div class="stat"><div class="number"><span>15</span> min</div><div class="label">To first call</div></div>
<div class="stat"><div class="number"><span>83</span>%</div><div class="label">Cheaper than competitors</div></div>
<div class="stat"><div class="number"><span>0</span></div><div class="label">Humans required</div></div>
</div>

<section id="how">
<div class="section-inner">
<div class="section-label">How It Works</div>
<div class="section-title">Three steps to autonomous calling</div>
<div class="section-desc">No engineering team needed. Describe your agent in plain English, point it at a phone number, and watch it work.</div>
<div class="steps">
<div class="step">
<div class="step-num">1</div>
<h3>Describe Your Agent</h3>
<p>Write a natural language prompt describing your agent's persona, goal, constraints, and escalation rules. Pick from industry templates or write your own.</p>
<span class="tag">10-15 minutes</span>
</div>
<div class="step">
<div class="step-num">2</div>
<h3>Make the Call</h3>
<p>Hit one API endpoint with a phone number. VoxAgent dials, greets, handles objections, books meetings, and hangs up gracefully. All autonomous.</p>
<span class="tag">1 API call</span>
</div>
<div class="step">
<div class="step-num">3</div>
<h3>Analyze &amp; Iterate</h3>
<p>Every call gets an AI-generated summary, outcome classification, and sentiment analysis. Tweak your prompts, see results on the next call.</p>
<span class="tag">Real-time dashboard</span>
</div>
</div>
</div>
</section>

<section id="industries" style="background:rgba(0,0,0,0.3)">
<div class="section-inner">
<div class="section-label">Domain Agnostic</div>
<div class="section-title">One platform. Every industry.</div>
<div class="section-desc">The same engine powers agents for real estate, SaaS, solar, insurance, healthcare, and more. Zero code changes between industries.</div>
<div class="industries">
<div class="industry"><div class="icon">&#x1F3E0;</div><h4>Real Estate</h4><p>Buyer outreach, property viewings, lead qualification</p></div>
<div class="industry"><div class="icon">&#x1F4BB;</div><h4>SaaS Sales</h4><p>Demo booking, decision-maker qualification</p></div>
<div class="industry"><div class="icon">&#x2600;&#xFE0F;</div><h4>Solar Energy</h4><p>Free assessments, savings analysis scheduling</p></div>
<div class="industry"><div class="icon">&#x1F6E1;&#xFE0F;</div><h4>Insurance</h4><p>Coverage reviews, policy renewals</p></div>
<div class="industry"><div class="icon">&#x1F3E5;</div><h4>Healthcare</h4><p>Appointments, follow-ups, reminders</p></div>
</div>
</div>
</section>

<section id="pricing">
<div class="section-inner">
<div class="section-label">Pricing</div>
<div class="section-title">Built to be the cheapest. Period.</div>
<div class="section-desc">Usage-based pricing. No seats, no minimums. Pay only for the calls your agents make.</div>
<div class="comparison">
<div class="comp-card them">
<h3>Competitors</h3>
<div class="price">$0.45 <span>/ call</span></div>
<div class="price-note">Bland.ai, Air.ai, Retell average</div>
<ul>
<li>Per-seat or per-minute pricing</li>
<li>Locked to specific industries</li>
<li>Flowchart-based configuration</li>
<li>Requires human supervision</li>
<li>Days to onboard new agent</li>
</ul>
</div>
<div class="comp-card us">
<h3>VoxAgent</h3>
<div class="price" style="color:var(--cyan)">$0.078 <span>/ call</span></div>
<div class="price-note">Standard tier, 5-minute call</div>
<ul>
<li>Usage-based, no seat fees</li>
<li>Any industry via natural language</li>
<li>Prompt-as-configuration (GenAI native)</li>
<li>Fully autonomous, zero humans</li>
<li>15 minutes from signup to first call</li>
</ul>
</div>
</div>
</div>
</section>

<section id="features">
<div class="section-inner">
<div class="section-label">Platform</div>
<div class="section-title">Everything you need to scale calling</div>
<div class="features-grid">
<div class="feature"><div class="f-icon">&#x1F9E0;</div><h4>GenAI Native</h4><p>The LLM IS the call logic. No flowcharts, no decision trees. Your natural language prompt defines the entire conversation flow, objection handling, and escalation rules.</p></div>
<div class="feature"><div class="f-icon">&#x1F527;</div><h4>Mid-Call Tools</h4><p>Agents can book meetings (Calendly), push to CRM (any webhook), look up contacts, transfer to humans, and end calls gracefully — all during live conversation.</p></div>
<div class="feature"><div class="f-icon">&#x1F50A;</div><h4>Natural Voice</h4><p>Google Neural2 Journey voices that sound human. Sentence-level TTS streaming for sub-800ms response latency. Interruption handling built in.</p></div>
<div class="feature"><div class="f-icon">&#x1F4CA;</div><h4>Post-Call Intelligence</h4><p>Every call gets an AI-generated summary, outcome classification (meeting booked, not interested, callback), sentiment analysis, and full transcript.</p></div>
<div class="feature"><div class="f-icon">&#x1F512;</div><h4>Multi-Tenant Isolation</h4><p>PostgreSQL row-level security ensures complete data isolation between customers. API key authentication, DNC compliance checking on every dial.</p></div>
<div class="feature"><div class="f-icon">&#x26A1;</div><h4>Hot-Reload Prompts</h4><p>Change your agent's behavior with a PATCH request. No deployment, no code review. Takes effect on the very next call.</p></div>
</div>
</div>
</section>

<div class="cta-section">
<h2>Ready to <span class="gradient">replace your SDRs</span>?</h2>
<p>Create your first AI calling agent in 15 minutes. No credit card required for the free tier.</p>
<div class="cta-buttons">
<a href="/onboarding" class="btn-primary">Get Started Free</a>
<a href="/docs" class="btn-secondary">Read the Docs</a>
</div>
</div>

<footer>
<div class="links">
<a href="/onboarding">Get Started</a>
<a href="/dashboard">Dashboard</a>
<a href="/docs">API Docs</a>
<a href="/health">Status</a>
</div>
<p>VoxAgent v0.1.0 &mdash; GenAI Native Autonomous Calling Platform</p>
</footer>

</body>
</html>"""