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
    <title>VoxAgent — Enterprise AI Voice Assistants</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19; /* Deep premium blue-black */
            --surface-color: #131b2f;
            --surface-color-hover: #1e2945;
            --border-color: #2a344d;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --accent-primary: #3b82f6; /* Trustworthy blue */
            --accent-primary-hover: #2563eb;
            --accent-teal: #10b981;
            --nav-bg: rgba(11, 15, 25, 0.85);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            -webkit-font-smoothing: antialiased;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-primary);
            line-height: 1.6;
            overflow-x: hidden;
        }

        a {
            text-decoration: none;
            color: inherit;
        }

        /* ─── TYPOGRAPHY ─── */
        h1, h2, h3, h4 {
            color: var(--text-primary);
            line-height: 1.2;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        p {
            color: var(--text-secondary);
        }

        /* ─── UTILS ─── */
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 24px;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 600;
            transition: all 0.2s ease;
            cursor: pointer;
            border: 1px solid transparent;
        }

        .btn-primary {
            background-color: var(--accent-primary);
            color: white;
            box-shadow: 0 4px 14px 0 rgba(59, 130, 246, 0.39);
        }

        .btn-primary:hover {
            background-color: var(--accent-primary-hover);
            transform: translateY(-1px);
        }

        .btn-secondary {
            background-color: transparent;
            color: var(--text-primary);
            border-color: var(--border-color);
        }

        .btn-secondary:hover {
            background-color: var(--surface-color);
            border-color: var(--text-secondary);
        }

        .section-header {
            text-align: center;
            margin-bottom: 64px;
        }

        .section-tag {
            color: var(--accent-primary);
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 12px;
            display: inline-block;
        }

        .section-header h2 {
            font-size: 40px;
            margin-bottom: 16px;
        }

        .section-header p {
            font-size: 18px;
            max-width: 600px;
            margin: 0 auto;
        }

        /* ─── NAV ─── */
        nav {
            position: fixed;
            top: 0;
            width: 100%;
            z-index: 100;
            background: var(--nav-bg);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-color);
        }

        .nav-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
            height: 72px;
        }

        .nav-brand {
            font-size: 20px;
            font-weight: 800;
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .nav-brand svg {
            color: var(--accent-primary);
        }

        .nav-links {
            display: flex;
            gap: 32px;
            align-items: center;
        }

        .nav-links a {
            font-size: 14px;
            font-weight: 500;
            color: var(--text-secondary);
            transition: color 0.2s;
        }

        .nav-links a:hover {
            color: var(--text-primary);
        }

        .nav-cta {
            background: var(--text-primary);
            color: var(--bg-color) !important;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 600;
            transition: all 0.2s;
        }

        .nav-cta:hover {
            background: white;
            opacity: 0.9;
            transform: none;
        }

        /* ─── HERO ─── */
        .hero {
            padding: 160px 0 80px;
            text-align: center;
            position: relative;
            z-index: 1;
        }

        /* Subtle background glow for depth */
        .hero::before {
            content: '';
            position: absolute;
            top: -20%;
            left: 50%;
            transform: translateX(-50%);
            width: 800px;
            height: 800px;
            background: radial-gradient(circle, rgba(59, 130, 246, 0.15) 0%, rgba(11, 15, 25, 0) 70%);
            z-index: -1;
            pointer-events: none;
        }

        .hero h1 {
            font-size: clamp(48px, 6vw, 72px);
            margin-bottom: 24px;
            max-width: 900px;
            margin-left: auto;
            margin-right: auto;
        }

        .hero-gradient-text {
            background: linear-gradient(135deg, #fff 0%, #94a3b8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero p {
            font-size: 20px;
            max-width: 680px;
            margin: 0 auto 40px;
        }

        .hero-ctas {
            display: flex;
            gap: 16px;
            justify-content: center;
            margin-bottom: 64px;
        }

        /* ─── TRUST BAR ─── */
        .trust-bar {
            border-top: 1px solid var(--border-color);
            border-bottom: 1px solid var(--border-color);
            padding: 40px 0;
            background: rgba(19, 27, 47, 0.3);
            text-align: center;
        }

        .trust-label {
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-weight: 600;
            margin-bottom: 24px;
        }

        .logos {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 60px;
            flex-wrap: wrap;
            opacity: 0.5;
            filter: grayscale(100%);
        }

        .logos svg {
            height: 28px;
            width: auto;
            fill: currentColor;
        }

        /* ─── VALUE METRICS ─── */
        .metrics-section {
            padding: 100px 0;
        }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 32px;
        }

        .metric-card {
            background: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 40px;
            text-align: center;
        }

        .metric-card h3 {
            font-size: 48px;
            margin-bottom: 8px;
            color: var(--text-primary);
        }

        .metric-card p {
            font-weight: 500;
        }

        /* ─── HOW IT WORKS ─── */
        .how-section {
            padding: 100px 0;
            background: rgba(19, 27, 47, 0.3);
        }

        .steps-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
        }

        .step-card {
            padding: 32px;
            background: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            transition: border-color 0.2s;
        }

        .step-card:hover {
            border-color: var(--accent-primary);
        }

        .step-icon {
            width: 48px;
            height: 48px;
            background: rgba(59, 130, 246, 0.1);
            color: var(--accent-primary);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            margin-bottom: 24px;
        }

        .step-card h3 {
            font-size: 20px;
            margin-bottom: 12px;
        }

        /* ─── FEATURES ─── */
        .features-section {
            padding: 100px 0;
        }

        .features-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 32px;
        }

        .feature-item {
            display: flex;
            gap: 20px;
            padding: 24px;
            border-radius: 12px;
            border: 1px solid transparent;
            transition: all 0.2s;
        }

        .feature-item:hover {
            background: var(--surface-color);
            border-color: var(--border-color);
        }

        .feature-icon-wrapper {
            flex-shrink: 0;
            width: 40px;
            height: 40px;
            background: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-primary);
        }

        .feature-item h3 {
            font-size: 18px;
            margin-bottom: 8px;
        }

        /* ─── CTA FOOTER ─── */
        .cta-bottom {
            padding: 100px 0;
            text-align: center;
            background: linear-gradient(180deg, transparent, rgba(19, 27, 47, 0.8));
            border-top: 1px solid var(--border-color);
        }

        .cta-bottom h2 {
            font-size: 40px;
            margin-bottom: 24px;
        }

        footer {
            border-top: 1px solid var(--border-color);
            padding: 40px 0;
            text-align: center;
        }

        .footer-links {
            display: flex;
            justify-content: center;
            gap: 24px;
            margin-bottom: 24px;
        }

        .footer-links a {
            color: var(--text-secondary);
            font-size: 14px;
        }

        .footer-links a:hover {
            color: var(--text-primary);
        }

        /* ─── RESPONSIVE ─── */
        @media (max-width: 768px) {
            .nav-links { display: none; }
            .metrics-grid, .steps-grid, .features-grid { grid-template-columns: 1fr; }
            .hero h1 { font-size: 36px; }
            .hero p { font-size: 16px; }
            .logos { gap: 30px; }
        }
    </style>
