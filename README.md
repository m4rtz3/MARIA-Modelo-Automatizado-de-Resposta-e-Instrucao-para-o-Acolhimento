# MARIA — Chat e dashboard

Aplicação web para conversar com a MARIA, um assistente sobre violência
doméstica e os dados do projeto, e consultar um dashboard Tableau.

## Componentes

- **`frontend/`**: interface React + Vite + Tailwind. Apresenta o chat e o
  dashboard Tableau; conversa com a API do backend. Não acessa o banco
  Supabase diretamente.
- **`backend/`**: API FastAPI. Usa o Gemini para responder, recupera trechos
  relevantes da base de conhecimento (RAG) e consulta os CSVs do pipeline
  quando necessário.
- **Supabase/Postgres + pgvector (opcional)**: guarda os trechos vetorizados
  da base para a busca do RAG. Sem `DATABASE_URL`, o backend usa um índice
  local em arquivos.
- **Tableau (opcional)**: fornece o dashboard incorporado na aba de dados.

O fluxo do chat é: navegador → API FastAPI → busca na base de conhecimento e,
quando pertinente, análise de dados → Gemini → resposta ao navegador. O
endpoint de estatísticas consulta os CSVs diretamente, sem passar pelo Gemini.

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
