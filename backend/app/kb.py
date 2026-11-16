"""
Base de conhecimento vetorizada — port fiel da célula de chunking do notebook.

Mesmo conceito de lá: chunking hierárquico (bloco > seção), separação de
meta-instrução (BLOCO 5) do índice pesquisável, índice persistente em disco
com hash do texto-fonte pra revetorizar só quando a KB muda.

Diferença: no notebook isso era um script solto com variáveis globais
(chunks, embeddings_chunks). Aqui vira uma classe porque o processo do
FastAPI fica no ar entre requisições — precisamos de um objeto de estado
único, carregado no startup (ver app/main.py).
"""
import hashlib
import json
import logging
from collections import Counter
from pathlib import Path
from typing import List, Optional

import numpy as np

from app.config import INDEX_DIR, KB_PATH
from app.llm import embed

logger = logging.getLogger("maria.kb")

TIPO_POR_BLOCO = {
    "BLOCO 1": "legislacao",
    "BLOCO 2": "pipeline_dados",
    "BLOCO 3": "datasenado",
    "BLOCO 4": "canais_denuncia",
    "BLOCO 5": "meta_instrucao",
    "BLOCO 6": "orientacao_pratica",
    "BLOCO 7": "pipeline_dados",
}

MAX_CHARS_CHUNK = 700
MIN_CHARS_SECAO = 40


def _limpa_titulo(linha: str) -> str:
    return linha.strip("# *").strip()


def _divide_paragrafos(texto_secao: str, max_chars: int = MAX_CHARS_CHUNK) -> List[str]:
    paragrafos = [p for p in texto_secao.split("\n\n") if p.strip()]
    subchunks, atual = [], ""
    for p in paragrafos:
        candidato = (atual + "\n\n" + p).strip() if atual else p
        if len(candidato) > max_chars and atual:
            subchunks.append(atual.strip())
            atual = p
        else:
            atual = candidato
    if atual.strip():
        subchunks.append(atual.strip())
    return subchunks


def chunk_hierarquico(texto: str) -> List[dict]:
    linhas = texto.split("\n")
    chunks = []
    bloco_atual, secao_atual = "", ""
    bloco_idx, secao_idx = -1, -1
    buffer_secao: List[str] = []

    def fecha_secao():
        nonlocal buffer_secao
        if not buffer_secao:
            return
        conteudo = "\n".join(buffer_secao).strip()
        buffer_secao = []
        if len(conteudo) < MIN_CHARS_SECAO:
            return
        tipo = next(
            (v for k, v in TIPO_POR_BLOCO.items() if bloco_atual.startswith(k)), "geral"
        )
        for sub_idx, sub_texto in enumerate(_divide_paragrafos(conteudo)):
            chunk_id = f"b{bloco_idx}_s{secao_idx}_c{sub_idx}"
            texto_final = f"[{secao_atual}]\n{sub_texto}" if secao_atual else sub_texto
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "bloco": bloco_atual,
                    "secao": secao_atual,
                    "titulo": secao_atual or bloco_atual,
                    "tipo": tipo,
                    "texto": texto_final,
                    "n_chars": len(texto_final),
                }
            )

    for linha in linhas:
        if linha.startswith("## "):
            fecha_secao()
            bloco_atual = _limpa_titulo(linha)
            bloco_idx += 1
            secao_idx = -1
            secao_atual = ""
        elif linha.startswith("### "):
            fecha_secao()
            secao_atual = _limpa_titulo(linha)
            secao_idx += 1
        else:
            buffer_secao.append(linha)
    fecha_secao()
    return chunks


class KnowledgeBase:
    """Estado único da base vetorizada, carregado no startup do FastAPI."""

    def __init__(self) -> None:
        self.chunks: List[dict] = []
        self.chunks_meta: List[dict] = []
        self.embeddings: Optional[np.ndarray] = None
        self.carregada = False

    def carregar_meta_instrucao(self) -> None:
        """Carrega somente as meta-instruções, sem inicializar embeddings."""
        if not KB_PATH.exists():
            self.chunks_meta = []
            logger.warning(
                "Arquivo da base de conhecimento não encontrado em %s — "
                "meta-instruções não carregadas.",
                KB_PATH,
            )
            return

        texto = KB_PATH.read_text(encoding="utf-8")
        self.chunks_meta = [
            chunk
            for chunk in chunk_hierarquico(texto)
            if chunk["tipo"] == "meta_instrucao"
        ]
        logger.info("Meta-instruções carregadas: %d", len(self.chunks_meta))

    def carregar(self, enriquecimento_extra: str = "") -> None:
        if not KB_PATH.exists():
            logger.error(
                "Arquivo da base de conhecimento não encontrado em %s — "
                "o chat vai responder sem contexto de RAG. Ajuste KB_PATH no .env.",
                KB_PATH,
            )
            self.carregada = False
            return

        kb_texto = KB_PATH.read_text(encoding="utf-8") + enriquecimento_extra

        _todos_chunks = chunk_hierarquico(kb_texto)
        chunks = [c for c in _todos_chunks if c["tipo"] != "meta_instrucao"]
        chunks_meta = [c for c in _todos_chunks if c["tipo"] == "meta_instrucao"]

        logger.info("Chunks pesquisáveis: %d | meta-instrução: %d", len(chunks), len(chunks_meta))
        for tipo, n in Counter(c["tipo"] for c in chunks).items():
            logger.info("  %s: %d", tipo, n)

        kb_hash = hashlib.md5(kb_texto.encode("utf-8")).hexdigest()[:12]
        meta_path = INDEX_DIR / f"chunks_{kb_hash}.json"
        emb_path = INDEX_DIR / f"embeddings_{kb_hash}.npy"

        if meta_path.exists() and emb_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                chunks = json.load(f)
            embeddings_chunks = np.load(emb_path)
            logger.info(
                "Índice carregado do cache (hash %s): %d chunks x %d dims",
                kb_hash, len(chunks), embeddings_chunks.shape[1],
            )
        else:
            embeddings_chunks = embed([c["texto"] for c in chunks])
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=1)
            np.save(emb_path, embeddings_chunks)
            logger.info(
                "Índice vetorizado e salvo (hash %s): %d chunks x %d dims",
                kb_hash, len(chunks), embeddings_chunks.shape[1],
            )

        self.chunks = chunks
        self.chunks_meta = chunks_meta
        self.embeddings = embeddings_chunks
        self.carregada = True


kb = KnowledgeBase()