</head>
<body>

    <nav>
        <div class="container nav-content">
            <a href="#" class="nav-brand">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" x2="12" y1="19" y2="22"></line></svg>
                VoxAgent
            </a>
            <div class="nav-links">
                <a href="#metrics">ROI</a>
                <a href="#how-it-works">How it Works</a>
                <a href="#features">Features</a>
                <a href="/docs">Documentation</a>
                <a href="/onboarding" class="nav-cta">Start Free Trial</a>
            </div>
        </div>
    </nav>

    <section class="hero container">
        <h1>Enterprise-Grade AI Voice Agents. <span class="hero-gradient-text">Zero Engineering Required.</span></h1>
        <p>Deploy secure, autonomous voice agents for sales, support, and operations in 15 minutes. Configured entirely through natural language.</p>
        <div class="hero-ctas">
            <a href="/onboarding" class="btn btn-primary">Start Building Free</a>
            <a href="#how-it-works" class="btn btn-secondary">Learn More</a>
        </div>
    </section>

    <div class="trust-bar">
        <div class="container">
            <div class="trust-label">Trusted by innovative teams</div>
            <div class="logos">
                <!-- Placeholder SVG Logos replacing trust signals -->
                <svg viewBox="0 0 100 30"><text x="0" y="20" font-family="Arial" font-weight="bold" font-size="20">Acme Corp</text></svg>
                <svg viewBox="0 0 100 30"><text x="0" y="20" font-family="Arial" font-weight="bold" font-size="20">GlobalHealth</text></svg>
                <svg viewBox="0 0 100 30"><text x="0" y="20" font-family="Arial" font-weight="bold" font-size="20">Nexus Realty</text></svg>
                <svg viewBox="0 0 100 30"><text x="0" y="20" font-family="Arial" font-weight="bold" font-size="20">FinTrust</text></svg>
            </div>
        </div>
    </div>

    <section id="metrics" class="metrics-section container">
        <div class="section-header">
            <div class="section-tag">Value Proposition</div>
            <h2>Dramatically reduce operational costs</h2>
            <p>VoxAgent delivers the lowest cost-per-interaction in the industry without sacrificing reliability or human-like latency.</p>
        </div>
        <div class="metrics-grid">
            <div class="metric-card">
                <h3>$0.07</h3>
                <p>Average cost per call</p>
            </div>
            <div class="metric-card">
                <h3>15m</h3>
                <p>Average deployment time</p>
            </div>
            <div class="metric-card">
                <h3>83%</h3>
                <p>Cheaper than human SDRs</p>
            </div>
        </div>
    </section>

    <section id="how-it-works" class="how-section">
        <div class="container">
            <div class="section-header">
                <div class="section-tag">How It Works</div>
                <h2>Three steps to autonomous operations</h2>
                <p>Replace complex flowcharts with intuitive, natural language prompting.</p>
            </div>
            <div class="steps-grid">
                <div class="step-card">
                    <div class="step-icon">1</div>
                    <h3>Provide Instructions</h3>
                    <p>Describe your agent's persona, goals, and constraints in plain English. VoxAgent understands context inherently.</p>
                </div>
                <div class="step-card">
                    <div class="step-icon">2</div>
                    <h3>Integrate Tools</h3>
                    <p>Connect your calendar, CRM, or custom webhooks. The agent autonomously decides when to trigger these tools mid-conversation.</p>
                </div>
                <div class="step-card">
                    <div class="step-icon">3</div>
                    <h3>Monitor & Iterate</h3>
                    <p>Review AI-generated summaries, sentiment metrics, and transcripts natively in the dashboard to refine performance.</p>
                </div>
            </div>
        </div>
    </section>

    <section id="features" class="features-section container">
        <div class="section-header">
            <div class="section-tag">Enterprise Capabilities</div>
            <h2>Built for scale, security, and compliance</h2>
        </div>
        <div class="features-grid">
            <div class="feature-item">
                <div class="feature-icon-wrapper">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                </div>
                <div>
                    <h3>Multi-Tenant Security</h3>
                    <p>Strict data isolation, role-based access control, and end-to-end encryption to protect your proprietary knowledge bases.</p>
                </div>
            </div>
            <div class="feature-item">
                <div class="feature-icon-wrapper">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                </div>
                <div>
                    <h3>Ultra-Low Latency</h3>
                    <p>Direct bidirectional Mu-Law streaming combined with optimized GenAI models ensures sub-800ms conversational responses.</p>
                </div>
            </div>
            <div class="feature-item">
                <div class="feature-icon-wrapper">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"></ellipse><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path></svg>
                </div>
                <div>
                    <h3>RAG Knowledge Injection</h3>
                    <p>Upload PDFs or company guidelines. Our intelligent vector search ensures the agent answers hyper-specific questions accurately.</p>
                </div>
            </div>
            <div class="feature-item">
                <div class="feature-icon-wrapper">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                </div>
                <div>
                    <h3>Mid-Call Webhooks</h3>
                    <p>Trigger external systems during the call. Schedule events, sync CRM data, or send confirmation emails on the fly.</p>
                </div>
            </div>
        </div>
    </section>

    <section class="cta-bottom">
        <div class="container">
            <h2>Ready to transform your communication?</h2>
            <div class="hero-ctas">
                <a href="/onboarding" class="btn btn-primary">Get Started Free</a>
                <a href="/dashboard" class="btn btn-secondary">View Live Dashboard</a>
            </div>
        </div>
    </section>

    <footer>
        <div class="container">
            <div class="footer-links">
                <a href="/onboarding">Sign Up</a>
                <a href="/dashboard">Dashboard</a>
                <a href="/docs">API Reference</a>
                <a href="/health">System Status</a>
            </div>
            <p style="font-size: 13px;">&copy; 2024 VoxAgent AI. All rights reserved.</p>
        </div>
    </footer>

</body>
</html>"""