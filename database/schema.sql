-- =====================================================================
-- Schema dos relatórios — v1
--
-- Dialeto: SQLite (dev local e testes). Na Fase 2 os modelos SQLAlchemy
-- espelham este arquivo e geram o equivalente em Postgres para o deploy
-- (INTEGER PRIMARY KEY -> IDENTITY, TEXT -> VARCHAR/TEXT, etc.).
--
-- SQLite só aplica FOREIGN KEY com:  PRAGMA foreign_keys = ON;
--
-- Modelo:
--   company 1──N asset      (uma empresa tem vários tickers: PETR3, PETR4)
--   company 1──N report     (relatórios são da empresa, não do ticker)
--   report  1──N summary    (um por método/modelo/versão de prompt)
--   report  1──N keypoint   (indicadores numéricos, sempre da heurística)
--
-- O schema antigo (user/wallet/wallet_transaction) está em
-- legacy_mysql_schema.sql; quando voltar, wallet_transaction referencia asset.
-- =====================================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS company (
    id            INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    -- Chave de busca: db.normalize.normalize_name(name). UNIQUE de propósito:
    -- duas empresas que normalizam igual são um erro de cadastro a corrigir,
    -- não uma ambiguidade a escolher.
    name_normalized TEXT  NOT NULL UNIQUE,
    cnpj         TEXT    UNIQUE,                 -- 14 dígitos, sem máscara
    cvm_code      TEXT    UNIQUE,                 -- código CVM (dados abertos)
    kind          TEXT    NOT NULL DEFAULT 'ACAO'
                  CHECK (kind IN ('ACAO', 'FII')),
    created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS asset (
    id            INTEGER PRIMARY KEY,
    company_id    INTEGER NOT NULL
                  REFERENCES company (id) ON DELETE CASCADE,
    ticker        TEXT    NOT NULL UNIQUE         -- ex.: BBSE3
                  CHECK (length(ticker) BETWEEN 5 AND 7)
);
CREATE INDEX IF NOT EXISTS ix_asset_company ON asset (company_id);

CREATE TABLE IF NOT EXISTS report (
    id            INTEGER PRIMARY KEY,
    company_id    INTEGER NOT NULL
                  REFERENCES company (id) ON DELETE CASCADE,
    report_type   TEXT    NOT NULL
                  CHECK (report_type IN ('ITR', 'DFP', 'EARNINGS_RELEASE',
                                         'FATO_RELEVANTE', 'FORMULARIO_REFERENCIA', 'OUTRO')),
    period        TEXT    NOT NULL,               -- trimestre em que fecha: 1T26..4T26 (9M25 = 3T25; 1S26 = 2T26)
    file_name     TEXT    NOT NULL,
    file_hash     TEXT    NOT NULL UNIQUE         -- SHA-256 do PDF: o mesmo arquivo nunca entra 2x
                  CHECK (length(file_hash) = 64),
    source_url    TEXT,
    page_count    INTEGER NOT NULL CHECK (page_count >= 0),
    -- Versão da heurística que gerou os keypoints (HEURISTIC_VERSION).
    -- '' = desconhecida: qualquer versão atual força a regeração.
    extractor_version TEXT NOT NULL DEFAULT '',
    parsed_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- Chave de negócio: um relatório por empresa/tipo/período.
    -- Reapresentação (mesmo período, PDF novo) = hash novo na MESMA linha:
    -- o batch atualiza file_hash e regera summary/keypoint.
    UNIQUE (company_id, report_type, period)
);

CREATE TABLE IF NOT EXISTS summary (
    id             INTEGER PRIMARY KEY,
    report_id      INTEGER NOT NULL
                   REFERENCES report (id) ON DELETE CASCADE,
    method         TEXT    NOT NULL CHECK (method IN ('heuristic', 'llm')),
    model          TEXT    NOT NULL,             -- 'qwen2.5:3b' | 'heuristic'
    prompt_version TEXT    NOT NULL,             -- 'prompt-v1' | 'heuristic-v1'
    content        TEXT    NOT NULL CHECK (length(content) > 0),
    content_format TEXT    NOT NULL CHECK (content_format IN ('json', 'markdown')),
    created_at     TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- "Gerar uma única vez": se esta combinação existe, o batch pula.
    -- Mudou o prompt? Sobe prompt_version e só então gera de novo.
    UNIQUE (report_id, method, model, prompt_version)
);

CREATE TABLE IF NOT EXISTS keypoint (
    id             INTEGER PRIMARY KEY,
    report_id      INTEGER NOT NULL
                   REFERENCES report (id) ON DELETE CASCADE,
    metric         TEXT    NOT NULL,             -- ex.: 'Lucro Líquido'
    value_text     TEXT    NOT NULL,             -- como aparece no PDF: 'R$ 1,2 bi'
    value_numeric  REAL,                         -- preenchido quando o parse numérico existir
    variation_text TEXT,                         -- ex.: '+12,3% a/a'
    period         TEXT,
    page           INTEGER
);
-- Sem UNIQUE aqui de propósito: o batch substitui os keypoints de um
-- relatório inteiro (DELETE + INSERT na mesma transação).
CREATE INDEX IF NOT EXISTS ix_keypoint_report ON keypoint (report_id);
