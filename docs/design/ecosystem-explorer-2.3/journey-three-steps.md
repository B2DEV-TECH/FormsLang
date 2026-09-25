# The three-step journey — design, before any UI

Status: **phase 1 design.** No UI code exists. This document fixes what each
step shows, the one primary action in each state, and the words used. It is
the object the evaluation sessions test
([evaluation protocol](evaluation/protocol.md)). The frames below are text
wireframes. Every value in them is a fact the 2.2 engine records for the
modernization lab (Case B) or the showcase (Case A), taken from
[`inventory-2.2.json`](inventory-2.2.json). None is a mock-up of an imagined
capability.

The journey, from spec §5.4:

> **(1) escolher tela → (2) clicar em uma relação → (3) entender sua evidência
> e, se interessar, seguir o próximo nó.**

There is no configuration modal, layer choice or origin/destination form before
step 3. Each state has **one primary action** and at most **two visible
secondary actions**. Everything else sits under "Mais opções".

UI strings are given in Portuguese, as the spec defines them. Technical terms
(`WRITES`, `SYMBOLIC_REFERENCE`) appear only under "Detalhes técnicos".

## Step 1 — escolher tela

Entry: "Explorar uma tela" on Overview/Start Here. It opens the existing map
workspace in "Por tela" mode. It is not a new main tab.

```
Projeto: Modernization lab                              [Ajuda]
┌──────────────────────────────────────────────────────────────┐
│ Buscar tela…                                                 │
└──────────────────────────────────────────────────────────────┘
  APPROVALS      tem referências externas
  CUSTOMERS      tem referências externas
  INVENTORY      tem referências externas
  ORDERS         abre outra tela · tem referências externas
```

(Measured: only `ORDERS` has `OPENS_FORM` edges, to `CUSTOMERS`, `INVENTORY` and
`APPROVALS`; all four call `OM_SHARED.SHOW_MESSAGE`, which is not supplied.)

- Order is **stable identity order**. No ranking by name, risk or attention.
  The 2.2 ESTATE map shows why: at 500 Forms, attention ranking kept 100 nodes
  that share no relation ([performance](performance-2.2-baseline.md)).
- Each card shows at most two cues. Counts sit behind "Detalhes"; a counter
  that was not observed reads "não observado", never 0.
- A single-Form project skips this list and opens the Form, with "Ver todas as
  telas" to go back. Case A (`DEMO_ALL_ELEMENTS`) is such a project.
- **Primary action:** choose a Form (click, or Enter on the search result).
  **Secondary:** Buscar. There is no other control.

## Step 2 — clicar em uma relação

The chosen Form sits at the centre. It shows one functional hop, as 4–8
groups, with the count of what is folded.

```
Projeto › APPROVALS                                     [Voltar à tela] [Ajuda]

   Superfície                 Código do Form            Fora do Form
   ┌──────────────────┐       ┌──────────────────┐      ┌─────────────────────┐
   │ WIN_APPROVAL      │       │ BK_APPROVAL       │ ───▶ │ altera dados        │
   │  └ CV_APPROVAL    │       │  BT_APPROVE ▸     │      │  LOM_ORDERS         │
   │ (vínculo pela     │       │  BT_REJECT  ▸     │ ─ ─▶ │ usa (não resolvido) │
   │  declaração do    │       │  +N gatilhos      │      │  OM_SHARED.SHOW_…   │
   │  canvas)          │       └──────────────────┘      └─────────────────────┘
   └──────────────────┘                                   +N relações recolhidas
```

- Only relations in the snapshot are drawn. `WIN_APPROVAL › CV_APPROVAL` needs
  a 2.3 snapshot with `CANVAS_IN_WINDOW`. In a 2.2 snapshot the surface group
  shows the window and canvas side by side, with the notice "Vínculo visual não
  disponível nesta revisão; reanalise para completar" (Case D).
- Solid line: observed. Dashed line ending in "não resolvido": the call is
  observed but the target was not found in the sources
  (`OM_SHARED.SHOW_MESSAGE`, `SYMBOLIC_REFERENCE`).
- The Form→table line is a summary of trigger→table edges. Clicking it opens
  the trigger-level relations; it is never evidence by itself.
- **Primary action:** click a relation. **Secondary:** Expandir (next layer of
  a group), Voltar à tela. Filters, depth, paths and zoom live in "Mais opções".

## Step 3 — ver evidência

