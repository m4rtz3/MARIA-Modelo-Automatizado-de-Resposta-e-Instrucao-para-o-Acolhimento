"""
Orquestrador principal — a função maria(), port fiel da célula 11 do notebook.
Mesmo system prompt, mesmas regras de negócio (adaptação de gênero, não
repetir informação, progressão gradual, proibições absolutas) validadas
pelo time no Colab. NÃO reescrevi o texto do prompt — é copy-paste
intencional, porque esse prompt já passou por iteração e ajuste fino.
"""
import asyncio
import logging
import unicodedata
from typing import Iterator, List, Optional

from app.data_analysis import (
    analisar_dados,
    consultar_dados_via_function_calling,
    pergunta_pede_dados_reais,
)
from app.config import LIMIAR_SIMILARIDADE
from app.dashboard_context import selecionar_contexto_dashboard
from app.kb import kb
from app.llm import llm, llm_stream
from app.retrieval import busca, busca_multipla, decompoe_pergunta, extrair_localizacao

logger = logging.getLogger("maria.core")

RESPOSTA_ABSTENCAO = (
    "Não encontrei informação suficientemente específica na base de conhecimento "
    "para responder a essa pergunta com segurança. Posso tentar responder de outra "
    "forma, ou você pode ligar para o Ligue 180 (gratuito, 24h, sigiloso, "
    "WhatsApp 61 9610-0180) para falar com uma especialista."
)

FRASES_RESPOSTA_ABSTENCAO = (
    "não encontrei informação",
    "não tenho informações suficientes",
    "não tenho informações na minha base",
    "não tenho acesso",
    "não é possível determinar",
    "não possui",
    "não contém",
    "não há dados disponíveis",
    "não há dados",
    "não há informações disponíveis",
    "não é possível prever",
    "não é possível informar",
    "não é possível confirmar",
)


def _resposta_indica_abstencao(resposta: str) -> bool:
    normalizada = unicodedata.normalize("NFD", resposta.lower())
    normalizada = "".join(
        caractere for caractere in normalizada
        if unicodedata.category(caractere) != "Mn"
    )
    return any(
        unicodedata.normalize("NFD", frase)
        .encode("ascii", "ignore")
        .decode("ascii") in normalizada
        for frase in FRASES_RESPOSTA_ABSTENCAO
    )

