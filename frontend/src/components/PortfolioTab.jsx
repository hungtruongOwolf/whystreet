import { useEffect, useState } from 'react'
import { TrendingUp, TrendingDown, LineChart, X, ArrowRight } from 'lucide-react'
import { getLatestPrice, getLatestAnomaly } from '../lib/api'

const KEY = 'whystreet.portfolio'
const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || [] } catch { return [] } }
const save = (h) => localStorage.setItem(KEY, JSON.stringify(h))

export default function PortfolioTab({ stocks, onExplore, onAnalyze }) {
  const [holdings, setHoldings] = useState(load)
  const [prices, setPrices] = useState({})
  const [moves, setMoves] = useState({})
  const [form, setForm] = useState({ ticker: stocks[0]?.ticker || 'NVDA', shares: '', cost: '' })

  useEffect(() => { save(holdings) }, [holdings])

  useEffect(() => {
    let cancelled = false
    Promise.all(holdings.map((h) => getLatestPrice(h.ticker).then((p) => [h.ticker, p?.close])))
      .then((pairs) => { if (!cancelled) setPrices(Object.fromEntries(pairs)) })
    Promise.all(holdings.map((h) => getLatestAnomaly(h.ticker).then((a) => [h.ticker, a]).catch(() => [h.ticker, null])))
      .then((pairs) => { if (!cancelled) setMoves(Object.fromEntries(pairs)) })
    return () => { cancelled = true }
  }, [holdings])

  const addHolding = (e) => {
    e.preventDefault()
    const shares = parseFloat(form.shares)
    const cost = parseFloat(form.cost)
    if (!form.ticker || !(shares > 0)) return
    setHoldings((h) => {
      const rest = h.filter((x) => x.ticker !== form.ticker)
      return [...rest, { ticker: form.ticker, shares, cost: cost > 0 ? cost : null }]
    })
    setForm((f) => ({ ...f, shares: '', cost: '' }))
  }

  const remove = (t) => setHoldings((h) => h.filter((x) => x.ticker !== t))

  const rows = holdings.map((h) => {
    const price = prices[h.ticker]
    const value = price != null ? price * h.shares : null
    const plPct = h.cost && price != null ? ((price - h.cost) / h.cost) * 100 : null
    return { ...h, price, value, plPct }
  })
  const total = rows.reduce((s, r) => s + (r.value || 0), 0)

  return (
    <div className="pf">
      <div className="pf-head">
        <div>
          <h2>Portfolio</h2>
          <p className="muted">Your holdings · total value <b>${total.toLocaleString(undefined, { maximumFractionDigits: 0 })}</b></p>
        </div>
      </div>

      <form className="pf-form" onSubmit={addHolding}>
        <select value={form.ticker} onChange={(e) => setForm({ ...form, ticker: e.target.value })}>
          {stocks.map((s) => <option key={s.ticker} value={s.ticker}>{s.ticker}</option>)}
        </select>
        <input type="number" step="any" placeholder="shares" value={form.shares}
          onChange={(e) => setForm({ ...form, shares: e.target.value })} />
        <input type="number" step="any" placeholder="avg cost (opt)" value={form.cost}
          onChange={(e) => setForm({ ...form, cost: e.target.value })} />
        <button type="submit">+ Add</button>
      </form>

      {rows.length === 0 ? (
        <p className="hint">No holdings yet. Add a stock above to track its value and P/L.</p>
      ) : (
        <table className="pf-table">
          <thead>
            <tr><th>Ticker</th><th>Shares</th><th>Price</th><th>Value</th><th>P/L</th><th>Latest move — why?</th><th></th></tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const mv = moves[r.ticker]
              return (
              <tr key={r.ticker}>
                <td><b>{r.ticker}</b></td>
                <td>{r.shares}</td>
                <td>{r.price != null ? `$${r.price.toFixed(2)}` : '…'}</td>
                <td>{r.value != null ? `$${r.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : '…'}</td>
                <td className={r.plPct == null ? '' : r.plPct >= 0 ? 'up' : 'down'}>
                  {r.plPct == null ? '—' : `${r.plPct >= 0 ? '+' : ''}${r.plPct.toFixed(1)}%`}
                </td>
                <td>
                  {mv && mv.return_pct != null ? (
                    <button className="pf-why" onClick={() => onAnalyze?.(r.ticker, mv)}>
                      <span className={`pf-why-move ${mv.return_pct >= 0 ? 'up' : 'down'}`}>
                        {mv.return_pct >= 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />} {mv.return_pct}%
                      </span>
                      <span className="pf-why-date">{mv.date}</span>
                      <span className="pf-why-cta">Why? <ArrowRight size={12} /></span>
                    </button>
                  ) : <span className="muted">—</span>}
                </td>
                <td>
                  <button className="pf-x" onClick={() => onExplore?.(r.ticker)} title="Explore in chart"><LineChart size={15} /></button>
                  <button className="pf-x" onClick={() => remove(r.ticker)} title="Remove"><X size={15} /></button>
                </td>
              </tr>
            )})}
          </tbody>
        </table>
      )}
    </div>
  )
}
