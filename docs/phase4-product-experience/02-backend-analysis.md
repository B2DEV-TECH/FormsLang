STATUS: DONE

# Fase 4 — Análise de Backend (pipeline, state machine, qualidade, performance)

Autor: b2dev_dev. Rodada de análise apenas — nenhum código foi alterado.
Toda afirmação sobre o estado atual cita arquivo:linha; onde não achei
evidência, digo "não encontrado" em vez de supor.

Ver também `00-briefing-b2codex-frontend.md` (o que o b2codex está
desenhando do lado UI) e `01-frontend-analysis.md` (entrega dele, quando
sair). Este documento cobre os itens 5–14 dos "Entregáveis da análise" do
pedido original do Geraldo, mais o diagnóstico do pipeline que embasa todos
eles.

---

## 1. Diagnóstico do pipeline (estado real, verificado)

### 1.1 Estágios

| Estágio | Arquivo:linha | Entrada | Saída | Observação |
|---|---|---|---|---|
| Parse | `parser.py:144 parse_xml()` | XML export do Forms2XML | `FormModule` (`model.py:102`) | Corrige mojibake cp1252 e newlines double-escaped |
| Classificação | `rules.py:28-38` | built-in usado no PL/SQL | verdict `AUTO/ASSISTED/MANUAL/DROP` + fallback `UNKNOWN` | Catálogo fechado; nunca inventa API |
| Análise | `analysis.py:39-61, 112-164` | módulo + catálogo | `UnitAnalysis` (risk factors, behavior, `engine_version`, `stale`) | `stale` já detecta análise desatualizada — reusar essa mecânica |
| Assessment | `assess.py:187 assess_module()` | módulo | `ModuleAssessment` (tiers SIMPLE/MODERATE/COMPLEX/REWRITE, `automatable_pct`) | Dedup por fingerprint em `PortfolioAssessment.finalize()` (341-393) |
| Grafo de dependências | `depgraph.py:407 build()` | módulo + PL/SQL | `DepGraph` (nodes/edges com evidência) | **É um explorador, não um gate.** Nenhum código em `convert.py`/`apexlang.py` consulta o grafo antes de gerar — confirmado por leitura direta. |
| Tasks | `convert.py:205 build_tasks()` | módulo | `ConversionTask` por trigger/program unit | |
| Propostas (IA) | `convert.py:393-422 propose_many()`, `workbench.py:585-632 _run_job()` | tasks | `Proposal` por task, salva individualmente em `store.py` | Ver §1.2 — job model |
| Geração | `apexlang.py:396-416` | proposals aprovadas | `.apx`/zip + `apexlang-manifest.json` | Manifesto cita os comandos `apex validate`/`apex import` como **texto**, nunca executa. Pipeline para aqui — Level 3. |
| Test spec | `testspec.py:163 TestCase` | — | Given/When/Then com estado `pending/accepted/rejected/needs_work` (`store.py:30`) | É revisão do *texto* do caso de teste, não execução real — sem campo de evidência de execução |

### 1.2 Modelo de job (propose_many) — achados que mudam o design da state machine

Li `workbench.py:544-632` linha a linha:

- Cada task é salva individualmente (`store.save_proposal` dentro do loop,
  linha 619) — uma interrupção no meio **não perde** o que já foi
  processado. Isso já é uma boa base pra "idempotente/resumível".
- **Não existe endpoint de cancelamento.** `grep "cancel" workbench.py` = 0
  resultados. Uma vez iniciado, o job só para sozinho ou por exceção.
- **Estado do job vive só em memória** (`self.job` dict, `workbench.py:561`).
  Se o processo do servidor morrer no meio, na próxima abertura o job
  simplesmente não existe mais — sem sinal de "isto foi interrompido, N
  tasks ficaram sem proposta". O usuário só percebe reabrindo a lista e
  contando manualmente.
- Dedup por fingerprint (`seen` dict, linha 586) é **local à chamada** —
  não persiste entre rodadas.
- "One job at a time" via lock (`self._lock`) — bom, evita corrida.

