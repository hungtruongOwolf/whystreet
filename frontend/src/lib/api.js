import { supabase } from '../supabaseClient'

// PostgREST caps rows per request (~1000), so paginate to get full history.
async function fetchAll(table, columns, ticker, orderCol) {
  const pageSize = 1000
  let from = 0
  const all = []
  for (;;) {
    const { data, error } = await supabase
      .from(table)
      .select(columns)
      .eq('ticker', ticker)
      .order(orderCol)
      .range(from, from + pageSize - 1)
    if (error) throw error
    all.push(...data)
    if (data.length < pageSize) break
    from += pageSize
  }
  return all
}

export async function getStocks() {
  const { data, error } = await supabase.from('stocks').select('*').order('ticker')
  if (error) throw error
  return data
}

export function getPriceBars(ticker) {
  return fetchAll('price_bars', 'date,close', ticker, 'date')
}

export function getAnomalies(ticker) {
  return fetchAll('anomaly_points', 'date,return_pct,zscore,type,volume_spike,priority', ticker, 'date')
}

export async function getLatestPrice(ticker) {
  const { data, error } = await supabase
    .from('price_bars').select('close,date').eq('ticker', ticker)
    .order('date', { ascending: false }).limit(1)
  if (error) throw error
  return data?.[0] || null
}

// Most recent detected volatility point for a ticker — the "what just moved" hook.
export async function getLatestAnomaly(ticker) {
  const { data, error } = await supabase
    .from('anomaly_points').select('date,return_pct,zscore,type')
    .eq('ticker', ticker).order('date', { ascending: false }).limit(1)
  if (error) throw error
  return data?.[0] || null
}
