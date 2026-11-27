# Diagnostico tecnico da qualidade das respostas da MARIA

## Metodo e alcance

Esta analise examinou o fluxo real implementado em `backend/app/maria.py`,
`backend/app/retrieval.py`, `backend/app/kb.py`, `backend/app/data_analysis.py`
e `backend/app/llm.py`, alem do corpus e das respostas geradas anteriormente.
Os valores observados foram comparados com `backend/data/knowledge_base.md`
e com os CSVs disponiveis em `backend/data/dados_bi`.

A avaliacao preliminar nao foi tratada como prova factual. Os arquivos JSON/CSV
registram 12 respostas geradas sem erros de execucao.

## A02 - Tipos de violencia

**Comportamento observado:** a resposta anunciou cinco formas e enumerou
fisica, psicologica, sexual, patrimonial, moral e vicaria.

**Evidencia:** a base de conhecimento registra seis formas, incluindo violencia
vicaria desde a Lei 15.384/2026. Porem, em `SYSTEM_PROMPT` havia a instrucao
"Explique qual dos 5 tipos..." e em `retrieval.py` a categoria legislativa era
descrita como "os 5 tipos de violencia".

**Causa confirmada:** conflito do prompt com a base atual. A resposta menciona
a sexta categoria, mas o texto introdutorio preserva uma contagem obsoleta.

**Correcao proposta:** remover todas as referencias antigas a cinco tipos;
ordenar o modelo a apresentar somente a quantidade efetivamente presente na
lista e a nao misturar quantidade com formas adicionais.

## A06 - Volume do pipeline

**Comportamento observado:** a resposta trouxe 3.878.962 notificacoes,
82.742 registros do SIM e 237.823 chaves reincidentes, mas nao iniciou pela
363.522 chaves compostas solicitadas.

**Evidencia:** `knowledge_base.md` define 363.522 chaves como unidade
consolidada. Os quatro arquivos `features_*.csv` tambem possuem 363.522 linhas.
A funcao `features_vitima.csv` calcula reincidencia em 237.823 chaves.
Nao existe `MARIA_chaves.csv` entre os CSVs atuais, apesar de o enriquecimento
do indice esperar esse nome opcionalmente.

**Causa confirmada ou muito bem sustentada:** o contexto misturou unidades
de analise diferentes (notificacoes, registros do SIM e chaves) e o roteador
estruturado nao disponha de uma consulta robusta para a unidade consolidada
quando o arquivo de chaves nao estava presente.

**Correcao proposta:** tornar `consultar_dataset_geral` dependente de uma
definicao computada a partir dos feature CSVs disponiveis, retornar explicitamente
363.522 como chaves compostas e distinguir notificacoes, registros do SIM e
chaves. Nao inserir o numero como constante no codigo.

## A07 - Distribucao dos niveis de risco

**Comportamento observado:** o sistema se absteve apesar de a distribuicao
estar em `knowledge_base.md`.

**Evidencia:** o score maximo preliminar foi 0.6160, portanto a abstencao nao
foi acionada pelo limiar 0.30. O contexto de texto limitava chunks nao
consultados a 300 caracteres. O trecho da distribucao pertence a uma secao
de tabela que pode ser cortada nessa montagem.

**Causa mais sustentada:** falha de completude da montagem do contexto
aplicada a trechos da categoria `pipeline_dados`, nao falha do threshold.
Sem a tabela completa no prompt, o gerador nao encontrou os valores e respondeu
com abstenção correta apenas em relação ao contexto entregue.

**Correcao proposta:** preservar chunks completos para `pipeline_dados`,
`datasenado` e `orientacao_pratica`, dentro do limite por quantidade de
resultados, e manter o limiar atual. A resposta nao deve misturar categorias
com o resultado de consulta.

## A08 - Indicadores relacionados a gestacao

**Comportamento observado:** a resposta usou 117.998 gestantes, 9,2% das
gestantes que informaram o campo, vindo do dashboard/SINAN. A referencia
esperada usa 46.909 chaves, 12,90%, indicador agregado por chave.

**Evidencia:** `features_vitima.csv` realmente soma 46.909 no campo
`vitima_gestante_em_algum_episodio` sobre 363.522 linhas (12,904%). O painel
6 da base registra 117.998 notificacoes do SINAN com gestante informada.
Essas duas respostas correspondem a denominadores e unidades diferentes.

**Causa confirmada:** mistura de uma consulta por notificacoes com a unidade
agregada por chave usada na referencia do pipeline.

**Correcao proposta:** classificar gestacao semecularmente para
`consultar_perfil_vitima`; esta consulta deve retornar o indicador agregado por
chave antes de qualquer texto do painel. O prompt deve explicitar que o valor
calculado por chave nao deve ser convertido em mulheres individuais.

## A13 - Prevalencia da violencia

**Comportamento observado:** a resposta informou 27% ao longo da vida e 33%
para situacoes concretas nos 12 meses, mas omitiu os 4% declarados nos 12
meses pedidos pela referencia.

**Evidencia:** `knowledge_base.md` distingue explicitamente 27% ao longo da
vida, 4% declarados nos ultimos 12 meses e 33% relatados em situacoes
concretas. O CSV `features_datasenado.csv` traz os valores 27 e 4.

**Causa confirmada:** incompletude de contexto ou de resposta e risco de
confundir medidas sem reconhecimento espontaneo (33%) com declaracao direta
(4%). O modelo respondeu a parte mais lexicamente proxima da pergunta sem
incluir todos os periodos.

**Correcao proposta:** preservar o bloco DataSenado completo e instruir
explicitamente que, quando a pergunta pede todos os periodos disponiveis,
todos sejam discriminados e medidas distintas nao sejam somadas.

## Separacao das causas

- **Recuperacao:** truncamento de 300 caracteres e conflito de categorizacao.
- **Consulta estruturada:** unidade consolidada/denominador nao suficientemente
  destacado; gestacao podia ser tomada de uma fonte ou painel diferente.
- **Montagem do contexto:** chunks numericos truncados e falta de instrucoes
  concretas de separacao de unidades.
- **Geracao:** duas frases com contagens conflitantes e omissao de indicador.
- **Avaliacao:** as metricas lexicais nao medem a acuracia dos valores, por isso
  serao mantidas separadas da cobertura factual por pontos verificaveis.
