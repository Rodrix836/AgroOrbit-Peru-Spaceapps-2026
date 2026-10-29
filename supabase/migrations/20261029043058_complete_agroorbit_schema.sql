-- Modelo completo de persistencia para el MVP. No agrega reglas ni valores
-- agronomicos sin fuente: el catalogo se poblara con evidencia verificable.

create table public.app_user (
    id uuid primary key default gen_random_uuid(),
    auth_user_id uuid unique references auth.users(id) on delete set null,
    display_name text not null check (length(btrim(display_name)) > 0),
    created_at timestamptz not null default now()
);

create table public.agronomic_source (
    id uuid primary key default gen_random_uuid(),
    citation text not null check (length(btrim(citation)) > 0),
    publisher text,
    url text,
    publication_year integer check (publication_year between 1800 and 2100),
    accessed_at date,
    created_at timestamptz not null default now()
);

create table public.crop (
    id uuid primary key default gen_random_uuid(),
    code text not null unique check (code ~ '^[a-z0-9_]+$'),
    name text not null check (length(btrim(name)) > 0),
    scientific_name text,
    botanical_family text,
    functional_group text,
    is_perennial boolean not null default false,
    cycle_min_days integer,
    cycle_max_days integer,
    cycle_source_id uuid references public.agronomic_source(id) on delete restrict,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    constraint crop_cycle_range check (
        (cycle_min_days is null and cycle_max_days is null and cycle_source_id is null)
        or (cycle_min_days > 0 and cycle_max_days >= cycle_min_days and cycle_source_id is not null)
    )
);

create index crop_cycle_source_id_idx on public.crop (cycle_source_id)
    where cycle_source_id is not null;

create table public.crop_requirement (
    id uuid primary key default gen_random_uuid(),
    crop_id uuid not null references public.crop(id) on delete cascade,
    criterion text not null check (length(btrim(criterion)) > 0),
    value jsonb not null check (jsonb_typeof(value) = 'object'),
    unit text,
    source_id uuid not null references public.agronomic_source(id) on delete restrict,
    evidence_level text not null check (evidence_level in ('A', 'B', 'C')),
    region_validity text,
    notes text,
    created_at timestamptz not null default now()
);

create index crop_requirement_crop_criterion_idx on public.crop_requirement (crop_id, criterion);
create index crop_requirement_source_id_idx on public.crop_requirement (source_id);

create table public.rotation_rule (
    id uuid primary key default gen_random_uuid(),
    rule_kind text not null check (rule_kind in (
        'same_crop', 'same_family', 'crop_pair', 'family_pair', 'group_pair'
    )),
    predecessor_crop_id uuid references public.crop(id) on delete restrict,
    successor_crop_id uuid references public.crop(id) on delete restrict,
    predecessor_family text,
    successor_family text,
    predecessor_group text,
    successor_group text,
    effect text not null check (effect in ('benefit', 'penalty', 'exclude')),
    weight numeric(5, 4) check (weight between 0 and 1),
    rationale text not null check (length(btrim(rationale)) > 0),
    source_id uuid not null references public.agronomic_source(id) on delete restrict,
    evidence_level text not null check (evidence_level in ('A', 'B', 'C')),
    region_validity text,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    constraint rotation_rule_scope check (
        (rule_kind in ('same_crop', 'same_family')
            and predecessor_crop_id is null and successor_crop_id is null
            and predecessor_family is null and successor_family is null
            and predecessor_group is null and successor_group is null)
        or (rule_kind = 'crop_pair'
            and predecessor_crop_id is not null and successor_crop_id is not null
            and predecessor_family is null and successor_family is null
            and predecessor_group is null and successor_group is null)
        or (rule_kind = 'family_pair'
            and predecessor_crop_id is null and successor_crop_id is null
            and predecessor_family is not null and successor_family is not null
            and predecessor_group is null and successor_group is null)
        or (rule_kind = 'group_pair'
            and predecessor_crop_id is null and successor_crop_id is null
            and predecessor_family is null and successor_family is null
            and predecessor_group is not null and successor_group is not null)
    )
);

