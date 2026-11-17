"""
Camada de chamadas aos modelos generativos e de embeddings do Gemini.

Portado 1:1 da lógica já validada no notebook MARIA_chatbot_rag_GEMINI_hardness_2:
- retry em falhas transitórias, com backoff crescente; não repetir 404 nem 429 de quota
- safety_settings em BLOCK_NONE (necessário pra um chatbot que discute
  violência/abuso sem ser bloqueado por engano pelo classificador do Gemini)
- checagem de finish_reason pra logar respostas cortadas

Nota de manutenção: `google.generativeai` está oficialmente descontinuado
pela Google. Mantido aqui porque é a versão já testada e hardened em
produção pelo time. Migrar para `google.genai` (SDK novo) é a recomendação
de médio prazo, mas é troca de biblioteca, não um patch — fazer como
tarefa isolada, com os mesmos testes de regressão (harness de retrieval +
os 4 casos de teste manuais do notebook) antes de substituir em produção.
"""
import hashlib
import logging
import time
from threading import Lock
from typing import TYPE_CHECKING, Iterator, List, Optional

import google.generativeai as genai
import numpy as np
from google.api_core.exceptions import (
    Aborted,
    BadGateway,
    DeadlineExceeded,
    InternalServerError,
    ServiceUnavailable,
)
from google.generativeai.types import HarmBlockThreshold, HarmCategory, RequestOptions
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import ReadTimeout

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

from app.config import (
    GOOGLE_API_KEY,
    MAX_TURNOS_HISTORICO,
    MODELO_EMB,
    MODELO_EMB_BACKEND,
    MODELO_EMB_FILE_NAME,
    MODELO_EMB_PATH,
    MODELO_EMB_REVISION,
    MODELO_LLM,
    TIMEOUT_REQUEST_S,
)

logger = logging.getLogger("maria.llm")

def _request_options() -> RequestOptions:
    return RequestOptions(timeout=TIMEOUT_REQUEST_S, retry=None)


SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

_encoder: Optional["SentenceTransformer"] = None
_encoder_lock = Lock()
_api_key: Optional[str] = GOOGLE_API_KEY or None


def hash_indice_embeddings(texto: str) -> str:
    """Separa caches quando muda a revisão do modelo ou o backend de inferência."""
    revisao = (
        f"{MODELO_EMB}|{MODELO_EMB_REVISION}|{MODELO_EMB_BACKEND}|"
        f"{MODELO_EMB_FILE_NAME}"
        if MODELO_EMB_BACKEND == "onnx"
        else f"{MODELO_EMB}|{MODELO_EMB_REVISION}|{MODELO_EMB_BACKEND}"
    )
    return hashlib.md5(f"{revisao}\0{texto}".encode("utf-8")).hexdigest()[:12]


def carregar_encoder() -> "SentenceTransformer":
    """Carrega o modelo configurado, limitando threads e memória no backend ONNX."""
    from sentence_transformers import SentenceTransformer

    model_kwargs = None
    if MODELO_EMB_BACKEND == "onnx":
        from onnxruntime import SessionOptions

        session_options = SessionOptions()
        session_options.intra_op_num_threads = 1
        session_options.inter_op_num_threads = 1
        session_options.enable_cpu_mem_arena = False
        model_kwargs = {
            "file_name": MODELO_EMB_FILE_NAME,
            "provider": "CPUExecutionProvider",
            "session_options": session_options,
            "export": False,
        }

    return SentenceTransformer(
        MODELO_EMB_PATH or MODELO_EMB,
        backend=MODELO_EMB_BACKEND,
        model_kwargs=model_kwargs,
        revision=(MODELO_EMB_REVISION or None) if not MODELO_EMB_PATH else None,
    )


def get_embedding_model() -> "SentenceTransformer":
    """Carrega o encoder sob demanda, uma única vez por processo."""
    global _encoder
    if _encoder is None:
        with _encoder_lock:
            if _encoder is None:
                _encoder = carregar_encoder()
                logger.info(
                    "Encoder de embeddings carregado (%s, backend=%s)",
                    MODELO_EMB,
                    MODELO_EMB_BACKEND,
                )
    return _encoder


def init_llm() -> None:
    """Chamado uma vez no startup do FastAPI (ver app/main.py lifespan)."""
    if _api_key:
        genai.configure(api_key=_api_key)
        logger.info("Gemini configurado (%s)", MODELO_LLM)
    else:
        logger.warning("GOOGLE_API_KEY ausente; configure-a em Configurações.")


def configurar_api_key(api_key: str) -> None:
    """Aplica uma chave de API em runtime, sem registrá-la em logs."""
    global _api_key
    genai.configure(api_key=api_key)
    _api_key = api_key


