-- Verity serving schema for Supabase Postgres. Idempotent. Applied by ingest/sync_supabase.py.
-- DuckDB (data/verity.duckdb) is the analytical warehouse; these tables are what the app, the agent and reviewers touch.
create extension if not exists pgcrypto;

create table if not exists public.datasets (
  id text primary key, name text not null, source_url text, local_path text, storage_bucket text, storage_path text,
  bytes bigint, rows bigint, snapshot_date date, sha256 text, notes text, loaded_at timestamptz default now()
);

create table if not exists public.timecodes (
  hcpcs text primary key, description text, minutes_per_unit numeric, unit_basis text, group_divisor int default 1, family text,
  fraud_vector text, mn_rate_per_unit numeric, mn_daily_cap_hours numeric, source text, notes text
);
alter table public.timecodes add column if not exists fraud_vector text;
alter table public.timecodes add column if not exists mn_rate_per_unit numeric;
alter table public.timecodes add column if not exists mn_daily_cap_hours numeric;
alter table public.timecodes add column if not exists source text;
alter table public.timecodes add column if not exists personal_service boolean;

create table if not exists public.revoked (
  id bigserial primary key, enrlmt_id text, npi text, first_name text, mdl_name text, last_name text, org_name text, state text,
  provider_type_desc text, revocation_rsn text, revoked_dt date, reenroll_bar_dt date
);
create index if not exists revoked_npi_idx on public.revoked (npi);

create table if not exists public.leie (
  id bigserial primary key, lastname text, firstname text, midname text, busname text, general text, specialty text, upin text, npi text,
  dob date, address text, city text, state text, zip text, excltype text, excl_dt date, rein_dt date, waiver_dt date, wvrstate text
);
create index if not exists leie_npi_idx on public.leie (npi);

create table if not exists public.enrollments (
  enrollment_id text primary key, ptype text not null, enrollment_state text, provider_type_code text, provider_type_text text, npi text,
  multiple_npi_flag text, ccn text, associate_id text, org_name text, dba_name text, inc_date date, inc_state text, org_structure text,
  proprietary_nonprofit text, address1 text, address2 text, city text, state text, zip5 text, zip9 text
);
create index if not exists enrollments_npi_idx on public.enrollments (npi);
create index if not exists enrollments_state_idx on public.enrollments (state, ptype);

create table if not exists public.owners (
  id bigserial primary key, ptype text not null, enrollment_id text, associate_id text, org_name text, owner_associate_id text, owner_type text,
  role_code text, role_text text, association_date date, first_name text, middle_name text, last_name text, title text, owner_org_name text,
  owner_dba text, address1 text, address2 text, city text, state text, zip text, pct_ownership numeric, flags text[], other_type_text text
);
do $$ begin
  if exists (select 1 from information_schema.columns where table_schema='public' and table_name='owners' and column_name='flags' and data_type='jsonb') then
    alter table public.owners drop column flags; alter table public.owners add column flags text[];
  end if;
end $$;
alter table public.owners add column if not exists other_type_text text;
create index if not exists owners_flags_idx on public.owners using gin (flags);
create index if not exists owners_enrollment_idx on public.owners (enrollment_id);
create index if not exists owners_owner_idx on public.owners (owner_associate_id);

create table if not exists public.chow (
  id bigserial primary key, ptype text, buyer_enrollment_id text, buyer_npi text, buyer_ccn text, buyer_org_name text, chow_type text,
  effective_dt date, seller_enrollment_id text, seller_npi text, seller_ccn text, seller_org_name text
);

create table if not exists public.saturation_county (
  id bigserial primary key, reference_period text, period_year text, type_of_service text, aggregation_level text, state text, county text,
  state_fips text, county_fips text, ffs_beneficiaries bigint, providers bigint, users_per_provider numeric, pct_users_of_ffs numeric,
  users bigint, providers_per_county numeric, dual_users bigint, total_payment numeric, moratorium boolean, providers_per_10k_ffs numeric
);
create index if not exists saturation_county_idx on public.saturation_county (type_of_service, state, county_fips);

-- Providers referenced by any flag or cluster (slim NPPES + Medicaid home state). Filled by the detectors' sync, not the full 8M NPPES.
create table if not exists public.providers (
  npi text primary key, entity_type text, name text, org_name text, address1 text, city text, state text, zip5 text, phone text,
  taxonomy text, enum_date date, deact_date date, medicaid_state text, ao_name text, ao_phone text, extra jsonb
);

-- Detector outputs
create table if not exists public.clusters (
  id text primary key, detector text not null, state text, county text, county_fips text, score numeric, dollars_at_risk numeric,
  n_providers int, summary text, features jsonb, created_at timestamptz default now()
);
create table if not exists public.cluster_members (
  id bigserial primary key, cluster_id text references public.clusters(id) on delete cascade, npi text, enrollment_id text, role text,
  org_name text, evidence jsonb
);
create index if not exists cluster_members_cluster_idx on public.cluster_members (cluster_id);

