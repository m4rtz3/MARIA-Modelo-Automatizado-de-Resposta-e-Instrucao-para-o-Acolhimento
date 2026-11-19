"""Seleção local de trechos da KB para perguntas sobre dashboards."""
import re
import unicodedata
from typing import List


_TERMOS_IGNORADOS = {
    "a", "agora", "ao", "aos", "as", "com", "como", "da", "das", "de",
    "dizer", "do", "dos", "e", "em", "o", "os", "para", "pode", "por",
    "que", "qual", "quais", "sobre", "me", "projeto", "maria", "dashboard",
    "dashboards", "painel", "paineis",
}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(
        caractere for caractere in texto
        if unicodedata.category(caractere) != "Mn"
    )
    return re.sub(r"\s+", " ", texto)


def selecionar_contexto_dashboard(
    pergunta: str,
    chunks: List[dict],
    top_k: int = 3,
) -> List[dict]:
    """Seleciona diretamente da KB atual os trechos do painel perguntado."""
    if not chunks or top_k <= 0:
        return []

    pergunta_normalizada = _normalizar(pergunta)
    numero_painel = re.search(
        r"\b(?:painel|dashboard)\s*(?:n(?:[ºo.]|umero)?\s*)?([1-8])\b",
        pergunta_normalizada,
    )
    termos = {
        termo for termo in re.findall(r"[a-z0-9]+", pergunta_normalizada)
        if len(termo) > 2 and termo not in _TERMOS_IGNORADOS
    }

    classificados = []
    for posicao, chunk in enumerate(chunks):
        titulo = _normalizar(str(chunk.get("titulo", "")))
        texto = _normalizar(str(chunk.get("texto", "")))
        termos_titulo = set(re.findall(r"[a-z0-9]+", titulo))
        termos_texto = set(re.findall(r"[a-z0-9]+", texto))
        pontuacao = sum(
            4 if termo in termos_titulo else 1 if termo in termos_texto else 0
            for termo in termos
        )
        if numero_painel and f"painel {numero_painel.group(1)}" in titulo:
            pontuacao += 100
        if pontuacao:
            classificados.append((pontuacao, posicao, chunk))

    classificados.sort(key=lambda item: (-item[0], item[1]))
    selecionados = [item[2] for item in classificados[:top_k]]
    if not selecionados:
        selecionados = chunks[:1]

    return [{**chunk, "sim": 1.0} for chunk in selecionados]