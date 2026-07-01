# 🔬 Deep Tech Deal Memo Generator

> AI-powered Investment Committee memo generator for deep tech startups — sector-specific analysis across AI, Space Tech, Robotics & Automation, and Advanced Materials.

[![Author](https://img.shields.io/badge/author-aitmai-black?style=flat-square&logo=github)](https://github.com/aitmai)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Deploy](https://img.shields.io/badge/deploy-Render-purple?style=flat-square)](https://render.com)

---

## Overview

A Flask application that generates structured VC Investment Committee memos for deep tech startups using Claude API with live web search. Input a company name and sector — get a fully structured IC memo with market analysis, team assessment, competitive landscape, and a sector-weighted Deep Tech Risk Framework.

Built as a portfolio piece targeting deep tech VC roles — specifically Toyota Ventures' Frontier Fund which invests in AI, space tech, robotics/automation, and advanced materials.

---

## Features

### Sector-Specific Analysis
Four deep tech verticals with tailored research frameworks, each with distinct market framing, risk focus, and moat assessment criteria:
- **AI** — model differentiation, data moat, foundation model commoditization risk, regulatory exposure
- **Space Tech** — flight heritage, launch economics, FAA/FCC regulatory pathway, capital intensity
- **Robotics & Automation** — labor displacement economics, hardware reliability, safety certifications, deployment environment
- **Advanced Materials** — manufacturing scalability, unit economics at scale, supply chain integration, EPA/regulatory exposure

### IC Memo Sections
- Executive Summary — investment thesis in 2-3 sentences
- Market Opportunity — TAM / SAM / SOM with methodology and sector-specific market dynamics
- Technology & Differentiation — technical moat and defensibility analysis
- Team Assessment — founder backgrounds and domain expertise
- Competitive Landscape — structured competitor comparison table
- Financial Snapshot — funding history, stage, valuation context
- Deep Tech Risk Framework — 4-dimension risk scoring weighted by sector
- IC Recommendation — Pass / Monitor / Pursue with reasoning

### Deep Tech Risk Framework
The differentiator: sector-weighted scoring across 4 dimensions that separates deep tech diligence from generic SaaS deal analysis:

| Dimension | Description |
|---|---|
| Technical Risk | Technology readiness level — lab to production validation stage |
| Capital Intensity | Total capital required to reach commercial scale |
| Regulatory Exposure | Certification timelines and compliance complexity |
| Hardware Dependency | Ratio of hardware to software in the business model |

Each sector applies different weights — a Space Tech deal weights capital intensity at 35% (vs. 15% for AI) because the capital requirements to reach orbit are fundamentally different from shipping software.

### Live Pipeline
- Real-time Server-Sent Events log showing analysis progress
- Claude API with web search tool — pulls live company data, funding news, and competitive intelligence
- Streaming status updates as each memo section is assembled

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask (Python) |
| AI / LLM | Claude Sonnet + web search tool use (Anthropic API) |
| Frontend | Vanilla HTML/CSS/JS — no build step |
| Streaming | Server-Sent Events |
| Deployment | Render |

---

## Setup

### Run locally

```bash
# Clone the repo
git clone https://github.com/aitmai/deep-tech-deal-memo-generator.git
cd deep-tech-deal-memo-generator

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY

# Run
python app.py
# → http://localhost:5051
```

### Deploy to Render

1. Push repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service → connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `python app.py`
5. Add environment variable: `ANTHROPIC_API_KEY`
6. Deploy

---

## Environment Variables

| Variable | Description | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude + web search | [console.anthropic.com](https://console.anthropic.com) |

---

## Example Usage

Enter any deep tech company and select the appropriate sector:

- **Xona Space Systems** + Space Tech → PNT satellite constellation IC memo
- **Pickle Robot** + Robotics & Automation → depalletizing robot IC memo
- **Joby Aviation** + AI → eVTOL autonomy IC memo
- **AM Batteries** + Advanced Materials → battery materials IC memo

All are real Toyota Ventures portfolio companies — useful for calibrating output quality.

---

## Project Structure

```
deep-tech-deal-memo-generator/
├── app.py               # Flask backend, Claude API, SSE streaming
├── templates/
│   └── index.html       # Full frontend — single file, no build needed
├── requirements.txt
├── Procfile             # Render/Heroku deployment
├── .env.example
└── .gitignore
```

---

## Security

- Never commit `.env` files — see `.gitignore`
- API key stored as environment variable, never in code
- All AI calls made server-side — key never exposed to client

---

## Roadmap

- [ ] PDF pitch deck upload and parsing
- [ ] Word doc memo export (python-docx)
- [ ] Google Sheets deal log integration
- [ ] Multiple company batch comparison
- [ ] Save/load memo history

---

## License

MIT © 2026 aitmai
