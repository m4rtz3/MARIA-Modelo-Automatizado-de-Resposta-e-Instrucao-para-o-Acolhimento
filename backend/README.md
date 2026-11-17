# MARIA — Backend

API REST em FastAPI para o chat e as consultas de dados do projeto. Este
backend transporta para um processo Python persistente o pipeline RAG do
notebook MARIA: busca na base de conhecimento, chamada ao Gemini e, quando
pertinente, consulta aos CSVs do projeto.

## Como funciona

1. No startup, o backend lê as configurações de `.env`, configura o Gemini
   quando `GOOGLE_API_KEY` já está definida, carrega os datasets usados em
   memória e carrega o encoder de embeddings.
2. Para uma mensagem, o pipeline prepara a pergunta, busca trechos relevantes
   da base e monta o contexto enviado ao Gemini.
3. A busca usa pgvector no Supabase/Postgres quando `DATABASE_URL` está
   configurada. Sem essa variável, usa o índice local em `data/indice/`.
4. As análises estatísticas de `/api/stats` e as consultas de dados usadas
   pelo chat leem os CSVs em `data/dados_bi/`; não são tabelas do Supabase.

O frontend não conecta diretamente ao banco: ele chama esta API. O Supabase
armazena o índice vetorial da base de conhecimento, não substitui os CSVs nem
o provedor Gemini.

## Requisitos e instalação

Recomenda-se Python 3.13 no Windows. Execute os comandos a partir da pasta
`backend`.

### Windows — CMD

```cmd
cd /d "C:\Users\Giovanna S Gomes\Downloads\maria-app\backend"
py -3.13 -m venv .venv-py313
.venv-py313\Scripts\python.exe -m pip install -r requirements.txt
if not exist .env copy .env.example .env
```

Edite `.env` e defina uma senha forte em `MARIA_SETTINGS_PASSWORD` (mínimo
12 caracteres) para habilitar o painel protegido. Você pode preencher
`GOOGLE_API_KEY` agora ou configurá-la no painel depois de iniciar o backend.
Configure também `DATABASE_URL` conforme a opção de índice abaixo. Se o
ambiente virtual já existe, não precisa recriá-lo; use diretamente
`.venv-py313\Scripts\python.exe`.

### Windows — PowerShell

```powershell
cd backend
py -3.13 -m venv .venv-py313
.\.venv-py313\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

### Linux / macOS

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
```

Edite `.env` para definir `MARIA_SETTINGS_PASSWORD` e as outras configurações
necessárias. `GOOGLE_API_KEY` pode ser informada pelo painel após iniciar a
API.

## Arquivos de dados

- `data/knowledge_base.md`: texto de referência usado pelo RAG. Substitua ou
  atualize com a base de conhecimento aprovada pelo projeto.
- `data/dados_bi/`: CSVs do pipeline consultados pelo endpoint de estatísticas
  e pelo function calling de dados. Os datasets maiores são lidos em blocos
  sob demanda; respostas de microdados são agregadas, não retornam linhas
  individuais.
- `data/indice/`: cache do índice vetorial local, usado somente quando
  `DATABASE_URL` está vazia.
- `data/chunks_meta_instrucao.json`: arquivo auxiliar de meta-instruções
  gerado pelo indexador.

Confira `KB_PATH` e `DADOS_BI_PATH` em `.env` se os dados não estiverem nos
caminhos padrão. Os caminhos padrão são relativos ao backend.

## Escolher onde fica o índice vetorial

O Supabase é um banco remoto. Quando o backend usa o Supabase, não é preciso
iniciar um container local de Postgres. O computador ou container onde roda
o backend precisa ter acesso à rede e receber a `DATABASE_URL`.

### Supabase com pgvector

1. No dashboard do projeto, abra **Connect** e obtenha a URI PostgreSQL.
   Use a opção **Session pooler** quando a rede for IPv4-only ou o host da
   conexão direta não resolver. Copie host, porta, usuário e URI exatamente
   como apresentados pelo painel; eles podem variar entre métodos de conexão.
2. No `.env` do backend, coloque a URI completa em `DATABASE_URL`, preenchendo
   a senha **Database Password** no lugar do marcador. Se a senha tiver
   caracteres reservados, codifique-os em URL (por exemplo, `@` como `%40`).
   Preserve os parâmetros de SSL indicados pelo Supabase.
3. No dashboard, abra **SQL Editor**, crie uma consulta, cole o conteúdo de
   `sql/schema_pgvector.sql` e execute. Isso cria a extensão `vector` e as
   tabelas do índice; é uma configuração por banco e o schema pode ser
   aplicado novamente com segurança.
4. Indexe a base de conhecimento uma vez pelo ambiente do backend, conforme
   os comandos abaixo. Rode novamente quando a base ou os dados usados no
   enriquecimento mudarem.

