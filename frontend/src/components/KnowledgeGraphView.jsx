import { useEffect, useMemo, useState } from 'react'
import { RefreshCw, ExternalLink, Calendar, Layers, X } from 'lucide-react'
import CausalGraph from './CausalGraph'
import { getKnowledgeGraph } from '../lib/analyze'

const TYPE_LABEL = { event: 'Event', entity: 'Entity', sector: 'Sector', stock: 'Stock' }

function hostOf(url) {
  try { return new URL(url).hostname.replace('www.', '') } catch { return url }
}
function fmtDate(d) {
  if (!d) return null
  try { return new Date(d).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) }
  catch { return d }
}

// The cumulative graph — grows with every analysis, filterable per stock.
export default function KnowledgeGraphView() {
  const [graph, setGraph] = useState({ nodes: [], edges: [] })
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [focus, setFocus] = useState('all')
  const [picked, setPicked] = useState(null)

  const load = () => {
    setLoading(true)
    setErr(null)
    getKnowledgeGraph()
      .then((g) => setGraph({ nodes: g.nodes || [], edges: g.edges || [] }))
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }
  useEffect(load, [])

  // Stock tickers present in the graph, for the filter.
  const stockNodes = useMemo(
    () => graph.nodes.filter((n) => n.type === 'stock').map((n) => n.id).sort(),
    [graph],
  )

  // When a stock is focused, show only its subgraph (the stock + everything it
  // connects to, plus links among those neighbours).
  const shown = useMemo(() => {
    if (focus === 'all') return graph
    const ids = new Set([focus])
    graph.edges.forEach((e) => { if (e.from === focus || e.to === focus) { ids.add(e.from); ids.add(e.to) } })
    const nodes = graph.nodes.filter((n) => ids.has(n.id))
    const edges = graph.edges.filter((e) => ids.has(e.from) && ids.has(e.to))
    return { nodes, edges }
  }, [graph, focus])

  // Neighbours + a representative source for the picked node.
  const detail = useMemo(() => {
    if (!picked) return null
    const links = graph.edges.filter((e) => e.from === picked.id || e.to === picked.id)
    const neighbours = [...new Set(links.map((e) => (e.from === picked.id ? e.to : e.from)))]
    const src = picked.source_url || links.map((e) => e.source_url).find(Boolean) || null
    return { neighbours, src, count: links.length }
  }, [picked, graph])

  return (
    <div className="kg-view">
      <div className="kg-head">
        <div>
          <h2>Knowledge Graph</h2>
          <p className="muted">
            Every analysis feeds this web — shared events &amp; sectors link stocks together.{' '}
            {shown.nodes.length} nodes · {shown.edges.length} links
            {focus !== 'all' && <> · focused on <b>{focus}</b></>}
          </p>
        </div>
        <div className="kg-controls">
          <select value={focus} onChange={(e) => { setFocus(e.target.value); setPicked(null) }} className="ticker-select">
            <option value="all">All stocks</option>
            {stockNodes.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <button className="link-btn" onClick={load}><RefreshCw size={13} /> refresh</button>
        </div>
      </div>
      {err && <div className="error">⚠ {err}</div>}
      {loading ? (
        <div className="kg-empty"><div className="spinner" /></div>
      ) : graph.nodes.length === 0 ? (
        <div className="kg-empty">
          <p className="hint">
            Empty so far. Analyze a few price moves (<b>Explain why →</b>) and they accumulate here
            into a growing web — the more you explore, the more cross-connections appear.
          </p>
        </div>
      ) : (
        <div className="kg-body">
          <div className="kg-canvas">
            <CausalGraph
              key={focus}
              graph={shown}
              onNodeSelect={setPicked}
            />
          </div>
          <aside className={`kg-detail ${picked ? 'open' : ''}`}>
            {picked ? (
              <>
                <div className="kg-detail-head">
                  <span className={`node-type ${picked.type}`}>{TYPE_LABEL[picked.type] || picked.type}</span>
                  <button className="close-sm" onClick={() => setPicked(null)}><X size={15} /></button>
                </div>
                <h3>{picked.label}</h3>
                <div className="kg-detail-meta">
                  {picked.date && <span><Calendar size={13} /> {fmtDate(picked.date)}</span>}
                  <span><Layers size={13} /> seen in {picked.weight || 1} analys{(picked.weight || 1) > 1 ? 'es' : 'is'}</span>
                </div>
                {detail?.src ? (
                  <a className="kg-src-btn" href={detail.src} target="_blank" rel="noreferrer">
                    <ExternalLink size={14} /> Open related news · {hostOf(detail.src)}
                  </a>
                ) : (
                  <p className="hint sm">No source link stored for this node.</p>
                )}
                {detail?.neighbours?.length > 0 && (
                  <div className="kg-neighbours">
                    <h4>Connected to ({detail.count})</h4>
                    <ul>
                      {detail.neighbours.slice(0, 10).map((nb) => (
                        <li key={nb} onClick={() => {
                          const node = graph.nodes.find((n) => n.id === nb)
                          if (node) setPicked(node)
                        }}>{nb}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            ) : (
              <div className="kg-detail-empty">
                <p className="hint">
                  Click any <b>node</b> to see what it is, <b>when</b> it happened, its related
                  news link, and everything it connects to.
                </p>
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  )
}
