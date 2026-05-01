-- ============================================================
-- 飞书决策一致性引擎 · 数据契约 SQL（schema.sql）
-- ============================================================
-- 镜像源：docs/03-SCHEMA.md v1.0
-- 适用：PostgreSQL 16 + pgvector 0.8.x
-- 落地：6 enums + 8 主表 + 1 向量表 + 15 named indexes + W2/W13/W14 CHECK + 3 BEFORE UPDATE 触发器
-- 修订：T-002 v1.0（2026-04-29）— 首版从 03-SCHEMA 派生
-- 警告：任何字段改动必须先改 03-SCHEMA.md，再改本文件，再改 memory_engine/models.py（CLAUDE.md §2.4）
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;
SET timezone = 'UTC';

-- ============================================================
-- §1. ENUMs (6 个；与 memory_engine/models.py 中 Python enum 1:1)
-- ============================================================

CREATE TYPE provenance_enum AS ENUM (
    'USER_STATED',
    'OKR_SYNCED',
    'APPROVAL_PASSED',
    'DOC_SYNCED',
    'MEETING_EXTRACTED',
    'SYSTEM_INFERRED'
);

CREATE TYPE evolution_type_enum AS ENUM (
    'ROOT',
    'SUPERSEDES',
    'REFINES',
    'GENERALIZES',
    'BRANCHES'
);

CREATE TYPE decision_state_enum AS ENUM (
    'ACTIVE',
    'STALE',
    'HYPOTHESIS',
    'GHOST',
    'ARCHIVED'
);

CREATE TYPE card_type_enum AS ENUM (
    'HARD_ASSERTION',
    'SOFT_INQUIRY',
    'GHOST_LOG',
    'CROSS_SYSTEM_ALERT',
    'EVOLUTION_NOTICE'
);

CREATE TYPE card_status_enum AS ENUM (
    'QUEUED',
    'PUSHED',
    'RESPONDED',
    'EXPIRED'
);

CREATE TYPE card_response_enum AS ENUM (
    'CONFIRMED',
    'DENIED',
    'NO_RESPONSE_24H',
    'IGNORED'
);

-- ============================================================
-- §2. 触发器函数（updated_at 自动维护）
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- §3. 主表（按 FK 依赖顺序）
-- ============================================================

