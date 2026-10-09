\restrict dbmate

-- Dumped from database version 16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: channel_kind; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.channel_kind AS ENUM (
    'webpush',
    'email',
    'telegram'
);


--
-- Name: delivery_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.delivery_status AS ENUM (
    'queued',
    'sent',
    'failed',
    'skipped'
);


--
-- Name: direction; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.direction AS ENUM (
    'long',
    'short'
);


--
-- Name: econ_impact; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.econ_impact AS ENUM (
    'high',
    'medium',
    'low'
);


--
-- Name: level_set; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.level_set AS ENUM (
    'daily',
    'weekly',
    'monthly',
    'prev_day',
    'fib_pivot'
);


--
-- Name: rule_kind; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.rule_kind AS ENUM (
    'indicator',
    'gate',
    'plan',
    'filter',
    'lifecycle'
);


--
-- Name: rule_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.rule_status AS ENUM (
    'approved',
    'provisional'
);


--
-- Name: screen_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.screen_status AS ENUM (
    'qualified',
    'trend_established',
    'trend_confirmed'
);


--
-- Name: signal_state; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.signal_state AS ENUM (
    'open',
    'confirmed',
    'target_hit',
    'stop_hit',
    'expired',
    'invalidated',
    'ambiguous'
);


--
-- Name: strategy_key; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.strategy_key AS ENUM (
    'three_eight',
    'fib_pivot',
    'stocks'
);


