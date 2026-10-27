# App da Democracia

O "Sofascore da política": o cidadão segue deputados federais e senadores e recebe, num só lugar,
votações, presença, agenda e notícias de cada um, com link para a fonte oficial.

Apartidário por construção: o app mostra dados oficiais e métricas com metodologia pública
(página **Como calculamos**), sem nota, ranking ou selo de "bom político".

## Estrutura

```
backend/            FastAPI (só lê do banco) + worker de ingestão diária
  app/
    main.py         app, CORS, rate limit, rotas /api/v1
    core/           config, segurança (Argon2, JWT), logs JSON, rate limit
    db/             engine e sessão (SQLAlchemy 2 async)
    models/         usuários, dados políticos, notícias/feed/operação
    schemas/        Pydantic (OpenAPI em /docs)
    api/v1/         auth, me (conta/seguidos/feed), politicians, votes, news, compare, admin
    services/       stats (métricas), feed (cursor), news_matching (notícia → político)
  ingestion/
    run_daily.py    entrypoint do cron diário
    sources/        camara.py, senado.py, news_rss.py
    jobs/           sync_politicians, sync_votes, sync_agenda, sync_bills,
                    sync_expenses, sync_news, refresh_stats
  alembic/          migrações
  tests/            pytest
frontend/           React 18 + Vite + TypeScript + Tailwind v4 + TanStack Query + Recharts
  src/pages/        Feed, Buscar, Perfil, Votação, Notícias, Conta, Onboarding, Como calculamos
  src/components/   PoliticianCard, VoteBadge, StatTile, AgendaList, FeedItemCard…
  src/api/          cliente HTTP (refresh token automático) + hooks TanStack Query
docker-compose.yml  Postgres + API + frontend para dev
.github/workflows/  CI (ruff, pytest, migrações no Postgres, eslint, vitest, build)
```

## Rodando localmente

### Com Docker

```bash
docker compose up
docker compose run --rm sync
```

O segundo comando roda a sincronização uma vez para popular o banco. Depois abra
http://localhost:5173 (API em http://localhost:8000/docs).

### Sem Docker (SQLite)