create index rotation_rule_predecessor_crop_id_idx on public.rotation_rule (predecessor_crop_id)
    where predecessor_crop_id is not null;
create index rotation_rule_successor_crop_id_idx on public.rotation_rule (successor_crop_id)
    where successor_crop_id is not null;
create index rotation_rule_source_id_idx on public.rotation_rule (source_id);

-- La tabla plot ya existe. Esta migracion se aplica antes de registrar parcelas.
alter table public.plot
    alter column id set default gen_random_uuid(),
    add column user_id uuid not null references public.app_user(id) on delete cascade,
    add column area_ha numeric(12, 4) check (area_ha > 0),
    add column water_source text,
    add column water_availability text check (water_availability in ('low', 'medium', 'high')),
    add column soil_texture text,
    add column soil_ph numeric(4, 2) check (soil_ph between 0 and 14),
    add column soil_salinity_ds_m numeric(8, 3) check (soil_salinity_ds_m >= 0),
    add column priority text check (priority in (
        'save_water', 'improve_soil', 'reduce_climate_risk',
        'diversify', 'maintain_productivity'
    )),
    add column declared_irrigated boolean,
    add column lgrip_class smallint check (lgrip_class between 0 and 3),
    add column lgrip_year integer check (lgrip_year between 1900 and 2100);

create index plot_user_id_idx on public.plot (user_id);

alter table public.nasa_observation
    alter column id set default gen_random_uuid(),
    add column collection_concept_id text,
    add column grid_cell_key text;

create table public.crop_cycle (
    id uuid primary key default gen_random_uuid(),
    plot_id uuid not null references public.plot(id) on delete cascade,
    crop_id uuid not null references public.crop(id) on delete restrict,
    sowing_date date not null,
    harvest_date date,
    status text not null check (status in ('active', 'finished', 'planned')),
    origin text not null check (origin in ('farmer', 'recommendation')),
    created_at timestamptz not null default now(),
    constraint crop_cycle_dates check (harvest_date is null or harvest_date >= sowing_date),
    constraint crop_cycle_finished_date check (status <> 'finished' or harvest_date is not null)
);

create index crop_cycle_plot_sowing_idx on public.crop_cycle (plot_id, sowing_date desc);
create index crop_cycle_crop_id_idx on public.crop_cycle (crop_id);
create unique index crop_cycle_one_active_per_plot_idx on public.crop_cycle (plot_id)
    where status = 'active';

create table public.device (
    id uuid primary key default gen_random_uuid(),
    plot_id uuid not null references public.plot(id) on delete cascade,
    external_id text not null unique check (length(btrim(external_id)) > 0),
    model text,
    status text not null default 'active' check (status in ('active', 'inactive')),
    installed_at timestamptz,
    created_at timestamptz not null default now()
);

create index device_plot_id_idx on public.device (plot_id);

create table public.sensor_reading (
    id uuid primary key default gen_random_uuid(),
    device_id uuid not null references public.device(id) on delete cascade,
    observed_at timestamptz not null,
    variable text not null check (length(btrim(variable)) > 0),
    raw_value numeric(14, 5) not null,
    calibrated_value numeric(14, 5),
    unit text not null,
    quality_flag text,
    received_at timestamptz not null default now(),
    constraint sensor_reading_unique_value unique (device_id, variable, observed_at)
);

create index sensor_reading_device_time_idx on public.sensor_reading (device_id, observed_at desc);

create table public.indicator (
    id uuid primary key default gen_random_uuid(),
    plot_id uuid not null references public.plot(id) on delete cascade,
    name text not null check (length(btrim(name)) > 0),
    value_numeric numeric(14, 5),
    value_text text,
    unit text,
    window_start timestamptz not null,
    window_end timestamptz not null,
    calculation_version text not null,
    source_refs jsonb not null default '[]'::jsonb check (jsonb_typeof(source_refs) = 'array'),
    computed_at timestamptz not null default now(),
    constraint indicator_one_value check ((value_numeric is null) <> (value_text is null)),
    constraint indicator_window check (window_end >= window_start)
);

create index indicator_plot_name_time_idx on public.indicator (plot_id, name, window_end desc);