create table if not exists public.flags (
  id bigserial primary key, detector text not null, npi text, billing_npi text, state text, month date, hcpcs text, metric text,
  value numeric, threshold numeric, score numeric, dollars numeric, evidence jsonb, created_at timestamptz default now()
);
create index if not exists flags_npi_idx on public.flags (npi);
create index if not exists flags_detector_idx on public.flags (detector, score desc);

create table if not exists public.evidence (
  id bigserial primary key, subject_type text not null, subject_id text not null, source_dataset text not null, source_row jsonb, note text,
  created_at timestamptz default now()
);
create index if not exists evidence_subject_idx on public.evidence (subject_type, subject_id);

-- Agent packets and the human feedback loop
create table if not exists public.packets (
  id uuid primary key default gen_random_uuid(), subject_type text not null, subject_id text not null, status text not null default 'draft',
  packet jsonb, storage_path text, created_by text, created_at timestamptz default now()
);
create table if not exists public.reviews (
  id bigserial primary key, packet_id uuid references public.packets(id) on delete cascade, subject_type text, subject_id text,
  decision text not null check (decision in ('accept','reject','needs_info')), reviewer text, notes text, created_at timestamptz default now()
);

-- Row level security: public read on everything, writes only through the service role (bypasses RLS) or signed-in reviewers.
do $$ declare t text; begin
  foreach t in array array['datasets','timecodes','revoked','leie','enrollments','owners','chow','saturation_county','providers','clusters','cluster_members','flags','evidence','packets','reviews'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists "public read" on public.%I', t);
    execute format('create policy "public read" on public.%I for select using (true)', t);
  end loop;
end $$;
drop policy if exists "reviewers insert" on public.reviews;
create policy "reviewers insert" on public.reviews for insert to authenticated with check (true);
drop policy if exists "reviewers insert packets" on public.packets;
create policy "reviewers insert packets" on public.packets for insert to authenticated with check (true);

-- ---- detector output columns added 2026-09-05 (idempotent) ----
alter table public.clusters add column if not exists rank int;
alter table public.clusters add column if not exists eligible boolean default true;
alter table public.clusters add column if not exists chain_or_pe boolean default false;
alter table public.clusters add column if not exists n_hospice int; alter table public.clusters add column if not exists n_hha int; alter table public.clusters add column if not exists n_snf int;
alter table public.clusters add column if not exists city text;
alter table public.clusters add column if not exists structure_score numeric; alter table public.clusters add column if not exists label_score numeric; alter table public.clusters add column if not exists context_score numeric;
alter table public.clusters add column if not exists dollars_medicare numeric;
alter table public.clusters add column if not exists graph jsonb;
alter table public.clusters add column if not exists lat numeric; alter table public.clusters add column if not exists lon numeric;
create index if not exists clusters_rank_idx on public.clusters (detector, rank);
alter table public.cluster_members add column if not exists ptype text; alter table public.cluster_members add column if not exists ccn text;
alter table public.cluster_members add column if not exists city text; alter table public.cluster_members add column if not exists state text; alter table public.cluster_members add column if not exists zip5 text;
alter table public.cluster_members add column if not exists inc_date date; alter table public.cluster_members add column if not exists labels jsonb;
alter table public.cluster_members add column if not exists medicaid_2024 numeric; alter table public.cluster_members add column if not exists medicare_2023 numeric;
alter table public.flags add column if not exists tier text;
alter table public.flags add column if not exists name text;
alter table public.flags add column if not exists entity_type text;
create index if not exists flags_state_idx on public.flags (state);
create index if not exists flags_tier_idx on public.flags (detector, tier, score desc);
alter table public.providers add column if not exists lat numeric; alter table public.providers add column if not exists lon numeric;
alter table public.providers add column if not exists county_fips text;
alter table public.packets add column if not exists title text;
alter table public.packets add column if not exists cluster_id text;
alter table public.packets add column if not exists npi text;
alter table public.packets add column if not exists model text;
alter table public.packets add column if not exists dollars numeric;
alter table public.reviews add column if not exists detector text;
alter table public.reviews add column if not exists score_at_review numeric;

-- county-level rollups for the map
create table if not exists public.county_risk (
  county_fips text primary key, state text, county_name text, lat numeric, lon numeric,
  n_clusters int, n_providers_flagged int, dollars_at_risk numeric, d1_dollars numeric, d2_dollars numeric, d3_dollars numeric, top_cluster_id text, top_score numeric
);
alter table public.county_risk enable row level security;
drop policy if exists "public read" on public.county_risk; create policy "public read" on public.county_risk for select using (true);

-- national summary the home page reads
create table if not exists public.summary (
  key text primary key, value jsonb, updated_at timestamptz default now()
);
alter table public.summary enable row level security;
drop policy if exists "public read" on public.summary; create policy "public read" on public.summary for select using (true);

-- reviewer feedback re-weighting: one row per detector, learned from reviews
create table if not exists public.score_weights (
  detector text primary key, weights jsonb, n_reviews int default 0, updated_at timestamptz default now()
);
alter table public.score_weights enable row level security;
drop policy if exists "public read" on public.score_weights; create policy "public read" on public.score_weights for select using (true);
