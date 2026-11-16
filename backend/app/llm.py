"""
Camada de chamada ao Gemini + embeddings locais.

Portado 1:1 da lógica já validada no notebook MARIA_chatbot_rag_GEMINI_hardness_2:
- retry em 429 (cota)/503/timeout, com backoff crescente
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
import logging
import time
from typing import Iterator, List, Optional

import google.generativeai as genai
import numpy as np
from google.api_core.exceptions import (
    DeadlineExceeded,
    GoogleAPICallError,
    ResourceExhausted,
    ServiceUnavailable,
    TooManyRequests,
)
from google.generativeai.types import HarmBlockThreshold, HarmCategory
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import ReadTimeout
from sentence_transformers import SentenceTransformer

from app.config import GOOGLE_API_KEY, MAX_TURNOS_HISTORICO, MODELO_EMB, MODELO_LLM, TIMEOUT_REQUEST_S

logger = logging.getLogger("maria.llm")

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

_encoder: Optional[SentenceTransformer] = None
_api_key: Optional[str] = GOOGLE_API_KEY or None


def init_llm() -> None:
    """Chamado uma vez no startup do FastAPI (ver app/main.py lifespan)."""
    global _encoder
    if _api_key:
        genai.configure(api_key=_api_key)
        logger.info("Gemini configurado (%s)", MODELO_LLM)
    else:
        logger.warning("GOOGLE_API_KEY ausente; configure-a em Configurações.")

    _encoder = SentenceTransformer(MODELO_EMB)
    logger.info("Encoder de embeddings carregado (%s)", MODELO_EMB)


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
        except (ResourceExhausted, TooManyRequests) as e:
            ultimo_erro = e
            if tentativa + 1 < tentativas:
                espera = espera_base * (tentativa + 1)
                logger.warning(
                    "Cota momentaneamente excedida (tentativa %d/%d), aguardando %ds...",
                    tentativa + 1, tentativas, espera,
                )
                time.sleep(espera)
        except (ServiceUnavailable, DeadlineExceeded) as e:
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
        except GoogleAPICallError as e:
            ultimo_erro = e
            if tentativa + 1 < tentativas:
                logger.warning(
                    "Erro de API (%s) (tentativa %d/%d), aguardando %ds...",
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
    request_options = {"timeout": TIMEOUT_REQUEST_S}

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
    request_options = {"timeout": TIMEOUT_REQUEST_S}

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
    if _encoder is None:
        raise RuntimeError("Encoder não inicializado — chame init_llm() no startup.")
    is_single = isinstance(textos, str)
    if is_single:
        textos = [textos]
    res = _encoder.encode(textos, show_progress_bar=False, convert_to_numpy=True)
    return res.squeeze() if is_single else res
