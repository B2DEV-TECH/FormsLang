# Minicase fixture

`module.xml` -- o menor módulo Forms2XML que ainda demonstra o pipeline
inteiro. Um bloco, 8 itens, 6 triggers, nenhum program unit, 47 linhas de
PL/SQL. 100% sintético, sem dado de cliente (nomeado `module.xml` como o
resto de `fixtures/`, pra não cair na regra do `.gitignore` que barra
exports reais).

Ele existe porque o showcase **não serve de demo**. O showcase é uma
bancada de cobertura: 5 blocos, 78 itens, 55 triggers, ~500 linhas de
PL/SQL, 59 unidades de revisão, tier REWRITE. É a coisa certa pra
*testar* e a errada pra *mostrar* -- ninguém segura 5 blocos e 55
triggers na cabeça enquanto acompanha um argumento numa gravação ou lê um
artigo. Esta fixture é o contrário: cabe numa tela, roda ponta a ponta em
minutos, e mesmo assim cobre os seis elementos obrigatórios do caso
mínimo completo.

Comparação direta, ambos medidos por `formslang assess`:

| | showcase | minicase |
|---|---|---|
| Blocos / itens / triggers | 5 / 78 / 55 | **1 / 8 / 6** |
| Program units | 4 | 0 |
| Linhas de PL/SQL | ~500 | **47** |
| Unidades de revisão | 59 | **6** |
| Effort points | -- | 35 |
| Automation-ok | -- | 61,5% |
| Tier | REWRITE | **SIMPLE** |
| Vereditos | `AUTO=13 DROP=1 ASSISTED=38 MANUAL=2 UNKNOWN=1` | `AUTO=3 ASSISTED=3` |

## Os seis elementos obrigatórios

A lista é a de `docs/assessment/modernization-gap-analysis.md` §1 -- a
mesma pela qual o showcase foi medido. Cada elemento tem exatamente um
dono aqui, e nenhum objeto existe sem cobrir um elemento:

| Elemento obrigatório | Objeto Forms | Veredito / hint |
|---|---|---|
| Consultar registros existentes | `BK_PRODUTO.PRE-QUERY` -- `SET_BLOCK_PROPERTY` com `DEFAULT_WHERE` de ativos | ASSISTED |
| Criar / atualizar um registro | `BK_PRODUTO.PRE-INSERT` -- PK pela sequence + `DT_CADASTRO := SYSDATE` | ASSISTED |
| Validação de campo obrigatório | itens `PK_ID`, `DS_NOME`, `VL_PRECO` (`Required="true"`) | vira `valueRequired: true` + `template: @/required` |
| Uma regra de negócio de verdade | `BK_PRODUTO.WHEN-VALIDATE-RECORD` -- peso líquido não pode passar do bruto | AUTO / **"APEX row validation"** |
| Um caminho de falha com erro compreensível | `BK_PRODUTO.CD_BARRA.WHEN-VALIDATE-ITEM` -- dígito verificador do EAN-13 | AUTO / **"APEX item validation"** |
| Evidência ligando a regra ao substituto | tabela `decision` + `approved.sql` + `apexlang-manifest.json.approved_components` | revisor, comentário, timestamp, trigger de origem, componente de destino, `message_source` |

O sexto trigger, `BK_PRODUTO.VL_PRECO.WHEN-VALIDATE-ITEM` (preço > 0),
não cobre elemento novo: ele existe pra exercitar o fallback de mensagem
do A7 -- veja "Proveniência da mensagem" abaixo.

## O que o módulo contém

- **`MINI_PRODUTO`** -- um `FormModule` com `MenuModule="DEFAULT&SMARTBAR"`
  (o Forms Builder carimba esse default ao criar o FMB; declarar aqui é o
  que faz o round-trip fechar em zero diffs).
- **1 trigger de formulário**: WHEN-NEW-FORM-INSTANCE (`GO_BLOCK` +
  `EXECUTE_QUERY`), pra tela já abrir consultada.
- **`BK_PRODUTO`** sobre `TAB_MINI_PRODUTO`, `RecordsDisplayCount="1"`
  (single-record), `OrderByClause="DS_NOME"`, com 3 triggers de bloco
  (PRE-QUERY, PRE-INSERT, WHEN-VALIDATE-RECORD) e 2 de item
  (WHEN-VALIDATE-ITEM em `CD_BARRA` e em `VL_PRECO`).
- **8 itens** numa grade de 2 colunas × 4 linhas (Points): `PK_ID`
  (Required + PrimaryKey + `UpdateAllowed="false"`), `DS_NOME`
  (Required), `CD_BARRA` (`MaximumLength="13"`), `VL_PRECO` (Required),
  `VL_PESO_LIQ`, `VL_PESO_BRUTO`, `FL_ATIVO` (Check Box, `CheckedValue`
  Y / `UncheckedValue` N), `DT_CADASTRO` (Date, `UpdateAllowed="false"`).
- **1 `Canvas`** (`CV_MAIN`, Content) e **1 `Window`** (`WIN_MAIN`).

