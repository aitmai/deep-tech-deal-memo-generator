import os
import sys
import json
import time
import threading
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from dotenv import load_dotenv
import anthropic

def clog(msg):
    """Force-flush cache debug messages to Render logs."""
    print(f"[CACHE] {msg}", flush=True)
    sys.stdout.flush()

load_dotenv()

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ── Airtable cache ──────────────────────────────────────────────────────────
import requests as req

CACHE_WEEKS      = 8
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "appPRlnlm12AP05TU")
AIRTABLE_TOKEN   = os.getenv("AIRTABLE_API_TOKEN", "")
AIRTABLE_TABLE   = "MemoCache"
AIRTABLE_URL     = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE}"


def airtable_headers():
    return {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }


def check_cache(company, sector):
    """Return (result_dict, saved_at_str) if valid cache found, else (None, None)."""
    if not AIRTABLE_TOKEN:
        clog("AIRTABLE_API_TOKEN not set — cache disabled")
        return None, None
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(weeks=CACHE_WEEKS)
        company_norm = company.lower().strip()
        sector_norm  = sector.lower().strip()

        # Search Airtable for matching records
        formula = f"AND(LOWER({{Company}})='{company_norm}', LOWER({{Sector}})='{sector_norm}')"
        params  = {"filterByFormula": formula, "sort[0][field]": "Timestamp", "sort[0][direction]": "desc", "maxRecords": 1}
        r = req.get(AIRTABLE_URL, headers=airtable_headers(), params=params, timeout=10)
        r.raise_for_status()
        records = r.json().get("records", [])

        if not records:
            clog(f"cache miss: {company} / {sector}")
            return None, None

        fields  = records[0].get("fields", {})
        ts_str  = fields.get("Timestamp", "")
        ts      = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        if ts < cutoff:
            clog(f"cache expired: {company} / {sector} saved {ts_str}")
            return None, None

        result   = json.loads(fields.get("ResultJSON", "{}"))
        saved_at = ts.strftime("%B %d, %Y")
        clog(f"cache hit: {company} / {sector} saved {saved_at}")
        return result, saved_at

    except Exception as e:
        clog(f"check_cache error: {e}")
        return None, None


def save_cache(company, sector, research_mode, result_dict):
    """Save memo result to Airtable cache."""
    if not AIRTABLE_TOKEN:
        return
    try:
        result_json = json.dumps(result_dict, separators=(',', ':'))
        payload = {
            "records": [{
                "fields": {
                    "Company":      company,
                    "Sector":       sector,
                    "Timestamp":    datetime.now(timezone.utc).isoformat(),
                    "ResearchMode": research_mode,
                    "ResultJSON":   result_json
                }
            }]
        }
        r = req.post(AIRTABLE_URL, headers=airtable_headers(), json=payload, timeout=15)
        r.raise_for_status()
        clog(f"saved: {company} / {sector} ({len(result_json)} chars)")
    except Exception as e:
        clog(f"save_cache error: {e}")
# ── End cache ────────────────────────────────────────────────────────────────

state = {
    "status": "idle",
    "sections": {},
    "log": [],
    "risk_scores": {},
    "recommendation": None,
    "company": None,
    "sector": None,
}
state_lock = threading.Lock()


def log(msg):
    with state_lock:
        state["log"].append({"ts": time.strftime("%H:%M:%S"), "msg": msg})