### 1.3 Achado crítico verificado nos dados reais (`LGPDF005.session.db`)

O fork de testes já tinha achado isto; eu confirmo a leitura e assino
embaixo porque muda a prioridade #1 do backend:

- 90 tasks reais, vereditos: `ASSISTED` 48, `AUTO` 17, `MANUAL` 10, **`''`
  (string vazia) 14**, `UNKNOWN` 1.
- **14 de 90 tasks têm verdict vazio — nem sequer `UNKNOWN`.** Isso já viola
  hoje o princípio "zero componente ignorado sem registro" que o próprio
  `methodology.md` do projeto declara. Antes de qualquer coisa de UI/state
  machine, isso é um bug de dados a corrigir: todo task precisa sair de
  `build_tasks()`/`assess.py` com verdict não-vazio (na pior hipótese,
  `UNKNOWN`).
- Só 2 das 90 tasks têm proposta gerada (ambas `provider=echo`,
  `confidence=0.0`). `decision`: 0 linhas.
- E, no módulo de demo (`DEMO_ORDER.session.db`), um `.apex.zip` de 24
  arquivos foi gerado com **0 proposals e 0 decisions**. Isto é a prova
  concreta, em dado real, do problema central que o Geraldo descreveu:
  hoje "arquivo gerado" não implica nenhuma revisão nem confiança.

### 1.4 Modelo de dados do módulo — gap que bloqueia a Matriz de Cobertura

Li `model.py` inteiro (155 linhas). `FormModule` **não modela
estruturalmente**: menus (só guarda `menu_module: str`, o nome, não a
estrutura), timers (**nenhum campo existe**), Java Beans/PJC (nenhum
campo), WebUtil (nenhum campo), visual attributes (nenhum campo),
navegação/tab-order (nenhum campo), validações declarativas fora de
trigger (só o flag `required` em `Item`). `canvases`, `windows`, `alerts`,
`editors`, `object_groups`, `reports`, `tab_pages` são `list[str]` — só
nomes, zero detalhe interno (`model.py:119-125`).

**Consequência direta pra Fase 4**: a Matriz de Cobertura completa que o
Geraldo pediu (que inclui timers, Java Beans/PJC, WebUtil, visual
attributes, navigation, validations como categorias próprias) **não pode
ser calculada hoje** — essas categorias não existem no parser. Isso não é
um problema de `report.py`/`assess.py` (que já agregam bem o que existe),
é um problema de **parser incompleto**. Proponho tratar isso como um
sub-plano de extensão do parser, priorizado por frequência real observada
em specs de clientes (não adivinhar — perguntar ao Geraldo quais dessas
categorias aparecem de fato nos Forms que ele migra, porque estender o
parser pra Java Beans/PJC é trabalho não-trivial e talvez nem apareça nos
projetos reais dele).

---

## 2. Máquina de estados do projeto (novo — hoje não existe)