Sem `DATABASE_URL`, o backend usa SQLite em `backend/dev.db`, prático para desenvolver.
Em produção use PostgreSQL 16 (as migrações criam `citext`, `pg_trgm` e o índice de busca por nome).

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"      # Linux/macOS: .venv/bin/pip
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m ingestion.run_daily
.venv/Scripts/uvicorn app.main:app --reload
```

Para uma carga inicial com mais histórico, use `SYNC_DAYS_BACK=30`. Para testar rápido,
`SYNC_LIMIT=10` limita os parlamentares por casa. Também dá para rodar só alguns jobs:
`python -m ingestion.run_daily votes stats`.

```bash
cd frontend
npm install
npm run dev
```

### Testes

```bash
cd backend && .venv/Scripts/pytest --cov
cd frontend && npm test
```

## Ingestão diária

Um único processo (`python -m ingestion.run_daily`) roda os jobs em sequência e encerra:

| Ordem | Job | Fonte |
|---|---|---|
| 1 | sync_politicians | Câmara `/deputados`, Senado `/senador/lista/atual` |
| 2 | sync_votes | Câmara `/votacoes` (só Plenário) + votos + orientações; Senado `/votacao` |
| 3 | sync_agenda | Câmara `/deputados/{id}/eventos` (próximos 14 dias) e presença em `/eventos/{id}/deputados` |
| 4 | sync_bills | Câmara `/proposicoes?idDeputadoAutor=` |
| 5 | sync_expenses | Câmara `Ano-{ano}.csv.zip`, Senado `despesa_ceaps_{ano}.csv` |
| 6 | sync_news | RSS da Agência Câmara/Senado + Google News (só para políticos com seguidores) |
| 7 | refresh_stats | recalcula `politician_stats` (legislatura atual e ano corrente) |

A sincronização é **incremental**: votações e presença continuam a partir do último item gravado
no banco (menos `SYNC_DAYS_BACK` dias de folga), então recessos longos ou dias sem rodar não
deixam buracos. Com o banco vazio, cada job carrega a legislatura inteira, em blocos de até 3 meses
(limite da API da Câmara). Para forçar uma recarga desde uma data, use `--since AAAA-MM-DD` ou a
variável `SYNC_SINCE`. A carga histórica não gera itens de feed (só eventos dos últimos
`FEED_MAX_AGE_DAYS` dias, padrão 30).

"Ausente" (em votações e sessões) só é contado para quem estava **em exercício** na data, segundo
o histórico oficial do deputado (`/deputados/{id}/historico`). Assim, suplências, licenças e
vacâncias não viram faltas.

Cada job é idempotente (upsert por `house + external_id`) e grava a execução em `ingestion_runs`.
Se uma fonte falhar, os demais jobs seguem, e o app continua mostrando o último dado salvo com
"atualizado em".

## Deploy no Railway

Projeto **App da Democracia** (ambiente `production`). Os serviços estão ligados ao repositório
GitHub e fazem deploy a cada push na `main`; cada um só reconstrói quando a própria pasta muda
(watch paths).

| Serviço | Root | Configuração |
|---|---|---|
| Postgres | template Railway | expõe `DATABASE_URL` |
| Backend | `/backend` | `Dockerfile`; pre-deploy `alembic upgrade head`; health check `/api/v1/health` |
| sync-diario | `/backend` | mesma imagem, start `python -m ingestion.run_daily`, Cron `0 6 * * *` (03h em Brasília), sem restart |
| Frontend | `/frontend` | `Dockerfile` (build do Vite + Caddy servindo `dist/` com fallback de SPA) |

Variáveis (referências do Railway entre `${{ }}`):

| Serviço | Variáveis |
|---|---|
| Backend | `DATABASE_URL=${{Postgres.DATABASE_URL}}`, `JWT_SECRET` (aleatório), `JWT_EXPIRES_MIN=15`, `CORS_ORIGINS=["https://${{Frontend.RAILWAY_PUBLIC_DOMAIN}}"]`, `PORT=8080` |
| sync-diario | `DATABASE_URL=${{Postgres.DATABASE_URL}}`, `SYNC_DAYS_BACK=3` |
| Frontend | `VITE_API_URL=https://${{Backend.RAILWAY_PUBLIC_DOMAIN}}` (usada no build), `PORT=8080` |

Opcionais: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `NEWS_API_KEY`, `LLM_API_KEY` (P1).

Recarga completa da legislatura: defina `SYNC_SINCE=2023-02-01` no serviço sync-diario, dispare
uma execução e depois remova a variável (sem ela, o cron volta ao modo incremental).

## Status do MVP

Pronto (P0): conta (e-mail/senha, refresh token com rotação, rota `/auth/google` para ID token do
Google), onboarding por UF, seguir/deixar de seguir, busca com filtros, feed por cursor, perfil com
desempenho e média da casa, agenda, votações com orientação do partido, notícias, página de votação,
exportação e exclusão de conta (LGPD), PWA instalável, rotas admin básicas e `/compare` (P1).

Pendências conhecidas:

- **Presença**: o formato do registro de presença e das ausências justificadas ainda precisa ser
  conferido na documentação oficial (questão em aberto do projeto). Hoje a presença da Câmara vem de
  `/eventos/{id}/deputados` nas sessões deliberativas do Plenário. Justificativas e a presença no
  Senado ainda não são importadas.
- **Senadores**: votos e cota já vêm do Senado, mas presença, proposições e agenda ainda não
  são importadas (no perfil, essas métricas aparecem vazias).
- **Relatoria**: os pareceres (PRL) da API da Câmara não são um sinal confiável de relatoria
  (um deputado tem ~10 mil), então "relatadas" ainda não é calculado.
- **Proposições apresentadas** contam só projetos (PL, PLP, PEC, PDL, PRC) em que o deputado é
  autor ou coautor; requerimentos e documentos de tramitação ficam de fora.
- **Login com Google no frontend**: falta o botão do Google Identity Services (o backend já aceita o ID token).
- **P1/P2**: notificações push/e-mail, resumos por IA, tela de comparação, temas, cards de compartilhamento e painel admin com interface.
- **Admin**: para promover um usuário, defina `role = 'admin'` direto no banco.
