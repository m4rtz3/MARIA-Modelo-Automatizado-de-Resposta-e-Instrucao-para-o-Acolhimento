from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Turno(BaseModel):
    """Um turno de conversa anterior, no formato que o front-end envia."""

    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    mensagem: str = Field(..., min_length=1, max_length=4000)
    historico: List[Turno] = Field(default_factory=list)
    top_k: int = Field(default=3, ge=1, le=8)
    temperatura: float = Field(default=0.6, ge=0.0, le=1.0)
    debug: bool = False


class ChatResponse(BaseModel):
    resposta: str
    localizacao_detectada: Optional[str] = None
    score_max_recuperacao: Optional[float] = None
    absteve: bool = False


class StatsRequest(BaseModel):
    pergunta: str = Field(..., min_length=1, max_length=500)


class StatsResponse(BaseModel):
    resultado: str


class SettingsUnlockRequest(BaseModel):
    senha: str = Field(..., min_length=1, max_length=256)


class SettingsUpdateRequest(SettingsUnlockRequest):
    google_api_key: Optional[str] = Field(default=None, min_length=10, max_length=500)


class HealthResponse(BaseModel):
    status: str
    kb_carregada: bool
    n_chunks: int
    datasets_carregados: List[str]
    datasets_sob_demanda: List[str] = Field(default_factory=list)
    datasets_disponiveis: List[str] = Field(default_factory=list)
