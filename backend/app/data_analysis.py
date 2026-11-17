"""
Consulta os CSVs do pipeline (features_vitima/agressor/historico/territorial)
sob demanda. Port fiel das células de Dados do notebook
MARIA_chatbot_rag_GEMINI_hardness_5 — duas camadas:

1. Funções nomeadas por categoria (_consulta_*), parametrizadas só por
   `ano`, que dobram como FERRAMENTAS de function calling nativo do
   Gemini (consultar_dados_via_function_calling) — o modelo decide se a
   pergunta precisa de dado real e qual função chamar, sem escrever JSON
   como texto solto pra gente dar parse (isso quebrava por corte de
   MAX_TOKENS antes de decidir a chamada).
2. analisar_dados() — casamento por palavra-chave (SINONIMOS), sem custo
   de API. Roda como segunda checagem dentro de maria() (só entra se o
   function calling não achou nada) e segue exposta em GET /api/stats.
"""
import csv
import logging
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
from google.generativeai.generative_models import GenerativeModel

from app.config import DADOS_BI_PATH, MODELO_LLM, TIMEOUT_REQUEST_S
from app.llm import _chama_com_retry

logger = logging.getLogger("maria.data_analysis")

_dados: Dict[str, pd.DataFrame] = {}
_arquivos_csv: Dict[str, Path] = {}
_csvs_sob_demanda: Dict[str, Path] = {}
_colunas_csv: Dict[str, list[str]] = {}
_TAMANHO_BLOCO_CSV = 10000

_CAMPOS_INDIVIDUAIS = {
    "nivel_risco": {"MARIA_individual": "nivel_risco", "MARIA_individual_legivel": "Nível de risco"},
    "faixa_etaria": {"MARIA_individual": "faixa_etaria", "MARIA_individual_legivel": "Faixa etária"},
    "raca_cor": {"MARIA_individual": "raca_cor", "MARIA_individual_legivel": "Raça/Cor"},
    "escolaridade": {"MARIA_individual": "escolaridade", "MARIA_individual_legivel": "Escolaridade"},
    "sit_conjugal": {"MARIA_individual": "sit_conjugal", "MARIA_individual_legivel": "Situação conjugal"},
    "gestante": {"MARIA_individual": "gestante", "MARIA_individual_legivel": "Gestante"},
    "tipo_violencia": {"MARIA_individual": "tipo_violencia", "MARIA_individual_legivel": "Tipo de violência"},
    "reincidencia": {"MARIA_individual": "reincidencia", "MARIA_individual_legivel": "Reincidência"},
    "local_ocor": {"MARIA_individual": "local_ocor", "MARIA_individual_legivel": "Local da ocorrência"},
    "autor_sexo": {"MARIA_individual": "autor_sexo", "MARIA_individual_legivel": "Sexo do agressor"},
    "autor_alcool": {"MARIA_individual": "autor_alcool", "MARIA_individual_legivel": "Agressor usou álcool"},
    "autor_parentesco": {"MARIA_individual": "autor_parentesco", "MARIA_individual_legivel": "Parentesco do agressor"},
    "vinculo_intimo": {"MARIA_individual": "vinculo_intimo", "MARIA_individual_legivel": "Vínculo íntimo"},
    "desfecho": {"MARIA_individual": "desfecho", "MARIA_individual_legivel": "Desfecho"},
    "evolucao_caso": {"MARIA_individual": "evolucao_caso", "MARIA_individual_legivel": "Evolução do caso"},
    "UF": {"MARIA_individual": "UF", "MARIA_individual_legivel": "UF"},
}


def listar_datasets_disponiveis() -> list[str]:
    return sorted(_arquivos_csv)


def listar_datasets_sob_demanda() -> list[str]:
    return sorted(_csvs_sob_demanda)

