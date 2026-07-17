"""WhyStreet backend — FastAPI.

Flow (reliable, decomposed):
  1. Call Linkup for live grounded evidence (retrieval).
  2. Send the evidence to the RocketRide Cloud pipeline (chat -> LLM -> response),
     which REASONS over it and returns a grounded causal graph + cited reasons.
  3. Cache the result in Supabase (analysis_results).

Both technologies are core: Linkup = live cited grounding, RocketRide = the AI
reasoning pipeline. No agent tool-calling (unreliable on free models).

NOTE: behind a Zscaler proxy locally we relax TLS verification (dev-only):
RocketRide websocket via ssl monkeypatch, Linkup via requests(verify=False),
Supabase via direct Postgres. None of this affects the Cloud deployment.
"""

import ssl

_orig_ctx = ssl.create_default_context


def _unverified_ctx(*args, **kwargs):
    ctx = _orig_ctx(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


ssl.create_default_context = _unverified_ctx  # dev-only, Zscaler workaround

import asyncio  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402
from pathlib import Path  # noqa: E402

import psycopg2  # noqa: E402
import psycopg2.extras  # noqa: E402
import requests  # noqa: E402
import urllib3  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from rocketride import RocketRideClient  # noqa: E402
from rocketride.schema import Question  # noqa: E402

urllib3.disable_warnings()
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
PIPE = str(ROOT / "pipeline" / "whystreet.pipe")
LINKUP_PIPE = str(ROOT / "pipeline" / "whystreet-linkup.pipe")
SOURCE_ID = "chat_1"
LINKUP_KEY = os.environ["ROCKETRIDE_LINKUP_KEY"]
NEO4J_URI = os.getenv("ROCKETRIDE_NEO4J_URI")
NEO4J_USER = os.getenv("ROCKETRIDE_NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("ROCKETRIDE_NEO4J_PASSWORD")

state: dict = {"client": None, "token": None, "linkup_token": None,
               "neo4j": None, "lock": asyncio.Lock()}


# ---------- Supabase (direct Postgres; Zscaler-safe) ----------
def pg():
    return psycopg2.connect(os.environ["SUPABASE_DB_URL"], connect_timeout=10)


# ---------- Neo4j (the causal knowledge graph lives here) ----------
# The cumulative causal graph is a real graph DB: (:Event|:Entity|:Sector|:Stock)
# nodes joined by [:CAUSES] edges. The RocketRide pipeline reads it via the
# db_neo4j graph-RAG node (NL -> Cypher) to ground each new analysis in prior
# accumulated causality; the backend writes new nodes/edges here after each run.
def neo4j_driver():
    if not (NEO4J_URI and NEO4J_PASSWORD):
        return None
    if state.get("neo4j") is None:
        from neo4j import GraphDatabase
        state["neo4j"] = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return state["neo4j"]


def _node_label(typ: str) -> str:
    return {"event": "Event", "entity": "Entity", "sector": "Sector",
            "stock": "Stock"}.get((typ or "event").lower(), "Event")


def kg_upsert_neo4j(ticker: str, date: str, graph: dict) -> None:
    """MERGE this analysis's causal nodes/edges into Neo4j. Best-effort — the
    Supabase mirror (kg_upsert) is authoritative if Aura is not configured."""
    drv = neo4j_driver()
    if not drv:
        return
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    idmap = {}
    for n in nodes:
        typ = (n.get("type") or "event").lower()
        label = ticker if typ == "stock" else (n.get("label") or n.get("id") or "").strip()
        if label:
            idmap[n.get("id")] = (label[:120], typ, n.get("source_url"))
    with drv.session() as ses:
        for label, typ, src in idmap.values():
            ses.run(
                f"MERGE (n:KG {{name:$label}}) "
                f"SET n:{_node_label(typ)}, n.type=$typ, n.weight=coalesce(n.weight,0)+1, "
                f"n.source_url=coalesce($src, n.source_url), "
                f"n.event_date = CASE WHEN $date > coalesce(n.event_date,'') THEN $date ELSE n.event_date END, "
                f"n.updated_at=timestamp()",
                label=label, typ=typ, src=src, date=date)
        for e in edges:
            f = idmap.get(e.get("from"))
            t = idmap.get(e.get("to"))
            if not f or not t or f[0] == t[0]:
                continue
            ses.run(
                "MATCH (a:KG {name:$f}), (b:KG {name:$t}) "
                "MERGE (a)-[r:CAUSES {tier:$tier}]->(b) "
                "SET r.direction=$dir, r.confidence=$conf, "
                "r.source_url=coalesce($src, r.source_url), "
                "r.weight=coalesce(r.weight,0)+1, r.updated_at=timestamp()",
                f=f[0], t=t[0], tier=(e.get("tier") or "indirect"),
                dir=e.get("direction"), conf=e.get("confidence") or 0.5,
                src=e.get("source_url"))


def kg_read_neo4j() -> dict | None:
    """Read the whole cumulative graph from Neo4j (for /api/kg). None if unavailable."""
    drv = neo4j_driver()
    if not drv:
        return None
    try:
        with drv.session() as ses:
            nrows = ses.run(
                "MATCH (n:KG) RETURN n.name AS label, n.type AS type, "
                "n.weight AS weight, n.source_url AS source_url, n.event_date AS date").data()
            erows = ses.run(
                "MATCH (a:KG)-[r:CAUSES]->(b:KG) RETURN a.name AS f, b.name AS t, "
                "r.tier AS tier, r.direction AS direction, r.confidence AS confidence, "
                "r.source_url AS source_url, r.weight AS weight").data()
        nodes = [{"id": r["label"], "label": r["label"], "type": r["type"],
                  "weight": r["weight"] or 1, "source_url": r["source_url"], "date": r["date"]}
                 for r in nrows]
        edges = [{"from": r["f"], "to": r["t"], "tier": r["tier"], "direction": r["direction"],
                  "confidence": float(r["confidence"] or 0.5), "source_url": r["source_url"],
                  "weight": r["weight"] or 1} for r in erows]
        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        print("neo4j read failed, falling back to Supabase:", e)
        return None


def neo4j_priors(ticker: str, limit: int = 12) -> str:
    """Graph-RAG READ: multi-hop Cypher over the accumulated causal graph — what
    has historically driven THIS ticker. Returns a compact text block to ground
    the new analysis in prior causality (empty string if none / unavailable)."""
    drv = neo4j_driver()
    if not drv:
        return ""
    try:
        with drv.session() as ses:
            rows = ses.run(
                "MATCH (cause:KG)-[:CAUSES*1..3]->(s:Stock {name:$ticker}) "
                "WHERE cause.name <> $ticker "
                "RETURN DISTINCT cause.name AS name, cause.type AS type, "
                "cause.event_date AS date ORDER BY date DESC LIMIT $limit",
                ticker=ticker, limit=limit).data()
        if not rows:
            return ""
        lines = [f"- {r['name']} ({r['type']}{', ' + r['date'] if r.get('date') else ''})"
                 for r in rows]
        return "\n".join(lines)
    except Exception as e:
        print("neo4j_priors failed:", e)
        return ""


def init_db() -> None:
    conn = pg()
    with conn, conn.cursor() as cur:
        cur.execute("alter table analysis_results add column if not exists summary text")
        cur.execute("alter table analysis_results add column if not exists explanation text")
        cur.execute("alter table analysis_results add column if not exists scores jsonb")
        cur.execute("alter table analysis_results add column if not exists similar_events jsonb")
        # Cumulative knowledge graph: nodes/edges accumulate across every analysis,
        # deduped by label so the same entity (a sector, a macro event, a ticker)
        # becomes ONE node that cross-links analyses.
        cur.execute(
            "create table if not exists kg_nodes ("
            "label text primary key, type text, weight int default 1, "
            "updated_at timestamptz default now())")
        cur.execute("alter table kg_nodes add column if not exists source_url text")
        cur.execute("alter table kg_nodes add column if not exists event_date text")
        cur.execute(
            "create table if not exists kg_edges ("
            "from_label text, to_label text, tier text, direction text, "
            "confidence numeric, source_url text, weight int default 1, "
            "updated_at timestamptz default now(), "
            "primary key (from_label, to_label, tier))")
    conn.close()


def kg_upsert(ticker: str, date: str, graph: dict) -> None:
    """Merge this analysis's nodes/edges into the cumulative knowledge graph,
    keyed by label so shared entities across analyses become one node. Each node
    keeps a representative source_url + the event_date it was last seen on, so the
    KG view can show "what & when" per node."""
    nodes = graph.get("nodes", []) or []
    edges = graph.get("edges", []) or []
    # local node id -> (canonical label, type, source_url); stock nodes canonicalize to the ticker
    idmap = {}
    for n in nodes:
        typ = n.get("type") or "event"
        label = ticker if typ == "stock" else (n.get("label") or n.get("id") or "").strip()
        if label:
            idmap[n.get("id")] = (label[:120], typ, n.get("source_url"))
    conn = pg()
    try:
        with conn, conn.cursor() as cur:
            for label, typ, src in idmap.values():
                cur.execute(
                    "insert into kg_nodes (label, type, weight, source_url, event_date) values (%s,%s,1,%s,%s) "
                    "on conflict (label) do update set weight = kg_nodes.weight + 1, "
                    "type = excluded.type, "
                    "source_url = coalesce(excluded.source_url, kg_nodes.source_url), "
                    "event_date = greatest(coalesce(excluded.event_date,''), coalesce(kg_nodes.event_date,'')), "
                    "updated_at = now()", (label, typ, src, date))
            for e in edges:
                f = idmap.get(e.get("from"))
                t = idmap.get(e.get("to"))
                if not f or not t or f[0] == t[0]:
                    continue
                cur.execute(
                    "insert into kg_edges (from_label, to_label, tier, direction, confidence, source_url, weight) "
                    "values (%s,%s,%s,%s,%s,%s,1) "
                    "on conflict (from_label, to_label, tier) do update set "
                    "weight = kg_edges.weight + 1, "
                    "confidence = greatest(coalesce(kg_edges.confidence,0), coalesce(excluded.confidence,0)), "
                    "source_url = coalesce(excluded.source_url, kg_edges.source_url), updated_at = now()",
                    (f[0], t[0], e.get("tier") or "indirect", e.get("direction"),
                     e.get("confidence") or 0.5, e.get("source_url")))
    finally:
        conn.close()


def get_cache(ticker: str, date: str):
    conn = pg()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "select summary, explanation, reasons, graph, scores, similar_events as similar, sources, generated_at "
            "from analysis_results where ticker=%s and date=%s", (ticker, date))
        row = cur.fetchone()
    conn.close()
    return row


def save_cache(ticker: str, date: str, data: dict) -> None:
    conn = pg()
    with conn, conn.cursor() as cur:
        cur.execute(
            "insert into analysis_results (ticker, date, summary, explanation, reasons, graph, scores, similar_events, sources, is_live_run) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,true) "
            "on conflict (ticker, date) do update set summary=excluded.summary, explanation=excluded.explanation, "
            "reasons=excluded.reasons, graph=excluded.graph, scores=excluded.scores, "
            "similar_events=excluded.similar_events, sources=excluded.sources, "
            "is_live_run=excluded.is_live_run, generated_at=now()",
            (ticker, date, data.get("summary"), data.get("explanation"),
             json.dumps(data.get("reasons", [])), json.dumps(data.get("graph", {})),
             json.dumps(data.get("scores", {})), json.dumps(data.get("similar", [])),
             data.get("sources", [])))
    conn.close()


# ---------- Linkup (retrieval) ----------
def _linkup_search(q: str, from_date: str | None = None, to_date: str | None = None,
                   max_results: int = 6) -> dict:
    """One date-scoped Linkup search. fromDate/toDate constrain PUBLICATION date
    server-side — the reliable lever for time-accuracy (source objects carry no
    date field of their own)."""
    payload = {"q": q, "depth": "standard", "maxResults": max_results, "outputType": "sourcedAnswer"}
    if from_date and to_date:
        payload["fromDate"] = from_date
        payload["toDate"] = to_date
    r = requests.post(
        "https://api.linkup.so/v1/search",
        headers={"Authorization": f"Bearer {LINKUP_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=60, verify=False,
    )
    r.raise_for_status()
    return r.json()


def linkup_evidence(ticker: str, date: str, move: str) -> dict:
    """Market-analyst retrieval flow. A move's cause is rarely confined to the
    move's own day: the TRIGGER often lands a session or two earlier (earnings
    print after the close → gap the next day), and the ROOT CAUSE usually builds
    over the preceding weeks (policy proposals/leaks, export rules, competitor or
    supplier signals, prior guidance, macro/rate shifts, a building sector
    narrative). So retrieve in TWO time layers and let the pipeline separate the
    proximate trigger from the earlier build-up when it assembles the chain."""
    try:
        d = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        d = None
    when = d.strftime("%B %Y") if d else date

    def win(days):
        return (d + timedelta(days=days)).strftime("%Y-%m-%d") if d else None

    # Layer 1 — TRIGGER: the proximate catalyst on / just before the move.
    trig = _linkup_search(
        f"What specific catalyst TRIGGERED {ticker} stock's {move} move on or just before "
        f"{date} ({when})? A single earnings report, product or news announcement, data "
        f"release, analyst rating action, or headline. Name the exact event and its date.",
        win(-7), win(2))

    # Layer 2 — BUILD-UP: precursor developments in the weeks BEFORE that primed it.
    build = None
    if d:
        build = _linkup_search(
            f"In the roughly six weeks BEFORE {date} ({when}), what EARLIER developments set "
            f"the stage for {ticker}'s {move} move? Tariff or policy proposals and leaks, "
            f"export controls, regulatory actions, competitor or supplier events, prior "
            f"company guidance, macro or interest-rate shifts, or a building sector "
            f"narrative. Name the dated precursor events; do NOT restrict to the move's own day.",
            win(-45), win(-3))

    # Merge: dedupe sources by URL, tag each with the layer it came from so the
    # reasoning model knows which evidence is proximate vs precursor.
    seen: set = set()
    sources: list = []
    for layer, res in (("trigger", trig), ("buildup", build)):
        if not res:
            continue
        for s in (res.get("sources") or []):
            u = s.get("url")
            if u and u not in seen:
                seen.add(u)
                sources.append({**s, "layer": layer})
    trig_ans = (trig or {}).get("answer", "") or ""
    build_ans = (build or {}).get("answer", "") if build else ""
    return {
        "answer_trigger": trig_ans,
        "answer_buildup": build_ans,
        "answer": (trig_ans + "\n" + build_ans).strip(),  # kept for back-compat
        "sources": sources,
    }


def build_evidence_message(ticker: str, date: str, move: str, ev: dict, vol: float | None) -> str:
    """The shared message fanned to all 3 pipeline branches. Branch-specific
    instructions live in the pipeline's prompt nodes; this carries the context
    + live Linkup evidence they all reason over."""
    sources = ev.get("sources", [])[:8]
    src_lines = "\n".join(
        f"{i+1}. [{s.get('layer','')}] {s.get('name','')} — {s.get('url','')}\n   {(s.get('snippet','') or '')[:280]}"
        for i, s in enumerate(sources))
    vol_line = (f"This stock's own daily volatility (1 sigma) is {vol:.2f}%. "
                f"Judge the {move} move relative to that.\n" if vol else "")
    trig = ev.get("answer_trigger", "") or ev.get("answer", "")
    build = ev.get("answer_buildup", "")
    # Graph-RAG grounding is OFF by default: with a weak free model it can bleed a
    # prior event into the current summary. Flip GRAPHRAG_PRIORS=on to A/B it once
    # a strong model / stable RocketRide is available. The Neo4j graph store,
    # /api/kg, and multi-hop queries are unaffected and always on.
    priors = neo4j_priors(ticker) if os.getenv("GRAPHRAG_PRIORS", "off").lower() == "on" else ""
    priors_block = (
        f"\n\n---\nKNOWN RELATED ENTITIES from the Neo4j causal graph (past drivers of {ticker} "
        f"in EARLIER, unrelated analyses). These are NOT the cause of the {date} move and MUST "
        f"NOT be described or summarized. Use them ONLY to keep entity/sector NAMES consistent "
        f"if the SAME driver genuinely appears in the live evidence above:\n{priors}"
        if priors else "")
    return (
        f"ANALYZE THIS MOVE — and ONLY this move: {ticker} on {date}, {move}.\n{vol_line}\n"
        f"EVIDENCE (retrieved live from Linkup — use ONLY this, never outside knowledge).\n"
        f"News explaining a move is NOT confined to the move's own day: the TRIGGER can land "
        f"a day or two before, and the ROOT CAUSE often builds over the prior weeks. Two "
        f"retrieval layers are given — use the BUILD-UP for root/early causes and the TRIGGER "
        f"for the proximate catalyst when you assemble the causal chain.\n\n"
        f"— PROXIMATE TRIGGER (around {date}):\n{trig}\n\n"
        f"— EARLIER BUILD-UP (weeks before {date}):\n{build or '(none surfaced)'}\n\n"
        f"SOURCES (each tagged [trigger] or [buildup]):\n{src_lines}"
        f"{priors_block}"
    )


def stock_volatility(ticker: str):
    """Approx daily volatility (%) from stored price_bars — for move-in-context."""
    try:
        conn = pg()
        with conn.cursor() as cur:
            cur.execute("select close from price_bars where ticker=%s order by date desc limit 120", (ticker,))
            closes = [float(r[0]) for r in cur.fetchall()][::-1]
        conn.close()
        if len(closes) < 20:
            return None
        rets = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        return (var ** 0.5) * 100
    except Exception:
        return None


def build_graph_from_chain(chain, ticker: str, move: str) -> dict:
    """Deterministically assemble a well-formed graph from a flat list of causal
    steps. This guarantees consistent ids, exactly one stock node, no dangling
    edges and no duplicates — things the LLM gets wrong when asked for a graph."""
    nodes: dict = {}
    order: list = []

    def add(label, typ, src, is_stock=False):
        if is_stock:
            label, typ = f"{ticker} {move}", "stock"
        label = (label or "").strip()[:70]
        if not label:
            return None
        if label not in nodes:
            nodes[label] = {"id": f"n{len(order)}", "type": typ or "event",
                            "label": label, "source_url": None if is_stock else src}
            order.append(label)
        elif not is_stock and src and not nodes[label].get("source_url"):
            nodes[label]["source_url"] = src
        return nodes[label]["id"]

    edges = []
    for s in (chain or []):
        if not isinstance(s, dict):
            continue
        src = s.get("source_url")
        c = add(s.get("cause"), s.get("cause_type"), src)
        e = add(s.get("effect"), s.get("effect_type"), src, is_stock=(s.get("effect_type") == "stock"))
        if not c or not e or c == e:
            continue
        edges.append({
            "from": c, "to": e,
            "tier": "direct" if s.get("strength") == "direct" else "indirect",
            "direction": "up" if s.get("polarity") == "up" else "down",
            "rationale": (s.get("relation") or "")[:90],
            "source_url": src, "confidence": 0.7,
        })
    return {"nodes": [nodes[lbl] for lbl in order], "edges": edges}


def _domain(u: str) -> str:
    try:
        return (u or "").split("//", 1)[-1].split("/", 1)[0].replace("www.", "")
    except Exception:
        return ""


def validate_sources(data: dict, ev: dict) -> dict:
    """Every source_url the LLM emits MUST be one Linkup actually returned. This
    kills hallucinated / mangled / wrong links. Slightly-off URLs are repaired to
    the real one by domain; anything else is nulled (nodes/edges) or dropped
    (reasons/similar keep only truly-cited items)."""
    valid = [s.get("url") for s in ev.get("sources", []) if s.get("url")]
    valid_set = set(valid)
    by_domain: dict = {}
    for u in valid:
        by_domain.setdefault(_domain(u), u)

    def fix(u):
        if not u:
            return None
        if u in valid_set:
            return u
        return by_domain.get(_domain(u))  # repair by domain, else None

    data["reasons"] = [dict(r, source_url=fix(r.get("source_url")))
                       for r in data.get("reasons", []) if fix(r.get("source_url"))]
    data["similar"] = [dict(s, source_url=fix(s.get("source_url")))
                       for s in data.get("similar", []) if fix(s.get("source_url"))]
    g = data.get("graph", {}) or {}
    for n in g.get("nodes", []):
        n["source_url"] = fix(n.get("source_url"))
    for e in g.get("edges", []):
        e["source_url"] = fix(e.get("source_url"))
    return data


def merge_branches(answers: list[str], ev: dict, ticker: str, move: str) -> dict:
    merged = {"summary": "", "explanation": "", "reasons": [], "graph": {"nodes": [], "edges": []},
              "scores": {}, "similar": [], "sources": []}
    for raw in answers:
        try:
            d = parse_answer(raw)
        except Exception:
            continue
        b = d.get("branch")
        if b == "graph" or "chain" in d or ("graph" in d and "branch" not in d):
            if isinstance(d.get("chain"), list):
                merged["graph"] = build_graph_from_chain(d["chain"], ticker, move)
            elif d.get("graph"):
                merged["graph"] = d["graph"]
        elif b == "reasons" or ("reasons" in d and "branch" not in d):
            merged["summary"] = d.get("summary") or merged["summary"]
            merged["explanation"] = d.get("explanation") or merged["explanation"]
            merged["reasons"] = d.get("reasons", merged["reasons"])
            merged["scores"] = d.get("scores", merged["scores"])
        elif b == "similar" or ("similar" in d and "branch" not in d):
            merged["similar"] = d.get("similar", merged["similar"])
    merged["sources"] = [s.get("url") for s in ev.get("sources", []) if s.get("url")]
    return merged


def parse_answer(raw: str) -> dict:
    t = (raw or "").strip()
    if t.startswith("```"):
        t = t[3:]
        if t[:4].lower() == "json":
            t = t[4:]
        if t.endswith("```"):
            t = t[:-3]
    # tolerate leading/trailing prose around the JSON
    i, j = t.find("{"), t.rfind("}")
    if i != -1 and j != -1:
        t = t[i:j + 1]
    return json.loads(t)


# ---------- RocketRide pipeline lifecycle ----------
async def start_pipe(client, path):
    """Start a pipeline, terminating any stale task for its project first."""
    pid = json.load(open(path))["project_id"]
    try:
        existing = await client.get_task_token(pid, SOURCE_ID)
    except Exception:
        existing = None
    if existing:
        await client.terminate(existing)
    return (await client.use(filepath=path))["token"]


async def reconnect():
    """Re-establish the RocketRide websocket + restart the pipelines after the
    connection drops (idle timeout leaves client._transport = None → chat 500s)."""
    try:
        client = RocketRideClient()
        await client.connect()
        state["client"] = client
        state["token"] = await start_pipe(client, PIPE)
        try:
            state["linkup_token"] = await start_pipe(client, LINKUP_PIPE)
        except Exception:
            state["linkup_token"] = None
        print("RocketRide reconnected:", state["token"])
    except Exception as e:
        print("reconnect failed:", e)
        raise


async def pipe_chat(token_key: str, question):
    """chat() with one transparent reconnect-and-retry on a dropped connection."""
    try:
        return await state["client"].chat(token=state[token_key], question=question)
    except Exception as e:
        print("pipe chat failed, reconnecting and retrying once:", e)
        await reconnect()
        return await state["client"].chat(token=state[token_key], question=question)


async def linkup_via_rocketride(ticker: str, date: str, move: str):
    """Get Linkup evidence THROUGH the RocketRide agent pipeline (agent actively
    calls Linkup). Returns the evidence dict, or None if the agent declined."""
    if not state.get("linkup_token"):
        return None
    try:
        async with state["lock"]:
            q = Question()
            q.addQuestion(f"ticker={ticker} date={date} move={move}")
            resp = await pipe_chat("linkup_token", q)
        d = parse_answer((resp.get("answers") or [""])[0])
        if d.get("sources"):
            print("Linkup evidence via RocketRide agent ✓")
            return d
    except Exception as e:
        print("linkup-via-rocketride failed, will fall back:", e)
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    client = RocketRideClient()
    await client.connect()
    state["client"] = client
    state["token"] = await start_pipe(client, PIPE)
    print("WhyStreet reasoning pipeline ready:", state["token"])
    try:
        state["linkup_token"] = await start_pipe(client, LINKUP_PIPE)
        print("WhyStreet Linkup pipeline ready:", state["linkup_token"])
    except Exception as e:
        print("Linkup pipeline unavailable (will use direct fallback):", e)
        state["linkup_token"] = None
    yield
    for tk in (state.get("token"), state.get("linkup_token")):
        try:
            if tk:
                await client.terminate(tk)
        except Exception:
            pass
    await client.disconnect()


app = FastAPI(title="WhyStreet API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class AnalyzeReq(BaseModel):
    ticker: str
    date: str
    return_pct: float | None = None
    force_live: bool = False


@app.get("/api/health")
async def health():
    return {"ok": True, "token": state["token"]}


@app.get("/api/kg")
async def knowledge_graph():
    """The cumulative causal knowledge graph across every analysis run. Served
    from Neo4j (the real graph DB) when configured; Supabase mirror otherwise."""
    g = kg_read_neo4j()
    if g is not None:
        return g
    conn = pg()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("select label, type, weight, source_url, event_date from kg_nodes")
        nodes = [{"id": r["label"], "label": r["label"], "type": r["type"], "weight": r["weight"],
                  "source_url": r["source_url"], "date": r["event_date"]}
                 for r in cur.fetchall()]
        cur.execute("select from_label, to_label, tier, direction, confidence, source_url, weight from kg_edges")
        edges = [{"from": r["from_label"], "to": r["to_label"], "tier": r["tier"],
                  "direction": r["direction"], "confidence": float(r["confidence"] or 0.5),
                  "source_url": r["source_url"], "weight": r["weight"]} for r in cur.fetchall()]
    conn.close()
    return {"nodes": nodes, "edges": edges}


@app.post("/api/analyze")
async def analyze(req: AnalyzeReq):
    if not req.force_live:
        row = get_cache(req.ticker, req.date)
        if row:
            return {"cached": True, **row}

    move = f"{req.return_pct}%" if req.return_pct is not None else "significantly"

    # 1) live grounded evidence. Direct Linkup is primary (fast + reliable);
    #    the dedicated RocketRide Linkup-agent pipeline is deployed and used only
    #    as a fallback (its 8b tool-calling is flaky and adds latency otherwise).
    ev = None
    try:
        ev = linkup_evidence(req.ticker, req.date, move)
    except Exception as e:
        print("direct linkup failed, trying agent pipeline:", e)
    if not ev or not ev.get("sources"):
        ev = await linkup_via_rocketride(req.ticker, req.date, move) or ev
    if not ev:
        raise HTTPException(status_code=502, detail="Linkup returned no evidence")

    # 2) RocketRide PARALLEL pipeline: 3 branches reason over the same evidence
    vol = stock_volatility(req.ticker)
    msg = build_evidence_message(req.ticker, req.date, move, ev, vol)
    async with state["lock"]:
        q = Question()
        q.addQuestion(msg)
        resp = await pipe_chat("token", q)
    answers = resp.get("answers") or []
    if not answers:
        raise HTTPException(status_code=502, detail="Pipeline returned no answers")

    data = merge_branches(answers, ev, req.ticker, move)
    data = validate_sources(data, ev)  # only real Linkup URLs survive
    if not data["graph"]["nodes"] and not data["reasons"]:
        raise HTTPException(status_code=502, detail="Pipeline produced no grounded output (LLM likely rate-limited)")

    save_cache(req.ticker, req.date, data)
    try:
        kg_upsert(req.ticker, req.date, data.get("graph", {}))
        try:
            kg_upsert_neo4j(req.ticker, req.date, data.get("graph", {}))
        except Exception as e:
            print("kg_upsert_neo4j failed:", e)
    except Exception as e:
        print("kg_upsert failed:", e)
    return {"cached": False, **data}
