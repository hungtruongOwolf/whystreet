import { useEffect, useRef } from 'react'
import {
  createChart, AreaSeries, ColorType, createSeriesMarkers,
} from 'lightweight-charts'

const UP = '#26a641'
const DOWN = '#f85149'

export default function PriceChart({ bars, anomalies, onSelectPoint, selectedDate }) {
  const containerRef = useRef(null)
  const wrapRef = useRef(null)
  const tipRef = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)
  const markersRef = useRef(null)
  const anomaliesRef = useRef([])
  const barsRef = useRef([])
  const onSelectRef = useRef(onSelectPoint)

  onSelectRef.current = onSelectPoint
  anomaliesRef.current = anomalies
  barsRef.current = bars

  // Create chart once
  useEffect(() => {
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: '#0e1116' },
        textColor: '#9aa4b2',
        fontFamily: 'Inter, system-ui, sans-serif',
      },
      grid: {
        vertLines: { color: '#1c2128' },
        horzLines: { color: '#1c2128' },
      },
      rightPriceScale: { borderColor: '#30363d' },
      timeScale: { borderColor: '#30363d', rightOffset: 4 },
      crosshair: { mode: 0 },
    })
    const series = chart.addSeries(AreaSeries, {
      lineColor: '#00b9ec',
      topColor: 'rgba(0,185,236,0.22)',
      bottomColor: 'rgba(0,185,236,0.01)',
      lineWidth: 2,
      priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
    })
    chartRef.current = chart
    seriesRef.current = series
    markersRef.current = createSeriesMarkers(series, [])

    // Click anywhere on the chart. If close to a detected breakout, select it;
    // otherwise build an ad-hoc point for the clicked date so ANY date can be
    // analyzed by the pipeline (not just the pre-computed points).
    chart.subscribeClick((param) => {
      if (!param.time) return
      const clicked = new Date(param.time).getTime()

      let best = null
      let bestDiff = Infinity
      for (const a of anomaliesRef.current) {
        const diff = Math.abs(new Date(a.date).getTime() - clicked)
        if (diff < bestDiff) { bestDiff = diff; best = a }
      }
      if (best && bestDiff <= 3 * 864e5) { onSelectRef.current?.(best); return }

      // Ad-hoc: snap to the nearest price bar, compute a ~5-session move as context.
      const arr = barsRef.current
      if (!arr.length) return
      let idx = 0
      let idxDiff = Infinity
      for (let i = 0; i < arr.length; i++) {
        const d = Math.abs(new Date(arr[i].date).getTime() - clicked)
        if (d < idxDiff) { idxDiff = d; idx = i }
      }
      const j = Math.max(0, idx - 5)
      const ret = ((arr[idx].close - arr[j].close) / arr[j].close) * 100
      onSelectRef.current?.({
        date: arr[idx].date,
        return_pct: Math.round(ret * 100) / 100,
        zscore: null,
        type: ['custom'],
        volume_spike: false,
        adhoc: true,
      })
    })

    // Hover tooltip: show the date + price under the cursor, and — if that day is
    // a detected volatility event — the move % and what kind of event it is.
    chart.subscribeCrosshairMove((param) => {
      const tip = tipRef.current
      if (!tip) return
      if (!param.time || !param.point || param.point.x < 0 || param.point.y < 0) {
        tip.style.display = 'none'; return
      }
      const price = param.seriesData.get(seriesRef.current)?.value
      if (price == null) { tip.style.display = 'none'; return }
      const date = param.time
      const anom = anomaliesRef.current.find((a) => a.date === date)
      const dateLabel = new Date(date).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
      let html = `<div class="tt-date">${dateLabel}</div><div class="tt-price">$${price.toFixed(2)}</div>`
      if (anom) {
        const up = anom.return_pct >= 0
        const kind = anom.adhoc ? 'custom' : ((anom.type || []).join(', ') || 'volatility event')
        html += `<div class="tt-move ${up ? 'up' : 'down'}">${up ? '▲ +' : '▼ '}${anom.return_pct}% · ${kind}</div>`
        html += `<div class="tt-hint">click to select · double-click to explain</div>`
      }
      tip.innerHTML = html
      tip.style.display = 'block'
      const wrap = wrapRef.current
      const w = wrap ? wrap.clientWidth : 600
      const left = Math.min(param.point.x + 14, w - 190)
      tip.style.left = `${Math.max(8, left)}px`
      tip.style.top = `${Math.max(8, param.point.y + 14)}px`
    })

    return () => chart.remove()
  }, [])

  // Update data + markers
  useEffect(() => {
    if (!seriesRef.current) return
    seriesRef.current.setData(bars.map((b) => ({ time: b.date, value: b.close })))
    // Only label the 5 biggest moves to avoid clutter; the rest are arrows only.
    const cut = [...anomalies]
      .map((a) => Math.abs(a.return_pct))
      .sort((x, y) => y - x)[Math.min(4, anomalies.length - 1)] ?? Infinity
    const markers = anomalies.map((a) => {
      const up = a.return_pct >= 0
      const major = Math.abs(a.return_pct) >= cut
      return {
        time: a.date,
        position: up ? 'belowBar' : 'aboveBar',
        color: up ? UP : DOWN,
        shape: up ? 'arrowUp' : 'arrowDown',
        text: major ? `${up ? '+' : ''}${a.return_pct}%` : '',
      }
    })
    markersRef.current.setMarkers(markers)
    chartRef.current.timeScale().fitContent()
  }, [bars, anomalies])

  // Move crosshair to the selected point
  useEffect(() => {
    if (selectedDate && chartRef.current) {
      chartRef.current.timeScale().scrollToPosition(0, false)
    }
  }, [selectedDate])

  return (
    <div ref={wrapRef} className="chart-wrap">
      <div ref={containerRef} className="chart" />
      <div ref={tipRef} className="chart-tip" style={{ display: 'none' }} />
    </div>
  )
}
