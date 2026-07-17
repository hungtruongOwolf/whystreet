"""Smoke test: connect to RocketRide Cloud, run whystreet.pipe, ask one
question, print the grounded answer. Run from the whystreet/ dir.

NOTE: This machine sits behind a Zscaler TLS-intercepting proxy whose CA cert
fails Python's strict verification. For LOCAL DEV TESTING ONLY we relax cert
verification for the websocket. Do NOT ship this; production runs on Cloud."""

import asyncio
import json
import ssl

_orig_ctx = ssl.create_default_context


def _unverified_ctx(*args, **kwargs):
    ctx = _orig_ctx(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


ssl.create_default_context = _unverified_ctx  # dev-only, Zscaler workaround

from rocketride import RocketRideClient  # noqa: E402
from rocketride.schema import Question  # noqa: E402


async def main() -> None:
    client = RocketRideClient()  # reads ROCKETRIDE_URI / ROCKETRIDE_APIKEY from .env
    try:
        await client.connect()
        print("✅ connected to RocketRide Cloud")

        # Clean up any previously running task for this pipeline (repeatable runs)
        pid = json.load(open("pipeline/whystreet.pipe"))["project_id"]
        try:
            existing = await client.get_task_token(pid, "chat_1")
        except Exception:
            existing = None
        if existing:
            print("terminating existing task:", existing)
            await client.terminate(existing)

        result = await client.use(filepath="pipeline/whystreet.pipe")
        token = result["token"]
        print("✅ pipeline started, token:", token)

        data = None
        for attempt in range(1, 4):  # retry: tool-calling is intermittent
            q = Question()
            q.addQuestion("ticker=NVDA date=2025-01-27 move=-16.97%. Explain why the stock moved.")
            print(f"… attempt {attempt}: asking (agent calls Linkup live)…")
            resp = await client.chat(token=token, question=q)
            raw = (resp.get("answers") or [""])[0]
            try:
                text = raw.strip()
                if text.startswith("```"):
                    text = text.split("```", 2)[1].lstrip("json").strip()
                d = json.loads(text)
            except Exception:
                print("   → not JSON:", raw[:100])
                continue
            if d.get("sources"):  # grounded → success
                data = d
                break
            print("   → empty/ungrounded (tool likely not called), retrying…")

        print("\n===== RESULT =====")
        if not data:
            print("failed to get a grounded result after retries")
        else:
            print("summary:", data.get("summary"))
            print("reasons:", len(data.get("reasons", [])))
            g = data.get("graph", {})
            print("graph nodes:", len(g.get("nodes", [])), "edges:", len(g.get("edges", [])))
            for e in g.get("edges", [])[:6]:
                print(f"  {e.get('from')} --{e.get('direction')}--> {e.get('to')}  [{(e.get('source_url') or '')[:50]}]")
            print("sources:", len(data.get("sources", [])))
    finally:
        await client.disconnect()
        print("\ndisconnected")


if __name__ == "__main__":
    asyncio.run(main())
