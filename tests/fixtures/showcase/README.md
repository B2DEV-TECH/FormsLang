# Showcase fixture

`module.xml` -- um módulo Forms2XML 100% sintético (sem dado de cliente,
committável; nomeado `module.xml` como o resto de `fixtures/corpus/`,
não `*_fmb.xml`, pra não cair na regra do `.gitignore` que barra exports
reais de cliente) desenhado para acionar deliberadamente quase todo
branch relevante de `apexlayout.py` / `apexlang.py` num único módulo, e
servir de exemplo de referência tanto do lado Forms quanto do lado APEX.

Diferente do golden corpus (`fixtures/corpus/`, focado em `rules.py` /
`depgraph.py` -- análise de trigger e grafo de dependência), esta fixture
mira o motor de layout geométrico e o export APEXlang: tipos de item, lado
do prompt, adoção de boilerplate, LOV estática, blocos tabulares/master-
detail, canvases (Content/Toolbar/Tab/Stacked) e itens ocultos.

## O que o módulo contém

- **Trigger de formulário** (escopo módulo).
- **`BK_PRODUTO`** -- bloco single-record, cabeçalho espalhado por
  `CV_MAIN` + `CV_TABS`, com ~24 itens cobrindo:
  - todo `item_type` mapeado (`Text Item`, `Display Item`, `Check Box`,
    `Radio Group`, `List Item`, `Bean Area`/textarea, `Push Button`);
  - todo lado de prompt (`Start`→left, `Top`→above, `End`→right,
    `Bottom`→below, `Hidden`→sem prompt, itens sem `Prompt`/`Label` mas
    com controle→`control`);
  - boilerplate `Text` adotado como prompt (ao lado e acima) e os casos
    que NÃO devem ser adotados (negrito, texto longo demais);
  - uma linha propositalmente lotada (8 itens) que reproduz a combinação
    inválida `columnSpan`/`labelColumnSpan` (ver "Bug conhecido" abaixo);
  - itens ocultos via `Visible="false"` **e** via ausência de
    `CanvasName` (as duas rotas para `layout.hidden`).
- **`BK_ITENS`** -- bloco tabular master-detail (via `Relation`) em
  `CV_TABS`/`TAB_ITENS`.
- **`CONTROL`** -- bloco não-database com botões, dividido entre o
  canvas toolbar (`CV_TOOLBAR`, Horizontal Toolbar) e um canvas
  stacked-invisible (`CV_CONFIRMA`, vira inline-dialog).
- **`ProgramUnit`**, **`RecordGroup`+`LOV`** estática (completude do lado
  Forms; o motor de layout não usa RecordGroup/LOV nomeada -- só gera LOV
  estática a partir de `List Item`/`Radio Group` com choices fixos),
  **`VisualAttribute`**, **`Relation`**, **`Alert`**, 4 `Canvas` (ordem de
  declaração é significativa: `CV_TOOLBAR` antes de `CV_MAIN` para o
  hosting do toolbar funcionar) e 1 `Window`.

## Como validar

Não existe ainda um teste automatizado pytest para esta fixture (é usada
via script ad hoc). Rotina manual:

```python
from formslang.parser import parse_xml
from formslang.apexlayout import build_layout
from formslang.apexlang import export_apexlang
from formslang.store import Store
from formslang.convert import build_tasks

module = parse_xml("tests/fixtures/showcase/module.xml")
layout = build_layout(module, 1)          # inspeciona a árvore de regiões

store = Store(":memory:")  # ou um caminho de arquivo
store.init_session(module.name, "tests/fixtures/showcase/module.xml")
store.add_tasks(build_tasks(module))
result = export_apexlang(store, module, "/tmp/out",
                          {"app_id": 101, "name": "DEMO_ALL_ELEMENTS", "alias": "demo-all-elements"})
```

Depois, `apex validate` (SQLcl) no zip exportado confirma que o APEXlang
gerado é sintaticamente válido -- mas **não** pega erros de renderização
de página (ver abaixo).

## Bug conhecido, reproduzido aqui de propósito -- CORRIGIDO

A linha lotada de `BK_PRODUTO` (`NR_PALETE`, `NR_CAIXA`, `NR_UNIDADE`,
`CD_LOTE`, ...) reproduzia `labelColumnSpan > columnSpan` -- combinação
que o APEX rejeita em tempo de renderização com
`WWV_FLOW_GRID_LAYOUT.LABEL_COLUMN_SPAN_TOO_BIG`. Causa raiz: em
`apexlayout.py`, `_fit()` calcula `Placed.label_span` como fração da
grade de 12 colunas completa, antes e independente de `_place_row()` /
`_arrange()` decidirem o `Grid.span` final do item numa linha lotada.

Reproduzido originalmente neste fixture (export em
`demo-all-elements.apex.zip`): `P1_NR_PALETE columnSpan: 1,
labelColumnSpan: 4`, `P1_NR_CAIXA columnSpan: 1, labelColumnSpan: 4`,
`P1_NR_UNIDADE columnSpan: 1, labelColumnSpan: 5`.

**`apex validate` (e também `apex import` real, testado à parte) NÃO
detectam isso** -- ambos retornam sucesso mesmo com a combinação inválida
presente no source exportado. Esse sintoma só aparece ao renderizar a
página de fato num workspace APEX real (abrir a página no navegador) --
por isso esta fixture existe como caso de regressão estático.

**Corrigido em `apexlayout.py`** via `_reconcile_label()`, chamada logo
após `_place_row()`/`_arrange()` atribuírem o `Grid.span` final de cada
item: o `label_span` é limitado (`min(label_span, grid.span - 1)`) para
nunca igualar ou superar o `columnSpan` real da linha; quando não sobra
nem uma coluna pra label separada, `label_span` vira `0` e
`apexlang._label_template()`/`formui.py` caem para o template flutuante
(`optional-floating`/`required-floating`) em vez de emitir a combinação
inválida. Reexportando este fixture com a correção, os quatro itens da
linha lotada agora saem sem `labelColumnSpan` nenhum (`template:
@/optional-floating`), e `apex validate` continua "Validation
successful."
