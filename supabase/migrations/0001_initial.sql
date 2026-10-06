-- Apply with Supabase CLI or SQL editor. Policies intentionally grant no
-- end-user access until an authenticated identity model is implemented.
create extension if not exists pgcrypto;

create table if not exists public.reviews (
  id uuid primary key default gen_random_uuid(),
  source_review_id text,
  product_id text,
  reviewer_id text,
  review_text text not null,
  rating numeric(2,1) check (rating >= 1 and rating <= 5),
  review_date date,
  verified_purchase boolean,
  created_at timestamptz not null default now()
);
create index if not exists reviews_product_id_idx on public.reviews(product_id);
create index if not exists reviews_reviewer_id_idx on public.reviews(reviewer_id);
create index if not exists reviews_review_date_idx on public.reviews(review_date);

create table if not exists public.analyses (
  id uuid primary key default gen_random_uuid(),
  review_id uuid references public.reviews(id) on delete set null,
  prediction text check (prediction in ('likely_genuine','potentially_suspicious','likely_fake')),
  risk_score numeric(5,2) check (risk_score >= 0 and risk_score <= 100),
  sentiment text check (sentiment in ('positive','neutral','negative')),
  model_version text,
  signals jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists analyses_created_at_idx on public.analyses(created_at desc);
create index if not exists analyses_risk_score_idx on public.analyses(risk_score desc);

alter table public.reviews enable row level security;
alter table public.analyses enable row level security;
revoke all on public.reviews, public.analyses from anon, authenticated;