Não use uma chave publishable/anon como senha PostgreSQL. Não coloque a
senha no código, não a envie em mensagens e não versione `.env`; o `.gitignore`
do backend exclui esse arquivo. O `.env.example` serve apenas como modelo.

Para indexar a partir do **CMD no Windows local**, com o arquivo `.env` e o
ambiente Python configurados:

```cmd
cd /d "C:\Users\Giovanna S Gomes\Downloads\maria-app\backend"
.venv-py313\Scripts\python.exe scripts\indexador.py
```

No **PowerShell**, use os comandos próprios desse terminal:

```powershell
Set-Location "C:\Users\Giovanna S Gomes\Downloads\maria-app\backend"
.\.venv-py313\Scripts\python.exe scripts\indexador.py
```

Os comandos `cd /d` e `if not exist` são sintaxe do CMD, não do PowerShell.
Na primeira execução, aguarde o carregamento das dependências e do encoder;
interromper o processo com `Ctrl+C` encerra a indexação.

O script lê `DATABASE_URL` e os caminhos de dados do `.env`, cria embeddings
e grava os chunks em `maria_chunks` e o hash da base em `maria_kb_meta`.
Quando o hash não mudou, informa que a base já está indexada e não repete a
carga. A primeira execução pode baixar o modelo de embeddings.

Também é possível executar o script no container **do backend**, se ele tiver
o código, dependências, arquivos de dados e a mesma `DATABASE_URL`. Atualizar
o `.env` no host não altera automaticamente as variáveis de um container já
criado; passe a variável ao container e recrie/reinicie-o conforme a forma
como ele é iniciado. Não é necessário iniciar o container local do Postgres
quando a URL aponta para o Supabase.

Para confirmar a indexação no SQL Editor do Supabase:

```sql
SELECT
  current_database() AS banco,
  (SELECT COUNT(*) FROM public.maria_chunks) AS trechos_indexados,
  (SELECT kb_hash FROM public.maria_kb_meta WHERE id = 1) AS hash_da_base,
  (SELECT n_chunks FROM public.maria_kb_meta WHERE id = 1) AS trechos_no_indice;
```

Confirme que o painel está no projeto correto antes de executar a consulta.

### Índice local sem banco

Deixe `DATABASE_URL=` vazia no `.env`. Ao iniciar o backend, ele gera e
persiste o índice em `data/indice/`. A primeira inicialização pode demorar
enquanto o modelo é baixado e a base é vetorizada; as próximas reutilizam o
cache se a base não mudou. Não é necessário ter PostgreSQL ou Docker para
esse modo.

### Postgres local em Docker (alternativa)

Essa opção só é necessária se você quiser usar um Postgres local, em vez do
Supabase ou do índice em arquivo. É diferente do banco remoto. O projeto não
documenta um comando universal para iniciar o container: use a configuração
Docker que você já tiver e a URL local correspondente em `DATABASE_URL`.
Execute `sql/schema_pgvector.sql` nesse banco local com `psql` e então rode
`scripts/indexador.py` no ambiente do backend. Não execute `psql` dentro do
container local esperando aplicar o schema no Supabase.

## Iniciar a API

No Windows CMD, a partir de `backend`:

```cmd
.venv-py313\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

PowerShell:

```powershell
.\.venv-py313\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Linux / macOS:

