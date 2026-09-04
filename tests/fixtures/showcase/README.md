# Showcase fixture

`module.xml` -- um módulo Forms2XML 100% sintético (sem dado de cliente,
committável; nomeado `module.xml` como o resto de `fixtures/corpus/`,
não `*_fmb.xml`, pra não cair na regra do `.gitignore` que barra exports
reais de cliente) desenhado para dois fins ao mesmo tempo:

1. **Bancada do FormsLang** -- acionar deliberadamente quase todo branch
   relevante de `apexlayout.py` / `apexlang.py` (layout geométrico, export
   APEXlang) e todas as faixas de veredito de `rules.py` (AUTO / DROP /
   ASSISTED / MANUAL / UNKNOWN) num único módulo.
2. **Demo ao vivo** -- converter no Forms Builder 14c, compilar e RODAR de
   verdade contra o schema `FORMSLANG` criado por `demo_schema.sql`, pra
   mostrar o pipeline inteiro Forms -> `assess` -> APEX com um form que
   tem cara de sistema legado de verdade (toolbar, abas, master-detail,
   LOVs, auditoria, janela modal, relatório, exportação).

Diferente do golden corpus (`fixtures/corpus/`, focado em `rules.py` /
`depgraph.py` com módulos pequenos), esta fixture é propositalmente
gorda: 5 blocos, 78 itens, 55 triggers, 4 program units, ~500 linhas de
PL/SQL.

## O que o módulo contém

- **4 `ModuleParameter`** (`P_CATEGORIA_INICIAL`, `P_MODO`, `P_USUARIO`,
  `P_DIR_EXPORT`) lidos como `:PARAMETER.X`. `P_MODO='CONSULTA'` trava o
  form em somente-leitura no WHEN-NEW-FORM-INSTANCE.
- **14 triggers de formulário**: PRE-FORM (GLOBALs + INSERT direto +
  `FORMS_DDL('COMMIT')`), WHEN-NEW-FORM-INSTANCE (título dinâmico,
  `CREATE_TIMER`, modo consulta, `EXECUTE_QUERY` inicial), POST-COMMIT,
  POST-FORM (`DELETE_TIMER`, `ERASE`), WHEN-TIMER-EXPIRED (relógio na
  toolbar), ON-ERROR (`ERROR_CODE`/`DBMS_ERROR_TEXT` -> alerta), ON-MESSAGE
  (`MESSAGE_CODE`), KEY-COMMIT / KEY-EXEQRY / KEY-LISTVAL / KEY-CLRFRM /
  KEY-EXIT (com `DisplayInKeyboardHelp`), WHEN-WINDOW-CLOSED,
  WHEN-TAB-PAGE-CHANGED (`GET_CANVAS_PROPERTY(TOPMOST_TAB_PAGE)`).
- **`BK_PRODUTO`** (`TAB_PRODUTO`) -- bloco single-record, cabeçalho
  espalhado por `CV_MAIN` + três abas de `CV_TABS`, cobrindo:
  - todo `item_type` mapeado (`Text Item`, `Display Item`, `Check Box`,
    `Radio Group`, `List Item`, `Bean Area`/textarea);
  - todo lado de prompt (`Start`→left, `Top`→above, `End`→right,
    `Bottom`→below, `Hidden`→sem prompt, item sem `Prompt`/`Label`);
  - boilerplate `Text` adotado como prompt (ao lado e acima) e os casos
    que NÃO devem ser adotados (negrito, texto longo demais);
  - a linha lotada de 8 itens que reproduz o bug `labelColumnSpan`
    (ver "Bug conhecido" abaixo);
  - itens ocultos via `Visible="false"` **e** via ausência de
    `CanvasName`;
  - propriedades Forms que o parser ainda não lê mas o compilador exige
    ou usa: `PrimaryKey`, `FormatMask`, `InitializeValue` (Radio Group e
    Check Box precisam -- FRM-30188 / FRM-30174 sem isso),
    `CheckedValue`/`UncheckedValue`, `ValidateFromList`, `MultiLine` +
    `WrapStyle`, `Tooltip`/`Hint`, `LowestAllowedValue`/`HighestAllowedValue`;
  - triggers de bloco PRE-QUERY (`DEFAULT_WHERE` dinâmico), POST-QUERY
    (lookups + `SET_ITEM_INSTANCE_PROPERTY` com visual attribute por
    registro), PRE-INSERT / PRE-UPDATE / PRE-DELETE, WHEN-VALIDATE-RECORD,
    WHEN-CREATE-RECORD, WHEN-NEW-RECORD-INSTANCE; triggers de item
    WHEN-VALIDATE-ITEM (um deles chama `PKG_PRODUTO.F_VALIDA_EAN13` no
    banco), WHEN-LIST-CHANGED, WHEN-RADIO-CHANGED, WHEN-CHECKBOX-CHANGED,
    WHEN-MOUSE-DOUBLECLICK (`LIST_VALUES` e `SHOW_EDITOR`);
  - duas `Relation` (filhas do bloco mestre, como o forms.xsd exige):
    `REL_ITENS` (Isolated, exclusão dos filhos feita à mão no PRE-DELETE)
    e `REL_AUDIT` (Deferred + AutoQuery).
