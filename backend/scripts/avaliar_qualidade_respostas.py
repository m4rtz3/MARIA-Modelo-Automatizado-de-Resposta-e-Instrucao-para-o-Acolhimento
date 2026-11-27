"""Avaliacao lexical e de abstenção das respostas reais da MARIA.

Importa diretamente app.maria.maria, sem notebook, sem globals e sem segundo LLM.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import re
import shutil
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

CORPUS_PATH = BACKEND_DIR / "data" / "corpus_referencias_qualidade.jsonl"
ABSTENCAO_PATH = BACKEND_DIR / "data" / "corpus_abstencao_qualidade.jsonl"
RESPOSTAS_PATH = BACKEND_DIR / "data" / "respostas_para_avaliar.jsonl"
CSV_PATH = BACKEND_DIR / "data" / "resultado_qualidade_respostas.csv"
JSON_PATH = BACKEND_DIR / "data" / "resultado_qualidade_respostas.json"


def ler_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")
    registros = []
    with path.open("r", encoding="utf-8-sig") as arquivo:
        for numero, linha in enumerate(arquivo, 1):
            linha = linha.strip()
            if not linha:
                continue
            try:
                item = json.loads(linha)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON inválido em {path}, linha {numero}: {exc}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"Cada linha de {path} deve conter um objeto JSON.")
            registros.append(item)
    return registros


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", str(texto).lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def tokens(texto: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalizar(texto))


def rouge(referencia: str, resposta: str) -> float:
    ref, ger = tokens(referencia), tokens(resposta)
    if not ref or not ger:
        return 0.0
    anterior = [0] * (len(ger) + 1)
    for token_ref in ref:
        atual = [0]
        for j, token_ger in enumerate(ger, 1):
            atual.append(
                anterior[j - 1] + 1 if token_ref == token_ger
                else max(anterior[j], atual[j - 1])
            )
        anterior = atual
    lcs = anterior[-1]
    precision = lcs / len(ger)
    recall = lcs / len(ref)
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


# Alias técnico usado por integrações e testes anteriores.
rouge_l = rouge


def token_scores(referencia: str, resposta: str) -> dict[str, float]:
    ref, ger = tokens(referencia), tokens(resposta)
    if not ref or not ger:
        return {"token_precision": 0.0, "token_recall": 0.0, "token_f1": 0.0}
    cr, cg = Counter(ref), Counter(ger)
    intersecao = sum((cr & cg).values())
    precision = intersecao / len(ger)
    recall = intersecao / len(ref)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {"token_precision": precision, "token_recall": recall, "token_f1": f1}


def metricas_tokens(referencia: str, resposta: str) -> tuple[float, float, float]:
    medidas = token_scores(referencia, resposta)
    return medidas["token_precision"], medidas["token_recall"], medidas["token_f1"]


def cobertura_pontos(pontos: list[str], resposta: str) -> tuple[float | None, list[dict[str, Any]]]:
    if not pontos:
        return None, []
    resposta_norm = normalizar(resposta)
    detalhes = []
    cobertos = 0
    for ponto in pontos:
        ponto_norm = normalizar(ponto).strip()
        coberto = bool(ponto_norm and ponto_norm in resposta_norm)
        if ponto_norm and not coberto:
            ponto_tokens = set(tokens(ponto_norm))
            resposta_tokens = set(tokens(resposta_norm))
            ponto_tokens.discard("para")
            ponto_tokens.discard("de")
            ponto_tokens.discard("da")
            ponto_tokens.discard("do")
            ponto_tokens.discard("em")
            ponto_tokens.discard("e")
            if ponto_tokens:
                coberto = len(ponto_tokens & resposta_tokens) / len(ponto_tokens) >= 0.5
        cobertos += coberto
        detalhes.append({"ponto": ponto, "coberto_literalmente": coberto})
    return cobertos / len(pontos), detalhes


FRASES_ABSTENCAO = (
    "não encontrei informação",
    "não tenho informações suficientes",
    "não consigo confirmar",
    "não tenho essa informação",
    "não é possível determinar",
    "não foi possível determinar",
)


def detectar_abstencao(texto: str) -> bool:
    norma = normalizar(texto)
    return any(normalizar(frase) in norma for frase in FRASES_ABSTENCAO)


def carregar_corpus(caminhos: list[Path]) -> list[dict[str, Any]]:
    casos = []
    ids = set()
    for caminho in caminhos:
        if not caminho.is_file():
            continue
        for pos, caso in enumerate(ler_jsonl(caminho), 1):
            caso_id = str(caso.get("id", "")).strip()
            pergunta = str(caso.get("pergunta", "")).strip()
            if not caso_id or not pergunta:
                raise ValueError(f"{caminho}: linha {pos} precisa ter 'id' e 'pergunta'.")
            if caso_id in ids:
                raise ValueError(f"Identificador duplicado no corpus: {caso_id}")
            ids.add(caso_id)
            referencia = str(
                caso.get("resposta_referencia", caso.get("expected_answer", ""))
            ).strip()
            pontos = caso.get("pontos_essenciais", caso.get("critical_points", []))
            if not isinstance(pontos, list):
                raise ValueError(f"Corpus {caso_id}: pontos essenciais deve ser lista.")
            campo = "abstencao_esperada" if "abstencao_esperada" in caso else (
                "requires_abstention" if "requires_abstention" in caso else (
                    "espera_abstencao" if "espera_abstencao" in caso else None
                )
            )
            caso["_referencia"] = referencia
            caso["_pontos"] = [str(p).strip() for p in pontos if str(p).strip()]
            caso["_abstencao_esperada"] = bool(caso[campo]) if campo else None
            casos.append(caso)
    if not casos:
        raise ValueError("Nenhum caso encontrado nos corpora informados.")
    return casos


def salvar_jsonl(path: Path, registros: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as arquivo:
        for item in registros:
            arquivo.write(json.dumps(item, ensure_ascii=False) + "\n")


def preservar_anterior(path: Path, selo: str) -> None:
    if not path.is_file():
        return
    destino = path.parent / "historico" / f"{path.stem}_{selo}{path.suffix}"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destino)


def avaliacao_completa(corpus: list[dict[str, Any]], respostas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    respostas_por_id = {str(r.get("id")): r for r in respostas if r.get("id") is not None}
    resultados = []
    for caso in corpus:
        resposta_item = respostas_por_id.get(str(caso["id"]))
        if not resposta_item:
            continue
        resposta = str(resposta_item.get("resposta_avaliada", "") or "")
        if not resposta and not resposta_item.get("erro_execucao"):
            continue
        referencia = caso["_referencia"]
        medidas = token_scores(referencia, resposta)
        cobertura, detalhes = cobertura_pontos(caso["_pontos"], resposta)
        absteve = bool(resposta_item.get("absteve", False))
        heurstica = detectar_abstencao(resposta)
        esperada = caso["_abstencao_esperada"]
        resultados.append({
            "id": caso["id"],
            "pergunta": caso["pergunta"],
            "resposta_referencia": referencia,
            "resposta_avaliada": resposta,
            "rouge_l_f1": rouge(referencia, resposta),
            "token_precision": medidas["token_precision"],
            "token_recall": medidas["token_recall"],
            "token_f1": medidas["token_f1"],
            "cobertura_pontos_essenciais": cobertura,
            "detalhes_pontos_essenciais": detalhes,
            "abstencao_esperada": esperada,
            "absteve": absteve,
            "abstencao_detectada_heuristicamente": heurstica,
            "compatibilidade_abstencao": (
                1.0 if esperada is None else float(esperada == absteve)
            ),
            "abstencao_compativel_heuristicamente": (
                None if esperada is None else esperada == heurstica
            ),
            "erro_execucao": resposta_item.get("erro_execucao"),
        })
    return resultados


# Alias usado pelos testes existentes.
def avaliar(corpus: list[dict[str, Any]], respostas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    casos = []
    for caso in corpus:
        caso = dict(caso)
        caso["_referencia"] = str(
            caso.get("resposta_referencia", caso.get("resposta_referencia", caso.get("expected_answer", "")))
        )
        caso["_pontos"] = list(caso.get("pontos_essenciais", caso.get("critical_points", [])))
        caso["_abstencao_esperada"] = bool(
            caso.get("abstencao_esperada", caso.get("requires_abstention", caso.get("espera_abstencao", False)))
        )
        casos.append(caso)
    resultados = avaliacao_completa(casos, respostas)
    return resultados


async def executar(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.WARNING)
    corpus = carregar_corpus([Path(args.corpus), Path(args.corpus_abstencao)])
    casos_execucao = corpus[:args.limite] if args.limite else corpus

    from app.maria import maria
    import app.main as main_module

    respostas_existentes = {}
    respostas_path = Path(args.respostas)
    if respostas_path.exists():
        for item in ler_jsonl(respostas_path):
            if item.get("id") is not None:
                respostas_existentes[str(item["id"])] = item

    selo = datetime.now().strftime("%Y%m%d_%H%M%S")
    for path in (respostas_path, Path(args.csv), Path(args.json)):
        preservar_anterior(path, selo)

    async with main_module.app.router.lifespan_context(main_module.app):
        for indice, caso in enumerate(casos_execucao, 1):
            caso_id = str(caso["id"])
            print(f"[{indice}/{len(casos_execucao)}] {caso_id}: chamando MARIA...")
            try:
                retorno = await maria(
                    str(caso["pergunta"]),
                    historico=[],
                    top_k=args.top_k,
                    temperatura=args.temperatura,
                    debug=False,
                )
                resposta = retorno.get("resposta")
                if not isinstance(resposta, str):
                    raise TypeError("O retorno de maria() não contém 'resposta' como texto.")
                respostas_existentes[caso_id] = {
                    "id": caso_id,
                    "pergunta": caso["pergunta"],
                    "resposta_avaliada": resposta,
                    "absteve": bool(retorno.get("absteve", False)),
                    "score_max_recuperacao": retorno.get("score_max_recuperacao"),
                    "localizacao_detectada": retorno.get("localizacao_detectada"),
                    "gerada_em": datetime.now().isoformat(timespec="seconds"),
                    "avaliacao_corpus": str(Path(args.corpus).resolve()),
                }
                print("   resposta registrada.")
            except Exception as exc:
                respostas_existentes[caso_id] = {
                    "id": caso_id,
                    "pergunta": caso["pergunta"],
                    "resposta_avaliada": "",
                    "erro_execucao": f"{type(exc).__name__}: {exc}",
                    "gerada_em": datetime.now().isoformat(timespec="seconds"),
                }
                print(f"   FALHA em {caso_id}: {type(exc).__name__}: {exc}")
            salvar_jsonl(
                respostas_path,
                [respostas_existentes[str(c["id"])] for c in casos_execucao if str(c["id"]) in respostas_existentes],
            )
            if args.intervalo > 0 and indice < len(casos_execucao):
                time.sleep(args.intervalo)

    respostas_por_id = ler_jsonl(respostas_path)
    resultados = avaliacao_completa(casos_execucao, respostas_por_id)
    metricas = [
        "rouge_l_f1", "token_precision", "token_recall", "token_f1",
        "cobertura_pontos_essenciais", "compatibilidade_abstencao",
    ]
    medias = {}
    for nome in metricas:
        valores = [r[nome] for r in resultados if isinstance(r.get(nome), (int, float))]
        medias[nome] = sum(valores) / len(valores) if valores else None

    resumo = {
        "executado_em": datetime.now().isoformat(timespec="seconds"),
        "corpora": [str(Path(args.corpus).resolve()), str(Path(args.corpus_abstencao).resolve())],
        "total_casos": len(casos_execucao),
        "respostas_com_texto": sum(bool(r["resposta_avaliada"]) for r in resultados),
        "erros": sum(bool(r["erro_execucao"]) for r in resultados),
        "medias": medias,
        "resultados_individuais": resultados,
        "nota_metodologica": (
            "Métricas lexicais e heurísticas; não representam acurácia factual, "
            "taxa de alucinação ou certeza de inexistência de alucinação."
        ),
    }

    csv_path, json_path = Path(args.csv).resolve(), Path(args.json).resolve()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    campos = list(resultados[0].keys()) if resultados else []
    campos = [c for c in campos if c != "detalhes_pontos_essenciais"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=campos, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(resultados)
    json_path.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nAvaliação concluída.")
    print(f"Casos processados: {len(casos_execucao)}")
    print(f"Respostas com texto: {resumo['respostas_com_texto']}")
    print(f"Erros: {resumo['erros']}")
    for nome, valor in medias.items():
        print(f"{nome}: {valor:.4f}" if valor is not None else f"{nome}: n/a")
    print(f"Respostas JSONL: {respostas_path.resolve()}")
    print(f"Resultados CSV: {csv_path}")
    print(f"Resultados JSON: {json_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia as respostas reais da MARIA.")
    parser.add_argument("--corpus", default=str(CORPUS_PATH))
    parser.add_argument("--corpus-abstencao", default=str(ABSTENCAO_PATH))
    parser.add_argument("--respostas", default=str(RESPOSTAS_PATH))
    parser.add_argument("--csv", default=str(CSV_PATH))
    parser.add_argument("--json", default=str(JSON_PATH))
    parser.add_argument("--limite", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--temperatura", type=float, default=0.0)
    parser.add_argument("--intervalo", type=float, default=12.0)
    args = parser.parse_args()
    if args.limite is not None and args.limite < 1:
        parser.error("--limite deve ser >= 1")
    if args.top_k < 1:
        parser.error("--top-k deve ser >= 1")
    if args.intervalo < 0:
        parser.error("--intervalo não pode ser negativo")
    asyncio.run(executar(args))


if __name__ == "__main__":
    main()
