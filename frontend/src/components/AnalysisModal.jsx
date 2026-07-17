import { useState } from 'react'
import { X, RefreshCw, TrendingUp, TrendingDown, ExternalLink } from 'lucide-react'
import CausalGraph from './CausalGraph'

function hostOf(url) {
  try { return new URL(url).hostname.replace('www.', '') } catch { return url }
}

export default function AnalysisModal({ meta, analysis, loading, error, onClose, onRetryLive }) {
  const [toast, setToast] = useState(null)
  const reasons = analysis?.reasons || []
  const graph = analysis?.graph || { nodes: [], edges: [] }
  const sources = analysis?.sources || []

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <div>
            <h2>
              Why did {meta.ticker} move{' '}
              <span className={meta.return_pct >= 0 ? 'up' : 'down'}>
                {meta.return_pct >= 0 ? '+' : ''}{meta.return_pct}%
              </span>{' '}
              on {meta.date}?
            </h2>
            <div className="modal-sub">
              {loading ? (
                <span className="badge live">● analyzing live…</span>
              ) : analysis ? (
                <>
                  <span className={`badge ${analysis.cached ? 'cached' : 'live'}`}>
                    {analysis.cached ? 'cached' : '● grounded LIVE'}
                  </span>
                  <span className="muted">{sources.length} sources · Linkup → RocketRide Cloud</span>
                  {analysis.cached && (
                    <button className="link-btn" onClick={onRetryLive}><RefreshCw size={12} /> re-run live</button>
                  )}
                </>
              ) : null}
            </div>
          </div>
          <button className="close" onClick={onClose}><X size={18} /></button>
        </header>

        {loading && (
          <div className="modal-loading">
            <div className="spinner" />
            <p>Agent is calling Linkup for live, sourced news and building the causal chain…</p>
          </div>
        )}

        {error && !loading && (
          <div className="modal-error">
            <p>⚠ {error}</p>
            <button className="why-btn active" onClick={onRetryLive}>Try again</button>
          </div>
        )}

        {analysis && !loading && (
          <div className="modal-body">
            <section className="graph-col">
              <h4 className="col-title">Causal chain</h4>
              {graph.nodes?.length ? (
                <CausalGraph
                  graph={graph}
                  onPickSource={(l) => { setToast(l); window.open(l.source_url, '_blank') }}
                />
              ) : (
                <p className="hint">No causal graph could be grounded for this move.</p>
              )}
            </section>

            <section className="reasons-col">
              <p className="summary">{analysis.summary}</p>

              {analysis.explanation && (
                <div className="mechanism">
                  <h4 className="col-title">How it moved the price — mechanism &amp; market psychology</h4>
                  <p className="mechanism-text">{analysis.explanation}</p>
                </div>
              )}

              {analysis.scores && Object.keys(analysis.scores).length > 0 && (
                <div className="scores">
                  <div className="score-item">
                    <span className="score-label">Risk</span>
                    <div className="conf-bar risk"><i style={{ width: `${analysis.scores.riskScore || 0}%` }} /></div>
                    <b>{analysis.scores.riskScore ?? '–'}</b>
                  </div>
                  <div className="score-item">
                    <span className="score-label">Recovery</span>
                    <div className="conf-bar rec"><i style={{ width: `${analysis.scores.recoveryScore || 0}%` }} /></div>
                    <b>{analysis.scores.recoveryScore ?? '–'}</b>
                  </div>
                  <div className="score-badges">
                    <span className={`sig ${(analysis.scores.signal || 'hold').toLowerCase()}`}>
                      {analysis.scores.signal || 'Hold'}
                    </span>
                    <span className="conf-badge">{analysis.scores.confidence || 'Low'} confidence</span>
                  </div>
                </div>
              )}

              <h4 className="col-title">Drivers (each cited)</h4>
              {reasons.length ? reasons.map((r, i) => (
                <div className="reason-card" key={i}>
                  <div className="reason-top">
                    <span className={`dir ${r.direction === 'up' ? 'up' : 'down'}`}>
                      {r.direction === 'up' ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                    </span>
                    <span className="reason-text">{r.text}</span>
                  </div>
                  <div className="conf-row">
                    <div className="conf-bar"><i style={{ width: `${Math.round((r.confidence ?? 0.5) * 100)}%` }} /></div>
                    <span className="conf-val">{Math.round((r.confidence ?? 0.5) * 100)}%</span>
                  </div>
                  {r.source_url && (
                    <a className="src" href={r.source_url} target="_blank" rel="noreferrer">
                      <ExternalLink size={12} /> {r.source_title || hostOf(r.source_url)}
                    </a>
                  )}
                </div>
              )) : <p className="hint">No grounded drivers found.</p>}

              {(analysis.similar || []).length > 0 && (
                <>
                  <h4 className="col-title">Similar past events</h4>
                  {analysis.similar.map((s, i) => (
                    <div className="sim-card" key={i}>
                      <div className="sim-top">
                        <span className={s.direction === 'up' ? 'up' : 'down'}>
                          {s.direction === 'up' ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
                        </span>
                        <span className="sim-date">{s.date}</span>
                      </div>
                      <div className="sim-head">{s.headline}</div>
                      {s.outcome && <div className="sim-out">{s.outcome}</div>}
                      {s.source_url && (
                        <a className="src" href={s.source_url} target="_blank" rel="noreferrer"><ExternalLink size={12} /> {hostOf(s.source_url)}</a>
                      )}
                    </div>
                  ))}
                </>
              )}

              {sources.length > 0 && (
                <details className="sources-all">
                  <summary>All {sources.length} sources</summary>
                  <ul>
                    {sources.map((s, i) => (
                      <li key={i}><a href={s} target="_blank" rel="noreferrer">{hostOf(s)}</a></li>
                    ))}
                  </ul>
                </details>
              )}
            </section>
          </div>
        )}

        {toast && <div className="toast" onAnimationEnd={() => setToast(null)}>Opened source: {hostOf(toast.source_url)}</div>}
      </div>
    </div>
  )
}