SINONIMOS = {
    "vitima": ["vítima", "vitima", "mulher", "mulheres", "ela", "pessoa"],
    "gestante": ["gestante", "grávida", "gravida", "gravidez", "gestação", "gestacao", "prenha", "esperando filho", "esperando bebê"],
    "agressor": ["agressor", "agrede", "bateu", "bate", "marido", "companheiro", "namorado", "parceiro", "ex", "quem agride", "quem bate", "suspeito"],
    "alcool": ["álcool", "alcool", "bebida", "bêbado", "bebado", "embriagado", "droga", "drogas", "sob efeito"],
    "vinculo": ["vínculo", "vinculo", "relação", "relacao", "parceiro", "marido", "companheiro", "namorado", "ex-marido", "ex-namorado", "pai", "padrasto", "irmão", "familiar"],
    "historico": ["histórico", "historico", "reincidência", "reincidencia", "recorrente", "repete", "repetição", "escalada", "walker", "notificação", "notificações", "quantas vezes", "frequência"],
    "violencia": ["violência", "violencia", "tipo de violência", "tipos", "física", "fisica", "psicológica", "psicologica", "sexual", "patrimonial", "moral"],
    "territorial": ["região", "regiao", "estado", "uf", "nordeste", "sudeste", "sul", "norte", "centro-oeste", "idh", "cidade", "municipal", "onde", "localização"],
    "datasenado": ["datasenado", "data senado", "pesquisa senado", "pesquisa de opinião", "pesquisa de opiniao"],
    "dados": ["quantas", "quantos", "total", "número", "numero", "porcentagem", "percentual", "dados", "estatística", "estatistica", "base", "dataset"],
    "lesao": ["lesão", "lesao", "autoprovocada", "autolesão", "autolesao", "automutilação", "suicídio", "suicidio"],
    "escolaridade": ["escolaridade", "estudo", "educação", "educacao", "analfabeta", "ensino"],
    "idade": ["idade", "anos", "faixa etária", "faixa etaria", "jovem", "idosa", "velha"],
}


def carregar_datasets() -> None:
    """Registra os CSVs no startup sem carregá-los inteiros na memória."""
    _dados.clear()
    _arquivos_csv.clear()
    _csvs_sob_demanda.clear()
    _colunas_csv.clear()
    if DADOS_BI_PATH.exists():
        _arquivos_csv.update({arquivo.stem: arquivo for arquivo in DADOS_BI_PATH.glob("*.csv")})

    for nome, arquivo in _arquivos_csv.items():
        with arquivo.open(encoding="utf-8-sig", newline="") as stream:
            _colunas_csv[nome] = next(csv.reader(stream), [])
        _csvs_sob_demanda[nome] = arquivo

    logger.info(
        "%d datasets registrados para leitura sob demanda; nenhum CSV carregado na memória",
        len(_arquivos_csv),
    )


def construir_enriquecimento_csvs() -> str:
    """Resumo estatístico do pipeline (BLOCO 7), pra anexar ao texto da KB
    antes do chunking — mesma lógica da célula "Enriquece com CSVs do
    pipeline" do notebook. Usado por app/kb.py (modo local) e por
    scripts/indexador.py (modo pgvector), pra não terem duas versões
    divergentes dessa lógica."""
    resumo = ["\n\n---\n", "## BLOCO 7: ESTATÍSTICAS DO PIPELINE\n"]

    arq = DADOS_BI_PATH / "MARIA_chaves.csv"
    if arq.exists():
        ch = pd.read_csv(arq, low_memory=False)
        resumo.append(f"Dataset: {len(ch):,} pessoas, {len(ch.columns)} colunas")
        if "nivel_risco" in ch.columns:
            for nv in ["basal", "moderado", "alto"]:
                n = (ch["nivel_risco"] == nv).sum()
                resumo.append(f"- {nv}: {n:,} ({n/len(ch)*100:.1f}%)")

    for arq_nome, prefixo, cols_interesse in [
        ("features_vitima.csv", "vitima",
         ["vitima_reincidencia", "vitima_lesao_autoprovocada", "vitima_gestante"]),
        ("features_agressor.csv", "agressor",
         ["agressor_alcool", "agressor_multiplos_envolvidos"]),
    ]:
        arq = DADOS_BI_PATH / arq_nome
        if arq.exists():
            df = pd.read_csv(arq, low_memory=False)
            resumo.append(f"\n### {prefixo.capitalize()}")
            for col in cols_interesse:
                if col in df.columns:
                    n = df[col].sum()
                    desc = col.replace(f"{prefixo}_", "").replace("_", " ").capitalize()
                    resumo.append(f"- {desc}: {n:,.0f} ({n/len(df)*100:.1f}%)")
            if prefixo == "agressor":
                for col in sorted(df.columns):
                    if "vinculo" in col and df[col].dtype in ["float64", "int64"]:
                        n = df[col].sum()
                        pct = n / len(df) * 100
                        if pct > 1:
                            resumo.append(
                                f"- {col.replace('agressor_', '').replace('_', ' ').capitalize()}: "
                                f"{n:,.0f} ({pct:.1f}%)"
                            )

    arq = DADOS_BI_PATH / "features_historico.csv"
    if arq.exists():
        hist = pd.read_csv(arq, low_memory=False)
        resumo.append("\n### Histórico")
        if "hist_n_notificacoes" in hist.columns:
            resumo.append(
                f"- Notificações/pessoa: média {hist['hist_n_notificacoes'].mean():.1f}, "
                f"mediana {hist['hist_n_notificacoes'].median():.0f}"
            )
        if "hist_tem_escalada_walker" in hist.columns:
            n = hist["hist_tem_escalada_walker"].sum()
            resumo.append(f"- Escalada de Walker: {n:,.0f} ({n/len(hist)*100:.1f}%)")
        for col in sorted(hist.columns):
            if "teve_viol_" in col and hist[col].dtype in ["float64", "int64"]:
                n = hist[col].sum()
                pct = n / len(hist) * 100
                if pct > 1:
                    resumo.append(
                        f"- {col.replace('hist_teve_', '').replace('_', ' ').capitalize()}: "
                        f"{n:,.0f} ({pct:.1f}%)"
                    )

    return "\n".join(resumo)


