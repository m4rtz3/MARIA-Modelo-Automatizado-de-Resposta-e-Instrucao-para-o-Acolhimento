#!/usr/bin/env python3
"""
MARIA — indexação da base de conhecimento no Postgres (pgvector)
=====================================================================
Isso é a "fase offline" do RAG: roda como script, fora do processo do
FastAPI, e só grava no banco quando a KB de fato mudou (mesmo cache por
hash que o índice local em arquivo já usava — ver app/kb.py — só que
agora a chave mora numa tabela do Postgres, não num nome de arquivo).

O FastAPI NUNCA chama esse script sozinho — ele só lê o que este script
já deixou pronto no banco (ver app/retrieval.py:busca_pg). Rodar de novo
sempre que a KB (o .md) ou os CSVs de dados_bi mudarem:

    cd backend
    python scripts/indexador.py

Reusa o chunking hierárquico de app/kb.py e o enriquecimento por CSVs de
app/data_analysis.py — mesma lógica do modo local, pra não ter duas
implementações de chunking divergindo com o tempo.

Variáveis de ambiente (mesmas do .env do backend):
    DATABASE_URL   ex: postgresql://usuario:senha@host:5432/maria
    KB_PATH        caminho do .md da base de conhecimento (default do .env)
    DADOS_BI_PATH  pasta com os CSVs do pipeline (default do .env)
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg
from pgvector.psycopg import register_vector

from app.config import DATABASE_URL, KB_PATH, MODELO_EMB
from app.data_analysis import construir_enriquecimento_csvs
from app.kb import chunk_hierarquico

if not DATABASE_URL:
    sys.exit("❌ Defina DATABASE_URL no .env (ex: postgresql://user:senha@host:5432/maria)")


def carrega_kb_enriquecida() -> str:
    if not KB_PATH.exists():
        sys.exit(f"❌ KB não encontrada em {KB_PATH} (defina KB_PATH)")
    kb_texto = KB_PATH.read_text(encoding="utf-8")
    print(f"✅ Base de conhecimento: {len(kb_texto):,} chars de {KB_PATH.name}")

    texto_resumo = construir_enriquecimento_csvs()
    kb_texto = kb_texto + texto_resumo
    print(f"✅ Base enriquecida: {len(kb_texto):,} chars")
    return kb_texto


def main():
    kb_texto = carrega_kb_enriquecida()
    kb_hash = hashlib.md5(kb_texto.encode("utf-8")).hexdigest()[:12]

    with psycopg.connect(DATABASE_URL, autocommit=False) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT kb_hash, n_chunks FROM maria_kb_meta WHERE id = 1")
            row = cur.fetchone()

        if row and row[0] == kb_hash:
            print(f"✅ KB sem alterações (hash {kb_hash}) — {row[1]} chunks já indexados, nada a fazer.")
            return

        todos_chunks = chunk_hierarquico(kb_texto)
        chunks = [c for c in todos_chunks if c["tipo"] != "meta_instrucao"]
        chunks_meta = [c for c in todos_chunks if c["tipo"] == "meta_instrucao"]

        print(f"Chunks pesquisáveis: {len(chunks)}")
        print(
            "Chunks de meta-instrução (injetados pelo app no SYSTEM_PROMPT, "
            f"não indexados): {len(chunks_meta)}"
        )
        for tipo, n in Counter(c["tipo"] for c in chunks).items():
            print(f"  {tipo}: {n}")

        print(f"\nCarregando encoder ({MODELO_EMB})...")
        from sentence_transformers import SentenceTransformer
        encoder = SentenceTransformer(MODELO_EMB)
        embeddings = encoder.encode(
            [c["texto"] for c in chunks], show_progress_bar=True, convert_to_numpy=True
        )

        print("Gravando no Postgres...")
        with conn.cursor() as cur:
            cur.execute("TRUNCATE maria_chunks")
            for c, emb in zip(chunks, embeddings):
                cur.execute(
                    """
                    INSERT INTO maria_chunks
                        (chunk_id, bloco, secao, titulo, tipo, texto, n_chars, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (c["chunk_id"], c["bloco"], c["secao"], c["titulo"],
                     c["tipo"], c["texto"], c["n_chars"], emb),
                )
            cur.execute(
                """
                INSERT INTO maria_kb_meta (id, kb_hash, n_chunks, atualizado_em)
                VALUES (1, %s, %s, now())
                ON CONFLICT (id) DO UPDATE
                    SET kb_hash = EXCLUDED.kb_hash,
                        n_chunks = EXCLUDED.n_chunks,
                        atualizado_em = now()
                """,
                (kb_hash, len(chunks)),
            )
        conn.commit()

        # chunks de meta-instrução (BLOCO 5) não vão pro índice de busca.
        # O app também os carrega da KB e os anexa ao SYSTEM_PROMPT.
        meta_path = Path(__file__).resolve().parent.parent / "data" / "chunks_meta_instrucao.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(chunks_meta, ensure_ascii=False, indent=1), encoding="utf-8")

        print(f"\n✅ Indexado (hash {kb_hash}): {len(chunks)} chunks × {embeddings.shape[1]} dims")
        print(f"   meta-instrução salva em {meta_path}")


if __name__ == "__main__":
    main()
