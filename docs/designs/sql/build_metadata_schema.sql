-- bamboo_spec_generator build metadata schema draft
-- Target DBMS: PostgreSQL

create table project (
    id uuid primary key,
    jira_project_key varchar(64) not null unique,
    bitbucket_project_key varchar(64) not null,
    representative_repo_slug varchar(255),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table build_plan (
    id uuid primary key,
    build_id varchar(255) not null unique,
    plan_key varchar(64) not null unique,
    latest_version_id uuid,
    active_definition_id uuid,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table project_repository (
    id uuid primary key,
    project_id uuid not null references project(id),
    repo_slug varchar(255) not null,
    coverity_project varchar(255),
    coverity_stream varchar(255),
    is_representative boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (project_id, repo_slug)
);

create unique index uq_project_repository_representative
    on project_repository(project_id)
    where is_representative = true;

create table project_build (
    id uuid primary key,
    project_id uuid not null references project(id),
    build_plan_id uuid not null unique references build_plan(id),
    build_name varchar(255) not null,
    build_type varchar(128) not null,
    runtime_stack varchar(128),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (project_id, build_name)
);

create table build_plan_definition (
    id uuid primary key,
    build_plan_id uuid not null references build_plan(id),
    project_id uuid not null references project(id),
    source_kind varchar(32) not null,
    definition_json jsonb not null,
    definition_hash varchar(128) not null,
    is_active boolean not null default false,
    created_at timestamptz not null default now(),
    unique (build_plan_id, definition_hash),
    check (source_kind in ('json', 'db', 'import'))
);

create unique index uq_build_plan_definition_active
    on build_plan_definition(build_plan_id)
    where is_active = true;

create table build_definition_history (
    id uuid primary key,
    build_plan_id uuid not null references build_plan(id),
    build_plan_definition_id uuid not null references build_plan_definition(id),
    change_type varchar(64) not null,
    change_summary text,
    created_at timestamptz not null default now()
);

create table build_version (
    id uuid primary key,
    build_plan_id uuid not null references build_plan(id),
    version_text varchar(32) not null,
    major integer not null check (major >= 0),
    minor integer not null check (minor >= 0),
    patch integer not null check (patch >= 0),
    branch_kind varchar(16) not null,
    commit_hash varchar(64) not null,
    is_latest boolean not null default false,
    latest_execution_id uuid,
    latest_success boolean,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (build_plan_id, version_text),
    unique (build_plan_id, commit_hash),
    check (branch_kind in ('master', 'release', 'dev'))
);

create unique index uq_build_version_latest
    on build_version(build_plan_id)
    where is_latest = true;

create table build_execution (
    id uuid primary key,
    build_plan_id uuid not null references build_plan(id),
    build_version_id uuid not null references build_version(id),
    build_number varchar(64) not null,
    commit_hash varchar(64) not null,
    success boolean not null,
    result_status varchar(64) not null,
    summary_message text,
    stage_name varchar(255),
    job_name varchar(255),
    task_name varchar(255),
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz not null default now(),
    unique (build_plan_id, build_number)
);

create table static_analysis_result (
    id uuid primary key,
    build_execution_id uuid not null references build_execution(id),
    tool_name varchar(64) not null,
    status varchar(64) not null,
    summary text,
    metrics_json jsonb,
    created_at timestamptz not null default now(),
    unique (build_execution_id, tool_name)
);

alter table build_plan
    add constraint fk_build_plan_latest_version
    foreign key (latest_version_id) references build_version(id);

alter table build_plan
    add constraint fk_build_plan_active_definition
    foreign key (active_definition_id) references build_plan_definition(id);

alter table build_version
    add constraint fk_build_version_latest_execution
    foreign key (latest_execution_id) references build_execution(id);

create index ix_project_repository_project_repr
    on project_repository(project_id, is_representative);

create index ix_project_build_project_name
    on project_build(project_id, build_name);

create index ix_build_plan_definition_build_active
    on build_plan_definition(build_plan_id, is_active);

create index ix_build_version_build_latest
    on build_version(build_plan_id, is_latest);

create index ix_build_version_build_commit
    on build_version(build_plan_id, commit_hash);

create index ix_build_execution_build_created
    on build_execution(build_version_id, created_at desc);

create index ix_build_execution_plan_number
    on build_execution(build_plan_id, build_number desc);

create index ix_static_analysis_execution_tool
    on static_analysis_result(build_execution_id, tool_name);