SECTOR_CONTEXT = {
    "AI": {
        "market_framing": "Focus on model differentiation, data moat, compute cost structure, and defensibility against foundation model commoditization. Assess whether the company has proprietary data or architecture advantages.",
        "risk_focus": "Technical risk = model performance vs. benchmarks and production reliability. Regulatory = AI Act, state-level AI regulation, liability exposure. Competition = speed of foundation model incumbents closing the gap.",
        "tam_hint": "Consider total AI software market, applicable vertical market, and realistic serviceable share given enterprise adoption cycles.",
        "moat_keywords": "proprietary data, model architecture, inference efficiency, API ecosystem, enterprise contracts, switching costs",
    },
    "Space Tech": {
        "market_framing": "Focus on launch cost trends, payload economics, orbital slot dynamics, and regulatory pathway (FAA/FCC licensing timelines). Assess hardware flight heritage and mission reliability.",
        "risk_focus": "Technical risk = flight-proven vs. lab-only vs. demo hardware. Capital intensity = extremely high with multi-year runway requirements before revenue. Regulatory = FAA launch licenses, FCC spectrum, ITAR/export controls.",
        "tam_hint": "Consider commercial launch market, satellite services, government contracts (NASA, DoD), and downstream applications.",
        "moat_keywords": "flight heritage, proprietary propulsion, launch cadence, government contracts, spectrum licenses, vertical integration",
    },
    "Robotics & Automation": {
        "market_framing": "Focus on labor cost displacement economics, deployment environment complexity (structured warehouse vs. unstructured real-world), safety certification pathway, and customer ROI timeline.",
        "risk_focus": "Hardware ratio = high. Regulatory = OSHA/safety certs, UL listings, industry-specific certifications. Technical risk = reliability and uptime in production conditions vs. demo conditions. Sales cycle = long enterprise procurement.",
        "tam_hint": "Consider total addressable labor cost in target industry, automation penetration rates, and replacement cycle economics.",
        "moat_keywords": "proprietary hardware design, sensor fusion, edge AI, safety certifications, customer integrations, field-proven reliability",
    },
    "Advanced Materials": {
        "market_framing": "Focus on manufacturing scalability from lab to pilot to commercial scale, unit economics at each stage, existing supply chain integration, and end-market pull (who pays and why now).",
        "risk_focus": "Capital intensity = very high for pilot plants and scale-up. Regulatory = EPA, material safety, application-specific (FDA if biomedical, DOT if transport). Technical risk = performance consistency at scale vs. lab conditions.",
        "tam_hint": "Consider incumbent material market being displaced, performance premium pricing potential, and volume economics at scale.",
        "moat_keywords": "proprietary synthesis process, patents, manufacturing know-how, supply agreements, performance specifications, certifications",
    },
}

RISK_DIMENSIONS = {
    "technical_risk": {
        "label": "Technical Risk",
        "description": "Technology readiness level, validation stage, and path from lab to production",
        "scale": "1=Lab-proven at scale, 5=Early prototype only"
    },
    "capital_intensity": {
        "label": "Capital Intensity",
        "description": "Total capital required to reach commercial scale and positive unit economics",
        "scale": "1=Low capex SaaS-like, 5=Billion-dollar infrastructure requirements"
    },
    "regulatory_exposure": {
        "label": "Regulatory Exposure",
        "description": "Regulatory burden, certification timelines, and compliance complexity",
        "scale": "1=Minimal regulation, 5=Multi-year approval process required"
    },
    "hardware_dependency": {
        "label": "Hardware Dependency",
        "description": "Ratio of hardware to software in business model and risk profile",
        "scale": "1=Pure software/AI, 5=Complex custom hardware required"
    },
}

SECTOR_WEIGHTS = {
    "AI":                    {"technical_risk": 0.35, "capital_intensity": 0.15, "regulatory_exposure": 0.30, "hardware_dependency": 0.10},
    "Space Tech":            {"technical_risk": 0.35, "capital_intensity": 0.35, "regulatory_exposure": 0.20, "hardware_dependency": 0.30},
    "Robotics & Automation": {"technical_risk": 0.30, "capital_intensity": 0.25, "regulatory_exposure": 0.25, "hardware_dependency": 0.30},
    "Advanced Materials":    {"technical_risk": 0.25, "capital_intensity": 0.40, "regulatory_exposure": 0.30, "hardware_dependency": 0.25},
}