- **`BK_ITENS`** (`TAB_PRODUTO_ITEM`) -- bloco tabular master-detail, 5
  linhas, scrollbar própria, `SEQ_ITEM` por MAX+1 no PRE-INSERT e um item
  de fórmula (`VL_TOTAL_LINHA`, `CalculateMode="Formula"`).
- **`BK_AUDIT`** (`TAB_PRODUTO_AUDIT`) -- detalhe somente-leitura da
  trilha gravada pelo trigger de banco; `DataType="Datetime"`, filtro
  extra vindo de `CONTROL.PC_TP_OPERACAO` (LOV estática) no PRE-QUERY.
- **`BK_RESUMO`** (`VW_PRODUTO_RESUMO`) -- bloco sobre view agregada (sem
  ROWID: `KeyMode="Non-Updateable"` + `PrimaryKey`), duplo clique na
  categoria faz drill-down no mestre.
- **`CONTROL`** -- bloco não-database: toolbar de 2 linhas (Salvar,
  Cancelar, Excluir, Consultar, Novo, Duplicar, Reajuste, Relatório,
  Exportar, check box "Somente ativos", Site, Calculadora, Ajuda, relógio),
  diálogo inline em canvas stacked (`CV_CONFIRMA`), janela modal de
  reajuste (`CV_REAJUSTE`/`WIN_REAJUSTE`, chama procedure do banco com
  parâmetro OUT) e botões dentro das abas.
- **4 `ProgramUnit`**: Procedure, Function e Package Spec + Body
  (`PKG_UTIL`).
- **3 `RecordGroup`** (Query simples, Query com WHERE, `Static` com
  `RecordGroupColumnRow`) e **4 `LOV`** -- `RG_CATEGORIA` é compartilhado
  por duas LOVs com `ReturnItem` diferentes.
- **3 `VisualAttribute`**, **4 `Alert`** (Note / Stop / Caution com 3
  botões), **1 `Editor`** (não existe atributo Item→Editor no forms.xsd;
  é aberto por `SHOW_EDITOR` num trigger), **1 `Report`** (Oracle Reports,
  só compila -- não há report server na demo).
- **5 `Canvas`** (`CV_TOOLBAR` Horizontal Toolbar, `CV_MAIN` Content com
  Frames/Text/Rectangle, `CV_TABS` Tab com 5 páginas, `CV_CONFIRMA`
  Stacked invisível, `CV_REAJUSTE` Content da segunda janela -- a ordem de
  declaração é significativa: `CV_TOOLBAR` antes de `CV_MAIN` para o
  hosting do toolbar funcionar) e **2 `Window`** (Document + Dialog Modal).

### Cobertura de vereditos (`rules.py`)

`formslang assess tests/fixtures/showcase/module.xml` hoje reporta
Triggers `AUTO=13 DROP=1 ASSISTED=38 MANUAL=2 UNKNOWN=1` e Built-ins
`AUTO=60 DROP=4 ASSISTED=55 MANUAL=14`, tier REWRITE. Os MANUAL são
propositais e cada um representa um padrão legado real:
`CREATE_TIMER`/`DELETE_TIMER`, `FORMS_DDL`, `HOST('calc.exe')`,
`RUN_REPORT_OBJECT`, `TEXT_IO`. As chamadas fora do catálogo
(`PKG_PRODUTO.*`, `PKG_UTIL.*`, `MESSAGE_CODE`, `GET_CANVAS_PROPERTY`,
`SET_ITEM_INSTANCE_PROPERTY`, `ERASE`, `SHOW_EDITOR`) caem em
`unknown_calls` de propósito -- é o que o assess deve apontar como
"regra já no banco" ou "dívida de catálogo".