--
-- Name: user_role; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.user_role AS ENUM (
    'owner',
    'admin'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounts (
    user_id uuid NOT NULL,
    type text NOT NULL,
    provider text NOT NULL,
    provider_account_id text NOT NULL,
    refresh_token text,
    access_token text,
    expires_at integer,
    token_type text,
    scope text,
    id_token text,
    session_state text
);


--
-- Name: allowlist; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.allowlist (
    email text NOT NULL,
    added_by uuid,
    added_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: app_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.app_settings (
    id boolean DEFAULT true NOT NULL,
    forex_enabled boolean DEFAULT true NOT NULL,
    updated_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT app_settings_id_check CHECK (id)
);


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    id bigint NOT NULL,
    at timestamp with time zone DEFAULT now() NOT NULL,
    user_id uuid,
    action text NOT NULL,
    target text,
    before jsonb,
    after jsonb
);


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;


--
-- Name: broker_spreads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.broker_spreads (
    broker_id uuid NOT NULL,
    instrument_id uuid NOT NULL,
    typical_spread_pips numeric(8,2) NOT NULL,
    symbol_override text
);


--
-- Name: brokers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.brokers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    platform_url_template text,
    notes text,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: candles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.candles (
    instrument_id uuid NOT NULL,
    granularity text NOT NULL,
    ts timestamp with time zone NOT NULL,
    o numeric(18,8) NOT NULL,
    h numeric(18,8) NOT NULL,
    l numeric(18,8) NOT NULL,
    c numeric(18,8) NOT NULL,
    volume integer DEFAULT 0 NOT NULL
);


--
-- Name: econ_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.econ_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    at timestamp with time zone NOT NULL,
    currency character(3) NOT NULL,
    title text NOT NULL,
    impact public.econ_impact DEFAULT 'high'::public.econ_impact NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: health_alerts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.health_alerts (
    condition text NOT NULL,
    first_seen_at timestamp with time zone NOT NULL,
    last_sent_at timestamp with time zone,
    resolved_at timestamp with time zone,
    detail jsonb DEFAULT '{}'::jsonb NOT NULL
);


--
-- Name: holdings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.holdings (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid,
    ticker text NOT NULL,
    purchase_price numeric(18,6) NOT NULL,
    purchase_date date NOT NULL,
    expected_profit_pct numeric(6,2) DEFAULT 30 NOT NULL,
    horizon_sessions smallint DEFAULT 20 NOT NULL,
    closed boolean DEFAULT false NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: instruments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.instruments (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    symbol text NOT NULL,
    provider_code text NOT NULL,
    asset_class text DEFAULT 'forex'::text NOT NULL,
    pip_size numeric(12,8) NOT NULL,
    display_decimals smallint NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    sort_order smallint DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: job_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.job_runs (
    id bigint NOT NULL,
    job text NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone,
    ok boolean,
    detail jsonb
);


--
-- Name: job_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.job_runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: job_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.job_runs_id_seq OWNED BY public.job_runs.id;


--
-- Name: levels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.levels (
    instrument_id uuid NOT NULL,
    trading_day date NOT NULL,
    set_kind public.level_set NOT NULL,
    data jsonb NOT NULL,
    computed_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: market_holidays; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.market_holidays (
    day date NOT NULL,
    market text NOT NULL,
    note text
);


--
-- Name: notification_prefs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification_prefs (
    user_id uuid NOT NULL,
    channels public.channel_kind[] DEFAULT '{webpush,email}'::public.channel_kind[] NOT NULL,
    strategies public.strategy_key[] DEFAULT '{three_eight,fib_pivot,stocks}'::public.strategy_key[] NOT NULL,
    instrument_ids uuid[],
    quiet_start time without time zone,
    quiet_end time without time zone,
    include_updates boolean DEFAULT true NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id bigint NOT NULL,
    user_id uuid,
    signal_id uuid,
    kind text NOT NULL,
    channel public.channel_kind NOT NULL,
    status public.delivery_status DEFAULT 'queued'::public.delivery_status NOT NULL,
    attempts smallint DEFAULT 0 NOT NULL,
    error text,
    payload jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    sent_at timestamp with time zone,
    next_attempt_at timestamp with time zone,
    dedupe_key text
);


--
-- Name: notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.notifications_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.notifications_id_seq OWNED BY public.notifications.id;


--
-- Name: notify_cursor; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notify_cursor (
    name text NOT NULL,
    last_id bigint DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: push_subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.push_subscriptions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid,
    endpoint text NOT NULL,
    p256dh text NOT NULL,
    auth text NOT NULL,
    user_agent text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_success_at timestamp with time zone
);


--
-- Name: rule_config_revision; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rule_config_revision (
    id boolean DEFAULT true NOT NULL,
    revision bigint DEFAULT 1 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT rule_config_revision_id_check CHECK (id)
);


--
-- Name: rule_definitions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rule_definitions (
    key text NOT NULL,
    strategy public.strategy_key NOT NULL,
    kind public.rule_kind NOT NULL,
    name text NOT NULL,
    source text NOT NULL,
    current_version integer NOT NULL
);


--
-- Name: rule_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rule_versions (
    key text NOT NULL,
    version integer NOT NULL,
    status public.rule_status NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    counts_toward_minimum boolean DEFAULT false NOT NULL,
    description text NOT NULL,
    params_schema jsonb NOT NULL,
    params jsonb NOT NULL,
    change_note text,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version character varying NOT NULL
);


--
-- Name: sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sessions (
    session_token text NOT NULL,
    user_id uuid NOT NULL,
    expires timestamp with time zone NOT NULL
);


--
-- Name: signal_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signal_events (
    id bigint NOT NULL,
    signal_id uuid,
    at timestamp with time zone DEFAULT now() NOT NULL,
    kind text NOT NULL,
    price numeric(18,8),
    note text
);


--
-- Name: signal_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.signal_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: signal_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.signal_events_id_seq OWNED BY public.signal_events.id;


--
-- Name: signal_indicators; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signal_indicators (
    signal_id uuid NOT NULL,
    key text NOT NULL,
    version integer NOT NULL,
    fired boolean NOT NULL,
    counted boolean NOT NULL,
    provisional boolean NOT NULL,
    level_ref text,
    detail jsonb NOT NULL
);


--
-- Name: signals; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signals (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    strategy public.strategy_key NOT NULL,
    instrument_id uuid,
    direction public.direction NOT NULL,
    state public.signal_state DEFAULT 'open'::public.signal_state NOT NULL,
    bar_ts timestamp with time zone NOT NULL,
    trading_day date NOT NULL,
    entry numeric(18,8) NOT NULL,
    stop numeric(18,8) NOT NULL,
    target numeric(18,8) NOT NULL,
    alt_target numeric(18,8),
    risk_pips numeric(10,2) NOT NULL,
    reward_pips numeric(10,2) NOT NULL,
    reward_risk numeric(8,3) NOT NULL,
    indicator_count smallint,
    has_provisional boolean DEFAULT false NOT NULL,
    is_countertrend boolean DEFAULT false NOT NULL,
    range_mode boolean DEFAULT false NOT NULL,
    version_set jsonb NOT NULL,
    context jsonb NOT NULL,
    dedupe_key text NOT NULL,
    closed_at timestamp with time zone,
    exit_price numeric(18,8),
    result_pips numeric(10,2),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: stock_daily_bars; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stock_daily_bars (
    ticker text NOT NULL,
    session_date date NOT NULL,
    o numeric(18,6) NOT NULL,
    h numeric(18,6) NOT NULL,
    l numeric(18,6) NOT NULL,
    c numeric(18,6) NOT NULL,
    volume bigint NOT NULL
);


--
-- Name: stock_screen_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stock_screen_results (
    session_date date NOT NULL,
    ticker text NOT NULL,
    status public.screen_status NOT NULL,
    close numeric(18,6) NOT NULL,
    high_52w numeric(18,6) NOT NULL,
    low_52w numeric(18,6) NOT NULL,
    apr_52w numeric(12,6) NOT NULL,
    close_5 numeric(18,6),
    close_10 numeric(18,6),
    close_20 numeric(18,6),
    close_50 numeric(18,6),
    acc_5 numeric(12,6),
    acc_10 numeric(12,6),
    acc_20 numeric(12,6),
    acc_50 numeric(12,6),
    apr_5 numeric(14,6),
    apr_10 numeric(14,6),
    apr_20 numeric(14,6),
    apr_50 numeric(14,6),
    consistent boolean DEFAULT false NOT NULL,
    version_set jsonb NOT NULL
);


--
-- Name: stock_tickers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stock_tickers (
    ticker text NOT NULL,
    name text,
    exchange text,
    active boolean DEFAULT true NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: strategy_configs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.strategy_configs (
    strategy public.strategy_key NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    instrument_ids uuid[],
    notes text,
    updated_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: strategy_param_overrides; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.strategy_param_overrides (
    key text NOT NULL,
    instrument_id uuid NOT NULL,
    params jsonb NOT NULL,
    updated_by uuid,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: telegram_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.telegram_links (
    user_id uuid NOT NULL,
    chat_id bigint,
    link_token text,
    linked_at timestamp with time zone
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    email text NOT NULL,
    name text,
    role public.user_role DEFAULT 'owner'::public.user_role NOT NULL,
    active boolean DEFAULT true NOT NULL,
    timezone text DEFAULT 'America/New_York'::text NOT NULL,
    active_broker_id uuid,
    acknowledged_notice_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    email_verified timestamp with time zone,
    image text
);


--
-- Name: verification_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.verification_tokens (
    identifier text NOT NULL,
    token text NOT NULL,
    expires timestamp with time zone NOT NULL
);


--
-- Name: worker_heartbeat; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.worker_heartbeat (
    id boolean DEFAULT true NOT NULL,
    at timestamp with time zone NOT NULL,
    version text,
    market jsonb,
    CONSTRAINT worker_heartbeat_id_check CHECK (id)
);


--
-- Name: audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);


--
-- Name: job_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_runs ALTER COLUMN id SET DEFAULT nextval('public.job_runs_id_seq'::regclass);


--
-- Name: notifications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications ALTER COLUMN id SET DEFAULT nextval('public.notifications_id_seq'::regclass);


--
-- Name: signal_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_events ALTER COLUMN id SET DEFAULT nextval('public.signal_events_id_seq'::regclass);


--
-- Name: accounts accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (provider, provider_account_id);


--
-- Name: allowlist allowlist_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.allowlist
    ADD CONSTRAINT allowlist_pkey PRIMARY KEY (email);


--
-- Name: app_settings app_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT app_settings_pkey PRIMARY KEY (id);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: broker_spreads broker_spreads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.broker_spreads
    ADD CONSTRAINT broker_spreads_pkey PRIMARY KEY (broker_id, instrument_id);


--
-- Name: brokers brokers_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brokers
    ADD CONSTRAINT brokers_name_key UNIQUE (name);


--
-- Name: brokers brokers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.brokers
    ADD CONSTRAINT brokers_pkey PRIMARY KEY (id);


--
-- Name: candles candles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candles
    ADD CONSTRAINT candles_pkey PRIMARY KEY (instrument_id, granularity, ts);


--
-- Name: econ_events econ_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.econ_events
    ADD CONSTRAINT econ_events_pkey PRIMARY KEY (id);


--
-- Name: health_alerts health_alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.health_alerts
    ADD CONSTRAINT health_alerts_pkey PRIMARY KEY (condition);


--
-- Name: holdings holdings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.holdings
    ADD CONSTRAINT holdings_pkey PRIMARY KEY (id);


--
-- Name: instruments instruments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.instruments
    ADD CONSTRAINT instruments_pkey PRIMARY KEY (id);


--
-- Name: instruments instruments_symbol_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.instruments
    ADD CONSTRAINT instruments_symbol_key UNIQUE (symbol);


--
-- Name: job_runs job_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.job_runs
    ADD CONSTRAINT job_runs_pkey PRIMARY KEY (id);


--
-- Name: levels levels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.levels
    ADD CONSTRAINT levels_pkey PRIMARY KEY (instrument_id, trading_day, set_kind);


--
-- Name: market_holidays market_holidays_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_holidays
    ADD CONSTRAINT market_holidays_pkey PRIMARY KEY (day);


--
-- Name: notification_prefs notification_prefs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_prefs
    ADD CONSTRAINT notification_prefs_pkey PRIMARY KEY (user_id);


--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);


--
-- Name: notify_cursor notify_cursor_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notify_cursor
    ADD CONSTRAINT notify_cursor_pkey PRIMARY KEY (name);


--
-- Name: push_subscriptions push_subscriptions_endpoint_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_endpoint_key UNIQUE (endpoint);


--
-- Name: push_subscriptions push_subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_pkey PRIMARY KEY (id);


--
-- Name: rule_config_revision rule_config_revision_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rule_config_revision
    ADD CONSTRAINT rule_config_revision_pkey PRIMARY KEY (id);


--
-- Name: rule_definitions rule_definitions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rule_definitions
    ADD CONSTRAINT rule_definitions_pkey PRIMARY KEY (key);


--
-- Name: rule_versions rule_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rule_versions
    ADD CONSTRAINT rule_versions_pkey PRIMARY KEY (key, version);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (session_token);


--
-- Name: signal_events signal_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_events
    ADD CONSTRAINT signal_events_pkey PRIMARY KEY (id);


--
-- Name: signal_indicators signal_indicators_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_indicators
    ADD CONSTRAINT signal_indicators_pkey PRIMARY KEY (signal_id, key);


--
-- Name: signals signals_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT signals_pkey PRIMARY KEY (id);


--
-- Name: stock_daily_bars stock_daily_bars_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_daily_bars
    ADD CONSTRAINT stock_daily_bars_pkey PRIMARY KEY (ticker, session_date);


--
-- Name: stock_screen_results stock_screen_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_screen_results
    ADD CONSTRAINT stock_screen_results_pkey PRIMARY KEY (session_date, ticker);


--
-- Name: stock_tickers stock_tickers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_tickers
    ADD CONSTRAINT stock_tickers_pkey PRIMARY KEY (ticker);


--
-- Name: strategy_configs strategy_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategy_configs
    ADD CONSTRAINT strategy_configs_pkey PRIMARY KEY (strategy);


--
-- Name: strategy_param_overrides strategy_param_overrides_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategy_param_overrides
    ADD CONSTRAINT strategy_param_overrides_pkey PRIMARY KEY (key, instrument_id);


--
-- Name: telegram_links telegram_links_link_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_links
    ADD CONSTRAINT telegram_links_link_token_key UNIQUE (link_token);


--
-- Name: telegram_links telegram_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_links
    ADD CONSTRAINT telegram_links_pkey PRIMARY KEY (user_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: verification_tokens verification_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.verification_tokens
    ADD CONSTRAINT verification_tokens_pkey PRIMARY KEY (identifier, token);


--
-- Name: worker_heartbeat worker_heartbeat_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.worker_heartbeat
    ADD CONSTRAINT worker_heartbeat_pkey PRIMARY KEY (id);


--
-- Name: econ_events_at_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX econ_events_at_idx ON public.econ_events USING btree (at);


--
-- Name: job_runs_job_started_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX job_runs_job_started_idx ON public.job_runs USING btree (job, started_at DESC);


--
-- Name: notifications_dedupe_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX notifications_dedupe_idx ON public.notifications USING btree (dedupe_key, COALESCE(user_id, '00000000-0000-0000-0000-000000000000'::uuid), channel) WHERE (dedupe_key IS NOT NULL);


--
-- Name: notifications_due_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX notifications_due_idx ON public.notifications USING btree (next_attempt_at) WHERE (status = 'queued'::public.delivery_status);


--
-- Name: signals_created_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX signals_created_idx ON public.signals USING btree (created_at DESC);


--
-- Name: signals_dedupe_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX signals_dedupe_idx ON public.signals USING btree (dedupe_key);


--
-- Name: signals_open_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX signals_open_idx ON public.signals USING btree (instrument_id) WHERE (state = ANY (ARRAY['open'::public.signal_state, 'confirmed'::public.signal_state]));


--
-- Name: stock_daily_bars_date_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX stock_daily_bars_date_idx ON public.stock_daily_bars USING btree (session_date);


--
-- Name: accounts accounts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: allowlist allowlist_added_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.allowlist
    ADD CONSTRAINT allowlist_added_by_fkey FOREIGN KEY (added_by) REFERENCES public.users(id);


--
-- Name: app_settings app_settings_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT app_settings_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(id);


--
-- Name: audit_log audit_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: broker_spreads broker_spreads_broker_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.broker_spreads
    ADD CONSTRAINT broker_spreads_broker_id_fkey FOREIGN KEY (broker_id) REFERENCES public.brokers(id) ON DELETE CASCADE;


--
-- Name: broker_spreads broker_spreads_instrument_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.broker_spreads
    ADD CONSTRAINT broker_spreads_instrument_id_fkey FOREIGN KEY (instrument_id) REFERENCES public.instruments(id) ON DELETE CASCADE;


--
-- Name: candles candles_instrument_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.candles
    ADD CONSTRAINT candles_instrument_id_fkey FOREIGN KEY (instrument_id) REFERENCES public.instruments(id) ON DELETE CASCADE;


--
-- Name: econ_events econ_events_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.econ_events
    ADD CONSTRAINT econ_events_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: holdings holdings_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.holdings
    ADD CONSTRAINT holdings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: levels levels_instrument_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.levels
    ADD CONSTRAINT levels_instrument_id_fkey FOREIGN KEY (instrument_id) REFERENCES public.instruments(id) ON DELETE CASCADE;


--
-- Name: notification_prefs notification_prefs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_prefs
    ADD CONSTRAINT notification_prefs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: notifications notifications_signal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_signal_id_fkey FOREIGN KEY (signal_id) REFERENCES public.signals(id) ON DELETE SET NULL;


--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: push_subscriptions push_subscriptions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.push_subscriptions
    ADD CONSTRAINT push_subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: rule_versions rule_versions_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rule_versions
    ADD CONSTRAINT rule_versions_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: rule_versions rule_versions_key_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rule_versions
    ADD CONSTRAINT rule_versions_key_fkey FOREIGN KEY (key) REFERENCES public.rule_definitions(key) ON DELETE CASCADE;


--
-- Name: sessions sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: signal_events signal_events_signal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_events
    ADD CONSTRAINT signal_events_signal_id_fkey FOREIGN KEY (signal_id) REFERENCES public.signals(id) ON DELETE CASCADE;


--
-- Name: signal_indicators signal_indicators_signal_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signal_indicators
    ADD CONSTRAINT signal_indicators_signal_id_fkey FOREIGN KEY (signal_id) REFERENCES public.signals(id) ON DELETE CASCADE;


--
-- Name: signals signals_instrument_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signals
    ADD CONSTRAINT signals_instrument_id_fkey FOREIGN KEY (instrument_id) REFERENCES public.instruments(id);


--
-- Name: strategy_configs strategy_configs_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategy_configs
    ADD CONSTRAINT strategy_configs_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(id);


--
-- Name: strategy_param_overrides strategy_param_overrides_instrument_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategy_param_overrides
    ADD CONSTRAINT strategy_param_overrides_instrument_id_fkey FOREIGN KEY (instrument_id) REFERENCES public.instruments(id) ON DELETE CASCADE;


--
-- Name: strategy_param_overrides strategy_param_overrides_key_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategy_param_overrides
    ADD CONSTRAINT strategy_param_overrides_key_fkey FOREIGN KEY (key) REFERENCES public.rule_definitions(key) ON DELETE CASCADE;


--
-- Name: strategy_param_overrides strategy_param_overrides_updated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.strategy_param_overrides
    ADD CONSTRAINT strategy_param_overrides_updated_by_fkey FOREIGN KEY (updated_by) REFERENCES public.users(id);


--
-- Name: telegram_links telegram_links_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.telegram_links
    ADD CONSTRAINT telegram_links_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: users users_active_broker_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_active_broker_fk FOREIGN KEY (active_broker_id) REFERENCES public.brokers(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict dbmate


--
-- Dbmate schema migrations
--

INSERT INTO public.schema_migrations (version) VALUES
    ('20261001000001'),
    ('20261001000002'),
    ('20261001000003'),
    ('20261002000001'),
    ('20261003000001'),
    ('20261008000001');
