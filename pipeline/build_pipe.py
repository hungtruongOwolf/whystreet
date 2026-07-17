"""Generate whystreet.pipe — a PARALLEL multi-step RocketRide pipeline.

Reliable "parallel N-node" design (RocketRide's showcased strength, à la the
FitCheck 6-node demo), WITHOUT flaky agent tool-calling:

  chat ─┬─ prompt_graph   → llm_graph   ─┐
        ├─ prompt_reasons → llm_reasons ─┤→ response_answers (3 inputs, merged)
        └─ prompt_similar → llm_similar ─┘

The three branches run CONCURRENTLY on RocketRide's C++ engine, each reasoning
over the SAME live Linkup evidence (injected by the backend into the chat
question). Each branch has a focused job and emits a tagged JSON object:
  - graph   : the causal graph, edges tiered direct | indirect | similar
  - reasons : summary + cited reasons + risk/recovery/signal/confidence scores
  - similar : analogous past events (for the "similar event" links + history)

The backend fans the evidence in and merges the three tagged answers.
LLM provider/model is env-driven (${ROCKETRIDE_LLM_*}).
"""

import json
from pathlib import Path

LLM = {
    "profile": "custom",
    "custom": {
        "apikey": "${ROCKETRIDE_LLM_KEY}",
        "base_url": "${ROCKETRIDE_LLM_BASE_URL}",
        "model": "${ROCKETRIDE_LLM_MODEL}",
        "modelTotalTokens": 32768,
    },
    "parameters": {},
}

BRANCHES = {
    "graph": [
        "You are the CAUSAL-CHAIN branch of WhyStreet. From the Linkup evidence, lay out the chain of "
        "cause and effect that drove this stock move, as a simple ordered LIST OF STEPS (do NOT build a "
        "node/edge graph — just the steps). Example: 'US export restrictions on advanced chips' -> "
        "'weaker China chip demand' -> 'semiconductor sector pressure' -> the stock. Name SPECIFIC real "
        "events (tariffs, export controls, macro/rate policy, supply-chain shocks, earnings, competitor "
        "moves), not vague summaries. Be skeptical — do NOT blame the biggest headline by default.",
        "The catalyst is NOT confined to the move's own day. Build the chain's ROOT/EARLY links from the "
        "EARLIER BUILD-UP evidence (developments in the weeks before) and the FINAL proximate link from the "
        "PROXIMATE TRIGGER evidence. Earlier causes are expected and correct — do not force every step onto "
        "the move date.",
        "Each step is one causal link: {\"cause\": short specific label, \"cause_type\": event|entity|sector, "
        "\"effect\": short label, \"effect_type\": event|entity|sector|stock, \"relation\": the mechanism in a "
        "short phrase, \"strength\": direct (mechanical business link) | indirect (macro/sentiment), "
        "\"polarity\": up|down (does this push the effect up or down), \"source_url\": the evidence URL "
        "supporting this step, copied verbatim from the SOURCES}.",
        "The LAST step's effect must be the stock itself: set \"effect\": \"<TICKER> <MOVE>\", \"effect_type\": "
        "\"stock\". Chain the steps so each effect becomes the next step's cause. 3-6 steps is ideal.",
        "GROUND every step with a real source_url from the evidence. Drop steps you cannot ground.",
        "Respond with ONLY: {\"branch\":\"graph\",\"chain\":[ ...steps... ]}. No prose, no fences.",
    ],
    "reasons": [
        "You are the REASONS+SCORES branch of WhyStreet, an evidence-first equity analyst. Using ONLY the "
        "Linkup evidence, explain WHY the stock moved. Judge the move relative to the stock's own volatility "
        "(given in the message): a move within ~2 sigma is ordinary noise, not a crisis. Never invent facts; "
        "if evidence is thin, say so and keep confidence Low.",
        "Write an 'explanation' (2-4 sentences): the TRANSMISSION MECHANISM — how the events actually reach "
        "this stock's price, AND the MARKET PSYCHOLOGY behind the move (fear, sentiment, risk-off/on, "
        "positioning, valuation re-rating, over/under-reaction). Explain the 'why it moved the price', not "
        "just what happened. Ground it in the evidence.",
        "Every reason MUST carry a source_url copied verbatim from the evidence SOURCES. Drop unsourced reasons.",
        "scores: riskScore 0-100, recoveryScore 0-100, signal one of Buy|Sell|Hold (default Hold unless the "
        "evidence is strong and consistent), confidence one of Low|Medium|High (Low if few sources).",
        "Respond with ONLY: {\"branch\":\"reasons\",\"summary\":\"one sentence\",\"explanation\":\"2-4 sentences on "
        "mechanism + market psychology\",\"reasons\":[{\"text\",\"direction\":up|down,\"confidence\":0-1,\"source_url\","
        "\"source_title\"}],\"scores\":{\"riskScore\",\"recoveryScore\",\"signal\",\"confidence\"}}. No prose, no fences.",
    ],
    "similar": [
        "You are the SIMILAR-EVENTS branch of WhyStreet. From the Linkup evidence, identify up to 4 analogous "
        "PAST events (same driver/category, for this stock or its sector) and what happened to the price after "
        "each. Use ONLY the evidence; if none are present, return an empty list.",
        "Each item MUST carry a source_url from the evidence SOURCES.",
        "Respond with ONLY: {\"branch\":\"similar\",\"similar\":[{\"date\",\"headline\",\"outcome\": short,"
        "\"direction\":up|down,\"source_url\"}]}. No prose, no fences.",
    ],
}


def branch_nodes(name, y):
    prompt_id = f"prompt_{name}"
    llm_id = f"llm_{name}"
    return [
        {
            "id": prompt_id,
            "provider": "prompt",
            "config": {"instructions": BRANCHES[name], "parameters": {}},
            "input": [{"lane": "questions", "from": "chat_1"}],
            "ui": {"position": {"x": 240, "y": y}, "measured": {"width": 150, "height": 66}, "nodeType": "default"},
        },
        {
            "id": llm_id,
            "provider": "llm_openai_api",
            "config": LLM,
            "input": [{"lane": "questions", "from": prompt_id}],
            "ui": {"position": {"x": 440, "y": y}, "measured": {"width": 150, "height": 66}, "nodeType": "default"},
        },
    ]


components = [
    {
        "id": "chat_1",
        "provider": "chat",
        "config": {"hideForm": True, "mode": "Source", "parameters": {}, "type": "chat"},
        "ui": {"position": {"x": 20, "y": 200}, "measured": {"width": 150, "height": 66}, "nodeType": "default"},
    },
]
for i, name in enumerate(["graph", "reasons", "similar"]):
    components += branch_nodes(name, 80 + i * 170)

components.append({
    "id": "response_answers_1",
    "provider": "response_answers",
    "config": {"laneName": "answers"},
    "input": [
        {"lane": "answers", "from": "llm_graph"},
        {"lane": "answers", "from": "llm_reasons"},
        {"lane": "answers", "from": "llm_similar"},
    ],
    "ui": {"position": {"x": 660, "y": 250}, "measured": {"width": 150, "height": 66}, "nodeType": "default"},
})

pipe = {
    "components": components,
    "project_id": "d74fc30d-c130-431d-a5ae-17b61461d1fc",
    "viewport": {"x": 0, "y": 0, "zoom": 1},
    "version": 1,
}

out = Path(__file__).resolve().parent / "whystreet.pipe"
out.write_text(json.dumps(pipe, indent=2))
print("wrote", out, "|", len(components), "nodes")