## Rodando de verdade no Forms Builder

### 1. Schema de demo (`demo_schema.sql`)

Cria, de forma idempotente (dropa e recria), no schema `FORMSLANG`:
`TAB_CATEGORIA`, `TAB_FORNECEDOR`, `TAB_PRODUTO` (+ `TAB_PRODUTO_SEQ`),
`TAB_PRODUTO_ITEM`, `TAB_PRODUTO_AUDIT`, `TAB_FORM_ACESSO`, a view
`VW_PRODUTO_RESUMO`, o package `PKG_PRODUTO` (`F_VALIDA_EAN13`,
`F_TOTAL_ITENS`, `F_DS_STATUS`, `P_APLICA_REAJUSTE`) e o trigger de
auditoria `TRG_TAB_PRODUTO_AUDIT`. Semeia 4 categorias, 4 fornecedores, 6
produtos com EAN-13 válidos, 6 itens e 9 linhas de auditoria (3 delas
geradas por UPDATEs de exemplo: reajuste de preço, inativação, bloqueio).
Não é lido pelo parser nem pelos testes.

```powershell
# SQLcl thin, sem tnsnames (no Git Bash exporte MSYS_NO_PATHCONV=1 antes,
# senão o /nolog vira caminho Windows e o SQLcl imprime o usage)
printf '%s\n' 'connect FORMSLANG/<senha>@localhost:1521/FREEPDB1' `
  '@tests\fixtures\showcase\demo_schema.sql' 'exit' | sql -S -thin /nolog
```

O script termina com SELECTs de conferência (`user_objects` tudo VALID,
contagens por tabela, `user_errors` vazio).

### 2. Converter e compilar

Pelo Forms Builder: **File > Convert...** (XML to Forms Module, "Overwrite
existing" marcado) apontando pro `module.xml`; abrir o `.fmb`, conectar
como `FORMSLANG` e **Compile All** (Ctrl+Shift+K); depois **Run Form**.

Por linha de comando (Forms 14.1.2, Home `C:\Oracle\FR1412` -- o antigo
`C:\Oracle\Middleware` foi removido em 2026-09-04, era um Home legado
paralelo):

```powershell
# XML -> FMB (não precisa de banco; avisa que não validou os Record Groups).
# frmxml2f.bat só acha java/jars com ORACLE_HOME setado.
$env:ORACLE_HOME = "C:\Oracle\FR1412"
C:\Oracle\FR1412\forms\templates\scripts\frmxml2f.bat module.xml OVERWRITE=YES

# FMB -> FMX (precisa de banco). NLS_LANG explícito é obrigatório numa
# instalação cujo registro tem NLS_LANG malformado: sem isso o logon
# falha com ORA-12705 SILENCIOSO (exit 1, sem module.err). Nunca passe
# help=yes -- abre um diálogo e trava o batch.
# frmcmp.exe é executável GUI (PE subsystem 2): o PowerShell NÃO espera
# ele terminar quando chamado com `&` -- volta em ~6ms, $LASTEXITCODE
# vazio, e module.fmx/module.err só aparecem uns 20s depois. Use
# Start-Process -Wait (ou pipe). Não precisa de ORACLE_HOME nem de
# ORACLE_HOME\bin no PATH (testado).
$env:NLS_LANG  = "AMERICAN_AMERICA.WE8MSWIN1252"
$env:TNS_ADMIN = "C:\Oracle\FR1412\user_projects\domains\forms_domain\config\fmwconfig"
$p = Start-Process -FilePath "C:\Oracle\FR1412\bin\frmcmp.exe" `
       -ArgumentList "module=module.fmb", "userid=FORMSLANG/<senha>@FREEPDB1", `
                     "logon=yes", "batch=yes", "compile_all=yes", "window_state=minimize" `
       -WorkingDirectory (Get-Location) -NoNewWindow -Wait -PassThru
$p.ExitCode              # 0
Get-Content module.err   # 61 unidades, todas "No compilation errors."
```

### 3. Roteiro de teste manual (o que a demo mostra)

1. Abrir: título da janela ganha o usuário, toolbar mostra o relógio, o
   bloco já vem consultado (6 produtos, ordenado por nome). Uma linha em
   `TAB_FORM_ACESSO` foi gravada pelo PRE-FORM.
