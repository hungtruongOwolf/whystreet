"""Generate whystreet-linkup.pipe — a RocketRide agent pipeline whose ONLY job
is to call the Linkup API via the http_request tool and return the raw result.

This puts Linkup genuinely INSIDE a RocketRide pipeline (agent actively calls
Linkup — the HWS requirement, visible in the canvas). The task is deliberately
minimal (one tool call, return raw) to maximize tool-calling reliability; the
backend falls back to a direct Linkup call if the agent ever declines the tool.
"""

import json
from pathlib import Path

instructions = [
    "You are a retrieval bot. Your ONLY job is to call the http_request tool exactly once and return its raw result. Do not analyze, summarize, or add anything.",
    "The user message contains a ticker, a date, and a % move.",
    "Call http_request: method POST, url https://api.linkup.so/v1/search, headers "
    "{\"Authorization\": \"Bearer ${ROCKETRIDE_LINKUP_KEY}\", \"Content-Type\": \"application/json\"}, "
    "body {\"q\": \"Why did <TICKER> stock move <MOVE>% around <DATE>? Explain the causal chain from root "
    "cause through sector/competitors to <TICKER>, and any similar past events.\", \"depth\": \"standard\", "
    "\"maxResults\": 4, \"outputType\": \"sourcedAnswer\"} — substitute the real <TICKER>/<MOVE>/<DATE>.",
    "Return the tool's JSON response verbatim as your answer (it has 'answer' and 'sources'). Output ONLY that JSON, nothing else.",
]

pipe = {
    "components": [
        {
            "id": "chat_1", "provider": "chat",
            "config": {"hideForm": True, "mode": "Source", "parameters": {}, "type": "chat"},
            "ui": {"position": {"x": 20, "y": 200}, "measured": {"width": 150, "height": 66}, "nodeType": "default"},
        },
        {
            "id": "agent_rocketride_1", "provider": "agent_rocketride",
            "config": {"max_waves": 3, "parameters": {}, "instructions": instructions},
            "input": [{"lane": "questions", "from": "chat_1"}],
            "ui": {"position": {"x": 240, "y": 200}, "measured": {"width": 150, "height": 86}, "nodeType": "default"},
        },
        {
            "id": "llm_openai_api_1", "provider": "llm_openai_api",
            "config": {"profile": "custom", "custom": {
                "apikey": "${ROCKETRIDE_LLM_KEY}", "base_url": "${ROCKETRIDE_LLM_BASE_URL}",
                "model": "${ROCKETRIDE_LLM_MODEL}", "modelTotalTokens": 32768}, "parameters": {}},
            "control": [{"classType": "llm", "from": "agent_rocketride_1"}],
            "ui": {"position": {"x": 150, "y": 380}, "measured": {"width": 150, "height": 66}, "nodeType": "default"},
        },
        {
            "id": "memory_internal_1", "provider": "memory_internal",
            "config": {"type": "memory_internal"},
            "control": [{"classType": "memory", "from": "agent_rocketride_1"}],
            "ui": {"position": {"x": 320, "y": 380}, "measured": {"width": 150, "height": 66}, "nodeType": "default"},
        },
        {
            "id": "tool_http_request_1", "provider": "tool_http_request",
            "config": {"type": "tool_http_request", "urlWhitelist": ["https://api.linkup.so"], "allowPOST": True, "allowGET": True},
            "control": [{"classType": "tool", "from": "agent_rocketride_1"}],
            "ui": {"position": {"x": 490, "y": 380}, "measured": {"width": 150, "height": 40}, "nodeType": "default"},
        },
        {
            "id": "response_answers_1", "provider": "response_answers",
            "config": {"laneName": "answers"},
            "input": [{"lane": "answers", "from": "agent_rocketride_1"}],
            "ui": {"position": {"x": 460, "y": 200}, "measured": {"width": 150, "height": 66}, "nodeType": "default"},
        },
    ],
    "project_id": "b21c7a55-6e44-4a1b-9c2e-1f0a5d3e7c88",
    "viewport": {"x": 0, "y": 0, "zoom": 1},
    "version": 1,
}

out = Path(__file__).resolve().parent / "whystreet-linkup.pipe"
out.write_text(json.dumps(pipe, indent=2))
print("wrote", out)