def _cria_modelo(sistema, generation_config):
    if not _api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY não configurada. Abra Configurações para defini-la."
        )
    try:
        return genai.GenerativeModel(
            model_name=MODELO_LLM,
            system_instruction=sistema if sistema else None,
            generation_config=generation_config,
            safety_settings=SAFETY_SETTINGS,
        )
    except Exception as e:
        logger.warning(
            "safety_settings customizados falharam (%s: %s) — usando padrões do Gemini.",
            type(e).__name__,
            e,
        )
        return genai.GenerativeModel(
            model_name=MODELO_LLM,
            system_instruction=sistema if sistema else None,
            generation_config=generation_config,
        )


def _chama_com_retry(func_chamada, tentativas=3, espera_base=2):
    ultimo_erro = None
    for tentativa in range(tentativas):
        try:
            return func_chamada()
        except (
            Aborted,
            BadGateway,
            DeadlineExceeded,
            InternalServerError,
            ServiceUnavailable,
        ) as e:
            ultimo_erro = e
            if tentativa + 1 < tentativas:
                logger.warning(
                    "Serviço instável/timeout (tentativa %d/%d), aguardando %ds...",
                    tentativa + 1, tentativas, espera_base,
                )
                time.sleep(espera_base)
        except (ReadTimeout, RequestsConnectionError) as e:
            ultimo_erro = e
            if tentativa + 1 < tentativas:
                logger.warning(
                    "Timeout de conexão (%s) (tentativa %d/%d), aguardando %ds...",
                    type(e).__name__, tentativa + 1, tentativas, espera_base,
                )
                time.sleep(espera_base)
    raise ultimo_erro


def _checa_finish_reason(resposta):
    try:
        candidato = resposta.candidates[0]
        motivo = candidato.finish_reason
        if motivo not in (1, "STOP"):
            logger.warning(
                "Resposta cortada — finish_reason=%s (1=STOP normal, 2=MAX_TOKENS, "
                "3=SAFETY, 4=RECITATION)",
                motivo,
            )
    except Exception:
        pass


def llm(
    prompt: str,
    sistema: Optional[str] = None,
    historico_chat: Optional[List[dict]] = None,
    max_tokens: int = 2048,
    temperatura: float = 0.0,
) -> str:
    """Envia um prompt ao Gemini mantendo a separação entre sistema e usuário.

    historico_chat aqui já vem no formato {'role': 'user'|'assistant', 'content': str}
    (o schema Turno do FastAPI) — diferente do notebook, que aceitava também
    tuplas do Gradio legado. Simplificado porque o front-end é nosso.
    """
    generation_config = genai.GenerationConfig(
        max_output_tokens=max_tokens, temperature=temperatura
    )
    model = _cria_modelo(sistema, generation_config)
    request_options = _request_options()

    if historico_chat:
        historico_truncado = historico_chat[-(MAX_TURNOS_HISTORICO * 2):]
        history_fmt = []
        for item in historico_truncado:
            role = "model" if item["role"] == "assistant" else "user"
            if item.get("content"):
                history_fmt.append({"role": role, "parts": [str(item["content"])]})
        chat = model.start_chat(history=history_fmt)
        resposta = _chama_com_retry(
            lambda: chat.send_message(prompt, request_options=request_options)
        )
    else:
        resposta = _chama_com_retry(
            lambda: model.generate_content(prompt, request_options=request_options)
        )

    _checa_finish_reason(resposta)
    return resposta.text.strip()


def llm_stream(
    prompt: str,
    sistema: Optional[str] = None,
    historico_chat: Optional[List[dict]] = None,
    max_tokens: int = 2048,
    temperatura: float = 0.0,
) -> Iterator[str]:
    """Abre uma resposta em streaming e retorna um iterador de fragmentos."""
    generation_config = genai.GenerationConfig(
        max_output_tokens=max_tokens, temperature=temperatura
    )
    model = _cria_modelo(sistema, generation_config)
    request_options = _request_options()

    if historico_chat:
        historico_truncado = historico_chat[-(MAX_TURNOS_HISTORICO * 2):]
        history_fmt = []
        for item in historico_truncado:
            role = "model" if item["role"] == "assistant" else "user"
            if item.get("content"):
                history_fmt.append({"role": role, "parts": [str(item["content"])]})
        chat = model.start_chat(history=history_fmt)
        resposta = _chama_com_retry(
            lambda: chat.send_message(
                prompt, stream=True, request_options=request_options
            )
        )
    else:
        resposta = _chama_com_retry(
            lambda: model.generate_content(
                prompt, stream=True, request_options=request_options
            )
        )

    def fragmentos():
        ultimo_chunk = None
        for chunk in resposta:
            ultimo_chunk = chunk
            texto = chunk.text
            if texto:
                yield texto
        if ultimo_chunk is not None:
            _checa_finish_reason(ultimo_chunk)

    return fragmentos()


def embed(textos):
    """Gera embeddings localmente via SentenceTransformer."""
    encoder = get_embedding_model()
    is_single = isinstance(textos, str)
    if is_single:
        textos = [textos]
    res = encoder.encode(textos, show_progress_bar=False, convert_to_numpy=True)
    return res.squeeze() if is_single else res