Nada além disso: sem toolbar, sem abas, sem LOV, sem alerta, sem
master-detail, sem program unit. Tudo isso já está coberto no showcase.

### Convenções de escrita do XML

Valem as mesmas do showcase, e estão repetidas no cabeçalho do
`module.xml` porque errar qualquer uma delas quebra em silêncio:

- Coordenadas em **Points** (`CoordinateSystem="Point"`).
- Quebra de linha dentro de `TriggerText` é `&amp;#10;` (duplo escape).
- **Nunca** `&amp;#9;` (tab): o Convert não decodifica, sobra um `&#9;`
  literal e o parser de PL/SQL morre no `&`. Indente com espaços.
- `<` e `>` dentro de texto vão com escape **simples** (`&lt;`, `&gt;`);
  o duplo (`&amp;lt;`) fica literal e também quebra o PL/SQL.

## Duas decisões deliberadas

**1. EAN-13 inline, não via package.** O showcase chama
`PKG_PRODUTO.F_VALIDA_EAN13`, que mora no banco. Aqui o algoritmo fica
dentro do trigger, de propósito, por dois motivos: a validation exportada
sai **autocontida** (importa e roda sem instalar package nenhum além da
tabela), e na gravação o revisor vê a regra de verdade na tela em vez de
uma chamada opaca. O custo é que o trigger tem 21 linhas em vez de 1 --
aceitável num módulo que tem 47 no total.

**2. Prompts e mensagens em PT-BR**, como o showcase. É um form legado
brasileiro e toda a evidência já gravada (`docs/quality-acceptance.md`)
está assim. Num módulo de 8 itens, trocar pra inglês depois é uma passada
de `sed` -- que é exatamente a vantagem de ser pequeno.

## Rodando de verdade no Forms Builder

### 1. Schema (`mini_schema.sql`)

Dois objetos, e só: `TAB_MINI_PRODUTO` e `TAB_MINI_PRODUTO_SEQ`, no
schema `FORMSLANG`. Idempotente (dropa e recria, ignorando ORA-00942 e
ORA-02289). As CHECK constraints **não** repetem as regras dos triggers
-- só o domínio de `FL_ATIVO` -- pra que na demo não haja dúvida de onde
nasceu a rejeição. Semeia 5 produtos com EAN-13 válidos: 4 ativos e 1
inativo, que existe pro `DEFAULT_WHERE` do PRE-QUERY ter o que filtrar.

```powershell
# SQLcl thin, sem tnsnames (no Git Bash exporte MSYS_NO_PATHCONV=1 antes)
sql -S -thin FORMSLANG/<senha>@localhost:1521/FREEPDB1 `
    @tests/fixtures/minicase/mini_schema.sql
