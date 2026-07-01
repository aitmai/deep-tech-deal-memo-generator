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
    return f"""You are a senior venture capital associate at a deep tech fund preparing an Investment Committee memo.

Company: {company}
Sector: {sector}
Additional context provided: {extra_info if extra_info else "None — research this company thoroughly."}

Sector-specific guidance:
- Market framing: {ctx['market_framing']}
- Risk focus: {ctx['risk_focus']}
- TAM approach: {ctx['tam_hint']}
- Key moat keywords to assess: {ctx['moat_keywords']}

Generate a thorough Investment Committee memo in this exact JSON structure. Be specific, analytical, and use real data where you can find it. Do not use placeholders:

{{
  "executive_summary": "2-3 sentence thesis paragraph. Lead with what the company does, why the timing is right, and the key investment thesis.",
  "market_opportunity": {{
    "tam": "Total Addressable Market estimate with methodology",
    "sam": "Serviceable Addressable Market with reasoning",
    "som": "Serviceable Obtainable Market realistic near-term",
    "market_dynamics": "2-3 sentences on key market tailwinds specific to {sector}"
  }},
  "technology_moat": "2-3 sentences assessing the core technical differentiation and defensibility. Be specific about what makes this hard to replicate.",
  "team_assessment": "2-3 sentences on founding team. Include relevant backgrounds, domain expertise, and any notable prior exits or technical credentials.",
  "competitive_landscape": [
    {{"competitor": "Name", "funding": "$XM", "differentiation": "How this company differs"}}
  ],
  "financial_snapshot": {{
    "funding_history": "Known funding rounds and investors",
    "current_stage": "Seed/Series A/etc",
    "revenue_status": "Known revenue or traction metrics",
    "burn_estimate": "Estimated burn rate if known, otherwise note unknown",
    "valuation_context": "Last known valuation or comparable deals"
  }},
  "risk_scores": {{
    "technical_risk": {{"score": 1-5, "reasoning": "One sentence explanation"}},
    "capital_intensity": {{"score": 1-5, "reasoning": "One sentence explanation"}},
    "regulatory_exposure": {{"score": 1-5, "reasoning": "One sentence explanation"}},
    "hardware_dependency": {{"score": 1-5, "reasoning": "One sentence explanation"}}
  }},
  "key_risks": ["Risk 1 specific to this company", "Risk 2", "Risk 3"],
  "key_strengths": ["Strength 1", "Strength 2", "Strength 3"],
  "recommendation": "Pass" or "Monitor" or "Pursue",
  "recommendation_reasoning": "2-3 sentences explaining the recommendation. Be direct and analytical."
}}

Return ONLY the JSON object. No preamble, no markdown fences, no explanation outside the JSON."""


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
        log("Searching for company data, funding history, and competitive landscape...")
        time.sleep(0.5)

        prompt = build_memo_prompt(company, sector, extra_info)

        log("Running sector-specific analysis framework...")

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract text from response
        full_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                full_text += block.text

        log("Parsing investment memo sections...")

        # Clean and parse JSON
        clean = full_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

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