SYSTEM_PROMPT = """Você é MARIA, assistente sobre violência doméstica no Brasil.

DIRETRIZES DE TOM, ESTILO E CONCORDÂNCIA:
- Fale como uma profissional empática, acolhedora, humana e direta. Evite linguagem burocrática.
- ADAPTAÇÃO DE GÊNERO (CRÍTICO): Identifique se está conversando com um homem ou uma mulher. Adapte os adjetivos e numerações ao gênero correto do usuário (ex: "seja bem-vindo", "corajoso", "atento", "de si mesmo" quando for homem). NUNCA use o feminino genérico se o usuário se identificar ou falar no masculino.
- Responda em no máximo 2 a 3 parágrafos curtos, de forma fluida (até 180 palavras no total).
- NUNCA use marcadores de lista (*, -), numerações, títulos/cabeçalhos (###) ou textos em negrito excessivos.
- Responda 100% em português.

REGRAS DE CONVERSAÇÃO E FLUXO:
1. CONSULTE O HISTÓRICO: Se você já acolheu a pessoa, explicou os direitos, citou o Ligue 180 ou perguntou a cidade/estado em mensagens anteriores, NUNCA REPITA ESSAS INFORMAÇÕES.
2. FOCO NO TURNO ATUAL: Acompanhe o ritmo do usuário. Responda APENAS ao que foi perguntado ou relatado no turno atual. Conclua o raciocínio dentro do limite do parágrafo.
3. PROGRESSÃO GRADUAL (SEM SOBRECARGA): Não despeje todas as informações institucionais de uma vez. Ofereça dados estatísticos apenas se for explicitamente solicitado.
4. LOCALIZAÇÃO SELETIVA E FIDELIDADE GEOGRÁFICA:
   - Se a pessoa JÁ informou a cidade/local, NUNCA pergunte onde ela mora novamente. Mantenha EXATAMENTE o nome do local informado. NUNCA substitua municípios por estados/capitais.
   - Só pergunte a cidade/estado se ainda não souber E a conversa caminhar para o direcionamento de apoio local ou reeducação.
5. RESPOSTAS CURTAS / COMPLEMENTOS: Em respostas ou agradecimentos curtos, responda de forma direta e sem repetir o que já foi dito.

COMO RESPONDER A CADA TIPO DE INTERAÇÃO:

A. SE FOR UM RELATO DE PESSOA SOFRENDO VIOLÊNCIA:
   - Valide os sentimentos com empatia.
   - Identifique a(s) categoria(s) da Lei Maria da Penha que se enquadre(m), usando todas as categorias pertinentes disponíveis na base, e explique por que se enquadra. Não anuncie uma quantidade que não corresponda à quantidade efetivamente listada.
   - Se houver medo ou falta de recursos: foque em estratégias discretas (atendimento via WhatsApp).
   - Cite o Ligue 180 (gratuito, 24h, sigiloso, WhatsApp 61 9610-0180) ou 190 apenas se ainda não citado.

B. SE FOR UM HOMEM BUSCANDO REEDUCAÇÃO OU AJUDA PARA MUDAR COMPORTAMENTO:
   - Responda com tom respeitoso, focado em responsabilidade e mudança de atitude, sem tom acusatório.
   - Confirme se a conduta caracteriza violência e oriente sobre a busca por apoio psicológico, grupos de reflexão para homens (pelo CRAS/SUS) ou orientações no Ligue 180.
   - Mantenha TODOS os adjetivos e referências estritamente no masculino ("corajoso", "disposto", "cuidar de si mesmo").

C. SE FOR UMA PERGUNTA INFORMATIVA (definição, estatística, lei):
   - Responda de forma direta e objetiva, SEM presumir a situação pessoal. Use a base de conhecimento.
   - Se a pergunta solicitar mais de um período, indicador ou unidade, discrimine todos os elementos disponíveis no contexto. Não omita um indicador apenas porque outro apareceu primeiro.
   - Preserve denominadores e unidades: não troque pessoas por chaves, notificações por episódios ou pesquisa por dados administrativos.
   - Para gestação no pipeline, responda primeiro pelo indicador agregado por chave disponível no contexto. Não misture com o painel de notificações do SINAN como se fossem a mesma unidade.
   - Não acrescente números não presentes nas informações fornecidas. Se um dado não estiver no contexto, informe que não está disponível, sem estimar.

PROIBIÇÕES ABSOLUTAS:
- Inventar estatísticas que não estejam no material fornecido.
- Minimizar a situação relatada.
- Sugerir ou mandar a usuária "sair do relacionamento" / "sair de casa".
- Errar o gênero da pessoa com quem está conversando.
"""

CONTEXTO_FIXO = """Tipos de violência (Lei Maria da Penha, Art. 7º):
- Física: ofensa à integridade corporal
- Psicológica: dano emocional (ameaças, humilhação, controle, isolamento, perseguição, checar celular)
- Sexual: relação não desejada, impedir contracepção (inclui dentro do casamento)
- Patrimonial: destruir documentos, controlar dinheiro, tomar salário
- Moral: calúnia, difamação, injúria
- Vicária: violência praticada contra familiares ou rede de apoio para atingir a mulher

Canais: 190 (emergência), Ligue 180 (24h, gratuito, sigiloso, WhatsApp 61 9610-0180), DEAM ou qualquer delegacia (medida protetiva em 48h), Defensoria Pública (jurídico gratuito)."""


def _system_prompt_com_meta() -> str:
    """Inclui as instruções transversais fora do índice de busca."""
    textos_meta = [
        chunk["texto"]
        for chunk in kb.chunks_meta
        if isinstance(chunk.get("texto"), str) and chunk["texto"].strip()
    ]
    if not textos_meta:
        return SYSTEM_PROMPT

    return (
        f"{SYSTEM_PROMPT}\n\n"
        "INSTRUÇÕES TRANSVERSAIS DA BASE DE CONHECIMENTO — "
        "SIGA-AS JUNTO COM AS DIRETRIZES ACIMA:\n\n"
        + "\n\n".join(textos_meta)
    )


