import os
import json
import time
import threading
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from dotenv import load_dotenv
import anthropic

load_dotenv()

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

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
    return f"""You are a senior VC associate at a deep tech fund preparing a concise Investment Committee memo.

Company: {company}
Sector: {sector}
Additional context: {extra_info if extra_info else "None provided."}

Sector guidance:
- Market: {ctx['market_framing']}
- Risk: {ctx['risk_focus']}
- TAM: {ctx['tam_hint']}
- Moat: {ctx['moat_keywords']}

Return ONLY this JSON object. Be specific and concise — 1-2 sentences per field maximum. No preamble, no markdown fences:

{{
  "executive_summary": "2 sentence investment thesis.",
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
    "technical_risk": {{"score": 3, "reasoning": "One sentence"}},
    "capital_intensity": {{"score": 3, "reasoning": "One sentence"}},
    "regulatory_exposure": {{"score": 3, "reasoning": "One sentence"}},
    "hardware_dependency": {{"score": 3, "reasoning": "One sentence"}}
  }},
  "key_risks": ["Risk 1", "Risk 2", "Risk 3"],
  "key_strengths": ["Strength 1", "Strength 2", "Strength 3"],
  "recommendation": "Pass",
  "recommendation_reasoning": "2 sentences. Be direct."
}}"""


def run_memo(company, sector, extra_info=""):
    with state_lock:
        state.update({
            "status": "running",
            "sections": {},
            "log": [],
            "risk_scores": {},
            "recommendation": None,
            "company": company,
            "sector": sector,
        })

    try:
        log(f"Initiating deep tech analysis: {company} ({sector})")
        log("Loading sector-specific analysis framework...")
        time.sleep(0.5)

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

        # Repair common JSON issues from LLM output
        import re
        # Remove trailing commas before } or ]
        clean = re.sub(r',\s*([}\]])', r'\1', clean)
        # Truncate to last complete JSON object if response was cut off
        last_brace = clean.rfind('}')
        if last_brace != -1:
            clean = clean[:last_brace+1]

        memo = json.loads(clean)

        log("Scoring deep tech risk framework...")
        weights = SECTOR_WEIGHTS[sector]
        risk_scores = memo.get("risk_scores", {})
        composite = 0
        for dim, w in weights.items():
            score = risk_scores.get(dim, {}).get("score", 3)
            composite += score * w

        with state_lock:
            state["sections"] = memo
            state["risk_scores"] = risk_scores
            state["recommendation"] = memo.get("recommendation", "Monitor")
            state["composite_risk"] = round(composite, 2)

        log(f"Memo complete. Recommendation: {memo.get('recommendation', 'Monitor')}")
        log(f"Composite risk score: {round(composite, 2)}/5.0")

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

    if not company:
        return jsonify({"error": "Company name required"}), 400

    with state_lock:
        if state["status"] == "running":
            return jsonify({"error": "Analysis already running"}), 409

    t = threading.Thread(target=run_memo, args=(company, sector, extra_info), daemon=True)
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