def _match(pergunta_lower: str, categoria: str) -> bool:
    return any(s in pergunta_lower for s in SINONIMOS.get(categoria, []))


def _extrair_ano(pergunta: str):
    m = re.search(r"(20[12]\d)", pergunta)
    return int(m.group(1)) if m else None


def _filtrar_por_ano(df: pd.DataFrame, ano):
    if ano is None or "chave_linkage" not in df.columns:
        return df, ""
    mask = df["chave_linkage"].str.contains(f"_{ano}_", na=False)
    df_filtrado = df[mask]
    if len(df_filtrado) == 0:
        return df, f"(sem dados para {ano}, mostrando total)"
    return df_filtrado, f"(filtrado para {ano}: {len(df_filtrado):,} pessoas)"


def _novo_resumo_csv() -> dict:
    return {
        "n": 0,
        "somas": {},
        "contagens": {},
        "minimos": {},
        "maximos": {},
        "frequencias": {},
    }


def _acumular_bloco(
    resumo: dict,
    bloco: pd.DataFrame,
    colunas_numericas: list[str],
    colunas_categoricas: list[str],
    colunas_frequencia: list[str],
) -> None:
    resumo["n"] += len(bloco)
    for coluna in colunas_numericas:
        if coluna not in bloco:
            continue
        valores = pd.to_numeric(bloco[coluna], errors="coerce").dropna()
        if valores.empty:
            continue
        resumo["somas"][coluna] = resumo["somas"].get(coluna, 0.0) + float(valores.sum())
        resumo["contagens"][coluna] = resumo["contagens"].get(coluna, 0) + len(valores)
        minimo = float(valores.min())
        maximo = float(valores.max())
        resumo["minimos"][coluna] = min(resumo["minimos"].get(coluna, minimo), minimo)
        resumo["maximos"][coluna] = max(resumo["maximos"].get(coluna, maximo), maximo)
        if coluna in colunas_frequencia:
            frequencias = resumo["frequencias"].setdefault(coluna, Counter())
            frequencias.update(valores.value_counts().to_dict())

    for coluna in colunas_categoricas:
        if coluna in bloco:
            resumo["frequencias"].setdefault(coluna, Counter()).update(
                bloco[coluna].dropna().astype(str).value_counts().to_dict()
            )


def _resumir_csv(
    nome: str,
    *,
    prefixos_numericos: tuple[str, ...] = (),
    colunas_numericas: tuple[str, ...] = (),
    colunas_categoricas: tuple[str, ...] = (),
    colunas_frequencia: tuple[str, ...] = (),
    ano: Optional[int] = None,
) -> tuple[Optional[dict], str]:
    arquivo = _arquivos_csv.get(nome)
    if not arquivo:
        return None, ""

    colunas = _colunas_csv.get(nome, [])
    numericas = [
        coluna for coluna in colunas
        if coluna in colunas_numericas
        or any(coluna.startswith(prefixo) for prefixo in prefixos_numericos)
    ]
    categoricas = [coluna for coluna in colunas if coluna in colunas_categoricas]
    coluna_ano = "chave_linkage" if ano is not None and "chave_linkage" in colunas else None
    colunas_lidas = list(dict.fromkeys([*numericas, *categoricas, *([coluna_ano] if coluna_ano else [])]))
    if not colunas_lidas and colunas:
        colunas_lidas = [colunas[0]]

    total = _novo_resumo_csv()
    filtrado = _novo_resumo_csv()
    with pd.read_csv(
        arquivo,
        usecols=colunas_lidas,
        chunksize=_TAMANHO_BLOCO_CSV,
    ) as blocos:
        for bloco in blocos:
            _acumular_bloco(total, bloco, numericas, categoricas, list(colunas_frequencia))
            if coluna_ano is None:
                continue
            mascara = bloco[coluna_ano].astype("string").str.contains(
                f"_{ano}_", na=False
            )
            selecionado = bloco[mascara]
            if not selecionado.empty:
                _acumular_bloco(
                    filtrado,
                    selecionado,
                    numericas,
                    categoricas,
                    list(colunas_frequencia),
                )

    if coluna_ano is None:
        return total, ""
    if filtrado["n"]:
        return filtrado, f"(filtrado para {ano}: {filtrado['n']:,} pessoas)"
    return total, f"(sem dados para {ano}, mostrando total)"