-- ---------------------------------------------------------------- §3.1 users
CREATE TABLE users (
    user_id          varchar(64)  PRIMARY KEY,
    feishu_user_id   varchar(128),
    name             varchar(128) NOT NULL,
    email            varchar(255),
    timezone         varchar(64)  NOT NULL DEFAULT 'Asia/Shanghai',
    work_hour_start  smallint     NOT NULL DEFAULT 9
                     CHECK (work_hour_start BETWEEN 0 AND 23),
    work_hour_end    smallint     NOT NULL DEFAULT 19
                     CHECK (work_hour_end BETWEEN 1 AND 24 AND work_hour_end > work_hour_start),
    is_active        boolean      NOT NULL DEFAULT true,
    created_at       timestamptz  NOT NULL DEFAULT now(),
    updated_at       timestamptz  NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_users_feishu_id
    ON users (feishu_user_id)
    WHERE feishu_user_id IS NOT NULL;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

COMMENT ON TABLE users IS '用户档案，含工作时间窗（W15 应用层使用）';

-- ---------------------------------------------------------------- §3.2 trace_log（W13 强制）
-- 早建以让 cards.trace_id FK 直接落点
CREATE TABLE trace_log (
    trace_id         varchar(64)  PRIMARY KEY,
    api_endpoint     varchar(255) NOT NULL,
    direction        varchar(8)   NOT NULL
                     CHECK (direction IN ('OUT', 'IN', 'HOOK')),
    request_payload  jsonb,
    response_payload jsonb,
    http_status      smallint,
    latency_ms       int,
    called_at        timestamptz  NOT NULL DEFAULT now(),
    error_message    text
);

CREATE INDEX idx_trace_called_at ON trace_log (called_at DESC);
CREATE INDEX idx_trace_endpoint  ON trace_log (api_endpoint, called_at DESC);

COMMENT ON TABLE trace_log IS '飞书 API trace（W13 在 DB 层强制 trace_id PK NOT NULL）';

-- ---------------------------------------------------------------- §3.3 decisions
CREATE TABLE decisions (
    decision_id        uuid             PRIMARY KEY DEFAULT gen_random_uuid(),
    subject            varchar(255)     NOT NULL,
    predicate          varchar(255)     NOT NULL,
    object             text             NOT NULL,
    logical_timestamp  timestamptz      NOT NULL,
    extracted_at       timestamptz      NOT NULL DEFAULT now(),
    provenance         provenance_enum  NOT NULL,
    confidence         numeric(3,2)     NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    uncertainty        numeric(3,2)     NOT NULL DEFAULT 0.00 CHECK (uncertainty BETWEEN 0 AND 1),
    state              decision_state_enum NOT NULL DEFAULT 'ACTIVE',
    parent_id          uuid             REFERENCES decisions(decision_id) ON DELETE RESTRICT,
    evolution_type     evolution_type_enum NOT NULL,
    consensus_sources  jsonb            NOT NULL DEFAULT '[]'::jsonb,
    consensus_score    numeric(3,2)     NOT NULL DEFAULT 0.00 CHECK (consensus_score BETWEEN 0 AND 1),
    source_event_id    text,
    original_text      text,
    access_count       int              NOT NULL DEFAULT 0 CHECK (access_count >= 0),
    last_accessed_at   timestamptz      NOT NULL DEFAULT now(),
    confirm_count      int              NOT NULL DEFAULT 0 CHECK (confirm_count >= 0),
    last_confirmed_at  timestamptz,
    last_decay_calc_at timestamptz      NOT NULL DEFAULT now(),
    business_impact    numeric(3,2)     NOT NULL DEFAULT 0.50 CHECK (business_impact BETWEEN 0 AND 1),
    owner_user_id      varchar(64)      REFERENCES users(user_id) ON DELETE SET NULL,
    created_at         timestamptz      NOT NULL DEFAULT now(),
    updated_at         timestamptz      NOT NULL DEFAULT now(),
    -- W2 不变量在 DB 层强制（决策 evolution_type 与 parent_id 必须联动一致）
    CONSTRAINT chk_decisions_evolution_parent CHECK (
        (evolution_type = 'ROOT' AND parent_id IS NULL)
        OR
        (evolution_type IN ('SUPERSEDES', 'REFINES', 'GENERALIZES', 'BRANCHES')
         AND parent_id IS NOT NULL)
    )
);

CREATE INDEX idx_decisions_subj_pred_state ON decisions (subject, predicate, state);
CREATE INDEX idx_decisions_state_decay     ON decisions (state, last_decay_calc_at);
CREATE INDEX idx_decisions_owner_state     ON decisions (owner_user_id, state)
    WHERE state IN ('ACTIVE', 'STALE', 'HYPOTHESIS');
CREATE INDEX idx_decisions_parent          ON decisions (parent_id)
    WHERE parent_id IS NOT NULL;
CREATE INDEX idx_decisions_fts             ON decisions
    USING gin (to_tsvector('simple', subject || ' ' || predicate || ' ' || object));

CREATE TRIGGER trg_decisions_updated_at
    BEFORE UPDATE ON decisions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

COMMENT ON TABLE decisions IS '决策原子主表，承载七字段 + 状态 + 五维衰减跟踪 + 跨源证据 + 演化关系（自引用 parent_id）';

-- ---------------------------------------------------------------- §3.4 decision_embeddings
CREATE TABLE decision_embeddings (
    decision_id    uuid         PRIMARY KEY REFERENCES decisions(decision_id) ON DELETE CASCADE,
    embedding      vector(1024) NOT NULL,
    model_name     varchar(64)  NOT NULL,
    model_version  varchar(32),
    generated_at   timestamptz  NOT NULL DEFAULT now()
);

-- HNSW 索引：cosine 距离（与应用层 cosine_similarity 对齐）
CREATE INDEX idx_emb_hnsw ON decision_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

COMMENT ON TABLE decision_embeddings IS '决策原子语义向量（pgvector v1，1024 维 = Doubao Embedding v1）';

-- ---------------------------------------------------------------- §3.5 card_quota（W14 强制）
CREATE TABLE card_quota (
    user_id     varchar(64) NOT NULL REFERENCES users(user_id),
    quota_date  date        NOT NULL,
    count       int         NOT NULL DEFAULT 0,
    max_daily   int         NOT NULL DEFAULT 5,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, quota_date),
    -- W14 不变量在 DB 层强制（单用户每日卡片推送 ≤ max_daily）
    CONSTRAINT chk_card_quota_count CHECK (count >= 0 AND count <= max_daily)
);

CREATE TRIGGER trg_card_quota_updated_at
    BEFORE UPDATE ON card_quota
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

COMMENT ON TABLE card_quota IS '每日打扰预算计数器（W14 在 DB 层强制 count ≤ max_daily）';

