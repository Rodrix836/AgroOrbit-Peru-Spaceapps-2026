-- Esquema inicial. Aplicar con Supabase CLI; no crear estas tablas manualmente.
create table public.plot (
    id uuid primary key,
    name varchar(120) not null,
    latitude numeric(9, 6) not null,
    longitude numeric(9, 6) not null,
    created_at timestamptz not null default now(),
    constraint plot_latitude_range check (latitude between -90 and 90),
    constraint plot_longitude_range check (longitude between -180 and 180)
);

create table public.nasa_observation (
    id uuid primary key,
    plot_id uuid not null references public.plot(id) on delete cascade,
    dataset varchar(80) not null,
    dataset_version varchar(40) not null default 'unspecified',
    variable varchar(80) not null,
    observed_at timestamptz not null,
    value double precision not null,
    unit varchar(40) not null,
    quality_flag varchar(40),
    fetched_at timestamptz not null default now(),
    constraint nasa_observation_unique_value unique (
        plot_id, dataset, dataset_version, variable, observed_at
    )
);

create index nasa_observation_plot_time_idx
    on public.nasa_observation (plot_id, observed_at);

-- El MVP accede a PostgreSQL desde FastAPI. No exponemos estas tablas
-- directamente a usuarios anónimos o autenticados por la Data API.
alter table public.plot enable row level security;
alter table public.nasa_observation enable row level security;
revoke all on public.plot, public.nasa_observation from anon, authenticated;
