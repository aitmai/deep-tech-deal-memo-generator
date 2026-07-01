# 🔬 Deep Tech Deal Memo Generator

> AI-powered Investment Committee memo generator for deep tech startups — sector-specific analysis across AI, Space Tech, Robotics & Automation, and Advanced Materials.

[![Author](https://img.shields.io/badge/author-aitmai-black?style=flat-square&logo=github)](https://github.com/aitmai)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Live](https://img.shields.io/badge/live-demo-00C9A7?style=flat-square)](https://deep-tech-deal-memo-generator.onrender.com)
[![Deploy](https://img.shields.io/badge/deploy-Render-purple?style=flat-square)](https://render.com)

**🔗 Live demo: [deep-tech-deal-memo-generator.onrender.com](https://deep-tech-deal-memo-generator.onrender.com)**

---

## Overview

A Flask application that generates structured VC Investment Committee memos for deep tech startups using Claude API. Input a company name and sector — get a fully structured IC memo with market analysis, team assessment, competitive landscape, sector-weighted risk scoring, corporate fit analysis, and a three-verdict recommendation framework.

Built as a portfolio piece targeting deep tech VC and corporate CVC roles — covering the four major deep tech verticals: AI, space tech, robotics/automation, and advanced materials.

---

## Features

### Three Research Modes
| Mode | Model | Web Search | Cost |
|---|---|---|---|
| ⚡ Fast | Claude Haiku 4.5 | No | ~$0.02/run |
| 🔎 Standard | Claude Haiku 4.5 | Yes (3 turns) | ~$0.03/run |
| 🔍 Deep | Claude Sonnet 4.6 | Yes (6 turns) | ~$0.08/run |

### Auto-Research
When additional context is left blank, the app automatically researches the company (funding history, revenue, competitors, current status) before generating the memo — using live web search in Standard and Deep modes.

### Airtable Memo Cache
Results are cached in Airtable for 8 weeks. On repeated queries the app returns the cached result instantly at zero cost. A Force Refresh checkbox bypasses the cache when fresh analysis is needed.

### Sector-Specific Analysis
Four deep tech verticals with tailored research frameworks:
- **AI** — model differentiation, data moat, foundation model commoditization risk, regulatory exposure
- **Space Tech** — flight heritage, launch economics, FAA/FCC regulatory pathway, capital intensity
- **Robotics & Automation** — labor displacement economics, hardware reliability, safety certifications, deployment environment
- **Advanced Materials** — manufacturing scalability, unit economics at scale, supply chain integration, regulatory exposure

### IC Memo Sections
- Executive Summary — investment thesis
- Market Opportunity — TAM / SAM / SOM with sector-specific dynamics
- Technology & Moat — technical differentiation and defensibility
- Team Assessment — founder backgrounds and domain expertise
- Competitive Landscape — structured competitor comparison table
- Financial Snapshot — funding history, stage, valuation context
- Deep Tech Risk Framework — 4-dimension sector-weighted risk scoring
- Corporate Fit — strategic relevance, partnership potential, competitive intelligence value
- Recommendation — three-verdict framework (Financial Return / Strategic Fit / Combined IC)
- Company Quality Grade — A–F standalone business quality score

### Deep Tech Risk Framework
Sector-weighted scoring across 4 dimensions:

| Dimension | Description |
|---|---|
| Technical Risk | Technology readiness — lab prototype vs. production-proven |
| Capital Intensity | Total capital required to reach commercial scale |
| Regulatory Exposure | Certification timelines and compliance complexity |
| Hardware Dependency | Hardware vs. software ratio in the business model |

Space Tech weights capital intensity at 35% vs. 15% for AI — reflecting how fundamentally different the risk profiles are across deep tech verticals.

### Three-Verdict Recommendation
| Verdict | What it measures |
|---|---|
| Financial Return | Traditional VC lens — traction, moat, market size, capital efficiency |
| Strategic Fit (Corporate) | Corporate CVC lens — relevance, partnership potential, competitive intelligence |
| Combined IC Recommendation | Weighted verdict — strategic fit can override weak financials at early stage |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask (Python) |
| AI / LLM | Claude Haiku 4.5 + Claude Sonnet 4.6 (Anthropic API) |
| Web Search | Anthropic web_search tool (Standard + Deep modes) |
| Cache | Airtable (8-week TTL, free tier) |
| Frontend | Vanilla HTML/CSS/JS — no build step |
| Streaming | Server-Sent Events (SSE) |
| Deployment | Render (free tier) |

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
# Edit .env with your keys

# Run
python app.py
# → http://localhost:5051
```

### Deploy to Render

1. Push repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service → connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `python app.py`
5. Add environment variables (see below)
6. Deploy

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | Anthropic API key — [console.anthropic.com](https://console.anthropic.com) |
| `AIRTABLE_API_TOKEN` | Optional | Airtable personal access token for memo caching |
| `AIRTABLE_BASE_ID` | Optional | Airtable base ID containing the MemoCache table |

If Airtable env vars are not set, the app runs without caching — every run calls Claude.

---

## Airtable Cache Setup

1. Create an Airtable base with a table named `MemoCache`
2. Add fields: `Company` (text), `Sector` (text), `Timestamp` (text), `ResearchMode` (text), `ResultJSON` (long text)
3. Create a personal access token at [airtable.com/create/tokens](https://airtable.com/create/tokens) with `data.records:read` and `data.records:write` scopes
4. Add `AIRTABLE_API_TOKEN` and `AIRTABLE_BASE_ID` to your Render environment variables

---

## Example Usage

Enter any deep tech company and select the appropriate sector:

- **Pickle Robot** + Robotics & Automation → depalletizing robot IC memo
- **Xona Space Systems** + Space Tech → PNT satellite constellation IC memo
- **AM Batteries** + Advanced Materials → battery electrode manufacturing IC memo
- **Glean** + AI → enterprise AI search IC memo
- **Jasper** + AI → AI content generation platform IC memo
- **ChimpRewriter** + AI → AI writing and paraphrasing tool IC memo

---

## Project Structure

```
deep-tech-deal-memo-generator/
├── app.py               # Flask backend, Claude API, Airtable cache, SSE streaming
├── templates/
│   └── index.html       # Full frontend — single file, no build needed
├── requirements.txt
├── Procfile             # Render deployment
├── .env.example
└── .gitignore
```

---

## Security

- Never commit `.env` files — see `.gitignore`
- All API keys stored as environment variables, never in code
- All AI and cache calls made server-side — keys never exposed to client

---

## Roadmap

- [ ] PDF pitch deck upload and parsing
- [ ] Word doc memo export (python-docx)
- [ ] Batch comparison across multiple companies
- [ ] Portfolio tracking dashboard

---

## License

MIT © 2026 aitmai