def _stats_binarias_resumo(
    resumo: dict, prefix: str, n: int, colunas: list[str], top: int = 15
):
    linhas = []
    for col in sorted(colunas):
        if col.startswith(prefix) and col != "chave_linkage":
            if col not in resumo["minimos"]:
                continue
            if resumo["maximos"][col] <= 1 and resumo["minimos"][col] >= 0:
                soma = resumo["somas"][col]
                pct = soma / n * 100 if n > 0 else 0
                if pct > 0.5:
                    nome = col.replace(prefix, "").replace("_", " ").strip().capitalize()
                    linhas.append((pct, f"  {nome}: {soma:,.0f} ({pct:.1f}%)"))
    linhas.sort(reverse=True)
    return [l[1] for l in linhas[:top]]


def _mediana_frequencias(frequencias: Counter) -> float:
    total = sum(frequencias.values())
    if not total:
        return 0.0
    posicoes = {(total - 1) // 2, total // 2}
    valores = []
    acumulado = 0
    for valor, quantidade in sorted(frequencias.items()):
        proximo = acumulado + quantidade
        valores.extend(valor for posicao in posicoes if acumulado <= posicao < proximo)
        acumulado = proximo
        if len(valores) == len(posicoes):
            break
    return float(sum(valores) / len(valores))


# ---------------------------------------------------------------------
# Funções por categoria — usadas tanto por analisar_dados() (palavra-chave)
# quanto como ferramentas de function calling (ver _TOOLS_DADOS abaixo).
# ---------------------------------------------------------------------
def _consulta_dataset_geral(ano: Optional[int] = None):
    resumo, nota = _resumir_csv(
        "MARIA_chaves",
        colunas_categoricas=("nivel_risco",),
        ano=ano,
    )
    if resumo is None:
        return []
    n = resumo["n"]
    colunas = _colunas_csv.get("MARIA_chaves", [])
    linhas = [f"DATASET {nota}: {n:,} pessoas, {len(colunas)} variáveis"]
    if "nivel_risco" in colunas:
        contagens = resumo["frequencias"].get("nivel_risco", Counter())
        for nv in ["basal", "moderado", "alto"]:
            cnt = contagens.get(nv, 0)
            linhas.append(f"  {nv}: {cnt:,} ({cnt/n*100:.1f}%)" if n > 0 else f"  {nv}: 0")
    return linhas


def _consulta_vitima(ano: Optional[int] = None):
    resumo, nota = _resumir_csv(
        "features_vitima",
        prefixos_numericos=("vitima_",),
        ano=ano,
    )
    if resumo is None:
        return []
    colunas = _colunas_csv.get("features_vitima", [])
    n = resumo["n"]
    linhas = [f"\nPERFIL DA VÍTIMA {nota} ({n:,} pessoas):"]
    for col in colunas:
        cl = col.lower()
        if "gestante" in cl:
            s = resumo["somas"].get(col, 0)
            linhas.append(f"  Gestantes: {s:,.0f} de {n:,} ({s/n*100:.1f}%)" if n > 0 else "  Gestantes: sem dados")
        elif "idade_media" in cl:
            quantidade = resumo["contagens"].get(col, 0)
            media = resumo["somas"].get(col, 0) / quantidade if quantidade else 0
            linhas.append(f"  Idade média: {media:.1f} anos")
        elif "idade_min" in cl:
            if col in resumo["minimos"]:
                linhas.append(f"  Idade mínima: {resumo['minimos'][col]:.0f} anos")
        elif "idade_max" in cl:
            if col in resumo["maximos"]:
                linhas.append(f"  Idade máxima: {resumo['maximos'][col]:.0f} anos")
    linhas.extend(_stats_binarias_resumo(resumo, "vitima_", n, colunas))
    return linhas


def _consulta_agressor(ano: Optional[int] = None):
    resumo, nota = _resumir_csv(
        "features_agressor",
        prefixos_numericos=("agressor_",),
        ano=ano,
    )
    if resumo is None:
        return []
    colunas = _colunas_csv.get("features_agressor", [])
    n = resumo["n"]
    linhas = [f"\nPERFIL DO AGRESSOR {nota} ({n:,} pessoas):"]
    vinculo_linhas = _stats_binarias_resumo(
        resumo, "agressor_vinculo_", n, colunas
    )
    if vinculo_linhas:
        linhas.append("  Vínculo com a vítima:")
        linhas.extend([f"  {l}" for l in vinculo_linhas])
    for col, desc in [("agressor_alcool", "Álcool envolvido"),
                       ("agressor_multiplos_envolvidos", "Múltiplos agressores")]:
        if col in colunas:
            s = resumo["somas"].get(col, 0)
            linhas.append(f"  {desc}: {s:,.0f} ({s/n*100:.1f}%)" if n > 0 else f"  {desc}: sem dados")
    meios_linhas = _stats_binarias_resumo(resumo, "agressor_meio_", n, colunas)
    if meios_linhas:
        linhas.append("  Meios de agressão:")
        linhas.extend([f"  {l}" for l in meios_linhas])
    return linhas


def _consulta_historico(ano: Optional[int] = None):
    resumo, nota = _resumir_csv(
        "features_historico",
        prefixos_numericos=("hist_",),
        colunas_frequencia=(
            "hist_n_notificacoes",
            "hist_n_tipos_violencia",
        ),
        ano=ano,
    )
    if resumo is None:
        return []
    colunas = _colunas_csv.get("features_historico", [])
    n = resumo["n"]
    linhas = [f"\nHISTÓRICO {nota} ({n:,} pessoas):"]
    if "hist_n_notificacoes" in colunas:
        quantidade = resumo["contagens"].get("hist_n_notificacoes", 0)
        media = (
            resumo["somas"].get("hist_n_notificacoes", 0) / quantidade
            if quantidade else 0
        )
        mediana = _mediana_frequencias(
            resumo["frequencias"].get("hist_n_notificacoes", Counter())
        )
        linhas.append(
            f"  Notificações/pessoa: média {media:.1f}, "
            f"mediana {mediana:.0f}"
        )
    if "hist_tem_escalada_walker" in colunas:
        s = resumo["somas"].get("hist_tem_escalada_walker", 0)
        linhas.append(f"  Escalada de Walker: {s:,.0f} ({s/n*100:.1f}%)" if n > 0 else "  Escalada: sem dados")
    viol_linhas = _stats_binarias_resumo(resumo, "hist_teve_viol_", n, colunas)
    if viol_linhas:
        linhas.append("  Tipos de violência:")
        linhas.extend([f"  {l}" for l in viol_linhas])
    if "hist_n_tipos_violencia" in colunas and n > 0:
        poli = resumo["frequencias"].get("hist_n_tipos_violencia", Counter())
        poli = sum(qtd for valor, qtd in poli.items() if float(valor) >= 2)
        linhas.append(f"  Polimorfia (2+ tipos): {poli:,} ({poli/n*100:.1f}%)")
    return linhas


def _consulta_territorial(ano: Optional[int] = None):
    resumo, nota = _resumir_csv(
        "features_territorial",
        colunas_categoricas=("terr_regiao", "terr_uf"),
        ano=ano,
    )
    if resumo is None:
        return []
    n = resumo["n"]
    linhas = [f"\nTERRITORIAL {nota} ({n:,} pessoas):"]
    if "terr_regiao" in _colunas_csv.get("features_territorial", []):
        for reg, cnt in resumo["frequencias"].get("terr_regiao", Counter()).items():
            linhas.append(f"  {reg}: {cnt:,} ({cnt/n*100:.1f}%)")
    if "terr_uf" in _colunas_csv.get("features_territorial", []):
        contagens_uf = resumo["frequencias"].get("terr_uf", Counter())
        for uf, cnt in contagens_uf.most_common(5):
            linhas.append(f"  {uf}: {cnt:,}")
    return linhas


def _consulta_datasenado():
    arquivo = _csvs_sob_demanda.get("features_datasenado")
    if not arquivo:
        return []

    somas: Dict[str, float] = {}
    quantidades: Dict[str, int] = {}
    n_linhas = 0
    for bloco in pd.read_csv(
        arquivo,
        usecols=lambda coluna: isinstance(coluna, str) and coluna.startswith("ds_"),
        chunksize=_TAMANHO_BLOCO_CSV,
    ):
        n_linhas += len(bloco)
        for coluna in bloco.columns:
            valores = pd.to_numeric(bloco[coluna], errors="coerce").dropna()
            somas[coluna] = somas.get(coluna, 0.0) + float(valores.sum())
            quantidades[coluna] = quantidades.get(coluna, 0) + len(valores)

    linhas = [f"PESQUISA DATA SENADO ({n_linhas:,} linhas; médias dos indicadores):"]
    for coluna in sorted(somas):
        if quantidades[coluna]:
            rotulo = coluna.removeprefix("ds_regiao_pct_").removeprefix("ds_pct_").replace("_", " ")
            linhas.append(f"  {rotulo}: {somas[coluna] / quantidades[coluna]:.2f}")
    return linhas


def _consulta_dados_individuais(
    dataset: str, categoria: str, ano: Optional[int] = None
):
    arquivo = _csvs_sob_demanda.get(dataset)
    coluna = _CAMPOS_INDIVIDUAIS.get(categoria, {}).get(dataset)
    if not arquivo or not coluna:
        return []

    coluna_ano = "ano" if dataset == "MARIA_individual" else "Ano"
    contagens = Counter()
    total = 0
    for bloco in pd.read_csv(
        arquivo,
        usecols=[coluna, coluna_ano],
        chunksize=_TAMANHO_BLOCO_CSV,
    ):
        if ano is not None:
            anos = pd.to_numeric(bloco[coluna_ano], errors="coerce")
            bloco = bloco[anos == ano]
        total += len(bloco)
        contagens.update(bloco[coluna].dropna().astype(str).value_counts().to_dict())

    if not total:
        return [f"Sem registros para {categoria} no dataset {dataset}."]

    linhas = [f"{categoria} em {dataset} ({total:,} registros{f', ano {ano}' if ano else ''}):"]
    linhas.extend(
        f"  {valor}: {quantidade:,} ({quantidade / total * 100:.1f}%)"
        for valor, quantidade in contagens.most_common(10)
        if quantidade >= 5
    )
    suprimidos = sum(quantidade for quantidade in contagens.values() if quantidade < 5)
    if suprimidos:
        linhas.append(f"  Categorias com menos de 5 registros: {suprimidos:,} (agrupadas)")
    return linhas


def analisar_dados(pergunta: str) -> str:
    """Analisa os CSVs do pipeline por casamento de palavra-chave
    (SINONIMOS) — sem custo de API. Usada pelo endpoint GET /api/stats e,
    dentro de maria(), como segunda checagem barata que só entra se o
    function calling (consultar_dados_via_function_calling) não achou
    nada, pra não duplicar o mesmo número duas vezes no prompt."""
    p = pergunta.lower()
    resultados = []
    ano = _extrair_ano(pergunta)

    if _match(p, "dados"):
        resultados.extend(_consulta_dataset_geral(ano))
    if (_match(p, "vitima") or _match(p, "gestante") or _match(p, "lesao")
            or _match(p, "escolaridade") or _match(p, "idade") or _match(p, "dados")):
        resultados.extend(_consulta_vitima(ano))
    if _match(p, "agressor") or _match(p, "vinculo") or _match(p, "alcool") or _match(p, "dados"):
        resultados.extend(_consulta_agressor(ano))
    if _match(p, "historico") or _match(p, "violencia") or _match(p, "dados"):
        resultados.extend(_consulta_historico(ano))
    if _match(p, "territorial"):
        resultados.extend(_consulta_territorial(ano))
    if _match(p, "datasenado"):
        resultados.extend(_consulta_datasenado())
    if any(term in p for term in ["microdados", "dados individuais", "dataset individual"]):
        categoria = next(
            (nome for nome, termos in {
                "nivel_risco": ["risco", "nível", "nivel"],
                "faixa_etaria": ["idade", "faixa etária", "faixa etaria"],
                "raca_cor": ["raça", "raca", "cor"],
                "escolaridade": ["escolaridade", "estudo"],
                "sit_conjugal": ["estado civil", "situação conjugal", "situacao conjugal"],
                "gestante": ["gestante", "gravidez"],
                "tipo_violencia": ["tipo de violência", "tipo de violencia"],
                "reincidencia": ["reincidência", "reincidencia"],
                "local_ocor": ["local", "município", "municipio", "uf", "estado"],
                "autor_sexo": ["sexo do agressor"],
                "autor_alcool": ["álcool", "alcool", "bebida"],
                "autor_parentesco": ["parentesco", "vínculo", "vinculo"],
                "desfecho": ["desfecho", "resultado do caso"],
                "evolucao_caso": ["evolução", "evolucao"],
            }.items() if any(term in p for term in termos)),
            None,
        )
        dataset = "MARIA_individual_legivel" if "legível" in p or "legivel" in p else "MARIA_individual"
        if categoria:
            resultados.extend(_consulta_dados_individuais(dataset, categoria, ano))

    if not resultados:
        return "(sem dados específicos para esta pergunta)"

    return "\n".join(resultados)


def pergunta_pede_dados_reais(pergunta: str) -> bool:
    """Evita roteamento pago quando a pergunta não pede dados ou estatísticas."""
    normalizada = unicodedata.normalize("NFD", pergunta.lower())
    normalizada = "".join(
        caractere for caractere in normalizada
        if unicodedata.category(caractere) != "Mn"
    )
    termos = (
        "quantas", "quantos", "quantidade", "percentual", "porcentagem",
        "estatistica", "dados", "dataset", "microdados", "prevalencia",
        "distribuicao", "frequencia", "mais comum", "mais frequente",
        "taxa", "media", "perfil", "data senado",
    )
    return any(termo in normalizada for termo in termos)


# ---------------------------------------------------------------------
# Function calling nativo do Gemini — o modelo decide, com argumentos
# tipados e validados pelo schema (sem JSON-texto solto pra dar parse),
# se a pergunta precisa de consulta a dado real e qual(is) função(ões)
# chamar. Mesmo princípio do "Router Query Engine" usado em RAG de
# produção pra rotear entre um índice de texto e uma fonte de dados
# estruturada — roteador independente do de categoria de KB
# (decompoe_pergunta, em app/retrieval.py), que nunca teve esse problema
# de truncamento e por isso continua em JSON-texto.
# ---------------------------------------------------------------------
_FERRAMENTAS_DADOS = {
    "consultar_dataset_geral": _consulta_dataset_geral,
    "consultar_perfil_vitima": _consulta_vitima,
    "consultar_perfil_agressor": _consulta_agressor,
    "consultar_historico": _consulta_historico,
    "consultar_territorial": _consulta_territorial,
    "consultar_pesquisa_datasenado": lambda ano=None: _consulta_datasenado(),
    "consultar_dados_individuais": _consulta_dados_individuais,
}

_TOOLS_DADOS = [{
    "function_declarations": [
        {
            "name": "consultar_dataset_geral",
            "description": ("Retorna o tamanho total do dataset e a distribuição de "
                             "nível de risco (basal/moderado/alto). Use para perguntas "
                             'gerais do tipo "quantas pessoas"/"o dataset todo".'),
            "parameters": {
                "type": "object",
                "properties": {
                    "ano": {"type": "integer",
                            "description": "Filtra pelo ano do caso (ex: 2020). Omitir para todos os anos."},
                },
            },
        },
        {
            "name": "consultar_perfil_vitima",
            "description": ("Retorna estatísticas do perfil da vítima: gestantes, idade, "
                             "lesão autoprovocada, reincidência e demais flags. Use para "
                             "qualquer pergunta sobre características das vítimas."),
            "parameters": {
                "type": "object",
                "properties": {
                    "ano": {"type": "integer",
                            "description": "Filtra pelo ano do caso (ex: 2020). Omitir para todos os anos."},
                },
            },
        },
        {
            "name": "consultar_perfil_agressor",
            "description": ("Retorna estatísticas do perfil do agressor: vínculo com a "
                             "vítima, envolvimento de álcool, múltiplos agressores, meios "
                             "de agressão. Use para perguntas sobre quem agride."),
            "parameters": {
                "type": "object",
                "properties": {
                    "ano": {"type": "integer",
                            "description": "Filtra pelo ano do caso (ex: 2020). Omitir para todos os anos."},
                },
            },
        },
        {
            "name": "consultar_historico",
            "description": ("Retorna estatísticas de histórico: número de notificações, "
                             "escalada de violência (Walker), tipos de violência sofridos, "
                             "polimorfia (2+ tipos). Use para perguntas sobre reincidência, "
                             "escalada ou tipos de violência mais comuns."),
            "parameters": {
                "type": "object",
                "properties": {
                    "ano": {"type": "integer",
                            "description": "Filtra pelo ano do caso (ex: 2020). Omitir para todos os anos."},
                },
            },
        },
        {
            "name": "consultar_territorial",
            "description": ("Retorna distribuição por região e por estado (UF). Use para "
                             "perguntas sobre onde os casos acontecem."),
            "parameters": {
                "type": "object",
                "properties": {
                    "ano": {"type": "integer",
                            "description": "Filtra pelo ano do caso (ex: 2020). Omitir para todos os anos."},
                },
            },
        },
        {
            "name": "consultar_pesquisa_datasenado",
            "description": ("Calcula as médias dos indicadores agregados da pesquisa DataSenado. "
                             "Use para perguntas explicitamente sobre a pesquisa DataSenado ou opinião pública."),
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "consultar_dados_individuais",
            "description": ("Calcula distribuições agregadas dos microdados individuais, lendo o CSV em blocos. "
                             "Use somente quando a pergunta pedir dados individuais/microdados; nunca retorna registros pessoais."),
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset": {
                        "type": "string",
                        "enum": ["MARIA_individual", "MARIA_individual_legivel"],
                        "description": "Escolha o CSV individual disponível.",
                    },
                    "categoria": {
                        "type": "string",
                        "enum": sorted(_CAMPOS_INDIVIDUAIS),
                        "description": "Categoria para agregar, como nível de risco, faixa etária ou tipo de violência.",
                    },
                    "ano": {
                        "type": "integer",
                        "description": "Filtra pelo ano do caso; omita para todos os anos.",
                    },
                },
                "required": ["dataset", "categoria"],
            },
        },
    ]
}]

