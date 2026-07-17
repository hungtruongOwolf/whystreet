const BASE = import.meta.env.VITE_API_BASE_URL || '/api'

// Calls the backend, which runs the RocketRide Cloud pipeline (agent + Linkup)
// and returns { cached, summary, reasons[], graph{nodes,edges}, sources[] }.
export async function analyzeMove({ ticker, date, return_pct, forceLive = false }) {
  const res = await fetch(`${BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker, date, return_pct, force_live: forceLive }),
  })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try { detail = (await res.json()).detail || detail } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json()
}

// The cumulative knowledge graph (grows with every analysis).
export async function getKnowledgeGraph() {
  const res = await fetch(`${BASE}/kg`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
