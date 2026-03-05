-- Chat messages table for mckoutie agent conversations
create table if not exists chat_messages (
  id uuid primary key default gen_random_uuid(),
  report_id text not null,
  user_id text not null,  -- twitter_id
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  created_at timestamptz default now()
);

-- Index for fast history lookups
create index if not exists idx_chat_messages_report_user
  on chat_messages(report_id, user_id, created_at);

-- Index for cleanup/analytics
create index if not exists idx_chat_messages_created
  on chat_messages(created_at);
