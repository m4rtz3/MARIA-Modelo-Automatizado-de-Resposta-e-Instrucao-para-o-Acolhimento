"""
API MARIA — expõe o pipeline RAG (app/maria.py) pro front-end React.

Rodar localmente:
    uvicorn app.main:app --reload --port 8000

Ver README.md na raiz do backend pra setup completo (venv, .env, onde
colocar a base de conhecimento e os CSVs, e como optar pelo índice em
Postgres/pgvector via DATABASE_URL — ver README.md e sql/schema_pgvector.sql).
"""
import asyncio
import json
import logging
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from google.api_core.exceptions import (
    DeadlineExceeded,
    GoogleAPICallError,
    ResourceExhausted,
    ServiceUnavailable,
    TooManyRequests,
)
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import ReadTimeout

from app import db
from app.config import (
    DATABASE_URL,
    FRONTEND_ORIGINS,
    MARIA_SETTINGS_PASSWORD,
    persist_google_api_key,
)
from app.data_analysis import analisar_dados, carregar_datasets, construir_enriquecimento_csvs
from app.data_analysis import (
    _dados as datasets_carregados,
    listar_datasets_disponiveis,
    listar_datasets_sob_demanda,
)
from app.kb import kb
from app.llm import configurar_api_key, init_llm
from app.maria import maria, maria_stream
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    SettingsUnlockRequest,
    SettingsUpdateRequest,
    StatsResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("maria.api")
_tentativas_config: dict[str, list[float]] = {}
_JANELA_TENTATIVAS_S = 900
_MAX_TENTATIVAS_CONFIG = 5


def _validar_senha_configuracoes(senha: str, request: Request) -> None:
    if len(MARIA_SETTINGS_PASSWORD) < 12:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "settings_unavailable",
                "message": "Configurações protegidas não estão habilitadas no backend.",
            },
        )

    ip = request.client.host if request.client else "unknown"
    agora = time.monotonic()
    tentativas = [
        instante for instante in _tentativas_config.get(ip, [])
        if agora - instante < _JANELA_TENTATIVAS_S
    ]
    if len(tentativas) >= _MAX_TENTATIVAS_CONFIG:
        _tentativas_config[ip] = tentativas
        raise HTTPException(
            status_code=429,
            detail={
                "code": "settings_rate_limited",
                "message": "Muitas tentativas. Aguarde alguns minutos e tente novamente.",
            },
        )

    if not secrets.compare_digest(senha, MARIA_SETTINGS_PASSWORD):
        tentativas.append(agora)
        _tentativas_config[ip] = tentativas
        raise HTTPException(
            status_code=401,
            detail={
                "code": "settings_auth_failed",
                "message": "Senha incorreta.",
            },
        )

    _tentativas_config.pop(ip, None)


