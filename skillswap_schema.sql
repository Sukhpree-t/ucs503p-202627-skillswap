-- =====================================================================
-- SkillSwap: Supabase (PostgreSQL 15/16) schema
-- Run in Supabase Dashboard > SQL Editor (in order, top to bottom).
-- Ledger model: double-entry. Every transfer = 1 debit + 1 credit.
-- Zero-sum invariant: SUM(accounts.balance) = 0 (the MINT account holds
-- the negative side of all credits ever issued).
-- =====================================================================

create extension if not exists vector;        -- pgvector
create extension if not exists btree_gist;    -- for slot-overlap exclusion
create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------
-- 0. APPLICATION CONFIGURATION
-- ---------------------------------------------------------------------
create table if not exists public.app_config (
  key         text primary key,
  value       text not null,
  description text,
  updated_at  timestamptz not null default now()
);
alter table public.app_config enable row level security;
create policy app_config_read on public.app_config for select to authenticated using (true);
create policy app_config_anon_read on public.app_config for select to anon using (true);

-- Single source of truth for starter credits
insert into public.app_config (key, value, description)
values ('starter_credits', '3', 'Number of starter credits granted on student registration')
on conflict (key) do update set value = excluded.value;

-- ---------------------------------------------------------------------
-- 1. USERS / PROFILES  (D1: User and Skill DB)
-- ---------------------------------------------------------------------
create table public.profiles (
  id                    uuid primary key references auth.users(id) on delete cascade,
  campus_email          text unique not null,
  full_name             text not null,
  avatar_url            text,
  department            text,
  study_year            smallint check (study_year between 1 and 6),
  bio                   text,
  role                  text not null default 'peer' check (role in ('peer','admin')),
  status                text not null default 'active' check (status in ('active','suspended')),
  suspension_reason     text,
  strike_count          int  not null default 0,
  quiz_completed        boolean not null default false,
  mentor_rating_avg     numeric(3,2) not null default 0,
  mentor_rating_count   int not null default 0,
  learner_rating_avg    numeric(3,2) not null default 0,
  learner_rating_count  int not null default 0,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

-- Skill catalogue (one embedding per skill name)
create table public.skills (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  slug        text not null unique,
  category    text,
  embedding   vector(384),              -- match your embedding model's dimension
  created_at  timestamptz not null default now()
);
create index skills_embedding_idx on public.skills
  using hnsw (embedding vector_cosine_ops);

-- A peer's offered / desired skills
create table public.user_skills (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references public.profiles(id) on delete cascade,
  skill_id            uuid not null references public.skills(id) on delete cascade,
  kind                text not null check (kind in ('offered','desired')),
  level               text not null check (level in ('beginner','intermediate','advanced')),
  description         text,
  hourly_rate_credits int check (hourly_rate_credits > 0),   -- only for 'offered'
  quiz_score          numeric(5,2),
  embedding_stale     boolean not null default true,         -- FR2/UC-02 E2: retry embedding later
  created_at          timestamptz not null default now(),
  unique (user_id, skill_id, kind),
  check (kind = 'offered' or hourly_rate_credits is null)
);
create index user_skills_skill_idx on public.user_skills (skill_id, kind);

-- Initial skill quiz (FR3)
create table public.quiz_questions (
  id            uuid primary key default gen_random_uuid(),
  skill_id      uuid not null references public.skills(id) on delete cascade,
  question      text not null,
  options       jsonb not null,            -- ["A","B","C","D"]
  correct_index smallint not null,
  difficulty    text default 'medium'
);

create table public.quiz_attempts (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.profiles(id) on delete cascade,
  skill_id    uuid not null references public.skills(id),
  score       numeric(5,2) not null,
  answers     jsonb,
  created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- 2. LEDGER  (D3: Postgres Ledger)  double-entry, zero-sum
-- ---------------------------------------------------------------------
create table public.accounts (
  id         uuid primary key default gen_random_uuid(),
  kind       text not null check (kind in ('user','escrow','mint')),
  owner_id   uuid unique references public.profiles(id) on delete restrict,
  balance    bigint not null default 0,
  created_at timestamptz not null default now(),
  -- user and escrow accounts can never go negative; mint is the only negative side
  check (kind = 'mint' or balance >= 0),
  check ((kind = 'user' and owner_id is not null) or (kind <> 'user' and owner_id is null))
);
-- exactly one escrow vault and one mint account
create unique index one_escrow_idx on public.accounts (kind) where kind = 'escrow';
create unique index one_mint_idx   on public.accounts (kind) where kind = 'mint';

create table public.ledger_transactions (
  id          uuid primary key default gen_random_uuid(),
  type        text not null check (type in
                ('starter_grant','escrow_lock','settlement','refund','dispute_refund','dispute_payout','dispute_split')),
  booking_id  uuid,                       -- FK added after bookings table
  description text,
  created_at  timestamptz not null default now()
);

create table public.ledger_entries (
  id             bigint generated always as identity primary key,
  transaction_id uuid not null references public.ledger_transactions(id) on delete restrict,
  account_id     uuid not null references public.accounts(id) on delete restrict,
  direction      text not null check (direction in ('debit','credit')),
  amount         bigint not null check (amount > 0),
  created_at     timestamptz not null default now()
);
create index ledger_entries_tx_idx on public.ledger_entries (transaction_id);
create index ledger_entries_acc_idx on public.ledger_entries (account_id, created_at desc);

-- Every transaction must balance: SUM(debits) = SUM(credits)
create or replace function public.check_tx_balanced() returns trigger
language plpgsql as $$
declare d bigint; c bigint;
begin
  select coalesce(sum(amount) filter (where direction='debit'),0),
         coalesce(sum(amount) filter (where direction='credit'),0)
    into d, c from public.ledger_entries where transaction_id = new.transaction_id;
  if d <> c then
    raise exception 'LEDGER_UNBALANCED: tx % debits % credits %', new.transaction_id, d, c;
  end if;
  return null;
end $$;

create constraint trigger ledger_balanced
  after insert on public.ledger_entries
  deferrable initially deferred
  for each row execute function public.check_tx_balanced();

-- Ledger is append-only
create or replace function public.block_ledger_mutation() returns trigger
language plpgsql as $$ begin raise exception 'Ledger is append-only'; end $$;
create trigger ledger_entries_immutable before update or delete on public.ledger_entries
  for each row execute function public.block_ledger_mutation();
create trigger ledger_tx_immutable before update or delete on public.ledger_transactions
  for each row execute function public.block_ledger_mutation();

-- ---------------------------------------------------------------------
-- 3. SCHEDULING  (D2: Scheduling DB)
-- ---------------------------------------------------------------------
create table public.availability_slots (
  id            uuid primary key default gen_random_uuid(),
  mentor_id     uuid not null references public.profiles(id) on delete cascade,
  skill_id      uuid references public.skills(id),
  start_time    timestamptz not null,
  end_time      timestamptz not null,
  rate_credits  int not null check (rate_credits > 0),     -- snapshot of rate at publish time
  status        text not null default 'open'
                check (status in ('open','booked','cancelled')),
  external_event_id text,                                   -- Google Calendar event id
  created_at    timestamptz not null default now(),
  check (end_time > start_time),
  -- a mentor cannot have overlapping live slots (UC-05 step 4)
  exclude using gist (
    mentor_id with =,
    tstzrange(start_time, end_time) with &&
  ) where (status <> 'cancelled')
);
create index slots_open_idx on public.availability_slots (start_time) where status = 'open';

create table public.calendar_connections (
  user_id        uuid primary key references public.profiles(id) on delete cascade,
  provider       text not null default 'google',
  refresh_token_secret_id uuid,          -- reference to Supabase Vault secret, never store raw token
  last_sync_at   timestamptz,
  last_sync_ok   boolean,
  created_at     timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- 4. BOOKINGS, SESSIONS
-- ---------------------------------------------------------------------
create table public.bookings (
  id                 uuid primary key default gen_random_uuid(),
  slot_id            uuid not null references public.availability_slots(id),
  learner_id         uuid not null references public.profiles(id),
  mentor_id          uuid not null references public.profiles(id),
  skill_id           uuid references public.skills(id),
  objectives         text,
  cost_credits       int not null check (cost_credits > 0),
  scheduled_start    timestamptz not null,
  scheduled_end      timestamptz not null,
  status             text not null default 'confirmed' check (status in
                       ('confirmed','in_progress','completed','refunded','disputed','cancelled')),
  escrow_status      text not null default 'held' check (escrow_status in
                       ('held','released','refunded','frozen','split')),
  learner_signed_off boolean not null default false,
  mentor_signed_off  boolean not null default false,
  grace_deadline     timestamptz,                -- no-show cutoff
  settled_at         timestamptz,
  created_at         timestamptz not null default now(),
  check (learner_id <> mentor_id)
);
-- a slot can only have one active booking (second line of defence after Redis lock)
create unique index one_active_booking_per_slot on public.bookings (slot_id)
  where status not in ('cancelled','refunded');
create index bookings_learner_idx on public.bookings (learner_id, scheduled_start desc);
create index bookings_mentor_idx  on public.bookings (mentor_id, scheduled_start desc);

alter table public.ledger_transactions
  add constraint ledger_tx_booking_fk foreign key (booking_id) references public.bookings(id);

create table public.session_rooms (
  booking_id     uuid primary key references public.bookings(id) on delete cascade,
  room_name      text not null unique,
  video_domain   text not null,
  video_provider text not null default 'daily',
  expires_at     timestamptz not null,
  created_at     timestamptz not null default now()
);

-- Signed JWT bookkeeping (single-session tokens, QR13)
create table public.session_tokens (
  jti         uuid primary key default gen_random_uuid(),
  booking_id  uuid not null references public.bookings(id) on delete cascade,
  user_id     uuid not null references public.profiles(id),
  expires_at  timestamptz not null,
  revoked     boolean not null default false,
  created_at  timestamptz not null default now()
);

-- Join/leave/heartbeat-gap events (live heartbeats stay in Redis, summary persisted here as dispute evidence)
create table public.session_events (
  id          bigint generated always as identity primary key,
  booking_id  uuid not null references public.bookings(id) on delete cascade,
  user_id     uuid references public.profiles(id),
  event_type  text not null check (event_type in
               ('joined','left','heartbeat_lost','heartbeat_resumed','room_created','room_failed')),
  created_at  timestamptz not null default now()
);
create index session_events_booking_idx on public.session_events (booking_id, created_at);

create table public.session_messages (
  id          uuid primary key default gen_random_uuid(),
  booking_id  uuid not null references public.bookings(id) on delete cascade,
  sender_id   uuid not null references public.profiles(id),
  body        text not null,
  created_at  timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- 5. REVIEWS, STRIKES, BADGES
-- ---------------------------------------------------------------------
create table public.reviews (
  id               uuid primary key default gen_random_uuid(),
  booking_id       uuid not null references public.bookings(id) on delete cascade,
  reviewer_id      uuid not null references public.profiles(id),
  reviewee_id      uuid not null references public.profiles(id),
  reviewer_role    text not null check (reviewer_role in ('learner','mentor')),
  rating           smallint not null check (rating between 1 and 5),     -- quality (learner) / engagement (mentor)
  punctuality      smallint check (punctuality between 1 and 5),         -- mentor rating learner
  comment          text,
  created_at       timestamptz not null default now(),
  unique (booking_id, reviewer_id)
);

create table public.strikes (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.profiles(id) on delete cascade,
  booking_id  uuid references public.bookings(id),
  reason      text not null check (reason in ('no_show','dispute_fault','misconduct')),
  created_at  timestamptz not null default now()
);

create table public.badges (
  id          uuid primary key default gen_random_uuid(),
  code        text unique not null,      -- e.g. 'top_mentor', 'punctual', 'first_swap'
  name        text not null,
  description text
);
create table public.user_badges (
  user_id    uuid references public.profiles(id) on delete cascade,
  badge_id   uuid references public.badges(id) on delete cascade,
  awarded_at timestamptz not null default now(),
  primary key (user_id, badge_id)
);

-- ---------------------------------------------------------------------
-- 6. DISPUTES, NOTIFICATIONS, AUDIT
-- ---------------------------------------------------------------------
create table public.disputes (
  id                   uuid primary key default gen_random_uuid(),
  booking_id           uuid not null references public.bookings(id),
  raised_by            uuid not null references public.profiles(id),
  reason               text not null check (reason in
                         ('mentor_no_show','poor_quality','learner_misconduct','technical_issue','other')),
  details              text,
  status               text not null default 'open' check (status in
                         ('open','info_requested','resolved','withdrawn')),
  evidence             jsonb not null default '{}'::jsonb,   -- heartbeats, timestamps, chat snapshot
  resolution           text check (resolution in ('refund_learner','pay_mentor','split')),
  learner_share        int,                                  -- credits to learner when split
  resolved_by          uuid references public.profiles(id),
  admin_notes          text,
  created_at           timestamptz not null default now(),
  resolved_at          timestamptz
);
-- only one open dispute per booking (UC-07 E2)
create unique index one_open_dispute on public.disputes (booking_id)
  where status in ('open','info_requested');

create table public.notifications (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.profiles(id) on delete cascade,
  type        text not null,      -- booking_alert, reminder, refund, dispute_update, strike, review
  title       text not null,
  body        text,
  data        jsonb,
  read_at     timestamptz,
  created_at  timestamptz not null default now()
);
create index notifications_user_idx on public.notifications (user_id, created_at desc);

create table public.audit_reports (
  id             uuid primary key default gen_random_uuid(),
  run_by         uuid references public.profiles(id),      -- null = automatic post-settlement run
  passed         boolean not null,
  total_debits   bigint not null,
  total_credits  bigint not null,
  total_issued   bigint not null,
  details        jsonb,                                    -- mismatched transactions
  created_at     timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- 7. SEED: system accounts
-- ---------------------------------------------------------------------
insert into public.accounts (kind) values ('escrow'), ('mint');

-- ---------------------------------------------------------------------
-- 8. HELPERS
-- ---------------------------------------------------------------------
create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from profiles where id = auth.uid() and role = 'admin' and status = 'active');
$$;

-- internal: move credits between two accounts atomically (locks both rows, lowest id first to avoid deadlocks)
create or replace function public.post_transfer(
  p_from uuid, p_to uuid, p_amount bigint, p_type text, p_booking uuid, p_desc text
) returns uuid language plpgsql security definer set search_path = public as $$
declare v_tx uuid;
begin
  if p_amount <= 0 then raise exception 'INVALID_AMOUNT'; end if;
  perform 1 from accounts where id in (p_from, p_to) order by id for update;
  insert into ledger_transactions (type, booking_id, description)
    values (p_type, p_booking, p_desc) returning id into v_tx;
  insert into ledger_entries (transaction_id, account_id, direction, amount) values
    (v_tx, p_from, 'debit',  p_amount),
    (v_tx, p_to,   'credit', p_amount);
  update accounts set balance = balance - p_amount where id = p_from;
  update accounts set balance = balance + p_amount where id = p_to;   -- CHECK blocks negative user balances
  return v_tx;
end $$;
revoke all on function public.post_transfer from public, anon, authenticated;

-- new auth user -> profile + wallet + starter credits (FR1, UC-01 A1)
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  v_acc uuid;
  v_mint uuid;
  v_starter int;
begin
  -- single source of truth for starter credits
  select coalesce(value::int, 3) into v_starter from public.app_config where key = 'starter_credits';
  if v_starter is null then v_starter := 3; end if;

  insert into profiles (id, campus_email, full_name)
    values (new.id, new.email, coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email,'@',1)));
  insert into accounts (kind, owner_id) values ('user', new.id) returning id into v_acc;
  select id into v_mint from accounts where kind = 'mint';
  perform post_transfer(v_mint, v_acc, v_starter, 'starter_grant', null, 'Starter credits');
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- keep rating aggregates fresh
create or replace function public.refresh_rating() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if new.reviewer_role = 'learner' then   -- learner rated the mentor
    update profiles p set
      mentor_rating_avg   = (select round(avg(rating),2) from reviews where reviewee_id = new.reviewee_id and reviewer_role='learner'),
      mentor_rating_count = (select count(*) from reviews where reviewee_id = new.reviewee_id and reviewer_role='learner')
    where p.id = new.reviewee_id;
  else
    update profiles p set
      learner_rating_avg   = (select round(avg(rating),2) from reviews where reviewee_id = new.reviewee_id and reviewer_role='mentor'),
      learner_rating_count = (select count(*) from reviews where reviewee_id = new.reviewee_id and reviewer_role='mentor')
    where p.id = new.reviewee_id;
  end if;
  return new;
end $$;
create trigger reviews_refresh after insert on public.reviews
  for each row execute function public.refresh_rating();

create or replace function public.touch_updated_at() returns trigger
language plpgsql as $$ begin new.updated_at = now(); return new; end $$;
create trigger profiles_touch before update on public.profiles
  for each row execute function public.touch_updated_at();

-- ---------------------------------------------------------------------
-- 9. CORE ACID FUNCTIONS (call via supabase.rpc from your FastAPI/server;
--    your Redis mutex still wraps book_slot, row locks here are the 2nd defence)
-- ---------------------------------------------------------------------

-- 9.1 semantic mentor search (FR5/FR6)
create or replace function public.match_mentors(
  query_embedding vector(384),
  max_rate int default null,
  min_rating numeric default 0,
  match_count int default 20,
  min_similarity float default 0.3
) returns table (
  mentor_id uuid, full_name text, skill_id uuid, skill_name text,
  similarity float, rate_credits int, rating numeric, rating_count int, next_slot timestamptz
) language sql stable as $$
  select p.id, p.full_name, s.id, s.name,
         1 - (s.embedding <=> query_embedding) as similarity,
         us.hourly_rate_credits, p.mentor_rating_avg, p.mentor_rating_count,
         (select min(a.start_time) from availability_slots a
           where a.mentor_id = p.id and a.status = 'open' and a.start_time > now())
  from user_skills us
  join skills s   on s.id = us.skill_id
  join profiles p on p.id = us.user_id
  where us.kind = 'offered' and p.status = 'active' and p.id <> auth.uid()
    and 1 - (s.embedding <=> query_embedding) >= min_similarity
    and (max_rate is null or us.hourly_rate_credits <= max_rate)
    and p.mentor_rating_avg >= min_rating
    and exists (select 1 from availability_slots a
                where a.mentor_id = p.id and a.status = 'open' and a.start_time > now())
  order by similarity desc, p.mentor_rating_avg desc
  limit match_count;
$$;

-- 9.2 book a slot: lock slot row, lock wallet row, escrow in one transaction (FR8-FR11)
create or replace function public.book_slot(
  p_slot_id uuid, p_objectives text default null, p_learner_id uuid default null
)
returns uuid language plpgsql security definer set search_path = public as $$
declare
  v_learner uuid := coalesce(p_learner_id, auth.uid());
  v_slot availability_slots%rowtype;
  v_acc accounts%rowtype;
  v_escrow uuid;
  v_booking uuid;
  v_learner_name text;
begin
  if v_learner is null then raise exception 'UNAUTHENTICATED'; end if;

  select * into v_slot from availability_slots where id = p_slot_id for update;
  if not found or v_slot.status <> 'open' or v_slot.start_time <= now() then
    raise exception 'SLOT_UNAVAILABLE';
  end if;
  if v_slot.mentor_id = v_learner then raise exception 'OWN_SLOT'; end if;

  select * into v_acc from accounts where owner_id = v_learner and kind = 'user' for update;
  if not found or v_acc.balance < v_slot.rate_credits then raise exception 'INSUFFICIENT_BALANCE'; end if;

  select id into v_escrow from accounts where kind = 'escrow';

  insert into bookings (slot_id, learner_id, mentor_id, skill_id, objectives, cost_credits,
                        scheduled_start, scheduled_end, grace_deadline)
  values (p_slot_id, v_learner, v_slot.mentor_id, v_slot.skill_id, p_objectives, v_slot.rate_credits,
          v_slot.start_time, v_slot.end_time, v_slot.start_time + interval '10 minutes')
  returning id into v_booking;

  perform post_transfer(v_acc.id, v_escrow, v_slot.rate_credits, 'escrow_lock', v_booking, 'Escrow lock');
  update availability_slots set status = 'booked' where id = p_slot_id;

  select full_name into v_learner_name from profiles where id = v_learner;
  if v_learner_name is null then v_learner_name := 'Campus Peer'; end if;

  insert into notifications (user_id, type, title, body, data) values
    (v_slot.mentor_id,
     'booking_alert',
     'Session Booked by ' || v_learner_name,
     coalesce(p_objectives, 'Peer mentoring session') || ' | ' || to_char(v_slot.start_time, 'Dy, Mon DD at HH24:MI TZ'),
     jsonb_build_object(
       'booking_id', v_booking,
       'slot_id', p_slot_id,
       'learner_id', v_learner,
       'learner_name', v_learner_name,
       'scheduled_start', v_slot.start_time,
       'scheduled_end', v_slot.end_time,
       'cost_credits', v_slot.rate_credits,
       'objectives', p_objectives
     ));

  return v_booking;
end $$;

-- 9.25 atomic join session (Sprint 4: validates participant, window, and escrow in 1 tx)
-- Note: session_events 'joined' means "token issued"; actual presence comes from Daily presence/webhooks in Sprint 5.
create or replace function public.join_session(
  p_booking_id uuid,
  p_user_id uuid default null,
  p_room_name text default null,
  p_video_domain text default 'daily',
  p_video_provider text default 'daily',
  p_expires_at timestamptz default null,
  p_jti uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  b bookings%rowtype;
  v_now timestamptz := now();
  v_actor_id uuid;
  v_is_owner boolean;
begin
  select * into b from bookings where id = p_booking_id for update;
  if not found then raise exception 'BOOKING_NOT_FOUND'; end if;

  -- Derive caller from auth.uid() if authenticated; otherwise use p_user_id (service_role)
  v_actor_id := auth.uid();
  if v_actor_id is null then
    v_actor_id := p_user_id;
  end if;

  -- Re-validate participant
  if v_actor_id is null or v_actor_id not in (b.learner_id, b.mentor_id) then
    raise exception 'FORBIDDEN';
  end if;

  -- Re-validate escrow_status
  if b.escrow_status <> 'held' then
    raise exception 'ESCROW_NOT_HELD';
  end if;

  -- Re-validate window (-10m before start, +15m after scheduled_end)
  if v_now < (b.scheduled_start - interval '10 minutes') then
    raise exception 'SESSION_NOT_STARTED';
  end if;
  if v_now > (b.scheduled_end + interval '15 minutes') then
    raise exception 'SESSION_WINDOW_EXPIRED';
  end if;

  v_is_owner := (v_actor_id = b.mentor_id);

  insert into session_rooms (booking_id, room_name, video_domain, video_provider, expires_at)
  values (p_booking_id, p_room_name, p_video_domain, p_video_provider, p_expires_at)
  on conflict (booking_id) do nothing;

  insert into session_tokens (jti, booking_id, user_id, expires_at)
  values (p_jti, p_booking_id, v_actor_id, p_expires_at)
  on conflict (jti) do nothing;

  -- session_events 'joined' means 'token issued' (Sprint 4); actual presence from Daily webhooks in Sprint 5
  insert into session_events (booking_id, user_id, event_type)
  values (p_booking_id, v_actor_id, 'joined');

  return jsonb_build_object(
    'success', true,
    'booking_id', p_booking_id,
    'room_name', p_room_name,
    'video_domain', p_video_domain,
    'is_owner', v_is_owner,
    'expires_at', p_expires_at
  );
end $$;
revoke all on function public.join_session from public, anon, authenticated;

-- 9.3 each side signs off; when both confirm, settle escrow -> mentor (FR24)
create or replace function public.sign_off_booking(p_booking_id uuid, p_user_id uuid default null)
returns text language plpgsql security definer set search_path = public as $$
declare
  b bookings%rowtype;
  v_escrow uuid;
  v_mentor_acc uuid;
  v_actor_id uuid;
begin
  select * into b from bookings where id = p_booking_id for update;
  if not found then raise exception 'BOOKING_NOT_FOUND'; end if;

  v_actor_id := coalesce(p_user_id, auth.uid());
  if v_actor_id is null or v_actor_id not in (b.learner_id, b.mentor_id) then
    raise exception 'FORBIDDEN';
  end if;

  -- Early sign-off rejected before scheduled_start
  if now() < b.scheduled_start then
    raise exception 'EARLY_SIGN_OFF_REJECTED';
  end if;

  if b.escrow_status <> 'held' then raise exception 'NOT_SETTLEABLE'; end if;

  if v_actor_id = b.learner_id then update bookings set learner_signed_off = true where id = b.id;
  else update bookings set mentor_signed_off = true where id = b.id; end if;

  select * into b from bookings where id = p_booking_id;
  if b.learner_signed_off and b.mentor_signed_off then
    select id into v_escrow from accounts where kind = 'escrow';
    select id into v_mentor_acc from accounts where owner_id = b.mentor_id;
    perform post_transfer(v_escrow, v_mentor_acc, b.cost_credits, 'settlement', b.id, 'Session settlement');
    update bookings set status = 'completed', escrow_status = 'released', settled_at = now() where id = b.id;
    return 'settled';
  end if;
  return 'waiting_for_other_party';
end $$;

-- 9.4 refund escrow to learner (no-show / room failure). Called by backend with service_role.
create or replace function public.refund_booking(p_booking_id uuid, p_strike_mentor boolean default false)
returns void language plpgsql security definer set search_path = public as $$
declare b bookings%rowtype; v_escrow uuid; v_learner_acc uuid;
begin
  select * into b from bookings where id = p_booking_id for update;
  if b.escrow_status <> 'held' then raise exception 'NOT_REFUNDABLE'; end if;
  select id into v_escrow from accounts where kind = 'escrow';
  select id into v_learner_acc from accounts where owner_id = b.learner_id;
  perform post_transfer(v_escrow, v_learner_acc, b.cost_credits, 'refund', b.id, 'Auto-refund');
  update bookings set status = 'refunded', escrow_status = 'refunded', settled_at = now() where id = b.id;
  update availability_slots set status = 'cancelled' where id = b.slot_id;
  if p_strike_mentor then
    insert into strikes (user_id, booking_id, reason) values (b.mentor_id, b.id, 'no_show');
    update profiles set strike_count = strike_count + 1 where id = b.mentor_id;
  end if;
  insert into notifications (user_id, type, title) values (b.learner_id, 'refund', 'Credits refunded');
end $$;
revoke all on function public.refund_booking from public, anon, authenticated;  -- service_role only

-- 9.5 raise dispute: freeze escrow (FR15/FR26)
create or replace function public.raise_dispute(p_booking_id uuid, p_reason text, p_details text default null)
returns uuid language plpgsql security definer set search_path = public as $$
declare b bookings%rowtype; v_id uuid;
begin
  select * into b from bookings where id = p_booking_id for update;
  if not found or auth.uid() not in (b.learner_id, b.mentor_id) then raise exception 'FORBIDDEN'; end if;
  if b.escrow_status <> 'held' then raise exception 'ALREADY_SETTLED'; end if;
  insert into disputes (booking_id, raised_by, reason, details, evidence)
  values (b.id, auth.uid(), p_reason, p_details,
    jsonb_build_object(
      'events',   (select coalesce(jsonb_agg(to_jsonb(e) order by e.created_at),'[]') from session_events e where e.booking_id = b.id),
      'messages', (select coalesce(jsonb_agg(to_jsonb(m) order by m.created_at),'[]') from session_messages m where m.booking_id = b.id)))
  returning id into v_id;                          -- unique index rejects a 2nd open dispute
  update bookings set status = 'disputed', escrow_status = 'frozen' where id = b.id;
  insert into notifications (user_id, type, title, data)
    select u, 'dispute_update', 'A dispute was opened', jsonb_build_object('dispute_id', v_id)
    from unnest(array[b.learner_id, b.mentor_id]) u;
  return v_id;
end $$;

-- 9.6 admin arbitration: refund / pay mentor / split (FR30)
create or replace function public.resolve_dispute(
  p_dispute_id uuid, p_outcome text, p_learner_share int default null,
  p_notes text default null, p_strike_mentor boolean default false
) returns void language plpgsql security definer set search_path = public as $$
declare d disputes%rowtype; b bookings%rowtype; v_escrow uuid; l_acc uuid; m_acc uuid; v_share int;
begin
  if not is_admin() then raise exception 'ADMIN_ONLY'; end if;
  select * into d from disputes where id = p_dispute_id for update;
  if d.status not in ('open','info_requested') then raise exception 'ALREADY_RESOLVED'; end if;
  select * into b from bookings where id = d.booking_id for update;
  select id into v_escrow from accounts where kind = 'escrow';
  select id into l_acc from accounts where owner_id = b.learner_id;
  select id into m_acc from accounts where owner_id = b.mentor_id;

  if p_outcome = 'refund_learner' then
    perform post_transfer(v_escrow, l_acc, b.cost_credits, 'dispute_refund', b.id, 'Dispute: refund learner');
    update bookings set status='refunded', escrow_status='refunded', settled_at=now() where id=b.id;
  elsif p_outcome = 'pay_mentor' then
    perform post_transfer(v_escrow, m_acc, b.cost_credits, 'dispute_payout', b.id, 'Dispute: pay mentor');
    update bookings set status='completed', escrow_status='released', settled_at=now() where id=b.id;
  elsif p_outcome = 'split' then
    v_share := coalesce(p_learner_share, 0);
    if v_share <= 0 or v_share >= b.cost_credits then raise exception 'INVALID_SPLIT'; end if;
    perform post_transfer(v_escrow, l_acc, v_share, 'dispute_split', b.id, 'Dispute split: learner');
    perform post_transfer(v_escrow, m_acc, b.cost_credits - v_share, 'dispute_split', b.id, 'Dispute split: mentor');
    update bookings set status='completed', escrow_status='split', settled_at=now() where id=b.id;
  else raise exception 'INVALID_OUTCOME'; end if;

  update disputes set status='resolved', resolution=p_outcome, learner_share=v_share,
         resolved_by=auth.uid(), admin_notes=p_notes, resolved_at=now() where id = d.id;

  if p_strike_mentor then
    insert into strikes (user_id, booking_id, reason) values (b.mentor_id, b.id, 'dispute_fault');
    update profiles set strike_count = strike_count + 1 where id = b.mentor_id;
  end if;
  insert into notifications (user_id, type, title, data)
    select u, 'dispute_update', 'Dispute resolved', jsonb_build_object('dispute_id', d.id, 'outcome', p_outcome)
    from unnest(array[b.learner_id, b.mentor_id]) u;
end $$;

-- 9.7 zero-sum ledger audit (FR28 / FR31). run_by = null when run automatically.
create or replace function public.audit_ledger(p_auto boolean default false)
returns audit_reports language plpgsql security definer set search_path = public as $$
declare
  v_deb bigint; v_cred bigint; v_issued bigint; v_sum_bal bigint; v_escrow_bal bigint; v_held bigint;
  v_bad jsonb; v_ok boolean; r audit_reports;
begin
  if not (is_admin() or auth.role() = 'service_role') then raise exception 'ADMIN_ONLY'; end if;
  select coalesce(sum(amount) filter (where direction='debit'),0),
         coalesce(sum(amount) filter (where direction='credit'),0) into v_deb, v_cred from ledger_entries;
  select coalesce(sum(le.amount),0) into v_issued
    from ledger_entries le join ledger_transactions lt on lt.id = le.transaction_id
    where lt.type = 'starter_grant' and le.direction = 'credit';
  select coalesce(sum(balance),0) into v_sum_bal from accounts;
  select balance into v_escrow_bal from accounts where kind = 'escrow';
  select coalesce(sum(cost_credits),0) into v_held from bookings where escrow_status in ('held','frozen');
  select coalesce(jsonb_agg(t.transaction_id), '[]') into v_bad from (
    select transaction_id from ledger_entries group by transaction_id
    having sum(amount) filter (where direction='debit') <> sum(amount) filter (where direction='credit')) t;

  -- invariants: debits = credits; all balances sum to 0; user wallets + escrow = credits issued; escrow = held bookings
  v_ok := (v_deb = v_cred) and (v_sum_bal = 0)
          and (v_escrow_bal = v_held)
          and ((select coalesce(sum(balance),0) from accounts where kind in ('user','escrow')) = v_issued)
          and (v_bad = '[]'::jsonb);

  insert into audit_reports (run_by, passed, total_debits, total_credits, total_issued, details)
  values (case when p_auto then null else auth.uid() end, v_ok, v_deb, v_cred, v_issued,
          jsonb_build_object('unbalanced_tx', v_bad, 'escrow_balance', v_escrow_bal, 'held_bookings', v_held))
  returning * into r;
  return r;
end $$;

-- ---------------------------------------------------------------------
-- 10. ROW LEVEL SECURITY
-- All money movement goes through the SECURITY DEFINER functions above;
-- clients never write accounts / ledger tables directly (QR14).
-- ---------------------------------------------------------------------
alter table profiles            enable row level security;
alter table skills              enable row level security;
alter table user_skills         enable row level security;
alter table quiz_questions      enable row level security;
alter table quiz_attempts       enable row level security;
alter table accounts            enable row level security;
alter table ledger_transactions enable row level security;
alter table ledger_entries      enable row level security;
alter table availability_slots  enable row level security;
alter table calendar_connections enable row level security;
alter table bookings            enable row level security;
alter table session_rooms       enable row level security;
alter table session_tokens      enable row level security;
alter table session_events      enable row level security;
alter table session_messages    enable row level security;
alter table reviews             enable row level security;
alter table strikes             enable row level security;
alter table badges              enable row level security;
alter table user_badges         enable row level security;
alter table disputes            enable row level security;
alter table notifications       enable row level security;
alter table audit_reports       enable row level security;

-- profiles: everyone signed in can read; users edit only safe columns of their own row
create policy profiles_read   on profiles for select to authenticated using (true);
create policy profiles_update on profiles for update to authenticated using (id = auth.uid()) with check (id = auth.uid());
revoke update on profiles from authenticated;
grant  update (full_name, avatar_url, department, study_year, bio) on profiles to authenticated;
create policy profiles_admin_update on profiles for update to authenticated using (is_admin());  -- suspend/reinstate (FR32)

create policy skills_read on skills for select to authenticated using (true);
create policy user_skills_read  on user_skills for select to authenticated using (true);
create policy user_skills_write on user_skills for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy quiz_q_read on quiz_questions for select to authenticated using (true);
create policy quiz_a_own  on quiz_attempts  for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- wallet: read only your own account + entries (FR4); admins read all
create policy accounts_own on accounts for select to authenticated using (owner_id = auth.uid() or is_admin());
create policy ledger_tx_read on ledger_transactions for select to authenticated using (
  is_admin() or exists (select 1 from ledger_entries e join accounts a on a.id = e.account_id
                        where e.transaction_id = ledger_transactions.id and a.owner_id = auth.uid()));
create policy ledger_entries_read on ledger_entries for select to authenticated using (
  is_admin() or exists (select 1 from accounts a where a.id = ledger_entries.account_id and a.owner_id = auth.uid()));

-- slots: all can browse open slots; mentors manage their own unbooked slots
create policy slots_read on availability_slots for select to authenticated using (true);
create policy slots_insert on availability_slots for insert to authenticated with check (mentor_id = auth.uid());
create policy slots_update on availability_slots for update to authenticated
  using (mentor_id = auth.uid() and status = 'open') with check (mentor_id = auth.uid());
create policy slots_delete on availability_slots for delete to authenticated
  using (mentor_id = auth.uid() and status = 'open');

create policy cal_own on calendar_connections for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- bookings & session data: participants and admins only (writes go through RPCs / service role)
create policy bookings_read on bookings for select to authenticated
  using (auth.uid() in (learner_id, mentor_id) or is_admin());
create policy rooms_read on session_rooms for select to authenticated using (
  exists (select 1 from bookings b where b.id = booking_id and auth.uid() in (b.learner_id, b.mentor_id)));
create policy events_read on session_events for select to authenticated using (
  is_admin() or exists (select 1 from bookings b where b.id = booking_id and auth.uid() in (b.learner_id, b.mentor_id)));
create policy msgs_read on session_messages for select to authenticated using (
  is_admin() or exists (select 1 from bookings b where b.id = booking_id and auth.uid() in (b.learner_id, b.mentor_id)));
create policy msgs_insert on session_messages for insert to authenticated with check (
  sender_id = auth.uid() and exists (select 1 from bookings b where b.id = booking_id and auth.uid() in (b.learner_id, b.mentor_id)));
-- session_tokens: no client policy (service role only)

-- reviews: public read; reviewer must be a participant of a completed booking
create policy reviews_read on reviews for select to authenticated using (true);
create policy reviews_insert on reviews for insert to authenticated with check (
  reviewer_id = auth.uid() and exists (
    select 1 from bookings b where b.id = booking_id and b.status = 'completed'
      and ((reviewer_role = 'learner' and b.learner_id = auth.uid() and reviewee_id = b.mentor_id)
        or (reviewer_role = 'mentor'  and b.mentor_id  = auth.uid() and reviewee_id = b.learner_id))));

create policy strikes_read on strikes for select to authenticated using (user_id = auth.uid() or is_admin());
create policy badges_read on badges for select to authenticated using (true);
create policy user_badges_read on user_badges for select to authenticated using (true);

create policy disputes_read on disputes for select to authenticated using (
  is_admin() or exists (select 1 from bookings b where b.id = booking_id and auth.uid() in (b.learner_id, b.mentor_id)));
-- withdraw own dispute (UC-07 A1) handled by a backend/RPC; admin updates via resolve_dispute()

create policy notif_own_read   on notifications for select to authenticated using (user_id = auth.uid());
create policy notif_own_update on notifications for update to authenticated using (user_id = auth.uid());

create policy audit_admin on audit_reports for select to authenticated using (is_admin());

-- lock down who may call which RPC
revoke execute on function public.audit_ledger  from public, anon;
revoke execute on function public.book_slot     from public, anon;
revoke execute on function public.sign_off_booking from public, anon;
revoke execute on function public.raise_dispute from public, anon;
revoke execute on function public.resolve_dispute from public, anon;

-- Realtime (notifications, session chat, slot status)
alter publication supabase_realtime add table public.notifications, public.session_messages, public.availability_slots;
