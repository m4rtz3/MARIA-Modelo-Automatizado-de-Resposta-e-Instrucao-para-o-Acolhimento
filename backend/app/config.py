"""
Configuração central do backend MARIA.
Todas as variáveis sensíveis (chave do Gemini) vêm de .env — nunca hardcoded.
"""
import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv, set_key

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

# ---- Gemini ----
_env_values = dotenv_values(ENV_PATH)
GOOGLE_API_KEY = (
    _env_values.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
)
MARIA_SETTINGS_PASSWORD = (
    _env_values.get("MARIA_SETTINGS_PASSWORD")
    or os.getenv("MARIA_SETTINGS_PASSWORD", "")
)
MODELO_LLM = os.getenv("MODELO_LLM", "gemini-3.6-flash")
MODELO_EMB = os.getenv(
    "MODELO_EMB", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
MODELO_EMB_REVISION = os.getenv("MODELO_EMB_REVISION", "")
MODELO_EMB_PATH = os.getenv("MODELO_EMB_PATH", "")
MODELO_EMB_BACKEND = os.getenv("MODELO_EMB_BACKEND", "torch")
MODELO_EMB_FILE_NAME = os.getenv(
    "MODELO_EMB_FILE_NAME", "onnx/model_quint8_avx2.onnx"
)

# ---- Paths de dados (mesma lógica de fallback do notebook original) ----
KB_PATH = Path(
    os.getenv("KB_PATH", str(BASE_DIR / "data" / "knowledge_base.md"))
)
DADOS_BI_PATH = Path(
    os.getenv("DADOS_BI_PATH", str(BASE_DIR / "data" / "dados_bi"))
)
INDEX_DIR = Path(os.getenv("INDEX_DIR", str(BASE_DIR / "data" / "indice")))
INDEX_DIR.mkdir(parents=True, exist_ok=True)

# ---- Índice de retrieval (pgvector) ----
# Se DATABASE_URL estiver configurada, o retrieval roda 100% no Postgres
# (maria_chunks/maria_kb_meta, ver sql/schema_pgvector.sql + scripts/indexador.py)
# em vez do índice local (chunks_<hash>.json + embeddings_<hash>.npy em
# INDEX_DIR). Vazia = modo local, útil pra dev sem precisar subir um banco.
# This backend's .env is authoritative for the database endpoint, so a stale
# DATABASE_URL inherited by Uvicorn cannot silently redirect it to localhost.
DATABASE_URL = dotenv_values(ENV_PATH).get("DATABASE_URL", os.getenv("DATABASE_URL", "")) or ""

# ---- Comportamento do chat ----
MAX_TURNOS_HISTORICO = int(os.getenv("MAX_TURNOS_HISTORICO", "6"))
TIMEOUT_REQUEST_S = int(os.getenv("TIMEOUT_REQUEST_S", "45"))
LIMIAR_SIMILARIDADE = float(os.getenv("LIMIAR_SIMILARIDADE", "0.30"))

# ---- CORS ----
# lista separada por vírgula, ex: "http://localhost:5173,https://meudashboard.com"
FRONTEND_ORIGINS = [
    o.strip()
    for o in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]


def persist_google_api_key(api_key: str) -> None:
    """Persiste a chave do Gemini no .env sem incluí-la em logs ou respostas."""
    sucesso, _, _ = set_key(
        ENV_PATH,
        "GOOGLE_API_KEY",
        api_key,
        quote_mode="always",
        encoding="utf-8",
    )
    if not sucesso:
        raise OSError("Não foi possível salvar GOOGLE_API_KEY no .env.")