def build_memo_prompt(company, sector, extra_info=""):
    ctx = SECTOR_CONTEXT[sector]
    return f"""You are a senior VC associate at a corporate venture capital fund (CVC) backed by a large industrial or technology corporation. The fund invests in deep tech startups across AI, space tech, robotics/automation, and advanced materials.

IMPORTANT: This is a corporate CVC, not a traditional VC fund. Strategic fit with the corporate parent's core business is a key investment criterion alongside financial returns. A company with strong technical differentiation relevant to the corporate parent's industry should score higher than pure financial metrics suggest — even if commercial traction is early or data is limited.

Company: {company}
Sector: {sector}
Additional context: {extra_info if extra_info else "None provided."}

Sector guidance:
- Market: {ctx['market_framing']}
- Risk: {ctx['risk_focus']}
- TAM: {ctx['tam_hint']}
- Moat: {ctx['moat_keywords']}

Return ONLY this JSON object. Be specific and concise — 1-2 sentences per field maximum. If you lack specific data, make reasonable assumptions based on sector and stage — do not refuse to analyze. State assumptions clearly. No preamble, no markdown fences:

{{
  "executive_summary": "2 sentence investment thesis from a corporate CVC perspective.",
  "market_opportunity": {{
    "tam": "TAM estimate with methodology",
    "sam": "SAM with reasoning",
    "som": "SOM near-term realistic",
    "market_dynamics": "1-2 sentences on key tailwinds for {sector}"
  }},
  "technology_moat": "1-2 sentences on technical differentiation and defensibility.",
  "team_assessment": "1-2 sentences on founding team, domain expertise, credentials.",
  "competitive_landscape": [
    {{"competitor": "Name", "funding": "$XM", "differentiation": "One sentence"}}
  ],
  "financial_snapshot": {{
    "funding_history": "Known rounds and investors",
    "current_stage": "Stage",
    "revenue_status": "Known traction or revenue",
    "valuation_context": "Last known valuation or comp deals"
  }},
  "risk_scores": {{
    "technical_risk": {{"score": 3, "reasoning": "One sentence. Score MUST be an integer between 1 and 5 only."}},
    "capital_intensity": {{"score": 3, "reasoning": "One sentence. Score MUST be an integer between 1 and 5 only."}},
    "regulatory_exposure": {{"score": 3, "reasoning": "One sentence. Score MUST be an integer between 1 and 5 only."}},
    "hardware_dependency": {{"score": 3, "reasoning": "One sentence. Score MUST be an integer between 1 and 5 only."}}
  }},
  "IMPORTANT_SCORING_RULE": "All risk scores above MUST be integers 1-5. Never use 6, 7, or any value outside 1-5.",
  "strategic_fit": {{
    "score": 3,
    "corporate_relevance": "1 sentence on how this technology benefits the corporate parent's core business.",
    "partnership_potential": "1 sentence on whether the corporate parent could be a customer, manufacturing partner, or distribution channel.",
    "competitive_intelligence": "1 sentence on whether investing gives the corporate parent visibility into a disruptive or enhancing technology."
  }},
  "key_risks": ["Risk 1", "Risk 2", "Risk 3"],
  "key_strengths": ["Strength 1", "Strength 2", "Strength 3"],
  "financial_recommendation": "Pursue or Monitor or Pass — choose exactly one word only",
  "financial_recommendation_reasoning": "1-2 sentences on financial return potential — traction, moat, market size, capital efficiency.",
  "strategic_recommendation": "Pursue or Monitor or Pass — choose exactly one word only",
  "strategic_recommendation_reasoning": "1-2 sentences on strategic value to the corporate parent — relevance, partnership potential, competitive intelligence value.",
  "recommendation": "Pursue or Monitor or Pass — choose exactly one of these three words only, no other text",
  "recommendation_reasoning": "2 sentences. Combined verdict weighing financial returns AND strategic fit. If strategic fit is strong, recommend Pursue or Monitor even with limited financial data.",
  "company_grade": "A",
  "company_grade_reasoning": "2 sentences. Grade as standalone business independent of fund fit. A=exceptional, B=solid, C=viable, D=struggling, F=not viable."
}}"""


