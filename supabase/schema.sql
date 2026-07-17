-- WhyStreet — Supabase schema (run in the Supabase SQL Editor)
-- See docs/05-schemas.md for what each table means.

create table if not exists stocks (
  ticker        text primary key,
  company_name  text,
  sector        text
);

create table if not exists price_bars (
  id      bigint generated always as identity primary key,
  ticker  text references stocks(ticker),
  date    date not null,
  open    numeric,
  high    numeric,
  low     numeric,
  close   numeric,
  volume  bigint,
  unique (ticker, date)
);

create table if not exists anomaly_points (
  id            bigint generated always as identity primary key,
  ticker        text references stocks(ticker),
  date          date not null,
  return_pct    numeric,
  zscore        numeric,
  type          text[],          -- {shock, peak, trough}
  volume_spike  boolean,
  priority      numeric,
  processed     boolean default false,   -- DEDUP: has the pipeline run yet
  unique (ticker, date)
);

create table if not exists analysis_results (
  id            bigint generated always as identity primary key,
  ticker        text,
  date          date not null,
  reasons       jsonb,           -- reasons[]
  graph         jsonb,           -- {nodes, edges}
  sources       text[],
  linkup_calls  int,
  is_live_run   boolean,
  generated_at  timestamptz default now(),
  unique (ticker, date)
);

create table if not exists watch_state (
  ticker               text primary key references stocks(ticker),
  last_processed_date  date
);

-- Indexes for common queries
create index if not exists idx_price_bars_ticker_date on price_bars(ticker, date);
create index if not exists idx_anomaly_ticker_date   on anomaly_points(ticker, date);