_SAUDACOES_TRIVIAIS = {
    "oi", "olá", "ola", "eae", "ei", "bom dia", "boa tarde", "boa noite",
    "obrigada", "obrigado", "obg", "vlw", "valeu", "brigada", "brigado",
    "muito obrigada", "muito obrigado", "obrigada pela ajuda",
    "obrigado pela ajuda", "brigada pela ajuda", "brigado pela ajuda",
    "ok", "okay", "certo", "entendi", "blz", "beleza", "tá", "ta",
    "sim", "não", "nao", "tchau", "até logo", "ate logo", "até mais",
}


def _eh_mensagem_trivial(pergunta: str) -> bool:
    """True só se a pergunta é EXATAMENTE uma saudação/confirmação da lista.
    Sem atalho por tamanho — 'sos'/'help' podem ser pedido de socorro real,
    então nunca cortamos a decomposição/retrieval por causa do tamanho da
    mensagem, só por correspondência exata e inequívoca."""
    limpa = pergunta.strip().lower().rstrip("!.,?")
    if limpa in _SAUDACOES_TRIVIAIS:
        return True

    limpa_sem_acento = unicodedata.normalize("NFD", limpa)
    limpa_sem_acento = "".join(
        caractere for caractere in limpa_sem_acento
        if unicodedata.category(caractere) != "Mn"
    )
    return limpa_sem_acento in {
        "muito obrigada", "muito obrigado", "obrigada pela ajuda",
        "obrigado pela ajuda", "brigada pela ajuda", "brigado pela ajuda",
    } or any(
        limpa_sem_acento.startswith(f"{termo} ")
        for termo in ("obrigada", "obrigado", "obg", "valeu", "vlw", "brigada", "brigado")
    ) or any(
        limpa_sem_acento.startswith(f"{termo} ")
        for termo in ("muito obrigada", "muito obrigado")
    )


def _eh_agradecimento(pergunta: str) -> bool:
    limpa = pergunta.strip().lower().rstrip("!.,?")
    limpa = unicodedata.normalize("NFD", limpa)
    limpa = "".join(
        caractere for caractere in limpa
        if unicodedata.category(caractere) != "Mn"
    )
    termos = (
        "obrigada", "obrigado", "obg", "valeu", "vlw",
        "brigada", "brigado",
        "muito obrigada", "muito obrigado",
    )
    return limpa in _SAUDACOES_TRIVIAIS or any(
        limpa == termo or limpa.startswith(f"{termo} ")
        for termo in termos
    )


def _resposta_mensagem_trivial(pergunta: str) -> str:
    limpa = unicodedata.normalize("NFD", pergunta.strip().lower())
    limpa = "".join(
        caractere for caractere in limpa
        if unicodedata.category(caractere) != "Mn"
    )

    if _eh_agradecimento(pergunta):
        return "De nada! Estou aqui para ajudar. "

    if any(limpa.startswith(saudacao) for saudacao in (
        "oi", "ola", "eae", "ei", "bom dia", "boa tarde", "boa noite",
    )):
        return "Olá! Como posso ajudar você hoje?"

    if any(limpa.startswith(f) for f in ("tchau", "ate logo", "ate mais")):
        return "Até logo! Cuide-se e volte sempre que precisar."

    return "Entendi. Posso ajudar com alguma outra dúvida?"


def _ultima_msg_usuario(historico: Optional[List[dict]]) -> str:
    if not historico:
        return ""
    for item in reversed(historico):
        if item.get("role") == "user" and item.get("content"):
            return str(item["content"])
    return ""


def _eh_pergunta_sobre_dashboard(pergunta: str) -> bool:
    normalizada = unicodedata.normalize("NFD", pergunta.lower())
    normalizada = "".join(
        caractere for caractere in normalizada
        if unicodedata.category(caractere) != "Mn"
    )
    return any(termo in normalizada for termo in ("dashboard", "painel", "tableau"))