_SISTEMA_ROTEADOR_DADOS = (
    "Você decide se uma pergunta sobre violência doméstica precisa de uma "
    "consulta a dados reais do pipeline (números, percentuais, perfis, pesquisa DataSenado ou microdados). "
    "Se precisar, chame a função correspondente (pode chamar mais de uma "
    "se a pergunta cruzar categorias). Se a pergunta for uma explicação de "
    "lei, uma orientação de conduta, ou não pedir número nenhum, NÃO chame "
    "nenhuma função."
)


def consultar_dados_via_function_calling(pergunta: str, debug: bool = False) -> str:
    """Deixa o Gemini decidir — via function calling nativo, não JSON-texto —
    se a pergunta precisa de consulta a dado real e, se sim, qual(is)
    função(ões) chamar, com o argumento `ano` já extraído da própria
    pergunta pelo modelo (não por regex nosso). Retorna o texto combinado
    dos resultados, ou string vazia se o modelo decidiu que não precisa de
    dado nenhum, ou se a chamada falhar por qualquer motivo — nunca lança
    exceção (mesma filosofia de fallback silencioso de decompoe_pergunta:
    esta etapa nunca pode travar o chat)."""
    try:
        modelo = GenerativeModel(
            model_name=MODELO_LLM,
            system_instruction=_SISTEMA_ROTEADOR_DADOS,
            tools=_TOOLS_DADOS,
        )
        resposta = _chama_com_retry(
            lambda: modelo.generate_content(
                pergunta,
                request_options={"timeout": TIMEOUT_REQUEST_S},
            )
        )

        partes_resultado = []
        candidato = resposta.candidates[0]
        for part in candidato.content.parts:
            fc = getattr(part, "function_call", None)
            if not fc or not getattr(fc, "name", None):
                continue
            func = _FERRAMENTAS_DADOS.get(fc.name)
            if not func:
                continue
            args = dict(fc.args) if fc.args else {}
            if "ano" in args and args["ano"] is not None:
                args["ano"] = int(args["ano"])
            if fc.name == "consultar_dados_individuais" and (
                not isinstance(args.get("dataset"), str)
                or args["dataset"] not in _csvs_sob_demanda
                or not isinstance(args.get("categoria"), str)
                or args["categoria"] not in _CAMPOS_INDIVIDUAIS
            ):
                logger.warning(
                    "Function calling retornou argumentos inválidos para %s.",
                    fc.name,
                )
                continue
            if debug:
                logger.debug("[function_call] %s(%s)", fc.name, args)
            try:
                linhas = func(**args)
            except (TypeError, ValueError):
                logger.exception(
                    "Não foi possível executar a ferramenta de dados %s.",
                    fc.name,
                )
                continue
            if linhas:
                partes_resultado.extend(linhas)

        return "\n".join(partes_resultado)

    except Exception:
        logger.exception(
            "Function calling de dados falhou; seguindo sem resultado do roteador."
        )
        return ""
