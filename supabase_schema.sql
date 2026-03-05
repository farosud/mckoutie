-- mckoutie Supabase schema
-- Run this in your Supabase SQL editor to set up the tables.

-- Users table: created on Twitter OAuth login
create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  twitter_id text unique not null,
  username text not null default '',
  name text not null default '',
  email text default '',
  stripe_customer_id text default '',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists idx_users_twitter_id on users(twitter_id);
create index if not exists idx_users_stripe_customer on users(stripe_customer_id);

-- Reports table: one row per analysis request
create table if not exists reports (
  id uuid primary key default gen_random_uuid(),
  report_id text unique not null,            -- short ID used in URLs
  startup_name text not null default '',
  target text not null default '',            -- URL or @handle
  tweet_id text default '',
  author_twitter_id text not null default '', -- who requested it
  author_username text not null default '',
  status text not null default 'pending',     -- pending|analyzing|ready|active|canceled|failed
  tier text default '',                       -- starter|growth|enterprise
  error text default '',
  checkout_url text default '',
  created_at timestamptz default now(),
  paid_at timestamptz,
  last_updated_at timestamptz,
  update_count int default 0,
  -- foreign key to users
  owner_id uuid references users(id)
);

create index if not exists idx_reports_report_id on reports(report_id);
create index if not exists idx_reports_author on reports(author_twitter_id);
create index if not exists idx_reports_status on reports(status);

-- Subscriptions table: tracks Stripe subscription lifecycle
create table if not exists subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) not null,
  report_id text not null,                    -- links to reports.report_id
  stripe_subscription_id text unique,
  stripe_customer_id text default '',
  tier text not null default 'starter',       -- starter|growth|enterprise
  status text not null default 'active',      -- active|canceled|past_due|unpaid
  created_at timestamptz default now(),
  canceled_at timestamptz
);

create index if not exists idx_subs_user on subscriptions(user_id);
create index if not exists idx_subs_report on subscriptions(report_id);
create index if not exists idx_subs_stripe on subscriptions(stripe_subscription_id);

-- Auto-update updated_at on users
create or replace function update_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists users_updated_at on users;
create trigger users_updated_at
  before update on users
  for each row execute function update_updated_at();
