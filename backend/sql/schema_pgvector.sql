-- =====================================================================
-- MARIA — esquema pgvector para o índice de retrieval
-- =====================================================================
-- Substitui os arquivos chunks_<hash>.json + embeddings_<hash>.npy do
-- índice local (app/kb.py) por duas tabelas no Postgres. A lógica de
-- idempotência é a mesma que já existia no notebook (não reindexar se a
-- KB não mudou), só que o "cache" agora é uma linha em maria_kb_meta em
-- vez de um nome de arquivo com hash.
--
-- Rodar uma vez por banco (idempotente — pode rodar de novo sem erro):
--   psql "$DATABASE_URL" -f sql/schema_pgvector.sql

CREATE EXTENSION IF NOT EXISTS vector;

-- O encoder usado no notebook é o paraphrase-multilingual-MiniLM-L12-v2,
-- que produz vetores de 384 dimensões. Se um dia trocarem de encoder,
-- essa dimensão MUDA e a tabela precisa ser recriada (embeddings de
-- dimensões diferentes não são comparáveis entre si).
CREATE TABLE IF NOT EXISTS maria_chunks (
    chunk_id    TEXT PRIMARY KEY,
    bloco       TEXT,
    secao       TEXT,
    titulo      TEXT,
    tipo        TEXT NOT NULL,
    texto       TEXT NOT NULL,
    n_chars     INTEGER NOT NULL,
    embedding   VECTOR(384) NOT NULL
);

-- Índice por tipo: toda busca com tipo_filtro (o roteamento de
-- categoria da KB) filtra por essa coluna antes de ordenar por
-- distância — vale a pena ter um índice B-tree normal nela também.
CREATE INDEX IF NOT EXISTS idx_maria_chunks_tipo ON maria_chunks (tipo);

-- Índice vetorial (HNSW) para a busca por similaridade de cosseno.
-- HNSW em vez de IVFFlat porque a base é pequena (algumas centenas de
-- chunks) — HNSW não precisa da fase de "treino" que o IVFFlat exige
-- com uma amostra mínima de linhas, e para poucos milhares de vetores
-- a diferença de performance entre os dois não importa.
CREATE INDEX IF NOT EXISTS idx_maria_chunks_embedding
    ON maria_chunks
    USING hnsw (embedding vector_cosine_ops);

-- Guarda o hash MD5 do texto-fonte da KB (kb_texto) já enriquecido com
-- os CSVs do pipeline — é a mesma chave de cache que o índice local usa
-- no nome do arquivo (chunks_<hash>.json). Uma linha só, id fixo.
CREATE TABLE IF NOT EXISTS maria_kb_meta (
    id          SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    kb_hash     TEXT NOT NULL,
    n_chunks    INTEGER NOT NULL,
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
