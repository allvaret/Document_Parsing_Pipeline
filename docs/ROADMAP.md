# Roadmap do MVP

Objetivo: site no ar até **24/11/2026** com relatórios de algumas empresas
processados. Escopo enxuto: o que não estiver aqui vai para o backlog v1.1.

Fluxo final:

```
PDFs (pasta local) ──► batch (local, 1x por relatório) ──► banco ──► API (só leitura) ──► site
                         heurística sempre + LLM opcional
```

Cada fase termina com: testes passando, critérios de pronto atendidos, commits
pequenos na branch da fase e PR para `develop`.

---

## Fase 0 — Consolidação ✅ (concluída)

Branch `chore/fase-0-consolidacao`: data_pipeline e database trazidos para o
projeto, falhas silenciosas corrigidas, modo explícito, `ReportResult`,
`database/schema.sql` v1, 27 testes.

---

## Fase 1 — Contrato e provedores de LLM ✅ (concluída)

**Já existe:** `ReportResult`, `SummaryMode`, client do Ollama com exceções.

**Fazer:**
- `LLMProvider` (Protocol) com `name` e `generate(prompt) -> str`, lançando `LLMError`.
- `OllamaProvider` encapsulando o client atual.
- `process_document` recebe o provedor (injeção) em vez de nome de modelo solto;
  `SummaryRecord.model` vem de `provider.name`.
- (Opcional) `GeminiProvider` atrás da mesma interface, chave via variável de ambiente.
  Só se a qualidade do Qwen 3B não servir.
- Teste com um `FakeProvider` (sem rede) cobrindo o caminho `--mode llm`.

**Pronto quando:** o pipeline roda em modo LLM com um provedor falso nos testes,
e trocar de provedor não exige mexer em `pipeline.py`.

**Fora do escopo:** retry automático, streaming.

---

## Fase 2 — Camada de banco ✅ (concluída)

**Fazer:**
- SQLAlchemy 2.x: modelos `Company`, `Asset`, `Report`, `Summary`, `Keypoint`
  espelhando **exatamente** `database/schema.sql` (PKs, FKs com `ON DELETE CASCADE`,
  `UNIQUE`, `CHECK`).
- `DATABASE_URL` por variável de ambiente; padrão `sqlite:///data/app.db`.
  Ativar `PRAGMA foreign_keys=ON` no SQLite via evento de conexão.
- `src/db/session.py` (pacote `db`, para não colidir com a pasta `database/` do SQL) com fábrica de sessão; `create_all` no MVP (Alembic na v1.1).
- Repositório (`src/db/repository.py`) com funções pequenas:
  `get_or_create_company`, `find_report(company, tipo, período)`,
  `find_report_by_hash`, `has_summary(report, método, modelo, versão)`,
  `save_result(session, ReportResult)`.
- Testes em SQLite em memória: FKs, unicidades e `save_result` ponta a ponta.

**Pronto quando:** um `ReportResult` do PDF de exemplo é gravado e relido igual,
e as restrições do schema são testadas também pela camada ORM.

---

## Fase 3 — Batch "gerar uma única vez" (19–21/11) — o coração do projeto

**CLI:** `python -m batch.run --dir pdfs/ --mode heuristic|llm [--force] [--dry-run]`

**Identificação do relatório:** o nome do arquivo segue `TICKER_TIPO_PERIODO.pdf`
(ex.: `BBSE3_ITR_2T26.pdf`). O nome do arquivo tem prioridade sobre a detecção
heurística; se faltar ticker, tipo ou período e a heurística também não achar,
o arquivo é **pulado com motivo no log** (nunca gravado pela metade).

**Algoritmo por PDF:**
1. Calcula `file_hash`. Se já existe report com esse hash **e** já há summary
   com (método, modelo, versão atual) → pula (`SKIP`).
2. Se existe report para (empresa, tipo, período) com hash diferente →
   reapresentação: atualiza o hash e regera summaries e keypoints.
3. `process_document(...)`; se `missing_storage_keys()` não estiver vazio → pula.
4. Grava tudo numa **única transação** (keypoints do report: DELETE + INSERT).
5. Erro em um PDF → loga, faz rollback daquele PDF e segue para o próximo.

**Saída:** resumo final com contagens (`novos`, `pulados`, `regerados`,
`falhas`) e código de saída ≠ 0 se houve falha. Modo `llm` checa o Ollama
antes de começar (falha cedo).

