"""
Pool de conexão com o Postgres (pgvector) — sobe uma vez no lifespan do
FastAPI (ver app/main.py), nunca por request. Se DATABASE_URL não estiver
configurada, o app roda em modo local (índice em arquivo, ver app/kb.py)
e esse pool nunca é aberto.

Pool SÍNCRONO (psycopg_pool.ConnectionPool), não assíncrono, de propósito:
o psycopg em modo async precisa de um SelectorEventLoop, e o uvicorn no
Windows força ProactorEventLoop por padrão fora do modo --reload/workers
(ver uvicorn/loops/asyncio.py) — o pool async travava em PoolTimeout no
startup. Um pool síncrono chamado via asyncio.to_thread (ver
app/retrieval.py:busca_pg) evita esse problema por completo e funciona
igual em qualquer plataforma, sem depender de qual event loop o servidor
decidiu usar.
"""
import logging
from typing import Optional

from pgvector.psycopg import register_vector
from psycopg.conninfo import conninfo_to_dict
from psycopg_pool import ConnectionPool

from app.config import DATABASE_URL

logger = logging.getLogger("maria.db")

pool: Optional[ConnectionPool] = None


def _configura_conexao(conn) -> None:
    register_vector(conn)


def open_pool() -> None:
    """Chamado uma vez no startup (lifespan). Não faz nada se DATABASE_URL
    não estiver configurada — o app cai pro modo local automaticamente."""
    global pool
    if not DATABASE_URL:
        logger.info("DATABASE_URL não configurada — retrieval em modo local (arquivo).")
        return

    pool = ConnectionPool(DATABASE_URL, configure=_configura_conexao, open=True)
    conninfo = conninfo_to_dict(DATABASE_URL)
    logger.info(
        "Pool de conexão com Postgres (pgvector) pronto (host=%s, port=%s).",
        conninfo.get("host"),
        conninfo.get("port"),
    )


def close_pool() -> None:
    global pool
    if pool is not None:
        pool.close()
        pool = None


def usando_pgvector() -> bool:
    return pool is not None