create table public.recommendation (
    id uuid primary key default gen_random_uuid(),
    plot_id uuid not null references public.plot(id) on delete cascade,
    generated_at timestamptz not null default now(),
    horizon_days integer not null check (horizon_days between 1 and 730),
    priority text not null check (priority in (
        'save_water', 'improve_soil', 'reduce_climate_risk',
        'diversify', 'maintain_productivity'
    )),
    engine_version text not null,
    status text not null check (status in ('ready', 'insufficient_data')),
    confidence text not null check (confidence in ('high', 'medium', 'low', 'insufficient')),
    recommended_crop_id uuid references public.crop(id) on delete restrict,
    input_snapshot jsonb not null check (jsonb_typeof(input_snapshot) = 'object'),
    summary text,
    constraint recommendation_status_crop check (
        (status = 'ready' and recommended_crop_id is not null and confidence <> 'insufficient')
        or (status = 'insufficient_data' and recommended_crop_id is null and confidence = 'insufficient')
    )
);

create index recommendation_plot_generated_idx on public.recommendation (plot_id, generated_at desc);
create index recommendation_recommended_crop_id_idx on public.recommendation (recommended_crop_id)
    where recommended_crop_id is not null;

create table public.recommendation_item (
    id uuid primary key default gen_random_uuid(),
    recommendation_id uuid not null references public.recommendation(id) on delete cascade,
    crop_id uuid not null references public.crop(id) on delete restrict,
    rank integer check (rank > 0),
    score numeric(6, 5) check (score between 0 and 1),
    eligible boolean not null,
    reasons jsonb not null default '[]'::jsonb check (jsonb_typeof(reasons) = 'array'),
    limiting_factors jsonb not null default '[]'::jsonb check (jsonb_typeof(limiting_factors) = 'array'),
    exclusion_reason text,
    constraint recommendation_item_unique_crop unique (recommendation_id, crop_id),
    constraint recommendation_item_eligibility check (
        (eligible and rank is not null and score is not null and exclusion_reason is null)
        or (not eligible and rank is null and score is null and exclusion_reason is not null)
    )
);

create unique index recommendation_item_rank_idx
    on public.recommendation_item (recommendation_id, rank) where rank is not null;
create index recommendation_item_crop_id_idx on public.recommendation_item (crop_id);

create table public.rotation_plan (
    id uuid primary key default gen_random_uuid(),
    recommendation_id uuid not null references public.recommendation(id) on delete cascade,
    step integer not null check (step > 0),
    action text not null check (action in ('crop', 'fallow')),
    crop_id uuid references public.crop(id) on delete restrict,
    start_on date not null,
    end_on date not null,
    climate_basis text not null check (climate_basis in ('recent', 'historical')),
    confidence text not null check (confidence in ('high', 'medium', 'low')),
    reason text,
    constraint rotation_plan_unique_step unique (recommendation_id, step),
    constraint rotation_plan_dates check (end_on >= start_on),
    constraint rotation_plan_action_crop check (
        (action = 'crop' and crop_id is not null)
        or (action = 'fallow' and crop_id is null)
    )
);

create index rotation_plan_crop_id_idx on public.rotation_plan (crop_id)
    where crop_id is not null;

-- Solo el backend tiene acceso directo a PostgreSQL en esta etapa. Los
-- clientes anon/authenticated no obtienen permisos ni politicas de lectura.
alter table public.app_user enable row level security;
alter table public.agronomic_source enable row level security;
alter table public.crop enable row level security;
alter table public.crop_requirement enable row level security;
alter table public.rotation_rule enable row level security;
alter table public.crop_cycle enable row level security;
alter table public.device enable row level security;
alter table public.sensor_reading enable row level security;
alter table public.indicator enable row level security;
alter table public.recommendation enable row level security;
alter table public.recommendation_item enable row level security;
alter table public.rotation_plan enable row level security;

revoke all on public.app_user, public.agronomic_source, public.crop,
    public.crop_requirement, public.rotation_rule, public.crop_cycle,
    public.device, public.sensor_reading, public.indicator,
    public.recommendation, public.recommendation_item,
    public.rotation_plan from anon, authenticated;
