create extension if not exists pgcrypto;

create or replace function public.meetwise_text_id(prefix text)
returns text
language sql
as $$
    select prefix || '_' || substr(replace(gen_random_uuid()::text, '-', ''), 1, 8);
$$;

create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    email text unique,
    full_name text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, email, full_name)
    values (
        new.id,
        new.email,
        coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name')
    )
    on conflict (id) do update
    set
        email = excluded.email,
        full_name = coalesce(excluded.full_name, public.profiles.full_name),
        updated_at = now();

    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_user();

create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create table if not exists public.workspaces (
    workspace_id text primary key default public.meetwise_text_id('ws'),
    name text not null,
    created_by uuid references public.profiles(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.workspace_members (
    workspace_id text not null references public.workspaces(workspace_id) on delete cascade,
    user_id uuid not null references public.profiles(id) on delete cascade,
    role text not null default 'member' check (role in ('owner', 'member')),
    joined_at timestamptz not null default now(),
    primary key (workspace_id, user_id)
);

create table if not exists public.teams (
    team_id text primary key default public.meetwise_text_id('tm'),
    workspace_id text not null references public.workspaces(workspace_id) on delete cascade,
    team_name text not null,
    created_by uuid references public.profiles(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists teams_workspace_name_unique
on public.teams (workspace_id, lower(team_name));

create table if not exists public.rooms (
    room_code text primary key,
    workspace_id text not null references public.workspaces(workspace_id) on delete cascade,
    team_id text not null references public.teams(team_id) on delete cascade,
    meeting_type text not null default 'general' check (meeting_type in ('standup', 'planning', 'review', 'general')),
    host_user_id uuid references public.profiles(id) on delete set null,
    host_name text not null,
    status text not null default 'active' check (status in ('active', 'ended', 'processing', 'complete', 'failed')),
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.room_participants (
    participant_id text primary key default public.meetwise_text_id('p'),
    room_code text not null references public.rooms(room_code) on delete cascade,
    user_id uuid references public.profiles(id) on delete set null,
    participant_name text not null,
    is_host boolean not null default false,
    audio_path text,
    upload_received boolean not null default false,
    joined_at timestamptz not null default now()
);

create index if not exists room_participants_room_idx
on public.room_participants (room_code);

create table if not exists public.summaries (
    summary_id text primary key default public.meetwise_text_id('sum'),
    workspace_id text not null references public.workspaces(workspace_id) on delete cascade,
    team_id text not null references public.teams(team_id) on delete cascade,
    room_code text not null unique references public.rooms(room_code) on delete cascade,
    meeting_title text not null,
    meeting_type text not null default 'general' check (meeting_type in ('standup', 'planning', 'review', 'general')),
    meeting_date date not null default current_date,
    duration_estimate text not null default 'Unknown',
    participant_count integer not null default 0,
    participants jsonb not null default '[]'::jsonb,
    summary_data jsonb not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists summaries_workspace_idx
on public.summaries (workspace_id, created_at desc);

create index if not exists summaries_team_idx
on public.summaries (team_id, created_at desc);

drop trigger if exists profiles_touch_updated_at on public.profiles;
create trigger profiles_touch_updated_at
before update on public.profiles
for each row execute procedure public.touch_updated_at();

drop trigger if exists workspaces_touch_updated_at on public.workspaces;
create trigger workspaces_touch_updated_at
before update on public.workspaces
for each row execute procedure public.touch_updated_at();

drop trigger if exists teams_touch_updated_at on public.teams;
create trigger teams_touch_updated_at
before update on public.teams
for each row execute procedure public.touch_updated_at();

drop trigger if exists rooms_touch_updated_at on public.rooms;
create trigger rooms_touch_updated_at
before update on public.rooms
for each row execute procedure public.touch_updated_at();

drop trigger if exists summaries_touch_updated_at on public.summaries;
create trigger summaries_touch_updated_at
before update on public.summaries
for each row execute procedure public.touch_updated_at();

alter table public.profiles enable row level security;
alter table public.workspaces enable row level security;
alter table public.workspace_members enable row level security;
alter table public.teams enable row level security;
alter table public.rooms enable row level security;
alter table public.room_participants enable row level security;
alter table public.summaries enable row level security;

drop policy if exists "profiles are viewable by owner" on public.profiles;
create policy "profiles are viewable by owner"
on public.profiles
for select
using (auth.uid() = id);

drop policy if exists "profiles are updatable by owner" on public.profiles;
create policy "profiles are updatable by owner"
on public.profiles
for update
using (auth.uid() = id);

drop policy if exists "authenticated users can create workspaces" on public.workspaces;
create policy "authenticated users can create workspaces"
on public.workspaces
for insert
to authenticated
with check (created_by = auth.uid());

drop policy if exists "workspace members can read workspaces" on public.workspaces;
create policy "workspace members can read workspaces"
on public.workspaces
for select
using (
    exists (
        select 1
        from public.workspace_members wm
        where wm.workspace_id = workspaces.workspace_id
          and wm.user_id = auth.uid()
    )
);

drop policy if exists "workspace owners can update workspaces" on public.workspaces;
create policy "workspace owners can update workspaces"
on public.workspaces
for update
using (
    exists (
        select 1
        from public.workspace_members wm
        where wm.workspace_id = workspaces.workspace_id
          and wm.user_id = auth.uid()
          and wm.role = 'owner'
    )
);

drop policy if exists "workspace members can read memberships" on public.workspace_members;
create policy "workspace members can read memberships"
on public.workspace_members
for select
using (
    exists (
        select 1
        from public.workspace_members wm
        where wm.workspace_id = workspace_members.workspace_id
          and wm.user_id = auth.uid()
    )
);

drop policy if exists "workspace owners can add memberships" on public.workspace_members;
create policy "workspace owners can add memberships"
on public.workspace_members
for insert
with check (
    exists (
        select 1
        from public.workspace_members wm
        where wm.workspace_id = workspace_members.workspace_id
          and wm.user_id = auth.uid()
          and wm.role = 'owner'
    )
);

drop policy if exists "workspace members can read teams" on public.teams;
create policy "workspace members can read teams"
on public.teams
for select
using (
    exists (
        select 1
        from public.workspace_members wm
        where wm.workspace_id = teams.workspace_id
          and wm.user_id = auth.uid()
    )
);

drop policy if exists "workspace members can create teams" on public.teams;
create policy "workspace members can create teams"
on public.teams
for insert
with check (
    exists (
        select 1
        from public.workspace_members wm
        where wm.workspace_id = teams.workspace_id
          and wm.user_id = auth.uid()
    )
);

drop policy if exists "workspace members can read rooms" on public.rooms;
create policy "workspace members can read rooms"
on public.rooms
for select
using (
    exists (
        select 1
        from public.workspace_members wm
        where wm.workspace_id = rooms.workspace_id
          and wm.user_id = auth.uid()
    )
);

drop policy if exists "workspace members can create rooms" on public.rooms;
create policy "workspace members can create rooms"
on public.rooms
for insert
with check (
    exists (
        select 1
        from public.workspace_members wm
        where wm.workspace_id = rooms.workspace_id
          and wm.user_id = auth.uid()
    )
);

drop policy if exists "workspace members can update rooms" on public.rooms;
create policy "workspace members can update rooms"
on public.rooms
for update
using (
    exists (
        select 1
        from public.workspace_members wm
        where wm.workspace_id = rooms.workspace_id
          and wm.user_id = auth.uid()
    )
);

drop policy if exists "workspace members can read participants" on public.room_participants;
create policy "workspace members can read participants"
on public.room_participants
for select
using (
    exists (
        select 1
        from public.rooms r
        join public.workspace_members wm on wm.workspace_id = r.workspace_id
        where r.room_code = room_participants.room_code
          and wm.user_id = auth.uid()
    )
);

drop policy if exists "workspace members can create participants" on public.room_participants;
create policy "workspace members can create participants"
on public.room_participants
for insert
with check (
    exists (
        select 1
        from public.rooms r
        join public.workspace_members wm on wm.workspace_id = r.workspace_id
        where r.room_code = room_participants.room_code
          and wm.user_id = auth.uid()
    )
);

drop policy if exists "workspace members can update participants" on public.room_participants;
create policy "workspace members can update participants"
on public.room_participants
for update
using (
    exists (
        select 1
        from public.rooms r
        join public.workspace_members wm on wm.workspace_id = r.workspace_id
        where r.room_code = room_participants.room_code
          and wm.user_id = auth.uid()
    )
);

drop policy if exists "workspace members can read summaries" on public.summaries;
create policy "workspace members can read summaries"
on public.summaries
for select
using (
    exists (
        select 1
        from public.workspace_members wm
        where wm.workspace_id = summaries.workspace_id
          and wm.user_id = auth.uid()
    )
);

drop policy if exists "workspace members can create summaries" on public.summaries;
create policy "workspace members can create summaries"
on public.summaries
for insert
with check (
    exists (
        select 1
        from public.workspace_members wm
        where wm.workspace_id = summaries.workspace_id
          and wm.user_id = auth.uid()
    )
);

drop policy if exists "workspace members can update summaries" on public.summaries;
create policy "workspace members can update summaries"
on public.summaries
for update
using (
    exists (
        select 1
        from public.workspace_members wm
        where wm.workspace_id = summaries.workspace_id
          and wm.user_id = auth.uid()
    )
);