-- ---------------------------------------------------------------- §3.6 cards
CREATE TABLE cards (
    card_id              uuid             PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              varchar(64)      NOT NULL REFERENCES users(user_id),
    decision_id          uuid             NOT NULL REFERENCES decisions(decision_id),
    related_decision_id  uuid             REFERENCES decisions(decision_id),
    card_type            card_type_enum   NOT NULL,
    status               card_status_enum NOT NULL DEFAULT 'QUEUED',
    priority_score       numeric(3,2)     NOT NULL DEFAULT 0.00 CHECK (priority_score BETWEEN 0 AND 1),
    response             card_response_enum,
    pushed_at            timestamptz,
    responded_at         timestamptz,
    trace_id             varchar(64)      REFERENCES trace_log(trace_id),
    created_at           timestamptz      NOT NULL DEFAULT now(),
    -- 状态机一致性：状态与 response/pushed_at 必须对齐
    CONSTRAINT chk_cards_response_consistency CHECK (
        (status = 'RESPONDED') = (response IS NOT NULL)
    ),
    CONSTRAINT chk_cards_pushed_consistency CHECK (
        (status IN ('PUSHED', 'RESPONDED', 'EXPIRED')) = (pushed_at IS NOT NULL)
    )
);

CREATE INDEX idx_cards_user_status ON cards (user_id, status);
CREATE INDEX idx_cards_dedup       ON cards (decision_id, related_decision_id, pushed_at)
    WHERE status IN ('PUSHED', 'RESPONDED');

COMMENT ON TABLE cards IS '推送卡片记录，支持 W11 24h 去重（idx_cards_dedup）与 W14 5/日预算（联 card_quota）';

-- ---------------------------------------------------------------- §3.7 reflect_logs
CREATE TABLE reflect_logs (
    log_id                       uuid                 PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id                  uuid                 NOT NULL REFERENCES decisions(decision_id),
    parent_id                    uuid                 REFERENCES decisions(decision_id),
    original_evolution_type      evolution_type_enum,
    quality_score                numeric(3,2)         NOT NULL CHECK (quality_score BETWEEN 0 AND 1),
    potential_missed_parent_id   uuid                 REFERENCES decisions(decision_id),
    suggested_type               evolution_type_enum,
    confidence_calibration       numeric(4,3)         NOT NULL DEFAULT 0.000
                                 CHECK (confidence_calibration BETWEEN -1 AND 1),
    reasoning                    varchar(255),
    evaluated_at                 timestamptz          NOT NULL DEFAULT now()
);

CREATE INDEX idx_reflect_decision_time ON reflect_logs (decision_id, evaluated_at DESC);
CREATE INDEX idx_reflect_quality       ON reflect_logs (quality_score);

COMMENT ON TABLE reflect_logs IS 'M3 Reflect Agent 质量档案（W6: 只 INSERT，不 UPDATE 决策历史）';

-- ---------------------------------------------------------------- §3.8 decay_calculations
CREATE TABLE decay_calculations (
    calc_id            uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    decision_id        uuid         NOT NULL REFERENCES decisions(decision_id),
    lambda_value       numeric(6,4) NOT NULL,
    f_freq             numeric(3,2) NOT NULL,
    f_consensus        numeric(3,2) NOT NULL,
    f_semantic         numeric(3,2) NOT NULL,
    f_uncertainty      numeric(3,2) NOT NULL,
    f_user_validation  numeric(3,2) NOT NULL,
    prev_uncertainty   numeric(3,2) NOT NULL,
    new_uncertainty    numeric(3,2) NOT NULL,
    reason             varchar(64)  NOT NULL,
    calculated_at      timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX idx_decay_decision_time ON decay_calculations (decision_id, calculated_at DESC);
CREATE INDEX idx_decay_time          ON decay_calculations (calculated_at DESC);

COMMENT ON TABLE decay_calculations IS '五维 λ 审计日志（含 5 因子 + 前后 uncertainty + 触发原因）';

-- ============================================================
-- 末尾：核查（运行后跑这几条应一切正常）
-- ============================================================
-- SELECT count(*) FROM pg_type WHERE typname LIKE '%_enum';   -- expect 6
-- SELECT count(*) FROM information_schema.tables
--     WHERE table_schema = 'public' AND table_type = 'BASE TABLE';  -- expect 8
-- SELECT count(*) FROM pg_indexes WHERE schemaname = 'public';  -- expect 15+8 PK = 23
-- SELECT count(*) FROM information_schema.triggers;  -- expect 3