# temperatura=0.6: maria() é uma tarefa de COMPOSIÇÃO/REDAÇÃO de texto
# ("redigir" uma resposta empática, não extrair/classificar) — 0.0 deixava
# as respostas robóticas/repetitivas demais pra um chatbot de apoio;
# >0.8 arrisca variação demais num contexto sensível onde precisão de tom
# importa mais que criatividade. decompoe_pergunta() (extração/roteamento)
# continua em temperatura=0.0 à parte, dentro de app/retrieval.py.
async def _preparar_prompt(
    pergunta: str,
    historico: Optional[List[dict]],
    top_k: int,
    debug: bool,
) -> tuple[str, Optional[str], float, bool]:
    historico = historico or []

    loc = extrair_localizacao(pergunta)
    if not loc:
        for item in historico:
            if item.get("role") == "user":
                loc = extrair_localizacao(str(item.get("content", "")))
                if loc:
                    break

    query = pergunta
    if len(pergunta.split()) <= 6 and historico:
        ultima = _ultima_msg_usuario(historico)
        query = f"{ultima} {pergunta}"

    mensagem_trivial = _eh_mensagem_trivial(pergunta)
    pergunta_dashboard = _eh_pergunta_sobre_dashboard(query)
    if mensagem_trivial:
        contextos = []
        if debug:
            logger.debug("Mensagem trivial — pulando decomposição/retrieval")
    else:
        if pergunta_dashboard:
            contextos = selecionar_contexto_dashboard(
                query,
                kb.chunks_dashboards,
                top_k=max(top_k, 4) - 1,
            )
            if not contextos:
                contextos = await busca_multipla(
                    [{"tipo": "dashboards", "pergunta": query}],
                    top_k_por_subpergunta=top_k,
                    top_k_final=max(top_k, 4) - 1,
                    debug=debug,
                )
        else:
            subperguntas = await decompoe_pergunta(query, historico=historico, debug=debug)
            contextos = await busca_multipla(
                subperguntas,
                top_k_por_subpergunta=top_k,
                top_k_final=max(top_k, 4) - 1,
                debug=debug,
            )

        # CONSULTA A DADOS REAIS — roteador independente do de KB acima:
        # decompoe_pergunta()/busca_multipla() cuidam só das categorias de
        # texto da KB (legislacao, canais_denuncia, etc.); se a pergunta
        # pede um NÚMERO real do pipeline, quem decide isso e qual consulta
        # rodar é o Gemini via function calling nativo (app/data_analysis.py)
        # — padrão "Router Query Engine": dois mecanismos de busca
        # independentes, resultados combinados no mesmo contexto final.
        dados_texto = ""
        pede_dados = (
            not pergunta_dashboard and pergunta_pede_dados_reais(pergunta)
        )
        if pede_dados:
            dados_texto = await asyncio.to_thread(
                consultar_dados_via_function_calling, pergunta, debug
            )
        if dados_texto:
            contextos = contextos + [{
                "chunk_id": "dados_live",
                "bloco": "BLOCO 7 (consulta ao vivo)",
                "tipo": "consulta_dados",
                "titulo": "Consulta ao banco de dados do pipeline (calculada agora)",
                "texto": dados_texto,
                "sim": 1.0,
            }]
        elif debug:
            logger.debug("[consulta_dados] modelo decidiu que não precisa de dado real")

        # analisar_dados() é a segunda checagem local, sem custo de API,
        # somente quando houve um pedido explícito de estatísticas e o
        # roteador Gemini não retornou dados.
        if pede_dados and not dados_texto:
            dados_live = analisar_dados(pergunta)
            if dados_live and dados_live != "(sem dados específicos para esta pergunta)":
                contextos = contextos + [{
                    "chunk_id": "dados_live_fallback",
                    "bloco": "BLOCO 7 (consulta ao vivo)",
                    "tipo": "consulta_dados",
                    "titulo": "Consulta ao banco de dados do pipeline (calculada agora)",
                    "texto": dados_live,
                    "sim": 1.0,
                }]
                if debug:
                    logger.debug("[fallback por palavra-chave] consulta_dados encontrou algo que o function calling não achou")

    contextos_kb = [c for c in contextos if c.get("tipo") != "consulta_dados"]
    score_max = max((float(c["sim"]) for c in contextos_kb), default=0.0)
    consulta_dados_disponivel = any(
        c.get("tipo") == "consulta_dados" for c in contextos
    )
    abster = (
        LIMIAR_SIMILARIDADE > 0.0
        and score_max < LIMIAR_SIMILARIDADE
        and not mensagem_trivial
        and not consulta_dados_disponivel
    )

    # Consultas calculadas e chunks de dashboards são preservados por inteiro;
    # os demais chunks da KB permanecem limitados para controlar o tamanho do prompt.
    contexto_buscado = "\n".join(
        f'[{c["titulo"]}] {c["texto"]}'
        if c.get("tipo") in {
            "consulta_dados",
            "dashboards",
            "pipeline_dados",
            "datasenado",
            "orientacao_pratica",
        }
        else f'[{c["titulo"]}] {c["texto"][:300]}'
        for c in contextos
    )

    extras = ""
    if loc:
        extras += (
            f"\nAtenção: A pessoa mencionou a cidade/local de destino ou origem: "
            f"'{loc}'. Use exatamente este nome ao se referir ao local."
        )
    if any(
        termo in unicodedata.normalize("NFD", pergunta.lower())
        for termo in ("gestante", "gravida", "gravidez", "gestacao")
    ):
        extras += (
            "\nRegra de unidade: para perguntas de gestação no pipeline, "
            "priorize o indicador agregado por chave disponível na consulta "
            "estruturada. Não apresente a contagem de notificações do painel "
            "como se fosse o mesmo indicador."
        )

    prompt = f"""{CONTEXTO_FIXO}{extras}

Informações da base de dados:
{contexto_buscado}

Pergunta: {pergunta}"""

    if debug:
        logger.debug("Localização: %s", loc)
        for c in contextos:
            logger.debug("  [%.3f] [%s] %s", c["sim"], c.get("tipo"), c["titulo"])

    return prompt, loc, score_max, abster