Hoje o estado é **reconstruído a cada request** contando `session()` +
`stats()` + lista de tasks (`workbench.py:235 state()`) — exatamente o
inverso do que foi pedido ("não inferir estados só pela presença de
arquivos"). Proposta:

### 2.1 Onde vive

Nova coluna persistida `pipeline_state` na entidade de projeto (o registro
multi-projeto/multi-org já existe em `projects.py` — a API está pronta,
só falta UI, conforme achado do fork de UI/UX). Junto: `state_changed_at`
e uma tabela `project_state_history` (transition, from, to, at, reason,
actor) — reaproveitando exatamente o padrão que `store.py:346 history()`
já usa pra decisão por unidade. Nunca inferir; toda transição passa por
uma função central com guard clauses explícitas (rejeita transição
inválida com erro, não silenciosamente).

### 2.2 Estados e o que os habilita (guard = condição objetiva, verificável em SQL/código, nunca "parece pronto")

| Estado | Guard de entrada | Mapeamento hoje |
|---|---|---|
| `CREATED` | projeto registrado, sem source importado | Existe (`projects.py`) |
| `SOURCE_READY` | `parse_xml()` ok, `FormModule` salvo | Implícito, não marcado |
| `PREFLIGHT_FAILED` | parse falhou OU pre-flight (§ novo, ver abaixo) reprovou | **Não existe pre-flight hoje** |
| `READY_FOR_ANALYSIS` | source ready, tasks ainda não construídas | Implícito |
| `ANALYZING` | `build_tasks()` + `assess_module()` + `depgraph.build()` rodando | Não marcado (síncrono hoje, provavelmente rápido — verificar) |
| `ANALYSIS_COMPLETE` | 100% das tasks com verdict não-vazio (fecha o bug do §1.3) | Parcial — hoje pode ficar com verdict `''` |
| `REVIEW_REQUIRED` | há ≥1 task sem decisão humana | É o estado "padrão" pós-análise |
| `READY_TO_GENERATE` | política de bloqueio satisfeita — ver §2.3 | **Não existe gate hoje**: dá pra gerar com 0 decisões |
| `GENERATING` | `apexlang.py` exportando | Não marcado |
| `GENERATED` | zip produzido | Existe como fato, não como estado nomeado |
| `VALIDATION_FAILED` | validação estrutural OU SQLcl reprovou | Não existe (validação não roda) |
| `VALIDATED` | estrutural + SQLcl OK | Não existe |
| `IMPORT_READY` | validado + ambiente APEX configurado | Não existe |
| `IMPORTED` | import real confirmado, evidência salva | Não existe |
| `FUNCTIONAL_TEST_REQUIRED` | importado, test cases pendentes | `testspec.py` tem o estado do caso, não do projeto |
| `COMPLETED` | todos os test cases definidos com `execution_status=passed` | Não existe (falta até o campo de execução real, ver §4 Level 7) |

### 2.3 Gate de `READY_TO_GENERATE` — decisão de produto, não só técnica

Proponho uma política configurável (não hardcoded), no estilo do
`policy.py` que já existe pro egress de IA: por padrão, bloquear geração
enquanto houver task `CRITICAL`/`HIGH` risk sem decisão humana, e sempre
embutir no `apexlang-manifest.json` um resumo honesto de cobertura (X/Y
unidades com proposta, X/Y com decisão) mesmo quando a geração é permitida
com pendências — pra nunca mais se repetir o caso do `.apex.zip` de 24
arquivos gerado com 0 decisões sem nenhum aviso embutido no próprio
artefato. Isto é uma pergunta que só o Geraldo decide (ver Riscos, §7):
bloquear geração ou só avisar de forma impossível de ignorar?

---

## 3. Modelo de jobs/progresso/cancelamento (mecânica)

Base real: já é per-task persisted (bom). Faltam três coisas concretas:

1. **Endpoint de cancelamento**: `POST /api/job/cancel` — seta uma flag
   `cancel_requested` checada entre tasks no loop de `_run_job()`
   (`workbench.py:588`); a task em andamento termina (não aborta no meio de
   uma chamada de IA — evita proposta corrompida), as seguintes não
   iniciam. Sem quebrar o "cada task salva individualmente".
2. **Estado do job persistido, não só em memória**: gravar
   `job_run` (id, project_id, started_at, ended_at, status
   `running/completed/cancelled/crashed`, total, done, failed) numa tabela.
   No boot do servidor, qualquer `job_run` com `status=running` sem
   `ended_at` é reclassificado pra `crashed` — isso é o que permite a UI
   dizer "essa rodada foi interrompida, restam N unidades" em vez de
   silenciosamente esquecer.
3. **Idempotência explícita**: reexecutar um job sobre tasks já com
   proposta bem-sucedida deve ser um *no-op* por padrão (pular, não
   reprocessar), com uma opção explícita "forçar reanálise" — hoje o
   comportamento nesse cenário não foi testado/verificado; tratar como
   open question de implementação, não suposição.

---

## 4. Sete níveis de sucesso — definição operacional

Cada nível abaixo é uma condição **objetiva e verificável em código**, não
uma sensação de "parece pronto". A UI nunca mostra "Success" sem apontar o
nível (isso é escopo do b2codex — aqui defino o contrato de dados que a UI
consome).

- **Level 0 — Parsed**: `parse_xml()` retornou `FormModule` sem exceção.
  Hoje: implícito (se chegou até a tela, passou). Proposto: gravar
  explicitamente `level_0_at`.
- **Level 1 — Classified**: 100% das tasks construídas têm verdict
  não-vazio (`AUTO/ASSISTED/MANUAL/DROP/UNKNOWN`). **Hoje isso falha nos
  dados reais** (14/90 com `''`) — corrigir a causa raiz em
  `build_tasks()`/`rules.py` é pré-requisito de qualquer coisa de Fase 4.
- **Level 2 — Planned**: toda task tem proposta gerada **ou** justificativa
  explícita de MANUAL/DROP (campo hoje inexistente para MANUAL/DROP —
  `Proposal` só existe quando roda IA). Proposto: um `Proposal` "vazio"
  com `apex_target='MANUAL'`/`'DROP'` e `notes` obrigatório também conta
  como Level 2 — hoje o schema não distingue "não tentado" de
  "decidiu não converter com justificativa".
- **Level 3 — Generated**: `.apx`/zip existe (já cumprido hoje). Mas o
  manifesto passa a carregar o resumo de cobertura honesto (§2.3).
- **Level 4 — Structurally validated** (NOVO, não existe): validador que
  abre o zip gerado e confere referências internas (páginas existem,
  shared components referenciados existem, `.apx` bem-formado) —
  reaproveitar o parser/estrutura que `apexlang.py` já usa pra montar o
  zip, rodando de trás pra frente como checagem.
- **Level 5 — SQLcl validated** (NOVO, não existe): chamar de fato
  `sql /nolog ... apex validate` via `subprocess`, capturar stdout/stderr/
  exit code como evidência, opt-in por projeto (exige caminho do SQLcl
  configurado — nunca assumir que está instalado).
- **Level 6 — APEX imported** (NOVO, não existe): ver §6 — decisão de
  produto sobre automatizar ou não.
- **Level 7 — Functionally verified** (NOVO, parcial): `testspec.py`
  precisa de um campo de **execução real** (`execution_status`
  `not_run/passed/failed`, `evidence`, `executed_by`, `executed_at`),
  distinto do estado de *revisão do texto* do caso de teste que já existe
  (`pending/accepted/rejected/needs_work`). Hoje só existe o segundo.

---

## 5. Matriz de cobertura Forms→APEX

**O que já existe** (`assess.py`, `report.py`): contagem de
blocks/items/triggers/program_units/lovs/record_groups/relations/
canvases/windows/alerts/tab_pages/reports, cruzado com
AUTO/ASSISTED/MANUAL/DROP/UNKNOWN, mais `automatable_pct`. É uma boa base
— só precisa dos eixos "convertido/validado/falhou" que não existem porque
os Levels 4-7 não existem (§4).

**O que falta no parser** (bloqueante, §1.4): menus, timers, Java
Beans/PJC, WebUtil, visual attributes, navigation, validations declarativas
— nenhuma dessas categorias tem representação estruturada em `model.py`
hoje. Proponho: antes de prometer a matriz completa de 20+ categorias do
pedido original, validar com o Geraldo quais categorias aparecem de fato
nos Forms reais que ele converte (LGPDF005 real só tem triggers e program
units — nenhuma das categorias "exóticas" apareceu nesse caso real) e
priorizar a extensão do parser por frequência real, não pela lista
completa de uma vez.

---

## 6. Plano de validação SQLcl/APEX

Hoje: `apexlang.py:407` só **imprime o texto do comando** no manifesto —
nunca invoca SQLcl. `README.md`/`SPEC.md` documentam o fluxo manual
(usuário roda `apex validate`/`apex import` sozinho, fora do FormsLang).

Proposta em duas fases, porque automatizar import real num workspace APEX
é uma decisão de risco/confiança, não só técnica:

- **V1 (Level 4-5, baixo risco)**: `subprocess` chamando SQLcl **só em
  modo validate** (não muta nada no APEX, é local/offline), opt-in,
  caminho do SQLcl configurável em Settings sem expor segredo nenhum
  (não há credencial aqui — validate é local). Evidência (stdout/exit
  code) fica salva e anexada ao projeto.
- **V2 (Level 6, risco maior)**: import real exige credencial de um
  workspace APEX de destino. Aqui bate direto no princípio de egress
  policy que o projeto já tem pra IA (`policy.py`, v0.1.4 compliance) —
  reusar o mesmo mecanismo de allowlist/consentimento explícito por
  organização, nunca importar silenciosamente. Alternativa mais segura pra
  v1 do produto: **não automatizar** — o usuário roda o import ele mesmo e
  o FormsLang só oferece um botão "marquei como importado" com campo de
  evidência (id do workspace, timestamp, screenshot opcional) — mais
  simples, zero risco de credencial, ainda fecha o Level 6 como estado
  auditável. **Decisão pro Geraldo, não decido sozinho** (ver §7).

---

## 7. Plano de cache e análise incremental

Hoje: dedup por fingerprint só dentro da mesma rodada (`workbench.py:586`,
`seen` dict local). Sem cache entre sessões, sem análise incremental (todo
reprocessamento é do módulo inteiro).

Proposta:
- **Cache persistido**: chave `(fingerprint, engine_version, provider,
  model)` → proposta. `analysis.py` já calcula `engine_version` como hash
  do catálogo de regras (§1.1) — é a chave certa pra invalidação
  automática quando as regras mudam, sem precisar de lógica nova de
  invalidação.
- **Análise incremental**: reaproveitar o `stale` que `analysis.py:143-145`
  já calcula por unidade — hoje ele só marca "esta análise ficou velha";
  proponho estender pra também pular reprocessamento de unidades
  **não-stale** num rerun, em vez de sempre reanalisar o módulo inteiro.

---

## 8. Golden fixtures — estratégia (hoje: zero)

Confirmado (fork de testes): não existe `tests/fixtures/`,
`tests/golden/` nem `tests/corpus/`. Tudo é um único `SAMPLE_XML` sintético
(`conftest.py:143`, módulo `DEMO_ORDER`) reusado pela maioria dos testes de
pipeline.

Proposta:
- Novo diretório `tests/fixtures/corpus/{tiny,small,medium,large,
  pathological}/*.xml`, 100% sintético (sem dado de cliente, consistente
  com o que o repo já faz).
  - `tiny`: 1 trigger, sem blocks.
  - `small`: equivalente ao `DEMO_ORDER` atual (~10 objetos).
  - `medium`: ~50 objetos, cobrindo o máximo de categorias que o parser já
    modela hoje.
  - `large`: 200+ objetos, múltiplos blocks/relations, testando os limites
    do `depgraph.py` (`MAX_DEPTH=4`, `MAX_RESULTS=250`, `depgraph.py:135-
    136`).
  - `pathological`: dependência circular, `GO_BLOCK` com nome dinâmico
    (não resolve — testa o comportamento de `unresolved_targets`), mojibake
    de encoding, PL/SQL gigante.
- Golden esperado por fixture: dump determinístico do `FormModule`
  parseado, contagem de verdicts esperada, proposta esperada em modo
  `EchoProvider` (offline, determinístico — já existe, `workbench.py`
  importa `EchoProvider`), lista de arquivos gerados + checksum (excluindo
  campos não-determinísticos como timestamp), warnings esperados.
- **Regra de ouro**: mudança no golden é sempre um diff revisado por
  humano num PR — nunca update automático de snapshot. Um script
  `--update-golden` existe só pra regravar depois de revisão manual
  explícita, nunca em CI.

---

## 9. Baseline de performance — plano, sem números inventados

Confirmado: **zero instrumentação hoje** (`grep` por
`perf_counter|time.time()|benchmark|elapsed|duration_ms` no pacote
`formslang/` não retorna nada relevante; único timer existe só no
client-side JS, não persistido). `ai.py` não captura tokens de
input/output da resposta do provider.

**Restrição que muda o desenho**: `pyproject.toml` declara
`dependencies = []` de propósito — comentário no próprio arquivo diz que é
pra rodar "em máquinas travadas onde instalar pacote é change request".
Isso descarta `psutil` pra medir CPU/memória. `resource.getrusage` é
POSIX-only (não funciona no Windows, que é a plataforma alvo real do
desktop app). Proponho **V1 sem CPU/memória** — só wall-clock (stdlib
`time.perf_counter()`, funciona igual nas duas plataformas), contagem de
chamadas, cache hit rate, tamanho do `.session.db` (`os.path.getsize`,
trivial) — e tratar CPU/memória via Windows (`ctypes`+`psapi`) como item
separado, só se o Geraldo achar que vale a complexidade.

Plano de instrumentação (novo módulo `formslang/telemetry.py`, stdlib
puro, nunca grava conteúdo/prompt/segredo — só duração e contadores,
coerente com a seção "Observabilidade local" do pedido original):
startup, upload/import, parsing, normalização, fingerprinting,
classificação, dependency graph, fila de IA, cada chamada de provider
(duração + tokens quando o provider retornar), geração, validação
estrutural, validação SQLcl, packaging/export, total end-to-end.

Rodar contra os 5 tamanhos do corpus (§8) assim que ele existir, medir
p50/p95/máximo/throughput/cache-hit-rate/nº de chamadas ao modelo/tokens.
**Não vou publicar nenhum número agora — não foi medido.** Os budgets
numéricos (deliverable 11 do pedido) só saem depois desse baseline real.

---

## 10. Métricas de qualidade / critérios objetivos de aceite (proposta)

Reaproveitando o princípio do `risk-model.md` (readiness score nunca
esconde trabalho atrás de uma média — cada componente aparece separado):

- **Cobertura de classificação**: % de unidades com verdict não-vazio —
  meta 100% (hoje falha, §1.3).
- **Cobertura de decisão pré-geração**: % de unidades com proposta ou
  justificativa MANUAL/DROP antes de permitir `READY_TO_GENERATE` (§2.3).
- **Taxa de validação estrutural**: % de exports que passam Level 4 sem
  erro.
- **Taxa de validação SQLcl**: % que passam Level 5 (quando SQLcl
  configurado).
- **Regressão em golden fixtures**: zero diffs não-explicados entre
  releases — todo diff é revisado, nenhum é "esperado" sem justificativa
  no PR.
- **Honestidade de superfície**: nenhuma tela mostra "Success"/"Converted"
  sem o nível (Level 0-7) explícito ao lado — isso é testável via
  auditoria de UI (b2codex) + snapshot dos textos gerados pelo backend.

---

## 11. Riscos e decisões pendentes (lado backend)

1. **Bloquear ou só avisar em `READY_TO_GENERATE` (§2.3)?** Bloquear é mais
   seguro mas pode travar fluxo de quem só quer ver um rascunho. Preciso
   da decisão do Geraldo — não decido sozinho porque muda o modelo de
   produto.
2. **Automatizar SQLcl import real (Level 6) ou ficar em
   "marquei como importado" com evidência manual (§6)?** Automatizar é
   mais forte mas introduz superfície de credencial/rede que o projeto
   até agora evitou deliberadamente (todo o resto é local-first). Minha
   recomendação: começar com attestation manual, automatizar só se virar
   pedido recorrente.
3. **Extensão do parser pra categorias exóticas (menus, timers, PJC,
   WebUtil) — vale o esforço agora?** Depende de quão comuns essas
   categorias são nos Forms reais que o Geraldo converte. O único dado
   real que tenho (`LGPDF005`) não usa nenhuma delas. Proponho perguntar
   antes de estender o parser especulativamente.
4. **CPU/memória no benchmark**: adiar (V1 só wall-clock) ou implementar
   via `ctypes` no Windows agora? Recomendo adiar.
5. O bug do verdict vazio (§1.3, 14/90 tasks) precisa virar um item de
   correção **antes** de qualquer trabalho novo de Fase 4 — é dado real
   quebrando um princípio que o projeto já diz que segue.