**Testes:**
- Rodar duas vezes → segunda execução só `SKIP`, mesmas contagens no banco.
- `--force` regera; mudar `PROMPT_VERSION` regera só o resumo LLM.
- PDF corrompido no meio do lote não impede os outros.

**Fora do escopo:** download automático dos PDFs da CVM/RI (v1.1).

**Pendências herdadas da revisão da Fase 2 (decidir/tratar aqui):**
- `--force`: `save_result` pula summary com a mesma chave (método, modelo,
  `prompt_version`), então regerar com o mesmo prompt não atualiza o `content`.
  Precisa de um modo de substituição (ex.: `replace_summaries=True`).
- Caminho do SQLite: `sqlite:///data/app.db` é relativo ao diretório de
  execução; rodar o batch de outra pasta cria um banco vazio sem aviso.
  Resolver a partir da raiz do projeto ou exigir `DATABASE_URL` no batch.
- O batch deve capturar `IntegrityError` (ex.: CNPJ de uma empresa com ticker
  de outra) e `InvalidCnpjError`, logar com mensagem clara e seguir.

---

## Fase 4 — API somente leitura (21–22/11)

**Endpoints:**
- `GET /empresas?q=` — busca (reaproveitar o matcher fuzzy), paginada.
- `GET /empresas/{ticker}` — dados da empresa e tickers.
- `GET /empresas/{ticker}/relatorios` — lista ordenada por período.
- `GET /relatorios/{id}` — keypoints + resumos (heurístico e, se houver, LLM).
- Manter `/calcular/{metodo}` e `/health`.

**Regras:** schemas de resposta Pydantic (nunca devolver modelo ORM direto),
404 com mensagem clara, CORS liberado só para a origem do frontend,
**nenhum endpoint escreve no banco ou chama LLM**.

**Pronto quando:** testes com `TestClient` + banco SQLite semeado cobrem
todos os endpoints, inclusive 404 e paginação.

---

## Fase 5 — Frontend mínimo (22–23/11)

- Busca por ticker/nome → lista de relatórios → página do relatório
  (keypoints em tabela + resumo).
- URL da API por variável de ambiente do Vite.
- Estados de carregando, vazio e erro. Sem login, sem carteira.
- Mostrar a origem do resumo (heurístico/LLM e modelo) — transparência.

**Pronto quando:** o fluxo completo funciona contra a API local com o banco
gerado pelo batch.

---

## Fase 6 — Deploy e README (24/11)

- Banco Postgres gerenciado (free tier), backend e frontend em hospedagens
  gratuitas. Confirmar limites atuais antes de escolher.
- O batch continua rodando **na minha máquina**, apontando o `DATABASE_URL`
  para o banco de produção.
- Processar 5–10 empresas reais antes de divulgar.
- README: diagrama do fluxo, as decisões de arquitetura do `CLAUDE.md`,
  como rodar localmente, link do site.

**Pronto quando:** o site público abre, busca e mostra relatórios, e o README
explica o projeto para um recrutador em 2 minutos.

---

## Backlog v1.1

- Download automático de ITR/DFP pela CVM (o `data_pipeline` já tem a base).
- `value_numeric` nos keypoints (parse de valores em formato brasileiro).
- Testes em massa da heurística de keypoints (valor/variação trocados).
- Alembic para migrações.
- Retry com backoff no provedor de LLM.
- Retomar usuário/carteira do schema legado.
- Índices de busca/ordenação (**necessário antes de escalar**: previsão de
  1000+ empresas e vários relatórios cada): `company.name` (busca/ordenação),
  `report (company_id, period)` para listar relatórios por período. Mudança
  entra primeiro no `database/schema.sql` e depois nos modelos (o teste de
  paridade cobra os dois). Avaliar também busca por prefixo/`LIKE` e, no
  Postgres, `pg_trgm`.
- Casar empresa por nome normalizado (hoje é nome exato; só vale sem CNPJ/ticker).
- `created_at`/`parsed_at` como `DateTime` (SQLite e Postgres formatam
  `CURRENT_TIMESTAMP` diferente; resolver antes de migrar para Postgres).
- `Literal`/enums do domínio nos campos controlados do ORM e mypy no CI.
- Concorrência no `get_or_create` (dois batches simultâneos); hoje há um só.
- Trocar `session.refresh` por `append` em `get_or_create_company`.
