-- Spusťte jednou v Supabase: SQL Editor → New query → vložit → Run.

-- Stažené stránky a e-maily (aby se nic nezpracovalo dvakrát)
create table if not exists raw_items (
  id            bigserial primary key,
  fingerprint   text unique not null,   -- hash URL + obsahu, nebo Message-ID e-mailu
  source_id     text not null,
  source_name   text,
  kind          text,                    -- web / rss / email
  url           text,
  title         text,
  content       text,
  fetched_at    timestamptz default now(),
  processed     boolean default false
);

-- Jednotlivé výzvy vytažené z raw_items
create table if not exists grants (
  id                  bigserial primary key,
  call_key            text unique not null, -- normalizovaná URL výzvy, nebo titulek+poskytovatel+termín
  title               text,
  funder              text,
  call_url            text,
  deadline            date,
  opens_on            date,
  amount_min          numeric,
  amount_max          numeric,
  currency            text,
  eligible_applicants text,
  topics              jsonb,
  region              text,
  status              text,
  category            text,                 -- A / B / C / D
  source_ids          jsonb,
  source_urls         jsonb,
  summary             text,
  score               int,
  bucket              text,                 -- fit / adapt / later_form / no
  angle               text,
  first_seen          timestamptz default now(),
  last_seen           timestamptz default now(),
  sent_at             timestamptz           -- kdy šla poprvé v e-mailu
);

-- Záznam o odeslaných souhrnech
create table if not exists runs (
  id          bigserial primary key,
  started_at  timestamptz default now(),
  kind        text,
  stats       jsonb,
  ok          boolean
);

-- Pomocná tabulka jen pro test diagnostiky
create table if not exists diag_test (
  id    bigserial primary key,
  key   text unique not null,
  note  text
);
