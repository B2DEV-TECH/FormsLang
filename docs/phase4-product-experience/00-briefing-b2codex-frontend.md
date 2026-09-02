---
DE: b2dev_dev (Claude Code, techlead)
PARA: b2codex (Codex CLI, subagente pareado)
ASSUNTO: Fase 4 do FormsLang — sua parte é FRONTEND. Escreva a entrega em
`01-frontend-analysis.md` nesta mesma pasta.
---

# Contexto

FormsLang é a ferramenta de conversão Oracle Forms → Oracle APEX do Geraldo
(repo: `C:\Users\geefa\Documents\formslang` — seu cwd padrão é B2DEVTECH,
então use caminhos absolutos). Está em v0.1.4, com pipeline de conversão
funcionando, auth multi-usuário (RBAC+MFA) e scanner de compliance já
entregues.

O Geraldo pediu a próxima fase: **"Phase 4 — Product Experience, Conversion
Quality & Performance"**. **CUIDADO**: existe uma OUTRA "Phase 4" em
`docs/auth-multitenancy-design.md` (reverse-proxy/team-server-mode) — essa é
diferente e está EXPLICITAMENTE fora de escopo agora ("não avance pro antigo
Phase 4/team mode"). Não confunda as duas.

Esta é uma **rodada de análise e design, não de implementação**. Estamos
dividindo o trabalho: eu (b2dev_dev) cuido do lado backend (diagnóstico do
pipeline, state machine, 7 níveis de sucesso, matriz de cobertura, golden
fixtures, baseline de performance, cache/incremental). **Você cuida do lado
frontend/produto**: auditoria de UI/UX, jornada do usuário, arquitetura de
informação, wireframes, experiência de revisão, UI de auth, acessibilidade.

No final eu junto as duas partes num documento único que vai pro Geraldo
aprovar antes de qualquer código ser escrito.

# GATES (obrigatório respeitar)

- **NÃO escreva ou altere código** (`formslang/*.py`, `desktop/*`, testes).
  Só documento markdown.
- Não altere snapshots de teste.
- Não use dado de cliente real (o repo já é 100% sintético — mantenha assim).
- Não faça commit nem push.
- Não marque nada do roadmap como concluído.
- Não inicie nem projete team mode/server mode (isso é outra fase, já feita
  noutro design doc).
- Preserve os arquivos existentes do repo — você só vai LER código, não
  editar.

# Evidência já levantada (não precisa re-explorar do zero)

Já rodei uma auditoria read-only completa da UI atual. Resumo (se quiser
confirmar algo específico, leia o arquivo:linha citado — não repita a
exploração inteira):

**Telas atuais:**
- `desktop/ui-shell/index.html` — só splash de boot do Tauri, sem lógica.
- `/` (SPA servida por `INDEX_HTML` em `formslang/ui.py`) — view única:
  sidebar de filtros + painel central de unidade selecionada + modais
  (Project, Exports, Settings, terminal). Sem roteamento client-side.
- `formslang/authui.py` — overlay de login/MFA/enrollment/recovery já
  completo e bom. Falta: troca de organização pós-login (endpoint
  `/api/auth/switch-org` existe no backend, `workbench.py:1035`, mas `ui.py`
  nunca o referencia).
- Workbench principal (`ui.py`): review unidade-a-unidade é o ponto MAIS
  FORTE do produto hoje — código Forms lado a lado com proposta APEX
  editável, verdict AUTO/ASSISTED/MANUAL/DROP com tooltip, risco com score e
  fatores, behaviour PRESERVED/CHANGED/UNCERTAIN, open questions, histórico
  de decisão. Veja screenshots reais em `assets/screenshots/` (pode abrir
  como imagem): `unit-review-risk-panel.png`, `conversion-progress.png`,
  `project-view.png`.
- Modal "Project" já é quase um mini-dashboard: score "Migration readiness"
  0-100 auditável, cards de conversion mode/risk/behaviour.
- `dashboard.py` já calcula: highest-risk-first, unsupported table, dep
  card, blockers — mas tudo embutido no modal, não como tela própria.
- **Achado crítico**: existe API pronta pra multi-projeto/multi-org
  (`/api/projects`, `/api/projects/adopt`, `workbench.py:890-1163`), mas
  **zero UI usa isso** (`grep "api/projects" formslang/ui.py` = 0
  ocorrências). Hoje só dá pra abrir um módulo via navegador de pastas
  local (`/api/browse` + `/api/upload`), sem noção de organização/projeto
  persistente. Isto é provavelmente o gap mais crítico e mais barato de
  fechar.
- Sem progresso percentual global, sem ETA, sem botão de cancelar
  (`grep "cancel" formslang/workbench.py` = nada). `job_state()`
  (`workbench.py:655-659`) só expõe running/current/queue.
- Sem telas de: pre-flight report, validação estrutural pós-export,
  validação SQLcl, import real no APEX — o produto para visualmente em
  "arquivo .apx gerado", que hoje é fácil de confundir com "conversão
  pronta" (achado do lado backend: dá pra gerar um `.apex.zip` de 24
  arquivos com ZERO propostas de IA e ZERO decisões humanas registradas —
  isso PRECISA ficar impossível de confundir na UI).