2. Navegar (Page Down): "Parafusadeira" aparece com o nome em vermelho
   (`VA_BLOQUEADO`, `TP_STATUS='BLOQUEADO'`). Botão Excluir desabilita em
   registro novo (WHEN-NEW-RECORD-INSTANCE).
3. Aba **Itens**: Furadeira totaliza `134,90`, Notebook `209,80`, Camiseta e
   Parafusadeira `0,00`; a coluna Total de cada linha é a fórmula.
4. Aba **Comercial**: fornecedor via LOV (F9 / duplo clique) -- só
   homologados aparecem; "Textil Delta" não. Datas/usuário de alteração
   são somente-leitura.
5. Aba **Auditoria**: histórico do produto; filtrar por `UPDATE` com a LOV
   estática + botão Filtrar.
6. Aba **Resumo**: 4 categorias com contagens e valor de estoque; duplo
   clique numa categoria reconsulta a tela principal filtrada.
7. Toolbar **Reajuste**: abre a janela modal, escolher categoria (LOV que
   reusa `RG_CATEGORIA`), informar 10, Aplicar -> alerta com a quantidade;
   a aba Auditoria ganha linhas "Preco alterado de X para Y".
8. **Novo** / **Duplicar** / **Salvar** (F10): defaults do WHEN-CREATE-RECORD;
   `PK_ID` vem da sequence no PRE-INSERT; `CD_BARRA` inválido é barrado
   pelo `F_VALIDA_EAN13` do banco; peso líquido > bruto é barrado pelo
   WHEN-VALIDATE-RECORD.
9. **Excluir**: diálogo inline (canvas stacked) -> Confirmar apaga os itens
   (PRE-DELETE) e o produto, alerta de sucesso.
10. **Exportar**: gera `produto_<id>.csv` em `P_DIR_EXPORT` (TEXT_IO).
    **Site** abre b2dev.tech, **Calculadora** chama `HOST`, **Ajuda** mostra
    usuário e nº de consultas da sessão (`:GLOBAL`).
11. Sair (Ctrl+Q / X) com alteração pendente: alerta de 3 botões.
12. **Relatório** só funciona com um Oracle Reports server configurado
    (`rep_server`); sem ele, mostra o status devolvido.

## Como validar (lado FormsLang)

Não existe ainda um teste automatizado pytest para esta fixture (é usada
via script ad hoc). Rotina manual:

```python
from formslang.parser import parse_xml
from formslang.apexlayout import build_layout
from formslang.apexlang import export_apexlang
from formslang.store import Store
from formslang.convert import build_tasks
from formslang.apeximport import run_import

module = parse_xml("tests/fixtures/showcase/module.xml")
layout = build_layout(module, 1)          # inspeciona a árvore de regiões

store = Store(":memory:")  # ou um caminho de arquivo
store.init_session(module.name, "tests/fixtures/showcase/module.xml")
store.add_tasks(build_tasks(module))
result = export_apexlang(store, module, "/tmp/out",
                          {"app_id": 101, "name": "DEMO_ALL_ELEMENTS", "alias": "demo-all-elements"})
run_import(result.zip_path, connect_string="localhost:1521/FREEPDB1",
           username="FORMSLANG", password="...", validate_only=True)   # apex validate
```

Estado atual: 22 regiões, 78 itens mapeados, 0 pulados, 2 LOVs estáticas
(`TP_UNIDADE`, `TP_STATUS`), `apex validate` "Validation successful."
Também vale conferir o XML contra o `forms.xsd` oficial (lxml
`XMLSchema.validate`) -- nenhum atributo aqui foi inventado; todos
existem no xsd do Forms 14c.

### Limitações conhecidas do mapeamento (de propósito, pra demo ser honesta)

- `MultiLine`/`WrapStyle` de `OBS_GERAL` não são lidos pelo parser -- vira
  `textField` no APEX; só `Bean Area` vira `textarea` (convenção
  documentada em `test_apexlang.py`).
- `WIN_REAJUSTE` (janela modal) vira uma região comum na mesma página, não
  uma página modal separada.
- `CalculateMode="Formula"` de `VL_TOTAL_LINHA` vira `Display Item` sem
  cálculo -- a fórmula fica registrada como dívida no assess.
- `Report`, `Editor`, `ModuleParameter` e os `RecordGroup`/`LOV` nomeados
  são contados pelo parser, mas o motor de layout não os consome (a LOV
  do APEX é gerada só a partir de `List Item`/`Radio Group`).

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
