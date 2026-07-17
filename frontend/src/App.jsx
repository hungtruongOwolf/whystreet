import { useEffect, useState } from 'react'
import { Activity, LineChart, Network, Wallet, ArrowRight } from 'lucide-react'
import PriceChart from './components/PriceChart'
import AnalysisModal from './components/AnalysisModal'
import KnowledgeGraphView from './components/KnowledgeGraphView'
import PortfolioTab from './components/PortfolioTab'
import { getStocks, getPriceBars, getAnomalies } from './lib/api'
import { analyzeMove } from './lib/analyze'
import './App.css'

export default function App() {
  const [view, setView] = useState('explorer')
  const [stocks, setStocks] = useState([])
  const [ticker, setTicker] = useState('NVDA')
  const [bars, setBars] = useState([])
  const [anomalies, setAnomalies] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Analysis modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [analysis, setAnalysis] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeErr, setAnalyzeErr] = useState(null)
  const [analyzeMeta, setAnalyzeMeta] = useState(null)

  useEffect(() => {
    getStocks().then(setStocks).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setSelected(null)
    Promise.all([getPriceBars(ticker), getAnomalies(ticker)])
      .then(([b, a]) => {
        if (cancelled) return
        setBars(b)
        setAnomalies(a)
      })
      .catch((e) => setError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [ticker])

  const company = stocks.find((s) => s.ticker === ticker)
  // Keep the 15 most significant moves, but show them in chronological order
  // (most recent first) so the list reads like a timeline, not a leaderboard.
  const listAnoms = [...anomalies]
    .sort((a, b) => Math.abs(b.return_pct) - Math.abs(a.return_pct))
    .slice(0, 15)
    .sort((a, b) => b.date.localeCompare(a.date))

  async function runAnalysis(meta, forceLive = false) {
    setAnalyzeMeta(meta)
    setModalOpen(true)
    setAnalyzing(true)
    setAnalyzeErr(null)
    if (!forceLive) setAnalysis(null)
    try {
      const data = await analyzeMove({
        ticker: meta.ticker,
        date: meta.date,
        return_pct: meta.return_pct,
        forceLive,
      })
      setAnalysis(data)
    } catch (e) {
      setAnalyzeErr(e.message)
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="logo"><Activity size={22} strokeWidth={2.5} /></span>
          <div>
            <h1>WhyStreet</h1>
            <p className="tag">The why behind Wall Street</p>
          </div>
        </div>
        {view === 'explorer' && (
          <select value={ticker} onChange={(e) => setTicker(e.target.value)} className="ticker-select header-center">
            {stocks.map((s) => (
              <option key={s.ticker} value={s.ticker}>
                {s.ticker} — {s.company_name}
              </option>
            ))}
          </select>
        )}
        <nav className="topnav">
          <button className={view === 'explorer' ? 'active' : ''} onClick={() => setView('explorer')}><LineChart size={16} /> Explorer</button>
          <button className={view === 'kg' ? 'active' : ''} onClick={() => setView('kg')}><Network size={16} /> Knowledge Graph</button>
          <button className={view === 'portfolio' ? 'active' : ''} onClick={() => setView('portfolio')}><Wallet size={16} /> Portfolio</button>
        </nav>
      </header>

      {error && <div className="error">⚠ {error}</div>}

      {view === 'kg' ? <KnowledgeGraphView /> : view === 'portfolio' ? (
        <PortfolioTab
          stocks={stocks}
          onExplore={(t) => { setTicker(t); setView('explorer') }}
          onAnalyze={(t, p) => runAnalysis({ ticker: t, date: p.date, return_pct: p.return_pct })}
        />
      ) : (
      <div className="main">
        <section className="chart-panel">
          <div className="chart-head">
            <h2>{ticker}</h2>
            <span className="muted">{company?.sector}</span>
            <span className="muted right">
              {loading ? 'loading…' : `${bars.length} days · ${anomalies.length} volatility points`}
            </span>
          </div>
          <PriceChart
            bars={bars}
            anomalies={anomalies}
            onSelectPoint={setSelected}
            selectedDate={selected?.date}
          />
        </section>

        <aside className="side">
          {selected ? (
            <div className="detail">
              <span className={`pill ${selected.return_pct >= 0 ? 'up' : 'down'}`}>
                {selected.return_pct >= 0 ? '▲' : '▼'} {selected.return_pct}%
              </span>
              <h3>{selected.date}</h3>
              <div className="meta">
                {selected.adhoc
                  ? <span>custom point · ~5-day move</span>
                  : <>
                      {selected.zscore != null && <span>{selected.zscore}σ from MA</span>}
                      <span>{(selected.type || []).join(', ')}</span>
                      {selected.volume_spike && <span>volume spike</span>}
                    </>}
              </div>
              <button className="why-btn active" onClick={() => runAnalysis({ ticker, date: selected.date, return_pct: selected.return_pct })}>
                Explain why <ArrowRight size={16} />
              </button>
              <p className="hint">
                Runs a RocketRide Cloud agent that calls Linkup live for sourced news
                and builds the causal chain behind this move.
              </p>
            </div>
          ) : (
            <p className="hint">
              Click <b>any point</b> on the line to analyze that date — or pick a
              detected breakout below. Highlighted arrows are the biggest moves.
            </p>
          )}

          <h4 className="list-title">Volatility events · by date</h4>
          <ul className="anom-list">
            {listAnoms.map((a) => (
              <li
                key={a.date}
                className={selected?.date === a.date ? 'active' : ''}
                onClick={() => setSelected(a)}
                onDoubleClick={() => runAnalysis({ ticker, date: a.date, return_pct: a.return_pct })}
              >
                <span className={a.return_pct >= 0 ? 'up' : 'down'}>
                  {a.return_pct >= 0 ? '+' : ''}{a.return_pct}%
                </span>
                <span className="date">{a.date}</span>
              </li>
            ))}
          </ul>
        </aside>
      </div>
      )}

      {modalOpen && (
        <AnalysisModal
          meta={analyzeMeta || {}}
          analysis={analysis}
          loading={analyzing}
          error={analyzeErr}
          onClose={() => setModalOpen(false)}
          onRetryLive={() => analyzeMeta && runAnalysis(analyzeMeta, true)}
        />
      )}
    </div>
  )
}
