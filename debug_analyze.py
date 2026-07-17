"""Debug: run the exact analyze flow for one point and print the RAW LLM output."""
import ssl
_o = ssl.create_default_context
ssl.create_default_context = lambda *a, **k: (lambda c: (setattr(c, "check_hostname", False), setattr(c, "verify_mode", ssl.CERT_NONE), c)[2])(_o(*a, **k))

import asyncio, json
from backend.app import linkup_evidence, build_prompt, PIPE
from rocketride import RocketRideClient
from rocketride.schema import Question


async def main():
    ev = linkup_evidence("TSLA", "2024-04-24", "-3.4%")
    print("LINKUP answer chars:", len(ev.get("answer", "")), "| sources:", len(ev.get("sources", [])))
    prompt = build_prompt("TSLA", "2024-04-24", "-3.4%", ev)
    print("prompt chars:", len(prompt))

    c = RocketRideClient()
    await c.connect()
    pid = json.load(open(PIPE))["project_id"]
    try:
        t = await c.get_task_token(pid, "chat_1")
    except Exception:
        t = None
    if t:
        await c.terminate(t)
    r = await c.use(filepath=PIPE)
    q = Question(); q.addQuestion(prompt)
    resp = await c.chat(token=r["token"], question=q)
    raw = (resp.get("answers") or [""])[0]
    print("\n===== RAW LLM OUTPUT (first 900) =====")
    print(raw[:900])
    await c.disconnect()

asyncio.run(main())