def run_memo(company, sector, extra_info="", research_mode="haiku", force_refresh=False):
    with state_lock:
        state.update({
            "status": "running",
            "sections": {},
            "log": [],
            "risk_scores": {},
            "recommendation": None,
            "company": company,
            "sector": sector,
            "from_cache": False,
        })

    try:
        # ── Cache check ──────────────────────────────────────────────────────
        if not force_refresh and not extra_info:
            log("Checking memo cache...")
            cached_result, saved_at = check_cache(company, sector)
            if cached_result:
                log(f"✓ Loaded from cache — saved {saved_at} (within {CACHE_WEEKS} weeks)")
                with state_lock:
                    state["sections"] = cached_result
                    state["risk_scores"] = cached_result.get("risk_scores", {})
                    state["recommendation"] = cached_result.get("recommendation", "Pass")
                    state["composite_risk"] = cached_result.get("_composite_risk", None)
                    state["status"] = "done"
                    state["from_cache"] = True
                return
        elif force_refresh:
            log("Force refresh — skipping cache, running fresh analysis...")
        # ── End cache check ──────────────────────────────────────────────────
        log(f"Initiating deep tech analysis: {company} ({sector})")

        # Auto-research step — gather company context if none provided
        if not extra_info:
            if research_mode == "sonnet":
                log("Deep mode: Sonnet + web search, full research (~$0.08/run)...")
                research_model = "claude-sonnet-4-6"
                use_web_search = True
                max_turns = 6
            elif research_mode == "standard":
                log("Standard mode: Haiku + web search, lightweight research (~$0.03/run)...")
                research_model = "claude-haiku-4-5-20251001"
                use_web_search = True
                max_turns = 3
            else:
                log("Fast mode: Haiku, training data only (~$0.02/run)...")
                research_model = "claude-haiku-4-5-20251001"
                use_web_search = False
                max_turns = 1

            research_prompt = f"""Research {company} in the {sector} sector for VC investment analysis.

Find and return:
1. What they do — one sentence
2. Founded year and HQ
3. Funding history — all rounds, amounts, lead investors, total raised
4. Latest ARR or revenue metrics
5. Valuation at last round
6. Key competitors — 3-4 names
7. Current status and recent news
8. Why a VC would be interested — one sentence
9. Biggest risk — one sentence

Be specific with real numbers. Plain text, under 150 words."""

            research_messages = [{"role": "user", "content": research_prompt}]
            auto_context = ""
            tools = [{"type": "web_search_20250305", "name": "web_search"}] if use_web_search else []

            for attempt in range(max_turns):
                research_kwargs = dict(
                    model=research_model,
                    max_tokens=800,
                    messages=research_messages
                )
                if tools:
                    research_kwargs["tools"] = tools

                research_response = client.messages.create(**research_kwargs)
                for block in research_response.content:
                    if hasattr(block, "text") and block.text:
                        auto_context += block.text

                if research_response.stop_reason == "end_turn":
                    break

                if research_response.stop_reason == "tool_use":
                    research_messages.append({"role": "assistant", "content": research_response.content})
                    tool_results = []
                    for block in research_response.content:
                        if block.type == "tool_use":
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": "Search completed."
                            })
                    research_messages.append({"role": "user", "content": tool_results})
                else:
                    break

            extra_info = auto_context.strip()
            log("Research complete. Building sector analysis...")
        else:
            log("Using provided context. Building sector analysis...")

        time.sleep(0.3)
        prompt = build_memo_prompt(company, sector, extra_info)
        log("Running IC memo generation via Claude Haiku...")

        # Handle single-turn response (no web search - uses training data)
        messages = [{"role": "user", "content": prompt}]

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=3000,
            messages=messages
        )

        # Extract text from response
        full_text = ""
        for block in response.content:
            if hasattr(block, "text") and block.text:
                full_text += block.text

        log("Parsing investment memo sections...")

        # Robust JSON extraction
        clean = full_text.strip()
        # Strip markdown fences
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0]
        elif "```" in clean:
            parts = clean.split("```")
            if len(parts) >= 3:
                clean = parts[1]
                if clean.startswith("json"):
                    clean = clean[4:]
        # Find JSON object boundaries if text has surrounding content
        if not clean.startswith("{"):
            start = clean.find("{")
            end = clean.rfind("}") + 1
            if start != -1 and end > start:
                clean = clean[start:end]
        clean = clean.strip()

        if not clean:
            raise ValueError("No JSON content found in Claude response")

        # Step 1 — strip problematic control characters and non-printable chars
        import re
        # Remove control characters except tab, newline, carriage return
        clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', clean)
        # Replace curly/smart quotes with straight quotes
        clean = clean.replace('\u201c', '"').replace('\u201d', '"')
        clean = clean.replace('\u2018', "'").replace('\u2019', "'")
        # Replace em-dash and en-dash with regular hyphen inside strings
        clean = clean.replace('\u2014', '-').replace('\u2013', '-')

        # Step 2 — use json_repair to fix any remaining structural issues
        from json_repair import repair_json
        clean = repair_json(clean, return_objects=False)

        # Step 3 — remove trailing commas as extra safety
        clean = re.sub(r',\s*([}\]])', r'\1', clean)

        # Step 4 — truncate to first complete JSON object
        brace_count = 0
        end_pos = 0
        for i, ch in enumerate(clean):
            if ch == '{':
                brace_count += 1
            elif ch == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_pos = i + 1
                    break
        if end_pos > 0:
            clean = clean[:end_pos]

        memo = json.loads(clean)

        # Clamp all risk scores to valid 1-5 range
        risk_scores = memo.get("risk_scores", {})
        for dim in risk_scores:
            if isinstance(risk_scores[dim], dict):
                try:
                    raw = float(risk_scores[dim].get("score", 3))
                    risk_scores[dim]["score"] = max(1, min(5, int(round(raw))))
                except (TypeError, ValueError):
                    risk_scores[dim]["score"] = 3

        # Normalize recommendation fields to valid values only
        valid_recs = {"pursue": "Pursue", "monitor": "Monitor", "pass": "Pass"}
        for field in ["recommendation", "financial_recommendation", "strategic_recommendation"]:
            val = str(memo.get(field, "Pass")).strip().lower()
            # Extract first matching keyword
            for key in ["pursue", "monitor", "pass"]:
                if key in val:
                    memo[field] = valid_recs[key]
                    break
            else:
                memo[field] = "Pass"

        log("Scoring deep tech risk framework...")
        weights = SECTOR_WEIGHTS[sector]
        risk_scores = memo.get("risk_scores", {})
        composite = 0
        for dim, w in weights.items():
            raw = risk_scores.get(dim, {})
            score = raw.get("score", 3) if isinstance(raw, dict) else 3
            try:
                score = float(score)
                score = max(1.0, min(5.0, score))  # clamp to valid range
            except (TypeError, ValueError):
                score = 3.0
            composite += score * w

        with state_lock:
            state["sections"] = memo
            state["risk_scores"] = risk_scores
            state["recommendation"] = memo.get("recommendation", "Monitor")
            state["composite_risk"] = round(composite, 2)

        log(f"Memo complete. Recommendation: {memo.get('recommendation', 'Monitor')}")
        log(f"Composite risk score: {round(composite, 2)}/5.0")

        # Save to cache (store composite risk inside memo for retrieval)
        memo["_composite_risk"] = round(composite, 2)
        log("Saving to memo cache...")
        save_cache(company, sector, research_mode, memo)
        log("✓ Result cached for 8 weeks.")

        with state_lock:
            state["status"] = "done"

    except Exception as e:
        log(f"ERROR: {e}")
        with state_lock:
            state["status"] = "error"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run():
    data = request.json
    company = data.get("company", "").strip()
    sector = data.get("sector", "AI")
    extra_info = data.get("extra_info", "").strip()
    research_mode = data.get("research_mode", "haiku")
    force_refresh = data.get("force_refresh", False)

    if not company:
        return jsonify({"error": "Company name required"}), 400

    with state_lock:
        if state["status"] == "running":
            return jsonify({"error": "Analysis already running"}), 409

    t = threading.Thread(target=run_memo, args=(company, sector, extra_info, research_mode, force_refresh), daemon=True)
    t.start()
    return jsonify({"ok": True})


@app.route("/status")
def status():
    with state_lock:
        return jsonify(dict(state))


@app.route("/stream")
def stream():
    def event_gen():
        last_log_idx = 0
        while True:
            with state_lock:
                current = dict(state)
                new_logs = current["log"][last_log_idx:]
                last_log_idx = len(current["log"])

            for entry in new_logs:
                yield f"data: {json.dumps({'type': 'log', 'ts': entry['ts'], 'msg': entry['msg']})}\n\n"

            yield f"data: {json.dumps({'type': 'state', 'status': current['status']})}\n\n"

            if current["status"] in ("done", "error"):
                yield f"data: {json.dumps({'type': 'complete', 'status': current['status']})}\n\n"
                break

            time.sleep(0.5)

    return Response(stream_with_context(event_gen()), mimetype="text/event-stream")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5051))
    app.run(host="0.0.0.0", port=port, debug=False)
