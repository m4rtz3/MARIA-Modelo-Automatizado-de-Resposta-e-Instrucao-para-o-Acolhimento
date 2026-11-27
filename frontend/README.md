# MARIA — Frontend

Aplicação React com Vite e Tailwind CSS v4. A interface tem duas áreas:
**Conversar**, um chat com respostas transmitidas em tempo real pela API
FastAPI, e **Dashboards**, com dez painéis interativos do Tableau.

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local
# edite .env.local e configure VITE_API_URL
npm run dev
```

O Vite abre em http://localhost:5173. Mantenha o backend rodando em paralelo;
as instruções estão em [../backend/README.md](../backend/README.md). O valor
padrão de `VITE_API_URL` é `http://localhost:8000`.

As variáveis `VITE_*` são incorporadas ao frontend durante o build. Se alterar
`.env.local`, reinicie o servidor Vite; para produção, configure a URL antes
de executar o build.

## Estrutura

```
src/
  api/mariaClient.js       # chamadas à API (chat em streaming e configurações)
  components/
    layout/                # cabeçalho, telefones de emergência e configurações
    chat/                  # conversa, mensagens, entrada e exportação
    dashboard/             # painéis, recomendações, filtros e embed Tableau
  utils/conversationStorage.js # armazenamento e exportação de conversas
  App.jsx
  index.css                # tokens de design (Tailwind v4 @theme)
```

## Recursos e dados locais

- Crie, alterne, exclua e exporte conversas como arquivos `.txt`. As conversas
  e a temperatura ficam no `localStorage` deste navegador; não há sincronização
  entre navegadores ou dispositivos.
- O chat envia a mensagem e o histórico da conversa ativa à API e ao Gemini
  para gerar a resposta. O frontend usa `/api/chat/stream` para exibir a
  resposta enquanto ela é gerada.
- A recomendação de dashboards analisa localmente mensagens da pessoa usuária
  nas conversas salvas. Ela exige pelo menos três mensagens correspondentes em
  duas conversas diferentes, dá mais peso às conversas recentes e seleciona o
  Panorama quando não há evidência suficiente. O texto não é enviado ao
  backend nem ao Tableau para essa análise.
- Os filtros genéricos (`tema`, `perfil`, `regiao` e `periodo`) são inferidos
  localmente a partir das até 12 mensagens mais recentes da pessoa usuária na
  conversa ativa. A extração é uma heurística por termos explícitos, não uma
  classificação clínica nem uma interpretação do contexto. O mapeamento para
  filtros Tableau começa vazio; por padrão, nenhum filtro é enviado.
- A barra de emergência oferece ligações para 190 (Polícia) e 180 (Central de
  Atendimento à Mulher). O chat informa que o serviço é destinado a pessoas
  com 18 anos ou mais.

O MARIA ainda não possui autenticação ou contas: as conversas e recomendações
seguem o escopo atual do navegador/perfil local, e não podem ser isoladas por
conta em dispositivos compartilhados. Exclua as conversas ao terminar nesses
dispositivos. As mensagens enviadas ao backend não são armazenadas para uso
em dashboards; não há gravação de relatos para um dashboard de XAI.

O painel de configurações é protegido por `MARIA_SETTINGS_PASSWORD`, definido
no `.env` do backend. Nele, é possível atualizar a chave Gemini (salva somente
pelo backend) e a temperatura (salva neste navegador e enviada com cada
mensagem). Em produção, publique e acesse a API somente por HTTPS.

## Sobre o embed do Tableau

`TableauEmbed.jsx` usa o Web Component oficial (`<tableau-viz>`) carregado
via `tableau.embedding.3.latest.min.js` do Tableau Public. Os links do workbook
usam HTTPS padrão (porta 443). Se o dashboard for
publicado no Tableau Server/Cloud da própria instituição em vez do Tableau
Público, troque a constante `TABLEAU_JS_URL` no mesmo arquivo pelo script
do seu servidor (formato `https://SEU-SERVIDOR/javascripts/api/tableau.embed.3.min.js`)
— o resto do componente funciona igual, só muda a origem do script.

`src/components/dashboard/dashboards.js` registra os dez painéis disponíveis,
carregando somente o selecionado. Esse arquivo também contém as URLs do Tableau;
`VITE_TABLEAU_URL` presente no `.env.example` não é usado atualmente pelo
catálogo. `dashboardRecommendations.js`
usa frases temáticas explícitas das mensagens da pessoa usuária e considera
uma recomendação confiável apenas quando o tema aparece em pelo menos três
mensagens e em duas conversas diferentes. Respostas da MARIA não são usadas.
O cálculo é local.

`src/components/dashboard/dashboardFilters.js` extrai filtros genéricos
(`tema`, `perfil`, `regiao` e `periodo`) das 12 mensagens mais recentes da
pessoa usuária na conversa ativa, sem usar respostas da MARIA. A extração é
uma heurística por termos explícitos, não uma classificação clínica ou uma
leitura do contexto. Por padrão, `TABLEAU_FILTER_MAPPING` está vazio e nenhum
filtro é acrescentado à URL.

Quando os nomes dos campos do painel forem conhecidos, configure o mapeamento
com os nomes exatos dos filtros e os valores aceitos pelo Tableau:

```js
export const TABLEAU_FILTER_MAPPING = {
  tema: {
    field: 'Tipo de violência',
    values: { fisica: 'Física', psicologica: 'Psicológica' },
  },
}
```

O `DashboardView` transforma apenas chaves e valores mapeados em parâmetros
da URL do painel. O texto das mensagens nunca é incluído. Como os parâmetros
fazem parte da URL, use esse recurso apenas com filtros que possam ser
compartilhados com o Tableau e evite incluir dados pessoais ou identificáveis.

## Build de produção

```bash
npm test
npm run build
```

`npm test` executa os testes do frontend; `npm run build` gera `dist/`, que
pode ser publicado em um host de site estático (Vercel, Netlify, Cloudflare
Pages). Configure `VITE_API_URL` para apontar ao backend implantado, não ao
localhost.