```bash
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Com `DATABASE_URL` configurada, a API abre um pool de conexões ao Postgres e
usa o índice já preparado pelo indexador; ela **não** indexa a base
automaticamente no startup. Sem `DATABASE_URL`, inicializa o índice local.
Documentação interativa: http://localhost:8000/docs.

## API

- `GET /api/health`: verifica o serviço e informa o estado da base/datasets.
- `POST /api/chat`: recebe `mensagem` e histórico opcional e retorna a
  resposta completa.
- `POST /api/chat/stream`: mesmo pipeline do chat; transmite os fragmentos
  SSE da resposta final enquanto o Gemini a gera.
- `POST /api/settings/unlock` e `POST /api/settings`: validam a senha
  administrativa e atualizam a chave do Gemini; a chave nova é gravada no
  `.env` do backend e aplicada sem reiniciar o processo.
- `GET /api/stats?pergunta=...`: calcula estatísticas diretamente dos CSVs,
  sem chamar o Gemini.

Exemplo de consulta direta:

```text
GET http://localhost:8000/api/stats?pergunta=microdados%20por%20faixa%20etaria%20em%202020
```

No chat, perguntas numéricas acionam o function calling do Gemini para
selecionar a consulta adequada aos CSVs. O roteador encaminha os argumentos
da ferramenta (incluindo dataset, categoria e ano para microdados), e os
resultados são calculados durante a requisição; microdados são agregados e
categorias com menos de cinco registros são agrupadas. O endpoint `/api/stats`
oferece a mesma análise local para consultas diretas, sem chamada ao Gemini.

O modelo dos corpos de requisição e resposta está em `app/schemas.py`.

## Configuração (`.env`)

Principais variáveis:

| Variável | Uso |
| --- | --- |
| `GOOGLE_API_KEY` | Chave do Gemini usada pelo backend. |
| `MARIA_SETTINGS_PASSWORD` | Senha com pelo menos 12 caracteres para desbloquear e confirmar mudanças no painel de configurações. |
| `MODELO_LLM` | Modelo de linguagem; padrão definido em `app/config.py`. |
| `MODELO_EMB` | Modelo de embeddings, padrão multilingual MiniLM de 384 dimensões. |
| `MODELO_EMB_BACKEND` | Backend do Sentence Transformers (`torch`, `onnx` ou `openvino`); padrão `torch`. |
| `DATABASE_URL` | URI PostgreSQL; vazia seleciona o índice em arquivo. |
| `KB_PATH` | Arquivo da base de conhecimento. |
| `DADOS_BI_PATH` | Diretório dos CSVs do pipeline. |
| `INDEX_DIR` | Diretório do índice local. |
| `FRONTEND_ORIGINS` | Origens CORS separadas por vírgula. |
| `MAX_TURNOS_HISTORICO` | Limite de turnos de histórico usado pelo chat. |
| `TIMEOUT_REQUEST_S` | Timeout de requisição configurado pelo projeto. |
| `LIMIAR_SIMILARIDADE` | Score mínimo de recuperação da base textual para responder; abaixo dele, o chat se abstém. Padrão `0.30`; `0.0` desativa a abstenção. |

Veja `.env.example` para o modelo completo. As variáveis são lidas no startup;
reinicie o processo do backend após alterá-las. Defina `MARIA_SETTINGS_PASSWORD`
em `backend/.env` e reinicie a API para habilitar o painel. Se a senha não
estiver definida ou tiver menos de 12 caracteres, as rotas de configuração
permanecem desabilitadas.

O botão de configurações no frontend exige essa senha para abrir e novamente
para confirmar. A chave nova não é devolvida pela API nem salva no navegador;
ela é gravada em `backend/.env` e aplicada ao Gemini imediatamente. O processo
do backend precisa ter permissão de escrita nesse arquivo. A temperatura é
uma preferência por navegador, salva no `localStorage` e enviada em cada
mensagem; valores menores tendem a respostas mais previsíveis, enquanto
valores maiores permitem mais variação, sem aumentar a precisão factual.

Em produção, publique a API somente por HTTPS: tanto a senha quanto uma nova
chave de API são enviadas do navegador ao backend durante a configuração.
Use uma senha forte e exclusiva, não versione nem compartilhe o `.env`.

## Organização do código

```text
app/
  config.py          # variáveis de ambiente e caminhos
  main.py            # API FastAPI, CORS, startup e endpoints
  schemas.py         # modelos de entrada e saída da API
  maria.py           # orquestração do chat e prompt do sistema
  llm.py             # integração com Gemini e retries
  kb.py              # leitura/chunking/cache do índice local
  retrieval.py       # recuperação de contexto local ou pgvector
  db.py              # pool de conexões PostgreSQL
  data_analysis.py   # leitura dos CSVs, estatísticas e ferramentas de dados
scripts/
  indexador.py       # embeddings e carga do índice Postgres
sql/
  schema_pgvector.sql
```

## Comportamentos importantes

- O pipeline mantém hardening da pergunta, busca múltipla, retry em erros
  temporários do Gemini (até 3 tentativas, com espera curta) e function
  calling para consultar dados do projeto quando a pergunta pede estatísticas.
- O histórico de conversas fica no `localStorage` do navegador e é enviado
  ao backend e ao Gemini como contexto para gerar respostas. O backend não
  persiste relatos nem os envia ao dashboard; a API de estatísticas lê apenas
  CSVs do projeto.
  A implantação de um dashboard de XAI com relatos exige uma decisão separada
  de privacidade, incluindo consentimento explícito e anonimização antes de
  qualquer armazenamento.
- O modelo `google.generativeai` usado atualmente emite um aviso de
  descontinuação. A migração para `google.genai` deve ser feita separadamente
  e validada com testes de regressão.
- O encoder de embeddings consome memória e pode baixar seus pesos na primeira
  execução. Em produção, forneça recursos adequados e mantenha os dados
  necessários disponíveis ao backend.
- Configure `FRONTEND_ORIGINS` com o domínio real do frontend em produção.
  O backend precisa estar hospedado em um ambiente Python persistente e
  acessível ao navegador; configure nele as mesmas variáveis e arquivos de
  dados necessários.