Clicking `BT_APPROVE → LOM_ORDERS` opens the relation inspector.

```
BT_APPROVE (gatilho WHEN-BUTTON-PRESSED)  →  altera dados  →  LOM_ORDERS

O que vimos
  O código do botão contém um UPDATE em LOM_ORDERS. O nome coincidiu com a
  tabela LOM_ORDERS das fontes de banco analisadas (resolução legada — não
  verificável quanto a schemas homônimos nesta revisão). (Escritas
  identificadas; a lista pode estar incompleta — ver Detalhes técnicos.)
O que isso sugere investigar
  Existe um package (LOM_ORDER_API) que também escreve em LOM_ORDERS. Este
  gatilho não o chama. É um candidato a "bypass" — ver o sinal abaixo.
O que isto não prova
  Não prova que o UPDATE executa sempre, nem qual dos dois caminhos é o dono
  correto da escrita, nem que não exista outra LOM_ORDERS em outro schema.

  [Ver por quê]   Abrir em Review   Seguir LOM_ORDERS ▸
  ▸ Detalhes técnicos: WRITES · FACT · RESOLVED_TO_DATABASE_OBJECT (legado) · evidência <id>
```

- "Ver por quê" is the primary action. It shows the evidence id and, under the
  existing source-read policy, the excerpt from the trigger body.
- The bypass signal is shown as a **separate layer**. It is labelled "sinal
  inferido" and linked to the facts behind it: the `WRITES` edge and the other
  writers. No drawn edge joins `BT_APPROVE` to `LOM_ORDER_API`. None exists in
  the assessment, where the only link is `DUPLICATES_LOGIC` at
  `INFERENCE`.
- **Known under-report in older assessments.** An assessment made before
  `plsql-evidence/2` does not record the `UPDATE lom_approvals` in the same
  trigger ([G-DML](gaps-and-capture.md#g-dml--update-right-after-then-is-not-recorded-as-a-write)).
  A new analysis records it. In both cases the inspector does not word the
  list of writes as complete ("todas as escritas"): the extraction is lexical
  and dynamic SQL is not followed. It says "escritas identificadas".
- **Legacy resolution.** Every 2.2 database resolution is shown as legacy and
  not verifiable against same-named objects in other schemas
  ([contract §5.1](contract-ecosystem-1.md#51-legacy-database-resolution-2122-snapshots)).
  The text says the name *matched* a table. It never says the table is
  confirmed.
- **Seguir o próximo nó** (optional): "Seguir LOM_ORDERS" moves the focus there,
  on an explicit action only. The legacy caveat stays visible on that node. The breadcrumb becomes
  `Projeto › APPROVALS › LOM_ORDERS`, and "Voltar" restores the Form, the
  selection and the expansion.

### The unresolved branch (evaluation task T4)

Clicking the dashed `BT_APPROVE → OM_SHARED.SHOW_MESSAGE`:

```
O que vimos
  O código chama OM_SHARED.SHOW_MESSAGE (2 ocorrências).
O que falta
  Não encontramos esse package nas fontes fornecidas. Para resolver, inclua a
  especificação e o corpo de OM_SHARED nas fontes do projeto.
O que isto não prova
  Não prova que OM_SHARED não existe no banco.
```

## Words the journey never uses

"fluxo de execução", "processo de negócio", "sempre executa", "caminho do
usuário", "tela usada pelo operador", "canvas visível" (for a value whose
origin is not verifiable), "todas as escritas",
"resolvido" or "confirmado" for a legacy database resolution,
"migração x%", scores. The evaluation checks this directly, through the exit
question on execution.

## Case A through the same three steps

`DEMO_ALL_ELEMENTS` opens directly (single Form). Under "Código do Form", select
`POST-COMMIT`. It has two relations:

- `usa P_CALC_TOTAL_ITENS` — observed. The target is the program unit of the
  same Form.
- `chama PKG_UTIL.P_MSG` — observed call, **target not resolved**, even though
  a `PKG_UTIL` program unit exists in this Form
  ([G-CALL-LOCAL](gaps-and-capture.md#2-contract-gaps-facts-22-does-not-record)).
  The inspector says the name was not linked. It does not link it by name.

`PKG_UTIL.F_USUARIO` appears only in the trigger text. There is no relation to
click ([G-CALL-EXPR](gaps-and-capture.md#2-contract-gaps-facts-22-does-not-record)).