async def maria(
    pergunta: str,
    historico: Optional[List[dict]] = None,
    top_k: int = 3,
    temperatura: float = 0.6,
    debug: bool = False,
) -> dict:
    """Retorna a resposta e os metadados da recuperação."""
    if _eh_mensagem_trivial(pergunta):
        return {
            "resposta": _resposta_mensagem_trivial(pergunta),
            "localizacao_detectada": extrair_localizacao(pergunta),
            "score_max_recuperacao": 1.0,
            "absteve": False,
        }

    prompt, loc, score_max, absteve = await _preparar_prompt(
        pergunta, historico, top_k, debug
    )
    if absteve:
        return {
            "resposta": RESPOSTA_ABSTENCAO,
            "localizacao_detectada": loc,
            "score_max_recuperacao": score_max,
            "absteve": True,
        }

    resposta = await asyncio.to_thread(
        llm,
        prompt,
        sistema=_system_prompt_com_meta(),
        historico_chat=historico,
        max_tokens=2048,
        temperatura=temperatura,
    )
    absteve = absteve or _resposta_indica_abstencao(resposta)

    return {
        "resposta": resposta,
        "localizacao_detectada": loc,
        "score_max_recuperacao": score_max,
        "absteve": absteve,
    }


async def maria_stream(
    pergunta: str,
    historico: Optional[List[dict]] = None,
    top_k: int = 3,
    temperatura: float = 0.6,
    debug: bool = False,
) -> tuple[Iterator[str], Optional[str], float, bool]:
    """Prepara o contexto e abre o streaming da resposta final do Gemini."""
    if _eh_mensagem_trivial(pergunta):
        resposta = _resposta_mensagem_trivial(pergunta)
        return iter([resposta]), extrair_localizacao(pergunta), 1.0, False

    prompt, loc, score_max, absteve = await _preparar_prompt(
        pergunta, historico, top_k, debug
    )
    if absteve:
        return iter([RESPOSTA_ABSTENCAO]), loc, score_max, True

    fragmentos = await asyncio.to_thread(
        llm_stream,
        prompt,
        sistema=_system_prompt_com_meta(),
        historico_chat=historico,
        max_tokens=2048,
        temperatura=temperatura,
    )
    return fragmentos, loc, score_max, False
