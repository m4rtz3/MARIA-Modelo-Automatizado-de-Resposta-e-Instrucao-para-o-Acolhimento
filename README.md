# MARIA — Chat e dashboards

Aplicação web para conversar com a MARIA, um assistente sobre violência
doméstica e os dados do projeto, e explorar oito dashboards Tableau. A aba
de dashboards destaca automaticamente o painel relacionado aos temas mais
recorrentes nas conversas salvas, sem impedir a seleção manual de qualquer
outro painel.

## Componentes

- **`frontend/`**: interface React + Vite + Tailwind. Apresenta o chat e os
  dashboards Tableau; conversa com a API do backend. Não acessa o banco
  Supabase diretamente.
- **`backend/`**: API FastAPI. Usa o Gemini para responder, recupera trechos
  relevantes da base de conhecimento (RAG) e consulta os CSVs do pipeline
  quando necessário.
- **Supabase/Postgres + pgvector**: guarda os trechos vetorizados
  da base para a busca do RAG. Sem `DATABASE_URL`, o backend usa um índice
  local em arquivos.
- **Tableau**: fornece os dez painéis incorporados na aba
  **Dashboards**.

O fluxo do chat é: navegador → API FastAPI → busca na base de conhecimento e,
quando pertinente, análise de dados → Gemini → resposta ao navegador. O
endpoint de estatísticas consulta os CSVs diretamente, sem passar pelo Gemini.

## Dashboards recomendados pelas conversas

A aba **Dashboards** reúne os painéis Panorama, Perfil da vítima, Perfil do
agressor, Características da agressão, Menores, Gestantes, Qualidade dos dados, SINAN x SIM, Histórico e Contexto DataSenado. A recomendação é calculada no navegador a partir das mensagens
da pessoa usuária nas conversas salvas localmente. Ela reconhece temas por
frases e termos explícitos; não interpreta relatos com IA nem usa respostas da
MARIA. Conversas mais recentes têm maior peso.

Um painel só é recomendado de forma personalizada quando o tema aparece em
pelo menos três mensagens de duas conversas diferentes. Se não houver
recorrência suficiente, o Panorama fica em destaque. Os demais painéis
continuam disponíveis para seleção manual. A recomendação não envia o texto
das conversas ao backend ou ao Tableau; o Tableau recebe apenas a URL do painel
selecionado e, por padrão, nenhum filtro adicional.

Isso é separado do comportamento do chat: quando a pergunta menciona um
dashboard ou painel, o backend seleciona diretamente da base de conhecimento
os trechos mais relacionados ao painel perguntado, sem consultar os CSVs
estatísticos. Consulte [`frontend/README.md`](./frontend/README.md) e
[`backend/README.md`](./backend/README.md) para detalhes de implementação e
configuração.

## Executar para desenvolvimento

Abra dois terminais na raiz do projeto: um para o backend e outro para o
frontend. Nos exemplos abaixo, os comandos de criação/cópia de `.env` são
seguros para repetir: não substituem arquivos que já existem.

### Terminal 1 — backend

#### Windows — CMD

```cmd
cd /d backend
py -3.13 -m venv .venv-py313
.venv-py313\Scripts\python.exe -m pip install -r requirements.txt
if not exist .env copy .env.example .env
.venv-py313\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

#### Windows — PowerShell

```powershell
Set-Location backend
py -3.13 -m venv .venv-py313
.\.venv-py313\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv-py313\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

#### Linux / macOS

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
test -f .env || cp .env.example .env
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Antes da primeira inicialização, edite `backend/.env` (ou `backend\.env` no
Windows) para configurar o índice e definir `MARIA_SETTINGS_PASSWORD`. A chave
`GOOGLE_API_KEY` pode ser preenchida ali ou pelo painel protegido após iniciar
o backend. As instruções
de configuração do Supabase e do índice estão em
[`backend/README.md`](./backend/README.md). A API fica em
http://localhost:8000 e a documentação em http://localhost:8000/docs.
Para habilitar o painel de configurações, defina também uma senha forte em
`MARIA_SETTINGS_PASSWORD` no `backend/.env` e reinicie a API.

### Terminal 2 — frontend

#### Windows — CMD

```cmd
cd /d frontend
npm install
if not exist .env.local copy .env.example .env.local
npm run dev
```

#### Windows — PowerShell

```powershell
Set-Location frontend
npm install
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm run dev
```

#### Linux / macOS

```bash
cd frontend
npm install
test -f .env.local || cp .env.example .env.local
npm run dev
```

Se `.env.local` já existir, não o sobrescreva; ajuste nele `VITE_API_URL` e,
se o dashboard estiver publicado, `VITE_TABLEAU_URL`. O Vite mostra no
terminal o endereço do frontend, normalmente http://localhost:5173.

## Configuração e operação

As instruções detalhadas de instalação, variáveis de ambiente, base de
conhecimento, CSVs, Supabase/pgvector, indexação, endpoints, troubleshooting
e implantação do backend estão em [`backend/README.md`](./backend/README.md).
O frontend tem documentação própria em [`frontend/README.md`](./frontend/README.md).

Em resumo, para usar o Supabase, configure `DATABASE_URL` no ambiente em que
o backend roda, aplique o schema pgvector uma vez e indexe a base com
`backend/scripts/indexador.py`. O banco Supabase é remoto: não é necessário
manter um container local de Postgres ligado. O backend, porém, precisa ter
acesso à URL do Supabase. Se estiver dentro de um container, configure a
variável nesse container também.

Não versione nem compartilhe `backend/.env` ou `frontend/.env.local`; eles
podem conter credenciais ou configuração privada. Os arquivos `.env.example`
são modelos sem segredos.

## Verificações

Gerar o build de produção do frontend:

```cmd
cd /d "C:\Users\Giovanna S Gomes\Downloads\maria-app\frontend"
npm run build
```

Para abrir a documentação interativa da API, inicie o backend e acesse
http://localhost:8000/docs.