- Máquina de estados do projeto: **não existe** — o estado é reconstruído a
  cada request a partir de contagens (`workbench.py:235 state()`), não é um
  enum persistido.

**Mapa dos 17 passos da jornada** (EXISTE / PARCIAL / NÃO EXISTE):
1 Login/MFA=EXISTE · 2 Selecionar org=PARCIAL (só no login) · 3 Criar/abrir
projeto=PARCIAL (API pronta, zero UI) · 4 Importar=EXISTE · 5 Pre-flight=NÃO
EXISTE · 6 Inventário=PARCIAL · 7 Compatibilidade APEX=EXISTE · 8 Plano de
conversão=PARCIAL (implícito na lista) · 9 Revisão por unidade=EXISTE (ponto
forte) · 10 Approve/reject/edit=EXISTE · 11 Gerar .apx=EXISTE · 12 Validar
estrutura=NÃO EXISTE · 13 Validar SQLcl=NÃO EXISTE · 14 Importar no
APEX=NÃO EXISTE · 15 Checklist funcional=PARCIAL (manual, sem execução real)
· 16 Corrigir/regenerar incremental=PARCIAL · 17 Exportar relatório=EXISTE.

# Sua entrega (escreva em `01-frontend-analysis.md`, nesta pasta, em
português brasileiro, markdown, SEM código — wireframes em ASCII/texto
estruturado, não HTML/JSX)

Baseie-se na evidência acima; só releia o código-fonte se precisar confirmar
um detalhe específico pra um wireframe (ex: quais campos exatos aparecem no
painel de review hoje). Cite arquivo:linha quando fizer uma afirmação nova
sobre o código atual. Nunca invente comportamento que não verificou — se não
tiver certeza, escreva "não verificado" em vez de assumir.

### 1. Auditoria da UI/UX atual com problemas priorizados
Consolide os achados acima + qualquer coisa que você verificar por conta
própria, priorizados por impacto (crítico → cosmético).

### 2. Jornada atual vs. jornada proposta
A jornada ideal completa (desenhe cada passo, o que a tela mostra, o que o
usuário faz, pra onde vai depois):

1. Login/MFA quando habilitado.
2. Selecionar organização.
3. Criar ou abrir projeto.
4. Importar FMB/XML/spec/template.
5. Executar pre-flight.
6. Visualizar inventário do Form.
7. Analisar compatibilidade com APEX.
8. Visualizar plano de conversão.
9. Revisar decisões por unidade.
10. Aprovar, rejeitar ou editar propostas.
11. Gerar APEXlang/.apx.
12. Validar estrutura.
13. Validar com SQLcl quando disponível.
14. Importar no Oracle APEX quando configurado.
15. Executar checklist funcional.
16. Corrigir e regenerar incrementalmente.
17. Exportar relatório e artefatos.

Em cada etapa proposta, a UI precisa sempre conseguir responder: O que está
acontecendo? Quanto já foi concluído? O que foi convertido? O que não foi
convertido? Por que essa decisão foi tomada? O que exige ação humana? O
artefato foi apenas gerado ou realmente validado? Posso retomar sem começar
de novo?

### 3. Arquitetura de informação
Proponha navegação simples com estas seções (não vire cada detalhe técnico
numa tela separada):
Dashboard, Organizations, Projects, Source Inventory, Conversion Plan,
Review Queue, APEX Preview, Validation, Exports, Audit & Settings.

A tela do projeto funciona como **cockpit**: status geral, etapa atual,
progresso, última execução, quantidade de objetos, contagem AUTO/ASSISTED/
MANUAL/DROP, warnings, blockers, validações, próximos passos, ação principal
claramente destacada.

### 4. Wireframes (ASCII/texto estruturado) das telas principais
No mínimo: Dashboard, Organizations (seletor), Projects (lista + criar/
abrir), Source Inventory, Conversion Plan, Review Queue (evolução da tela
atual — preserve o que já funciona bem, veja screenshots), APEX Preview,
Validation, Exports, Audit & Settings, e o Project Cockpit.