```

### 2. Converter e compilar

```powershell
$env:ORACLE_HOME = "C:\Oracle\FR1412"
# XML -> FMB (não precisa de banco)
& "$env:ORACLE_HOME\bin\frmxml2f.bat" module.xml
# FMB -> FMX (precisa de banco; frmcmp.exe é GUI, use Start-Process -Wait,
# e NLS_LANG explícito, senão o logon falha com ORA-12705 silencioso)
```

Os detalhes e as armadilhas dessas duas chamadas estão documentados uma
vez só, no README do showcase -- não vale repetir aqui.

### 3. Round-trip verificado

`module.fmb` (49.152 bytes) foi gerado pelo Forms 14.1.2 real a partir
deste `module.xml`, e reconvertido de volta pra XML com `Forms2XML`. O
resultado, comparado ao original:

```
ROUND-TRIP DIFFS (ignorando source_path): 0
convert log warnings: none
PL/SQL fingerprints: 6/6 idênticos
```

**Zero diffs** -- melhor que o showcase, que ainda carrega o delta
`records_distance 3 -> 20`. Isso significa que o que está commitado aqui
é exatamente o que o Forms devolve, não uma aproximação escrita à mão.

## A cadeia inteira, cronometrada

O critério de aceitação do card A5 pede a cadeia rodando em menos de
cinco minutos à mão. Medido:

| Etapa | Resultado | Tempo |
|---|---|---|
| `parse` | 6 unidades de revisão (< 12, o teto do critério) | < 0,2 s |
| `review` | 3 regras AUTO aprovadas à mão | manual |
| `export` | `minicase.apex.zip`, 27.795 bytes | incluído acima |
| `apex validate --offline` | `Validation successful.` / `Result : OK` | 13,7 s |
| `import` + `render` | app descartável num workspace APEX real | pendente |

Parse → export levam **0,2 s**; a validação offline (SQLcl 26.2.2.0,
APEXlang 26.1.0+3102, sem banco e sem credencial) leva **13,7 s**. A
metade que falta -- import e render -- é a mesma rotina já provada no
showcase em `docs/quality-acceptance.md`.

### Proveniência da mensagem (card A7)

As três regras aprovadas foram escritas de propósito em duas formas
diferentes, pra provar os dois caminhos do A7 dentro de um módulo só:

| Validation | Como o código aprovado rejeita | `message_source` no manifest |
|---|---|---|
| WHEN-VALIDATE-RECORD | `raise_application_error` com a frase do peso | `approved code` |
| CD_BARRA.WHEN-VALIDATE-ITEM | `raise_application_error` com a frase do EAN-13 | `approved code` |
| VL_PRECO.WHEN-VALIDATE-ITEM | `raise value_error;` -- **levanta mudo, de propósito** | `Forms trigger` |

O terceiro é o teste do fallback: o código aprovado não carrega frase
nenhuma, então a única origem possível do `errorMessage` é o `MESSAGE()`
do trigger do Forms. É exatamente o que o export emitiu -- "Preco deve
ser maior que zero." -- e o comentário da própria validation diz de onde
veio ("the one the Forms trigger already showed").

As três saem como `type: plsqlError` com `plsqlCodeRaisingError` -- a
validation passa quando o código roda sem levantar, que é como o trigger
do Forms rejeitava. A de registro sai com
`displayLocation: inlineInNotification` (o Forms validava o registro
inteiro, não um campo); as duas de item saem com
`inlineWithFieldAndInNotification` + `associatedItem`, e aparecem ao lado
do campo.

## Roteiro de demonstração

O que a gravação mostra, em ordem:

1. Abrir o form no Forms Builder: 4 produtos consultados (o inativo não
   aparece -- é o PRE-QUERY trabalhando), ordenados por nome.
2. Digitar um `CD_BARRA` com dígito verificador errado: o
   WHEN-VALIDATE-ITEM barra com "Codigo de barras invalido: informe um
   EAN-13."
3. Pôr peso líquido acima do bruto e salvar: o WHEN-VALIDATE-RECORD barra
   com "Peso liquido nao pode ser maior que o peso bruto."
4. `formslang assess` no mesmo XML: 6 unidades, tier SIMPLE, 3 AUTO.
5. Revisar e aprovar as 3 AUTO, exportar, `apex validate --offline`.
6. Importar num workspace APEX, abrir a página e repetir os passos 2 e 3
   **no navegador**: as mesmas frases, agora inline ao lado do campo.

O ponto da demo é o passo 6 fechar com as mesmas frases do passo 2-3 --
a regra atravessou o pipeline sem ninguém reescrever a mensagem.

## O que o export gera pros 8 itens

Lido do `p00001-mini-produto.apx` de verdade, não do que a documentação
antiga dizia:

| Item Forms | Tipo Forms | `type:` no APEX | Extras carregados |
|---|---|---|---|
| `PK_ID` | Text Item / Number | `numberField` | `valueRequired: true`, `template: @/required` |
| `DS_NOME` | Text Item / Char | `textField` | `valueRequired: true` |
| `CD_BARRA` | Text Item / Char | `textField` | -- |
| `VL_PRECO` | Text Item / Number | `numberField` | `valueRequired: true` |
| `VL_PESO_LIQ` | Text Item / Number | `numberField` | -- |
| `VL_PESO_BRUTO` | Text Item / Number | `numberField` | -- |
| `FL_ATIVO` | Check Box | `checkbox` | `default staticValue: "Y"` (do `CheckedValue`) |
| `DT_CADASTRO` | Text Item / Date | `datePicker` | `formatMask: "DD/MM/YYYY"` |

Os `Tooltip`/`Hint` do Forms viram `helpText`, e o `Prompt` vira `label`
com o `alignment` correspondente ao lado do prompt no canvas.

> Nota: o README do showcase ainda diz que `Date`/`Number` saem como
> `textField` "de propósito". Isso **envelheceu** -- o mapeamento hoje
> emite `numberField`, `datePicker` e `checkbox`, e as três keywords
> passam no `apex validate` offline (que é justamente quem reprova
> keyword desconhecida). O que ainda não foi provado é o render dessas
> três no navegador.

## Limitações conhecidas

- **O bloco continua não-bindado.** A página exportada valida, mas não
  busca nem grava sozinha: não há `source` nem `automaticRowProcessing`
  no `.apx`. Isso é o card A3, parado numa decisão de projeto sobre a
  origem da PK. Vale igual pro showcase.
- **`UpdateAllowed="false"` não atravessa.** `PK_ID` e `DT_CADASTRO` são
  não-editáveis no Forms; a página exportada não tem nenhuma ocorrência
  de `readOnly` (conferido: zero). Os dois saem editáveis no APEX.
- **O check box sai sem lista de valores.** `FL_ATIVO` vira
  `type: checkbox` e herda o default `"Y"`, mas nenhum LOV é anexado ao
  item -- o par `CheckedValue`/`UncheckedValue` não vira as duas opções.
  Passa no `apex validate`; se aparece utilizável na tela, só o render
  prova.
- **Nem o `.fmb` nem o `.fmx` são versionados.** `.gitignore:16` barra
  `*.fmb`, e o showcase segue a mesma regra: o que está no git são o
  `module.xml`, o `.sql` e este README. Os binários são artefatos locais
  -- o `module.fmb` existe na sua cópia de trabalho só pra reproduzir o
  round-trip; a evidência versionada é o resultado registrado acima, não
  o arquivo. Pra recriá-lo, rode o `frmxml2f.bat` da seção 2.
