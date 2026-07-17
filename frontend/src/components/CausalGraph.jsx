import { useEffect, useMemo, useRef, useState } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { forceX, forceY, forceCollide } from 'd3-force-3d'

// Edge tiers (visual language learned from OttoTrade): confidence of the causal link.
const TIER = {
  direct: { color: '#22c55e', dash: [], label: 'Direct' },
  indirect: { color: '#f59e0b', dash: [5, 4], label: 'Indirect' },
  similar: { color: '#38bdf8', dash: [6, 4], label: 'Similar event' },
}
const NODE_COLOR = {
  event: '#f97316', entity: '#5aa9ff', sector: '#b98cff', stock: '#00d1b2',
}

export default function CausalGraph({ graph, onPickSource, onNodeSelect }) {
  const fgRef = useRef(null)
  const wrapRef = useRef(null)
  const [size, setSize] = useState({ w: 600, h: 380 })
  const [sel, setSel] = useState(null)

  const data = useMemo(() => {
    const nodes = (graph?.nodes || []).map((n) => ({ ...n }))
    const ids = new Set(nodes.map((n) => n.id))
    const links = (graph?.edges || [])
      .filter((e) => ids.has(e.from) && ids.has(e.to))
      .map((e) => ({ ...e, source: e.from, target: e.to }))
    return { nodes, links }
  }, [graph])

  useEffect(() => {
    if (!wrapRef.current) return
    const ro = new ResizeObserver((es) => {
      const r = es[0].contentRect
      setSize({ w: Math.max(320, r.width), h: Math.max(300, r.height) })
    })
    ro.observe(wrapRef.current)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    const fg = fgRef.current
    if (!fg) return
    fg.d3Force('charge')?.strength(-200)
    fg.d3Force('centerX', forceX(0).strength(0.03))
    fg.d3Force('centerY', forceY(0).strength(0.03))
    fg.d3Force('collide', forceCollide((n) => radius(n) + 10))
    const t = setTimeout(() => fg.zoomToFit(400, 50), 700)
    return () => clearTimeout(t)
  }, [data, size])

  const radius = (n) => (n.type === 'stock' ? 15 : 7)

  return (
    <div ref={wrapRef} className="cgraph">
      <ForceGraph2D
        ref={fgRef}
        width={size.w}
        height={size.h}
        graphData={data}
        backgroundColor="rgba(0,0,0,0)"
        cooldownTicks={120}
        onNodeClick={(n) => {
          const now = n.id === sel ? null : n.id
          setSel(now)
          onNodeSelect?.(now ? n : null)
          // In contexts without a side panel (the modal), fall back to opening the source.
          if (!onNodeSelect && n.source_url) onPickSource?.({ source_url: n.source_url, label: n.label })
        }}
        onBackgroundClick={() => { setSel(null); onNodeSelect?.(null) }}
        nodeLabel={(n) => (n.source_url ? `${n.label} — click for source` : n.label)}
        nodeCanvasObject={(node, ctx, scale) => {
          const r = radius(node)
          const pulse = 0.65 + 0.35 * Math.sin(Date.now() / 500)
          const col = NODE_COLOR[node.type] || '#8b949e'
          const isSel = node.id === sel
          ctx.save()
          ctx.shadowColor = col
          ctx.shadowBlur = ((node.type === 'stock' ? 16 : 12) + 8 * pulse) / scale
          ctx.beginPath()
          ctx.arc(node.x, node.y, r, 0, 2 * Math.PI)
          if (node.type === 'stock') {
            ctx.fillStyle = '#050506'; ctx.fill()
            ctx.lineWidth = 2.4 / scale; ctx.strokeStyle = isSel ? '#fff' : col; ctx.stroke()
          } else {
            ctx.fillStyle = col; ctx.globalAlpha = 0.85; ctx.fill(); ctx.globalAlpha = 1
            ctx.lineWidth = 1.4 / scale; ctx.strokeStyle = col; ctx.stroke()
          }
          ctx.restore()
          // labels: always for stock, on hover/select otherwise
          if (node.type === 'stock' || isSel) {
            const fs = (node.type === 'stock' ? 11 : 9.5) / scale
            ctx.font = `${node.type === 'stock' ? 700 : 500} ${fs}px Inter, sans-serif`
            ctx.textAlign = 'center'; ctx.textBaseline = node.type === 'stock' ? 'middle' : 'top'
            ctx.fillStyle = node.type === 'stock' ? '#f8fafc' : '#c9d1d9'
            const txt = node.type === 'stock' ? node.label : (node.label || '').slice(0, 28)
            ctx.fillText(txt, node.x, node.type === 'stock' ? node.y : node.y + r + 2 / scale)
          }
        }}
        nodePointerAreaPaint={(node, color, ctx) => {
          ctx.fillStyle = color
          ctx.beginPath(); ctx.arc(node.x, node.y, radius(node) + 3, 0, 2 * Math.PI); ctx.fill()
        }}
        linkCanvasObject={(link, ctx, scale) => {
          const s = link.source, t = link.target
          if (!s || s.x == null || t.x == null) return
          const tier = TIER[link.tier] || TIER.indirect
          const touches = sel && (s.id === sel || t.id === sel)
          ctx.save()
          ctx.globalAlpha = sel ? (touches ? 1 : 0.1) : 0.7
          ctx.strokeStyle = tier.color
          ctx.lineWidth = (0.8 + 2 * (link.confidence ?? 0.5)) / scale
          ctx.setLineDash(tier.dash.map((d) => d / scale))
          if (touches) { ctx.shadowColor = tier.color; ctx.shadowBlur = 6 / scale }
          ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(t.x, t.y); ctx.stroke()
          ctx.restore()
        }}
        linkDirectionalArrowLength={5}
        linkDirectionalArrowRelPos={1}
        linkDirectionalArrowColor={(l) => (TIER[l.tier] || TIER.indirect).color}
        linkDirectionalParticles={(l) => (sel && (l.source.id === sel || l.target.id === sel) ? 4 : 0)}
        linkDirectionalParticleWidth={2}
        onLinkClick={(l) => l.source_url && onPickSource?.(l)}
      />
      <div className="cgraph-legend">
        {Object.values(TIER).map((t) => (
          <span key={t.label}><i style={{ background: t.color, borderStyle: t.dash.length ? 'dashed' : 'solid' }} />{t.label}</span>
        ))}
        <span className="cgraph-hint">click node = focus · click link = source</span>
      </div>
    </div>
  )
}
