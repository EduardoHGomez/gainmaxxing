-- =========================================================================
-- entries: every meal/snack the user actually ate, day by day
-- =========================================================================
create table public.entries (
  id            bigint generated always as identity primary key,
  created_at    timestamptz not null default now(),
  date          date        not null default ((now() at time zone 'America/Mexico_City')::date),
  meal_type     text        check (meal_type in ('breakfast','lunch','dinner','snack','pre-workout','post-workout','other')),
  food          text        not null,
  calories      integer     not null check (calories >= 0 and calories < 10000),
  protein_g     numeric(5,1)         check (protein_g >= 0 and protein_g < 500),
  notes         text
);

create index idx_entries_date       on public.entries (date desc);
create index idx_entries_created_at on public.entries (created_at desc);

-- =========================================================================
-- meals: curated catalog of foods/meals that have worked (preferences)
-- =========================================================================
create table public.meals (
  id            bigint generated always as identity primary key,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  name          text        not null,
  food          text        not null,
  portion       text,
  meal_type     text        check (meal_type in ('breakfast','lunch','dinner','snack','pre-workout','post-workout','other')),
  calories      integer     not null check (calories >= 0 and calories < 10000),
  protein_g     numeric(5,1)         check (protein_g >= 0 and protein_g < 500),
  notes         text
);

create index idx_meals_meal_type      on public.meals (meal_type);
create unique index idx_meals_name_ci on public.meals (lower(name));

-- updated_at auto-bump on update
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger meals_set_updated_at
before update on public.meals
for each row execute function public.set_updated_at();

-- =========================================================================
-- Roles & RLS
--
-- Supabase auto-creates three Postgres roles on every new project:
--   anon          -> mapped to the "publishable" / legacy "anon" API key
--   authenticated -> a logged-in user (we don't use Supabase Auth here)
--   service_role  -> mapped to the "secret" / legacy "service_role" key,
--                    BYPASSES RLS by design
--
-- The bot uses the service_role key (server-side only). RLS is enabled so
-- that if the anon/authenticated keys ever leak, no rows are exposed.
-- We add zero policies for anon/authenticated, which means: "RLS denies
-- everything for those roles." service_role still has full access because
-- it bypasses RLS at the engine level.
--
-- The grants below are explicit so the schema is self-documenting and
-- portable to non-Supabase Postgres: revoke from anon/authenticated, grant
-- to service_role.
-- =========================================================================

alter table public.entries enable row level security;
alter table public.meals   enable row level security;

-- Belt-and-suspenders: explicitly revoke any public/anon table privileges
-- (Supabase grants some by default to anon/authenticated for new tables).
revoke all on public.entries from anon, authenticated;
revoke all on public.meals   from anon, authenticated;

-- Ensure the service_role can do everything (it can already, but be explicit).
grant all on public.entries to service_role;
grant all on public.meals   to service_role;
grant usage, select on all sequences in schema public to service_role;
