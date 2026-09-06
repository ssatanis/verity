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

-- unified provider risk (detectors/risk_score.py) and provider plazas (detectors/d1_ghost_networks.py)
create table if not exists public.provider_risk (
  npi text primary key, rank int, name text, entity_type text, city text, state text, taxonomy text, county_fips text, medicaid_state text,
  tier int, tier_label text, score numeric, n_detectors int, detectors jsonb, dollars_at_risk numeric, reasons text,
  d3_a int, d3_b int, d3_paid_after numeric, d3_sources text, d3_first_event date, d3_months int,
  d2_tier text, months_impossible int, months_over_mn_cap int, months_umbrella int, peak_hours_per_day numeric, max_billing_orgs int, paid_flagged_months numeric, growth_paid_24_22 numeric,
  d1_cluster_id text, d1_rank int, d1_eligible boolean, d1_label_family int, d1_score numeric, d1_medicaid_2024 numeric, d1_medicare_2023 numeric
);
-- enforcement feed (DOJ, HHS-OIG, state attorneys general) and forward exposure, added 2026-09-05; idempotent for existing projects
alter table public.provider_risk add column if not exists enf_adjudicated int, add column if not exists enf_alleged int, add column if not exists enf_first_event date,
  add column if not exists enf_actions text, add column if not exists enf_sources text, add column if not exists enf_url text, add column if not exists enf_title text,
  add column if not exists exposure_12m numeric;
create index if not exists provider_risk_rank_idx on public.provider_risk (rank);
create index if not exists provider_risk_state_idx on public.provider_risk (state, tier);
create index if not exists provider_risk_name_idx on public.provider_risk (lower(name) text_pattern_ops);
alter table public.provider_risk enable row level security;
drop policy if exists "public read" on public.provider_risk; create policy "public read" on public.provider_risk for select using (true);
create table if not exists public.hub_addresses (
  address text primary key, level text, n_providers int, n_hospice int, n_hha int, n_snf int, n_since_2019 int, n_labelled int, revoked_entity_here int,
  city text, state text, zip5 text, county_fips text, npis jsonb, hub boolean
);
alter table public.hub_addresses enable row level security;
drop policy if exists "public read" on public.hub_addresses; create policy "public read" on public.hub_addresses for select using (true);
create index if not exists providers_name_idx on public.providers (lower(name) text_pattern_ops);
alter table public.reviews add column if not exists notes_family text;

-- factor desk: thirty factors per provider network with percentile and robust z, plus a momentum row
create table if not exists public.network_factors (
  cluster_id text not null, factor text not null, family text, label text, unit text, direction text, note text,
  value numeric, percentile numeric, z numeric, outlook text, primary key (cluster_id, factor)
);
create index if not exists network_factors_cluster_idx on public.network_factors (cluster_id);
alter table public.network_factors enable row level security;
drop policy if exists "public read network_factors" on public.network_factors;
create policy "public read network_factors" on public.network_factors for select using (true);

-- fuzzy provider search (trigram similarity) with optional state and city filters
create extension if not exists pg_trgm;
create index if not exists providers_name_trgm on public.providers using gin (name gin_trgm_ops);
create index if not exists provider_risk_name_trgm on public.provider_risk using gin (name gin_trgm_ops);
create or replace function public.search_providers(q text, st text default null, ct text default null, lim int default 12)
returns table (npi text, name text, city text, state text, entity_type text, tier int, sim real)
language sql stable as $$
  with u as (
    select r.npi, r.name, r.city, r.state, r.entity_type, r.tier, similarity(r.name, q) as sim from public.provider_risk r
    union all
    select p.npi, p.name, p.city, p.state, p.entity_type, null::int, similarity(p.name, q) from public.providers p
    where not exists (select 1 from public.provider_risk r2 where r2.npi = p.npi)
  )
  select npi, name, city, state, entity_type, tier, sim from u
  where sim > 0.25 and (st is null or state = upper(st)) and (ct is null or city ilike ct || '%')
  order by sim desc, tier nulls last limit lim
$$;

-- procedure-level evidence: largest Medicaid codes per provider with national comparison, and codes that recur among flagged providers
create table if not exists public.provider_codes (
  npi text not null, hcpcs text not null, description text, paid numeric, share numeric, lines numeric, months int, patient_months numeric,
  dpm numeric, dpm_pct numeric, dpm_median numeric, dpm_p95 numeric, high_vector boolean, code_family text,
  avg_submitted numeric, avg_allowed numeric, charge_ratio numeric, peer_ratio_median numeric, peer_ratio_p90 numeric, medicare_services numeric, rk int,
  primary key (npi, hcpcs)
);
create index if not exists provider_codes_npi_idx on public.provider_codes (npi);
create table if not exists public.provider_codes_medicare (
  npi text not null, hcpcs text not null, description text, services numeric, beneficiaries numeric, paid numeric, share numeric,
  avg_submitted numeric, avg_allowed numeric, charge_ratio numeric, peer_ratio_median numeric, peer_ratio_p90 numeric, rk int, primary key (npi, hcpcs)
);
create table if not exists public.procedure_trends (
  hcpcs text primary key, description text, n_flagged int, n_all int, n_tier1 int, n_tier2 int, paid_flagged numeric, paid_all numeric, lift numeric, vector text, family text
);
alter table public.provider_codes enable row level security; alter table public.provider_codes_medicare enable row level security; alter table public.procedure_trends enable row level security;
drop policy if exists "public read provider_codes" on public.provider_codes; create policy "public read provider_codes" on public.provider_codes for select using (true);
drop policy if exists "public read provider_codes_medicare" on public.provider_codes_medicare; create policy "public read provider_codes_medicare" on public.provider_codes_medicare for select using (true);
drop policy if exists "public read procedure_trends" on public.procedure_trends; create policy "public read procedure_trends" on public.procedure_trends for select using (true);
alter table public.provider_risk add column if not exists procedure_points int; alter table public.provider_risk add column if not exists procedure_reason text;

-- Enforcement releases the daily feed has fetched: DOJ press releases and HHS-OIG enforcement actions, one row per release,
-- with the fields the extraction step read out of each and the NPIs the matching step tied to it at high confidence.
-- The console's News tab and the "recent enforcement in this area" section on every provider read this table.
create table if not exists public.enforcement (
  id text primary key, source text not null, title text not null, published date, url text, district text, state text,
  action_type text, tier text, programs text, scheme text, dollars_alleged numeric, dollars_ordered numeric, action_date date,
  body text, npis jsonb, image_url text, updated_at timestamptz default now()
);
create index if not exists enforcement_published_idx on public.enforcement (published desc);
create index if not exists enforcement_state_idx on public.enforcement (state, published desc);
alter table public.enforcement enable row level security;
drop policy if exists "public read" on public.enforcement; create policy "public read" on public.enforcement for select using (true);
