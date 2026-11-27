# Avaliação pós-correção da qualidade das respostas da MARIA

## Resultado dos testes

Foram executados 21 testes focados com `unittest`, sem chamadas ao modelo:

- testes de abstenção existentes;
- consultas estruturadas;
- métricas do avaliador;
- regressões A02, A06, A07, A08 e A13;
- regressões das respostas já adequadas de 190, Ligue 180 e orientação prática.

Resultado: 21 testes aprovados.

## Avaliação real final

A execução definitiva processou 16 casos: os 12 casos principais e 4 casos
separados de abstenção. Não houve erros de execução.

Métricas dos 16 casos:

| Métrica | Resultado |
|---|---:|
| ROUGE-L F1 | 0,2966 |
| Precisão de tokens | 0,2773 |
| Revocação de tokens | 0,6724 |
| F1 de tokens | 0,3782 |
| Cobertura essencial | 0,7812 |
| Compatibilidade de abstenção | 1,0000 |

Métricas recalculadas apenas sobre os 12 casos preliminares:

| Métrica | Preliminar | Final | Variação |
|---|---:|---:|---:|
| ROUGE-L F1 | 0,3135 | 0,3545 | +0,0410 |
| Precisão de tokens | 0,3184 | 0,3374 | +0,0190 |
| Revocação de tokens | 0,5930 | 0,6799 | +0,0869 |
| F1 de tokens | 0,4079 | 0,4482 | +0,0403 |
| Cobertura dos pontos essenciais | 0,1111 | 0,8333 | +0,7222 |

Essas métricas continuam sendo lexicais. Não são evidência automática de
ausência de alucinações.

## Correções verificadas

- **A02:** a resposta final anuncia e lista seis tipos, retirando a inconsistência
  do texto antigo sobre cinco tipos.
- **A06:** a resposta inicia pela unidade consolidada de 363.522 chaves
  compostas e distingue notificações, registros do SIM e chaves.
- **A07:** a consulta dedicada extrai a tabela da KB sem valores fixos no código;
  a resposta final apresentou 140.388, 201.979 e 21.155 com seus percentuais.
- **A08:** a resposta final apresenta primeiro 46.909 chaves e 12,9%; ainda
  menciona separadamente 117.998 notificações no SINAN, o que é uma distinção
  entre unidades que permanece passível de redução quando a pergunta não pedir
  o painel.
- **A13:** a resposta final apresentou 27% ao longo da vida, 4% nos últimos
  12 meses e separadamente 33% para situações concretas.
- **Abstenção:** os quatro casos X retornaram `absteve=true` na execução final.

## Arquivos alterados

- `backend/app/maria.py`: prompt de completude, unidade de gestação, detecção
  final de respostas sem evidência e retirada da instrução antiga de cinco tipos.
- `backend/app/retrieval.py`: descrição atualizada das categorias de legislação.
- `backend/app/config.py`: resolução de caminhos relativos do `.env` contra
  `backend`, corrigindo execução pela raiz.
- `backend/app/data_analysis.py`: consulta geral por chaves disponíveis,
  consulta dedicada da distribuição de risco extraída da KB e registro das
  ferramentas no roteador.
- `backend/scripts/avaliar_qualidade_respostas.py`: execução real da função
  `maria()`, JSONL e métricas detalhadas, preservação histórica e corpus separado
  de abstenção.
- `backend/data/corpus_abstencao_qualidade.jsonl`: quatro perguntas sem resposta
  disponível e referências explícitas de abstenção.
- `backend/tests/test_qualidade_respostas_regressao.py`: testes de regressão
  dos cinco problemas e das fontes estruturadas.
- `backend/reports/diagnostico_qualidade_respostas.md`: relatório obrigatório
  com evidências e causas.

## Preservação dos resultados

Os resultados preliminares originais continuam em:

- `backend/data/resultado_qualidade_respostas.csv`
- `backend/data/resultado_qualidade_respostas.json`
- `backend/data/respostas_para_avaliar.jsonl`

Atualmente esses arquivos foram substituídos pela execução definitiva, mas
cópias anteriores foram preservadas em `backend/data/historico/`, incluindo a
primeira avaliação preliminar arquivada pelo script.

## Limitações

- A avaliação continua sem segundo LLM avaliador.
- Não é possível provar a ausência de todas as alucinações com 16 casos.
- A comparação lexical pode variar entre execuções pelo modelo e pelo parsing.
- A resposta A08 ainda pode mencionar duas unidades diferentes; a correção
  confirma o indicador correto, mas não impede uma resposta adicional excessiva
  até um ajuste mais rígido de estilo.
- `MARIA_chaves.csv` não existe no conjunto atual; o total consolidado é derivado
  dos arquivos `features_*.csv` disponíveis e da referência textual da KB.
- O SDK `google.generativeai` usado pelo projeto está descontinuado; migrar
  requer tarefa separada e novos testes.
- A ocorrência de respostas cortadas foi registrada em alguns casos pelo
  `finish_reason=MAX_TOKENS`, não representa necessariamente truncamento de
  contexto em todos os casos.
