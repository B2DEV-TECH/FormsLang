# Fase 4 — Plano de execução (b2codex executa, b2dev_dev revisa e testa)

Modelo de trabalho definido pelo Geraldo em 31/08/2026:

| Papel | Quem | O quê |
|---|---|---|
| Planejamento | b2dev_dev | Especifica cada tarefa, critério de aceite e como será testada |
| Execução | b2codex | Escreve o código/teste, roda, reporta |
| Revisão + teste | b2dev_dev | Lê o diff, roda os testes de forma independente, aprova ou devolve |
| Aprovação final | Geraldo | Merge/commit e decisões de produto |

## Regras invioláveis pro executor (b2codex)

1. **Zero dependência externa nova.** `pyproject.toml` declara
   `dependencies = []` de propósito ("máquinas travadas onde instalar
   pacote é change request"). Só stdlib. Dev-deps já existentes
   (`pytest`, `ruff`) podem ser usadas.
2. **Nenhum commit, nenhum push.** Deixa o working tree sujo; quem commita
   é o Geraldo.
3. **Nenhum snapshot/golden atualizado automaticamente.** Golden só muda
   por diff revisado por humano.
4. **Nenhum material de cliente.** Fixtures 100% sintéticas.
5. **Nunca logar conteúdo**: código, spec, prompt, resposta do modelo,
   credencial, dado de Form, segredo de MFA. Telemetria = só duração e
   contador.
6. **Todo trabalho vem com teste.** Sem teste, eu devolvo.
7. Rodar `ruff` e `pytest` antes de reportar; colar a saída real no
   relatório (não "deve passar").

---

## LOTE 1 — pré-requisitos neutros (não dependem de decisão de produto)

Estas quatro tarefas são independentes das perguntas em aberto do Lote 2 e
podem rodar já. Ordem: T1 → T2 → T3 → T4 (uma por vez, com revisão entre
elas).

### T1 — Verdict nunca vazio (bug real, prioridade máxima)

**Evidência do problema:** no `LGPDF005.session.db` real, 14 de 90 tasks
têm `verdict = ''` (string vazia) — nem `UNKNOWN`. Isso viola o princípio
"zero componente ignorado sem registro" que o próprio `methodology.md`
declara, e quebra o Level 1 do modelo de qualidade (ver
`02-backend-analysis.md` §4).

**O que fazer:**
1. Achar a **causa raiz** — por onde uma task sai de `build_tasks()`
   (`convert.py:205`) / classificação (`rules.py:28-38`) sem verdict.
   Reportar a causa antes de corrigir.
2. Garantir que nenhum caminho produza verdict vazio: fallback explícito
   `UNKNOWN` no ponto onde a classificação não resolve.
3. Leitura defensiva: onde o código lê verdict de sessões antigas já
   gravadas, tratar `''` como `UNKNOWN` (não reescrever `.session.db`
   existente — dado histórico não se altera).

**Critério de aceite:**
- Teste novo que constrói tasks a partir da fixture e afirma que todo
  verdict ∈ `{AUTO, ASSISTED, MANUAL, DROP, UNKNOWN}` — zero vazios.
- O teste **falha antes** da correção e passa depois (colar as duas saídas).
- `pytest` completo verde, `ruff` limpo.

**Como eu vou testar (independente):** rodo a suíte inteira; abro o
`LGPDF005.session.db` real e confiro que a leitura defensiva mostra os 14
como `UNKNOWN` e não em branco; leio o diff procurando `except`/fallback
silencioso.

---

### T2 — `telemetry.py`: instrumentação de tempo (stdlib puro)

Hoje há **zero** instrumentação no pacote `formslang/` (nenhum
`perf_counter`, nenhum `elapsed`, nada persistido). Sem isso não existe
baseline de performance, e sem baseline não dá pra propor budget numérico
nenhum — o Geraldo foi explícito: *não inventar números*.

**O que fazer:**
- Módulo novo `formslang/telemetry.py`, stdlib pura, com um context manager
  de estágio (`with stage("parse", project_id): ...`) usando
  `time.perf_counter()`.
- Tabela nova no session store: `stage_timing (id, project_id, stage,
  started_at, duration_ms, item_count, ok, error_kind)`. `error_kind` é a
  **classe** da exceção, nunca a mensagem (mensagem pode conter conteúdo).
- Instrumentar os estágios: parse, classificação, assessment, depgraph,
  build_tasks, cada chamada de provider de IA (duração + tokens **se** o
  provider devolver; se não devolver, gravar `NULL`, não estimar), geração
  `.apx`, packaging/export.
- **Escopo V1: só wall-clock.** Sem CPU, sem memória —
  `resource.getrusage` é POSIX-only e o alvo é Windows; `psutil` está
  barrado pela regra 1. Tamanho do DB via `os.path.getsize` (trivial, pode
  incluir).

**Critério de aceite:**
- Testes: o context manager grava duração; grava mesmo quando o bloco
  levanta exceção (e propaga a exceção, não engole); `error_kind` guarda o
  nome da classe e nada mais.
- Um teste de guarda que varre o módulo e falha se aparecer qualquer
  gravação de campo livre vindo de conteúdo do usuário.
- `pyproject.toml` inalterado (nenhuma dep nova).

**Como eu vou testar:** rodo a suíte; faço um parse real de fixture e leio
a tabela `stage_timing` direto no SQLite pra confirmar que gravou; grep no
diff atrás de qualquer `str(e)` ou log de conteúdo.

---

### T3 — Job persistido + cancelamento

Hoje (`workbench.py:544-632`): cada proposta já é salva individualmente
(bom — não perde trabalho), mas o estado do job vive **só em memória**
(`self.job`, linha 561) e **não existe cancelamento** (`grep cancel` = 0
resultados). Se o processo morre no meio, na próxima abertura não sobra
nenhum sinal de que a rodada foi interrompida com N unidades pendentes.

**O que fazer:**
1. Tabela `job_run (id, project_id, started_at, ended_at, status, total,
   done, failed, cancel_requested)`, `status ∈ {running, completed,
   cancelled, crashed}`.
2. No boot: todo `job_run` com `status='running'` e `ended_at IS NULL` vira
   `crashed` — é isso que permite a UI dizer "essa rodada foi interrompida,
   restam N".
3. `POST /api/job/cancel`: seta `cancel_requested`; o loop de `_run_job`
   (linha 588) checa **entre** tasks. A task em andamento **termina**
   normalmente — nunca abortar no meio de uma chamada de IA, pra não
   gravar proposta pela metade.
4. Rerun idempotente: por padrão **pular** tasks que já têm proposta
   bem-sucedida (no-op), com flag explícita `force` pra reprocessar.
   Preservar o lock de "um job por vez" que já existe.

**Critério de aceite:**
- Teste: job cancelado no meio → status `cancelled`, tasks já processadas
  mantêm proposta, as seguintes ficam intactas.
- Teste: `job_run` órfão em `running` vira `crashed` no boot.
- Teste: rerun sem `force` não refaz o que já tem proposta; com `force`,
  refaz.

**Como eu vou testar:** rodo os testes; disparo um job real com a fixture
`large` e cancelo no meio pra ver o comportamento de verdade, não só o
mock.

---

### T4 — Corpus de fixtures + golden

Hoje não existe `tests/fixtures/`, `tests/golden/` nem `tests/corpus/` —
tudo é um único `SAMPLE_XML` sintético em `conftest.py:143`.

**O que fazer:**
- `tests/fixtures/corpus/{tiny,small,medium,large,pathological}/*.xml`,
  100% sintéticos:
  - `tiny`: 1 trigger, sem blocks.
  - `small`: equivalente ao `DEMO_ORDER` atual (~10 objetos).
  - `medium`: ~50 objetos cobrindo o máximo de categorias que o parser
    **já** modela (não inventar categorias que `model.py` não tem).
  - `large`: 200+ objetos, múltiplos blocks/relations — testa os limites do
    `depgraph.py` (`MAX_DEPTH=4`, `MAX_RESULTS=250`).
  - `pathological`: dependência circular, `GO_BLOCK` com alvo dinâmico
    (não resolve — testa `unresolved_targets`), mojibake cp1252, PL/SQL
    gigante.
- Golden por fixture: dump determinístico do `FormModule`, contagem de
  verdicts, proposta com `EchoProvider` (offline/determinístico, já
  existe), lista de arquivos gerados + checksum **excluindo campos
  não-determinísticos** (timestamp, uuid, path absoluto).
- Runner de regressão que mostra **diff legível**, não só "falhou".
- Script `--update-golden` que só roda por invocação manual explícita.
  **Nunca em CI.**

**Critério de aceite:**
- Os 5 níveis rodam verdes duas vezes seguidas (determinismo real).
- Mudar uma regra em `rules.py` de propósito faz o golden falhar com diff
  legível — demonstrar isso na prática e depois reverter.
- Nenhum caminho de CI chama `--update-golden`.

**Como eu vou testar:** rodo duas vezes e comparo; faço eu mesmo a mudança
proposital numa regra pra ver o diff quebrar; confiro que nada de cliente
entrou nas fixtures.

---

## LOTE 2 — bloqueado por decisão do Geraldo

Estas dependem de escolha de produto e **não começam** antes da resposta:

1. **Gate de geração** — bloquear `READY_TO_GENERATE` quando houver unidade
   HIGH/CRITICAL sem decisão humana, ou apenas avisar de forma impossível
   de ignorar? (Hoje dá pra gerar um `.apex.zip` de 24 arquivos com 0
   propostas e 0 decisões — foi o que aconteceu no `DEMO_ORDER`.)
2. **Level 6 (import APEX)** — automatizar via SQLcl com credencial de
   workspace, ou ficar em "marquei como importado" com evidência manual?
   Minha recomendação: attestation manual primeiro.
3. **Extensão do parser** — vale estender agora pra menus/timers/Java
   Beans/PJC/WebUtil/visual attributes? O único Form real que temos
   (`LGPDF005`) não usa nenhuma dessas. Precisa saber quais aparecem de
   fato nos projetos reais antes de investir.
4. **CPU/memória no benchmark** — adiar (recomendo) ou implementar via
   `ctypes`+`psapi` no Windows agora?

Depois do Lote 1 e das respostas acima: state machine persistida (§2 do
backend), Levels 4-5 (validação estrutural + SQLcl), cache
cross-sessão/análise incremental (§7), e o baseline de performance medido
de verdade sobre o corpus.
