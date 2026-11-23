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

**Decisão de abertura — documentos de evento.** Comunicados e fatos relevantes
(ex.: `comunicado_petr3_33064.pdf`) não têm período fiscal, e o período faz parte
da chave única do relatório. No MVP eles são **pulados com motivo no log**
(`tipo não periódico`); na v1.1 ganham chave própria (número de protocolo da CVM,
que já aparece no nome do arquivo). Confirmar antes de implementar.

**Identificação do relatório (empresa, tipo, período).** Os PDFs não seguem um
padrão de nome. Exemplos reais (pasta `assets/`, fora do git):

| Arquivo | Empresa | Tipo | Período |
|---|---|---|---|
| `Press-release-Cemig-2026-03-31.pdf` | nome | "press release" | data de fechamento → 1T26 |
| `Desempenho Financeiro Petrobras 3T25.pdf` | nome | — | 3T25 |
| `Earnings Release 3T25.pdf` | — | release | 3T25 |
| `comunicado_petr3_33064.pdf` | ticker | comunicado | — |

Cada campo é resolvido por uma cadeia de fontes, da mais confiável para a menos.
A fonte usada fica registrada (`origin`, `content`, `filename`, `cli`), no mesmo
espírito do `name_method` da empresa:

1. **Origem** (`origin`) — metadados de onde o PDF veio. Hoje nenhum; com o
   scraper (v1.1), categoria e data de referência da CVM viram a fonte principal.
2. **Conteúdo** (`content`) — heurísticas do parser sobre capa e títulos
   (`extract_report_type`, `extract_period`, nome da empresa).
3. **Nome do arquivo** (`filename`):
   - ticker (`[A-Z]{4}\d{1,2}`) → empresa via `asset`/`ticker_map`;
   - nome da empresa → busca fuzzy (`data_pipeline.search.matcher`);
   - período explícito (`3T25`, `1S26`, `12M25`) ou data ISO. Data de fim de
     trimestre (31/03, 30/06, 30/09, 31/12) = aquele trimestre. Outra data é
     tratada como publicação → trimestre anterior, marcado como **inferido** no log.
4. **Override manual** (`cli`) — `--type`, `--period`, `--ticker` para o lote
   inteiro (pastas homogêneas). Vence todas as outras fontes.

Regras:
- Conflito entre fontes (conteúdo diz 3T25, nome sugere 2T25) é logado como
  aviso; vale a fonte de maior prioridade.
- Empresa, tipo ou período sem resolução → arquivo **pulado com motivo**. Nunca
  gravar como `OUTRO` nem pela metade: esses campos formam a chave única, e dois
  documentos sem tipo do mesmo período colidiriam.
- Código em `src/batch/identify.py`, uma função por fonte, testada isoladamente
  com os nomes de arquivo reais acima.

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
- Identificação: cada fonte isolada com os nomes reais, prioridade entre
  fontes, conflito logado, arquivo sem chave completa pulado.
- Mesmo PDF identificado de forma diferente em duas execuções não quebra no
  `UNIQUE(file_hash)`.
- Subir `HEURISTIC_VERSION` regera keypoints; o resto continua `SKIP`.

**Fora do escopo:** download automático dos PDFs da CVM/RI (v1.1).

**Pendências herdadas da revisão da Fase 2:**
- `--force` não regera: `save_result` pula summary com a mesma chave (método,
  modelo, `prompt_version`). Adicionar modo de substituição explícito
  (`replace_summaries=True`), usado só pelo `--force`.
- Caminho do SQLite relativo ao diretório de execução: rodar o batch de outra
  pasta cria um banco vazio sem aviso. Resolver a partir da raiz do projeto e
  imprimir no início da execução qual banco está sendo usado.
- Capturar `IntegrityError` e `InvalidCnpjError` por arquivo, com mensagem
  clara, e seguir para o próximo.
- Buscar o report **pelo hash antes** de resolver a chave de negócio: se a
  identificação de um mesmo PDF mudar entre execuções, o insert bate no
  `UNIQUE(file_hash)`. Mesmo hash com chave diferente → aviso, não insert.

**Puxados do backlog (adiar deixaria o debug mais difícil):**
- **Casar empresa por nome normalizado** (hoje é nome exato). A identificação
  pelo nome do arquivo depende disso; sem ela, "Cemig", "CEMIG" e "Cia Energética
  de Minas Gerais" viram três empresas, cada uma com relatórios pendurados —
  dado duplicado que é caro de desfazer depois.
- **Versão da extração nos keypoints.** Keypoints não guardam qual heurística os
  gerou. Adicionar `report.extractor_version` (= `HEURISTIC_VERSION`) no
  `schema.sql` e nos modelos; subir a versão deve regerar keypoints, e o `SKIP`
  passa a considerá-la. Sem isso, depois de melhorar a heurística não dá para
  saber quais relatórios ainda têm keypoints antigos.
- **Log de execução persistido.** Um JSONL por execução em `logs/batch/`
  (arquivo, hash, fontes usadas por campo, resultado, motivo, duração). É o que
  permite responder "por que este relatório foi pulado?" dias depois.
- **Uma execução por vez.** Lock simples por arquivo no início do batch, em vez
  de resolver concorrência no `get_or_create`.

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
- **Antes do primeiro dado em produção** (depois disso, mudar o schema sem
  migração vira dor de cabeça):
  - Alembic com uma migração base equivalente ao `schema.sql`.
  - `created_at`/`parsed_at` como `DateTime` (SQLite e Postgres formatam
    `CURRENT_TIMESTAMP` de forma diferente).
  - Rodada de testes em massa dos keypoints nos PDFs reais; publicar só o que
    passar na revisão.
- Processar 5–10 empresas reais antes de divulgar.
- README: diagrama do fluxo, as decisões de arquitetura (escritas no próprio
  README), como rodar localmente, link do site.

**Pronto quando:** o site público abre, busca e mostra relatórios, e o README
explica o projeto para um recrutador em 2 minutos.

---

## Backlog v1.1

Itens que **podem** esperar sem complicar o debug. O que não podia foi puxado
para a Fase 3 (nome normalizado, versão da extração, log, lock) ou para antes
do deploy na Fase 6 (Alembic, `DateTime`, testes em massa dos keypoints).

- Scraper de ITR/DFP pela CVM/RI (o `data_pipeline` já tem a base), entregando
  ao batch os metadados de origem (fonte 1 da identificação).
- Documentos de evento (comunicados, fatos relevantes) com chave por protocolo.
- `value_numeric` nos keypoints. Pode esperar: o `value_text` está gravado, então
  dá para preencher depois direto do banco, sem reprocessar PDFs.
- Retry com backoff no provedor de LLM.
- Retomar usuário/carteira do schema legado.
- Índices de busca/ordenação antes de escalar (1000+ empresas): `company.name`
  e busca por prefixo/`LIKE` (no Postgres, `pg_trgm`). A listagem por empresa já
  usa o índice do `UNIQUE (company_id, report_type, period)`. Mudança entra
  primeiro no `schema.sql`; o teste de paridade cobra os modelos.
- `Literal`/enums do domínio nos campos controlados do ORM e mypy no CI (os
  `CHECK` do banco já barram valores inválidos).
- Trocar `session.refresh` por `append` em `get_or_create_company`.