def _erro_chat(exc: Exception, endpoint: str) -> JSONResponse:
    logger.exception("Erro ao processar %s", endpoint)

    if isinstance(exc, (ResourceExhausted, TooManyRequests)):
        status_code = 429
        codigo = "quota_exceeded"
        mensagem = (
            "A cota de uso da MARIA foi atingida após algumas tentativas. "
            "Aguarde alguns minutos e tente enviar sua mensagem novamente."
        )
    elif isinstance(exc, (DeadlineExceeded, ReadTimeout)):
        status_code = 504
        codigo = "llm_timeout"
        mensagem = (
            "A resposta demorou mais que o esperado. Tente enviar sua "
            "mensagem novamente."
        )
    elif isinstance(exc, (ServiceUnavailable, RequestsConnectionError)):
        status_code = 503
        codigo = "llm_unavailable"
        mensagem = (
            "O serviço da MARIA está temporariamente indisponível. "
            "Aguarde um pouco e tente novamente."
        )
    elif isinstance(exc, GoogleAPICallError):
        status_code = 502
        codigo = "llm_error"
        mensagem = (
            "Não foi possível obter uma resposta da MARIA agora. "
            "Tente novamente mais tarde."
        )
    else:
        status_code = 500
        codigo = "chat_error"
        mensagem = (
            "Ocorreu um erro ao processar sua mensagem. "
            "Tente novamente em instantes."
        )

    return JSONResponse(
        status_code=status_code,
        content={"code": codigo, "detail": mensagem},
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando MARIA API...")
    t0 = time.time()

    init_llm()  # configura Gemini; o encoder é carregado sob demanda
    carregar_datasets()  # carrega os CSVs do pipeline (opcional, pra /api/stats e function calling)

    if DATABASE_URL:
        # O modo pgvector não carrega a KB local nem seus embeddings, mas
        # ainda precisa das meta-instruções para montar o prompt do chat.
        kb.carregar_meta_instrucao()
        # Pool síncrono (ver app/db.py) — abrir é uma chamada bloqueante,
        # roda numa thread pra não travar o loop do FastAPI no startup.
        await asyncio.to_thread(db.open_pool)
    else:
        # Sem DATABASE_URL: modo local — mesmo enriquecimento com os CSVs
        # do pipeline (BLOCO 7) que scripts/indexador.py aplica no modo
        # pgvector, pra o índice local não ficar sem essa parte da KB.
        kb.carregar(enriquecimento_extra=construir_enriquecimento_csvs())

    logger.info("Startup concluído em %.1fs", time.time() - t0)
    yield
    logger.info("Encerrando MARIA API.")
    await asyncio.to_thread(db.close_pool)


app = FastAPI(
    title="MARIA API",
    description="API do chatbot RAG de apoio a vítimas de violência doméstica.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        kb_carregada=db.usando_pgvector() or kb.carregada,
        n_chunks=len(kb.chunks) if not db.usando_pgvector() else -1,
        datasets_carregados=list(datasets_carregados.keys()),
        datasets_sob_demanda=listar_datasets_sob_demanda(),
        datasets_disponiveis=listar_datasets_disponiveis(),
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Resposta bloqueante — retorna a mensagem completa de uma vez."""
    try:
        historico = [t.model_dump() for t in req.historico]
        resultado = await maria(
            req.mensagem,
            historico=historico,
            top_k=req.top_k,
            temperatura=req.temperatura,
            debug=req.debug,
        )
        return ChatResponse(**resultado)
    except Exception as e:
        return _erro_chat(e, "/api/chat")


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """Entrega os fragmentos gerados pelo Gemini conforme são recebidos."""
    try:
        historico = [t.model_dump() for t in req.historico]
        fragmentos, localizacao, score_max, absteve = await maria_stream(
            req.mensagem,
            historico=historico,
            top_k=req.top_k,
            temperatura=req.temperatura,
            debug=req.debug,
        )
    except Exception as e:
        return _erro_chat(e, "/api/chat/stream")

    def proximo_fragmento(iterator):
        try:
            return True, next(iterator)
        except StopIteration:
            return False, None

    async def gerador():
        iterator = iter(fragmentos)
        try:
            while True:
                existe, texto = await asyncio.to_thread(proximo_fragmento, iterator)
                if not existe:
                    break
                yield f"data: {json.dumps({'type': 'chunk', 'content': texto}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'localizacao_detectada': localizacao, 'score_max_recuperacao': score_max, 'absteve': absteve}, ensure_ascii=False)}\n\n"
        except Exception as e:
            erro = _erro_chat(e, "/api/chat/stream")
            payload = json.loads(bytes(erro.body))
            yield f"data: {json.dumps({'type': 'error', **payload}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gerador(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/settings/unlock")
async def unlock_settings(req: SettingsUnlockRequest, request: Request):
    """Valida a senha administrativa sem criar sessão ou persistir a senha."""
    _validar_senha_configuracoes(req.senha, request)
    return {"ok": True}


@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest, request: Request):
    """Aplica alterações autenticadas e persiste somente a chave do Gemini."""
    _validar_senha_configuracoes(req.senha, request)
    api_key = req.google_api_key.strip() if req.google_api_key else None
    if api_key:
        if "\n" in api_key or "\r" in api_key or "\0" in api_key:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_api_key",
                    "message": "A chave informada contém caracteres inválidos.",
                },
            )
        try:
            persist_google_api_key(api_key)
            configurar_api_key(api_key)
        except OSError:
            logger.exception("Não foi possível persistir a chave do Gemini.")
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "settings_save_failed",
                    "message": "Não foi possível salvar a chave no .env do backend.",
                },
            )
    return {"ok": True, "api_key_updated": bool(api_key)}


@app.get("/api/stats", response_model=StatsResponse)
def stats(pergunta: str):
    """Consulta direta aos CSVs do pipeline (não passa pelo Gemini — é
    estatística real, calculada na hora). Ver app/data_analysis.py."""
    try:
        return StatsResponse(resultado=analisar_dados(pergunta))
    except Exception:
        logger.exception("Erro ao processar /api/stats")
        raise HTTPException(status_code=500, detail="Erro ao consultar os dados.")
