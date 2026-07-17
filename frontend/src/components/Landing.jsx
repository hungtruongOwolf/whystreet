import {
  Activity, ArrowRight, Search, Brain, Network, ShieldCheck,
  Clock, LineChart, Wallet, ExternalLink, Sparkles, TrendingUp, TrendingDown,
} from 'lucide-react'

const STEPS = [
  { icon: LineChart, title: 'Detect', text: 'A math detector flags only statistically significant moves - the ~15 events that matter per stock, not thousands of headlines.' },
  { icon: Search, title: 'Ground', text: 'Linkup pulls live news from that exact time window - a proximate trigger plus the earlier build-up over weeks.' },
  { icon: Brain, title: 'Reason', text: 'A RocketRide Cloud pipeline turns evidence into a causal chain, cited drivers, scores, and the market-psychology behind the move.' },
  { icon: Network, title: 'Remember', text: 'Every analysis merges into a growing Neo4j knowledge graph that cross-links stocks through shared events and sectors.' },
]

const FEATURES = [
  { icon: Network, title: 'Causal chain graph', text: 'See the real chain - policy → sector → competitor → your stock - not a vague headline.' },
  { icon: ShieldCheck, title: 'Every claim sourced', text: 'No claim survives without a verifiable Linkup news URL. Grounded, not generated.' },
  { icon: Brain, title: 'Market psychology', text: 'A plain-language read of how the news transmitted to price and sentiment.' },
  { icon: Clock, title: 'Time-aware retrieval', text: 'Causes build up over weeks - we search the run-up, not just the move’s own day.' },
  { icon: Sparkles, title: 'Growing knowledge graph', text: 'The more you explore, the smarter it gets - recurring drivers surface across your portfolio.' },
  { icon: Wallet, title: 'Portfolio-aware', text: 'Ask “why did my stock move?” for anything you hold, any date.' },
]

const TECH = ['Linkup', 'RocketRide Cloud', 'Neo4j', 'Supabase', 'React']

export default function Landing({ onEnter, onGoto }) {
  return (
    <div className="lp">
      {/* Nav */}
      <nav className="lp-nav">
        <div className="lp-brand">
          <span className="lp-logo"><Activity size={20} strokeWidth={2.6} /></span>
          <span>WhyStreet</span>
        </div>
        <div className="lp-nav-links">
          <a href="#how">How it works</a>
          <a href="#features">Features</a>
          <a href="https://github.com/hungtruongOwolf/whystreet" target="_blank" rel="noreferrer">GitHub</a>
          <button className="lp-btn lp-btn-primary sm" onClick={onEnter}>Launch app <ArrowRight size={15} /></button>
        </div>
      </nav>

      {/* Hero */}
      <header className="lp-hero">
        <div className="lp-glow" />
        <a className="lp-badge" href="https://luma.com/6u7f4gen?tk=WgHmpn" target="_blank" rel="noreferrer">
          <span className="dot" /> Built for HackWithSeattle 2.0
        </a>
        <h1>
          The <span className="grad">why</span> behind<br />Wall Street.
        </h1>
        <p className="lp-sub">
          Markets move and you’re told <i>what</i> happened - never <i>why</i>. WhyStreet
          detects sharp price moves and explains each one as a <b>live-sourced causal
          chain</b>, grounded in real news and remembered in a knowledge graph.
        </p>
        <div className="lp-cta">
          <button className="lp-btn lp-btn-primary" onClick={onEnter}>
            Launch the Explorer <ArrowRight size={18} />
          </button>
          <a className="lp-btn lp-btn-ghost" href="https://github.com/hungtruongOwolf/whystreet" target="_blank" rel="noreferrer">
            <ExternalLink size={18} /> View on GitHub
          </a>
        </div>

        {/* Mock causal chain */}
        <div className="lp-chain">
          <span className="lp-node ev">Export rule</span>
          <ArrowRight size={16} className="lp-arrow" />
          <span className="lp-node sec">AI chip sector</span>
          <ArrowRight size={16} className="lp-arrow" />
          <span className="lp-node ev">DeepSeek shock</span>
          <ArrowRight size={16} className="lp-arrow" />
          <span className="lp-node stock"><TrendingDown size={14} /> NVDA −17%</span>
        </div>
      </header>

      {/* Problem */}
      <section className="lp-section lp-problem">
        <h2>Too much noise. No idea why.</h2>
        <p className="lp-lead">
          Every new investor drowns in market information. Your stock suddenly drops or
          spikes - and you can’t tell what’s going on.
        </p>
        <div className="lp-qs">
          <div className="lp-q">Is the <b>whole market</b> falling?</div>
          <div className="lp-q">Is it just <b>that sector</b> rotating?</div>
          <div className="lp-q">Or something specific to <b>that company</b>?</div>
        </div>
        <p className="lp-lead muted">
          WhyStreet answers the one question that matters - <b>what happened, and why</b> -
          for any move, with sources you can verify.
        </p>
      </section>

      {/* How it works */}
      <section className="lp-section" id="how">
        <div className="lp-eyebrow">How it works</div>
        <h2>Detect → Ground → Reason → Remember</h2>
        <div className="lp-steps">
          {STEPS.map((s, i) => (
            <div className="lp-step" key={s.title}>
              <div className="lp-step-ico"><s.icon size={22} /></div>
              <div className="lp-step-n">0{i + 1}</div>
              <h3>{s.title}</h3>
              <p>{s.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="lp-section" id="features">
        <div className="lp-eyebrow">Features</div>
        <h2>Grounded, agentic, and it compounds</h2>
        <div className="lp-grid">
          {FEATURES.map((f) => (
            <div className="lp-card" key={f.title}>
              <div className="lp-card-ico"><f.icon size={20} /></div>
              <h3>{f.title}</h3>
              <p>{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Tech */}
      <section className="lp-section lp-tech">
        <div className="lp-eyebrow">Powered by</div>
        <div className="lp-tech-row">
          {TECH.map((t) => <span className="lp-chip" key={t}>{t}</span>)}
        </div>
      </section>

      {/* Final CTA */}
      <section className="lp-final">
        <div className="lp-glow2" />
        <h2>Stop guessing. Start understanding.</h2>
        <p>Pick a stock, click any move, and watch the causal chain build itself - live.</p>
        <div className="lp-cta">
          <button className="lp-btn lp-btn-primary" onClick={onEnter}>
            Launch the Explorer <ArrowRight size={18} />
          </button>
          <button className="lp-btn lp-btn-ghost" onClick={() => onGoto('kg')}>
            <Network size={18} /> See the knowledge graph
          </button>
        </div>
      </section>

      <footer className="lp-foot">
        <span><TrendingUp size={14} /> WhyStreet - the why behind Wall Street</span>
        <span className="muted">Linkup · RocketRide Cloud · Neo4j · Built for HackWithSeattle 2.0</span>
      </footer>
    </div>
  )
}