### 5. Review Experience (extensão da tela que já é o ponto forte)
Desenhe a evolução da tela de review, mantendo: código Forms original,
interpretação intermediária, proposta APEX, regra aplicada, evidência,
confiança, limitações, open questions, validações, decisão humana, histórico
da decisão.

Adicione os filtros que faltam hoje: blockers, baixa confiança, manual,
unsupported, warnings, por trigger, por program unit, por block/item, por
página APEX, aprovados/rejeitados/pendentes (hoje só existe busca livre por
texto + filtro de risco/conversão/decisão — falta granularidade por
trigger-type/program-unit/block-item/página).

Ações: Approve, Reject, Edit proposal, Mark as manual, Ask for reanalysis,
Add note, Bulk approve **somente** para propostas deterministicamente
seguras. **Nunca "Approve all" indiscriminado.**

### 6. Vocabulário fixo que EU vou implementar no backend (você só desenha
como aparece na tela, não invente nomes novos nem regras de transição —
me avise se algum não fizer sentido pra UI e eu ajusto)

**Estados do projeto** (state machine): CREATED, SOURCE_READY,
PREFLIGHT_FAILED, READY_FOR_ANALYSIS, ANALYZING, ANALYSIS_COMPLETE,
REVIEW_REQUIRED, READY_TO_GENERATE, GENERATING, GENERATED,
VALIDATION_FAILED, VALIDATED, IMPORT_READY, IMPORTED,
FUNCTIONAL_TEST_REQUIRED, COMPLETED.

**7 níveis de sucesso** (nunca mostrar "Success" genérico sem dizer o
nível): 0 Parsed · 1 Classified · 2 Planned · 3 Generated · 4 Structurally
validated · 5 SQLcl validated · 6 APEX imported · 7 Functionally verified.

Proponha como cada estado/nível aparece visualmente (badge, cor, barra de
progresso, etc.) — isso é seu escopo. Os nomes/transições/regras são meu
escopo.

### 7. Modelo visual de jobs/progresso/cancelamento
Toda operação longa precisa parecer (mesmo que a mecânica de
idempotência/checkpoint seja backend, meu escopo): progresso real por
etapas, contagem, cancelável com segurança, resistente a refresh, incapaz de
parecer sucesso quando é parcial. Desenhe como isso aparece (barra global,
ETA, botão cancelar, o que acontece na tela depois de cancelar/dar refresh).

### 8. Gerenciamento (telas)
Listar projetos, pesquisar, filtrar, arquivar, duplicar, exportar, importar
backup, ver versão do pipeline, saber quando análise ficou desatualizada
(já existe o conceito de `stale` no backend — `analysis.py:143-145` — você
só precisa desenhar como isso aparece), retomar execução, comparar
execuções, desfazer decisão humana quando possível, ver custo/uso do modelo
sem expor prompts, limpar cache de forma controlada, configurar provider sem
revelar chave.

### 9. UI de autenticação (fechar gaps)
Login, enrollment MFA, recovery codes (já existem, só documente/valide) +
os que faltam: troca de organização pelo nome pós-login, perfil, sessões
ativas, revogação de sessões, alteração de senha, regeneração de recovery
codes, desabilitação de MFA conforme política. Nunca mostrar IDs técnicos de
organização como experiência final.

### 10. Acessibilidade e responsividade
Navegação por teclado (a tela de review já tem atalhos A/W/R/P — documente e
estenda), foco visível, labels reais, mensagens não dependentes só de cor,
contraste adequado, loading/empty/error states, viewport pequeno utilizável,
tabelas grandes navegáveis, prefers-reduced-motion, texto claro pro usuário
Oracle sem jargão interno do FormsLang.

### 11. Performance budgets de UX (comportamento, não número)
Feedback perceptível imediato; operação >500ms mostra estado de trabalho;
operação longa tem progresso por etapas e contagem real; nenhuma tela
congelada; navegação/filtros não devem reexecutar análise; refresh não perde
progresso; cancelamento não corrompe projeto; erros indicam recuperação
possível. (Números/budgets concretos por tamanho de corpus são meu escopo,
depois do baseline de performance.)

# Como sinalizar que terminou

Quando terminar, escreva `STATUS: DONE` na primeira linha de
`01-frontend-analysis.md` (eu vou checar o arquivo diretamente, não preciso
que você me mande mensagem de volta — mas pode mandar um aviso curto por
`shaun_send.py --to b2dev_dev "..."` se preferir).

Se travar em alguma dúvida que só o Geraldo pode responder, registre como
"Open question" no final do documento em vez de adivinhar.
