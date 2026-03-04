"""
Report generator — turns analysis JSON into two outputs:
1. TEASER: 3-4 tweet thread (public, free) — the hook
2. FULL BRIEF: markdown report → HTML (paywalled at $39/mo subscription)
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"


def generate_report_id(startup_name: str, timestamp: str | None = None) -> str:
    """Generate a short unique report ID."""
    ts = timestamp or datetime.now(tz=timezone.utc).isoformat()
    raw = f"{startup_name}-{ts}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def generate_teaser_thread(analysis: dict) -> list[str]:
    """
    Generate 3-4 tweet thread for the public teaser.
    This is the free preview — must be good enough to screenshot,
    incomplete enough to pay $100 for the full thing.
    """
    profile = analysis.get("company_profile", {})
    bullseye = analysis.get("bullseye_ranking", {})
    inner = bullseye.get("inner_ring", {})

    name = profile.get("name", "Your startup")
    one_liner = profile.get("one_liner", "")
    stage = profile.get("stage", "unknown")
    hot_take = analysis.get("hot_take", "")
    exec_summary = analysis.get("executive_summary", "")

    # Top 3 channels
    inner_channels = inner.get("channels", [])
    channel_scores = {}
    for ch in analysis.get("channel_analysis", []):
        channel_scores[ch["channel"]] = ch.get("score", "?")

    # Tweet 1: The headline
    tweet1 = f"mckoutie just analyzed {name}.\n\n"
    if one_liner:
        tweet1 += f"{one_liner}\n\n"
    tweet1 += f"Stage: {stage}\n"
    if profile.get("unique_angle"):
        tweet1 += f"Edge: {profile['unique_angle'][:120]}\n"
    tweet1 += "\nFull analysis below"

    # Tweet 2: Top channels
    tweet2 = f"Top 3 growth channels for {name}:\n\n"
    for i, ch in enumerate(inner_channels[:3], 1):
        score = channel_scores.get(ch, "?")
        tweet2 += f"{i}. {ch} ({score}/10)\n"
    if inner.get("reasoning"):
        reasoning = inner["reasoning"]
        if len(reasoning) > 140:
            reasoning = reasoning[:137] + "..."
        tweet2 += f"\n{reasoning}"

    # Tweet 3: The hot take (the thing that makes people screenshot)
    tweet3 = ""
    if hot_take:
        if len(hot_take) > 260:
            hot_take = hot_take[:257] + "..."
        tweet3 = f"Hot take on {name}:\n\n{hot_take}"
    else:
        # Use first paragraph of exec summary
        first_para = exec_summary.split("\n\n")[0] if exec_summary else ""
        if len(first_para) > 260:
            first_para = first_para[:257] + "..."
        tweet3 = f"The real insight:\n\n{first_para}"

    # Tweet 4: The CTA — link goes to mckoutie.com/report/{id}
    tweet4 = (
        f"Full 19-channel analysis for {name}:\n"
        f"- 90-day action plan\n"
        f"- Budget allocation\n"
        f"- Risk matrix\n"
        f"- Specific tactics per channel\n\n"
        f"${settings.report_price_usd}/mo — living report with monthly updates\n\n"
        f"{{report_link}}"  # Placeholder — filled by orchestrator with mckoutie.com URL
    )

    # Clean up — ensure each tweet is under 280 chars
    tweets = [tweet1, tweet2, tweet3, tweet4]
    cleaned = []
    for t in tweets:
        if t:
            if len(t) > 280:
                t = t[:277] + "..."
            cleaned.append(t)

    return cleaned


def generate_full_report_markdown(analysis: dict) -> str:
    """Generate the full consulting brief as markdown."""
    profile = analysis.get("company_profile", {})
    name = profile.get("name", "Startup")
    now = datetime.now(tz=timezone.utc).strftime("%B %d, %Y")

    sections = []

    # Header
    sections.append(f"# mckoutie Strategy Brief: {name}")
    sections.append(f"*Generated {now}*\n")
    sections.append("---\n")

    # Executive Summary
    sections.append("## Executive Summary\n")
    sections.append(analysis.get("executive_summary", "N/A"))
    sections.append("")

    # Company Profile
    sections.append("## Company Profile\n")
    sections.append(f"**Name:** {profile.get('name', 'N/A')}")
    sections.append(f"**What they do:** {profile.get('one_liner', 'N/A')}")
    sections.append(f"**Stage:** {profile.get('stage', 'N/A')}")
    sections.append(f"**Team size:** {profile.get('estimated_size', 'N/A')}")
    sections.append(f"**Market:** {profile.get('market', 'N/A')}")
    sections.append(f"**Business model:** {profile.get('business_model', 'N/A')}")
    sections.append(f"**Unique angle:** {profile.get('unique_angle', 'N/A')}")
    sections.append("")

    sections.append("### Strengths")
    for s in profile.get("strengths", []):
        sections.append(f"- {s}")
    sections.append("")

    sections.append("### Weaknesses & Risks")
    for w in profile.get("weaknesses", []):
        sections.append(f"- {w}")
    sections.append("")

    # Bullseye Framework
    bullseye = analysis.get("bullseye_ranking", {})
    sections.append("## Bullseye Framework — Channel Prioritization\n")

    inner = bullseye.get("inner_ring", {})
    sections.append("### Inner Ring (Test NOW)")
    for ch in inner.get("channels", []):
        sections.append(f"- **{ch}**")
    sections.append(f"\n*{inner.get('reasoning', '')}*\n")

    promising = bullseye.get("promising", {})
    sections.append("### Promising (Test Next)")
    for ch in promising.get("channels", []):
        sections.append(f"- {ch}")
    sections.append(f"\n*{promising.get('reasoning', '')}*\n")

    longshot = bullseye.get("long_shot", {})
    sections.append("### Long Shot (Maybe Later)")
    for ch in longshot.get("channels", []):
        sections.append(f"- {ch}")
    sections.append(f"\n*{longshot.get('reasoning', '')}*\n")

    # Channel-by-Channel Analysis
    sections.append("## 19-Channel Deep Analysis\n")

    for ch in analysis.get("channel_analysis", []):
        sections.append(f"### {ch.get('channel', 'Unknown')}")
        sections.append(f"**Score:** {ch.get('score', '?')}/10 | "
                        f"**Effort:** {ch.get('effort', '?')} | "
                        f"**Timeline:** {ch.get('timeline', '?')} | "
                        f"**Budget:** {ch.get('budget', '?')}")
        sections.append("")

        sections.append(f"**Why:** {ch.get('why_or_why_not', 'N/A')}\n")
        sections.append(f"**Killer insight:** {ch.get('killer_insight', 'N/A')}\n")
        sections.append(f"**First move:** {ch.get('first_move', 'N/A')}\n")

        sections.append("**Specific ideas:**")
        for idea in ch.get("specific_ideas", []):
            sections.append(f"- {idea}")
        sections.append("")

    # 90-Day Plan
    plan = analysis.get("ninety_day_plan", {})
    sections.append("## 90-Day Action Plan\n")

    for month_key, month_label in [("month_1", "Month 1"), ("month_2", "Month 2"), ("month_3", "Month 3")]:
        m = plan.get(month_key, {})
        sections.append(f"### {month_label}: {m.get('focus', 'TBD')}")
        sections.append(f"**Target metric:** {m.get('target_metric', 'TBD')}")
        sections.append(f"**Budget:** {m.get('budget', 'TBD')}")
        sections.append("")
        for action in m.get("actions", []):
            sections.append(f"- {action}")
        sections.append("")

    # Budget Allocation
    budget = analysis.get("budget_allocation", {})
    sections.append("## Budget Allocation\n")
    sections.append(f"**Total recommended (90 days):** {budget.get('total_recommended', 'TBD')}\n")

    sections.append("| Channel | Amount | Rationale |")
    sections.append("|---------|--------|-----------|")
    for b in budget.get("breakdown", []):
        sections.append(f"| {b.get('channel', '')} | {b.get('amount', '')} | {b.get('rationale', '')} |")
    sections.append("")

    # Risk Matrix
    sections.append("## Risk Matrix\n")
    sections.append("| Risk | Probability | Impact | Mitigation |")
    sections.append("|------|-------------|--------|------------|")
    for r in analysis.get("risk_matrix", []):
        sections.append(
            f"| {r.get('risk', '')} | {r.get('probability', '')} | "
            f"{r.get('impact', '')} | {r.get('mitigation', '')} |"
        )
    sections.append("")

    # Competitive Moat
    sections.append("## Competitive Moat Analysis\n")
    sections.append(analysis.get("competitive_moat", "N/A"))
    sections.append("")

    # Hot Take
    sections.append("## The Hot Take\n")
    sections.append(f"*{analysis.get('hot_take', 'N/A')}*")
    sections.append("")

    # Footer
    sections.append("---")
    sections.append("*Generated by mckoutie — McKinsey at home.*")
    sections.append("*This analysis is AI-generated and should be used as a starting point, not gospel.*")

    return "\n".join(sections)


def save_report(report_id: str, analysis: dict, markdown: str) -> Path:
    """Save both the raw JSON and markdown report to disk."""
    report_dir = REPORTS_DIR / report_id
    report_dir.mkdir(parents=True, exist_ok=True)

    # Save raw analysis
    with open(report_dir / "analysis.json", "w") as f:
        json.dump(analysis, f, indent=2)

    # Save markdown
    with open(report_dir / "report.md", "w") as f:
        f.write(markdown)

    logger.info(f"Report saved to {report_dir}")
    return report_dir


def generate_report_html(markdown_content: str, startup_name: str) -> str:
    """Convert markdown report to styled HTML page."""
    import markdown as md

    html_body = md.markdown(
        markdown_content,
        extensions=["tables", "fenced_code", "toc"],
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>mckoutie — {startup_name} Strategy Brief</title>
    <style>
        :root {{
            --bg: #0a0a0a;
            --text: #e0e0e0;
            --accent: #00ff88;
            --accent2: #ff6b35;
            --muted: #666;
            --border: #222;
            --card-bg: #111;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'SF Mono', 'Fira Code', 'JetBrains Mono', monospace;
            background: var(--bg);
            color: var(--text);
            line-height: 1.7;
            max-width: 900px;
            margin: 0 auto;
            padding: 2rem 1.5rem;
        }}
        h1 {{
            color: var(--accent);
            font-size: 1.8rem;
            margin: 2rem 0 0.5rem;
            border-bottom: 2px solid var(--accent);
            padding-bottom: 0.5rem;
        }}
        h2 {{
            color: var(--accent2);
            font-size: 1.3rem;
            margin: 2.5rem 0 1rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 0.3rem;
        }}
        h3 {{
            color: var(--text);
            font-size: 1.1rem;
            margin: 1.5rem 0 0.5rem;
        }}
        p {{ margin: 0.8rem 0; }}
        strong {{ color: var(--accent); }}
        em {{ color: var(--muted); font-style: italic; }}
        ul, ol {{ padding-left: 1.5rem; margin: 0.5rem 0; }}
        li {{ margin: 0.3rem 0; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
            font-size: 0.9rem;
        }}
        th {{
            background: var(--card-bg);
            color: var(--accent);
            padding: 0.6rem;
            text-align: left;
            border-bottom: 2px solid var(--accent);
        }}
        td {{
            padding: 0.5rem 0.6rem;
            border-bottom: 1px solid var(--border);
        }}
        tr:hover td {{ background: var(--card-bg); }}
        hr {{
            border: none;
            border-top: 1px solid var(--border);
            margin: 2rem 0;
        }}
        .header {{
            text-align: center;
            padding: 2rem 0;
            border-bottom: 2px solid var(--accent);
            margin-bottom: 2rem;
        }}
        .header h1 {{ border: none; font-size: 2.2rem; }}
        .header p {{ color: var(--muted); }}
        @media (max-width: 600px) {{
            body {{ padding: 1rem; font-size: 0.9rem; }}
            h1 {{ font-size: 1.4rem; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>mckoutie</h1>
        <p>McKinsey at home</p>
    </div>
    {html_body}
</body>
</html>"""
