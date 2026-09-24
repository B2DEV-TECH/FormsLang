# Evaluation protocol — five professionals, three-step journey

Status of the criterion: **PENDING.** No session has taken place. The
criterion stays pending until the sessions are run and recorded in
[`sessions.csv`](sessions.csv). It is never reported as met, partially met or
"expected to pass" before that. [`criteria.csv`](criteria.csv) holds its
status.

Source: spec §5.4 and the product criterion in §11. Sessions are organised by
the project owner. This document fixes how they run, so that the result can
be compared and published with its limits.

## 1. What is being tested

The explorer's language and orientation: can a professional who knows Oracle,
with no training, (1) choose a screen, (2) open a relation, (3) understand its
evidence and come back, and then recognise a target the analysis could not
resolve? The sessions also test that the explorer does not persuade anyone
that a static graph proves execution.

They do not test performance, accessibility conformance or analysis
correctness. Those have their own gates.

## 2. Acceptance criterion (internal, not a customer claim)

| Id | Criterion | Target |
|---|---|---|
| C1 | Participants who complete **each** task (T1–T4) | ≥ 4 of 5, per task |
| C2 | Median time to the first relation with evidence open (T2) | ≤ 90 s |
| C3 | Participants who leave believing the graph proves execution | 0 |

All three must hold on the **same build**. C1 is judged per task: 4/5 on T1,
T2 and T3 with 3/5 on T4 fails C1.

## 3. Participants

- **Five** professionals minimum, recorded as `P1`…`P5` (more are allowed;
  the criterion then applies to all of them).
- Eligibility: they work with Oracle (PL/SQL, Forms, APEX or EBS), and they
  have **not** implemented, designed or reviewed this explorer. Record years of
  Oracle experience and whether they have used Oracle Forms.
- No names, e-mails or employers in the spreadsheet or in any published
  result. Keep the key between pseudonym and person outside the repository.
- Oral consent before starting: synthetic project, no customer data, notes
  taken, screen recording only if they agree (`recording` column).

## 4. Setup

- **Build.** An installed FormsLang build with the explorer (phase 4 or later).
  Record the exact version, the commit and the installer type (EXE or MSI). If
  the UI changes after a session in a way that touches a task, the sessions for
  that task are repeated on the new build.
- **Project.** The modernization lab, created from
  `examples/modernization-lab/forms/xml` and
  `examples/modernization-lab/database` **without `seed/`**, and analysed
  before the participant sits down. Record the `analysis_revision`. Use the
  same project for all five.
- **Starting screen.** The project Overview, at 1440 or 1920 px wide, with no
  prior search, selection or panel open. Clear the browser state between
  participants.
- **Nothing shown beforehand.** No tour, demo, slides or explanation of the
  graph. If asked "what is this?", answer: "Faz parte do que queremos
  observar; como você interpretaria?"

## 5. Running a session (about 25 minutes)

1. Consent and eligibility questions (2 min).
2. Ask the participant to think aloud. Read each task **verbatim** from
   [`tasks.md`](tasks.md). The task wording avoids the UI's own words
   ("relação", "evidência", "Ver por quê", "não resolvido"), so the task does
   not point to the button.
3. Start the stopwatch when you finish reading the task. Stop it at the end
   state defined for that task (§6), or at **5 minutes**, which counts as not
   completed.
4. Do not help. If the participant is stuck for 60 s, you may read the task
   again, once. Any other help — pointing, naming a control, answering "is it
   this one?" — makes the task **assisted**, and an assisted task counts as
   not completed.
5. After T4, ask the exit questions (§7) in order, before any debrief.
6. Debrief. Now you may explain. Record difficulties in `notes`.

## 6. Tasks and their end states

| Task | Asked (see tasks.md) | Completed when | Time recorded |
|---|---|---|---|
| T1 | Find the approvals screen. | The `APPROVALS` Form is the explorer's focus. | `time_s` |
| T2 | Find where the approvals screen changes order data, and show what supports it. | The evidence of a `BT_APPROVE` or `BT_REJECT` → `LOM_ORDERS` relation is open. The participant then says in their own words that it comes from the button's code (an UPDATE). | `time_s`; also `first_evidence_s` = when **any** relation's evidence first opens |
| T3 | Go back to the approvals screen as you left it. | `APPROVALS` is the focus again, reached with Voltar/breadcrumb, with no new search. | `time_s` |
| T4 | Find something this screen uses that the analysis could not locate, and say what is missing. | The participant opens `OM_SHARED.SHOW_MESSAGE` (or another unresolved target) and says the package's source was not supplied / not found — **not** that it does not exist. | `time_s` |

C2 uses `first_evidence_s` from T2: the time from the end of reading T2 to the
first evidence panel the participant opens. The median is over all
participants. A participant who opens no evidence within 5 min enters the
median as 300 s, so failures are not dropped.

## 7. Exit questions (C3)

Ask in this order and write down the answer verbatim:

1. "Pelo que você viu, quando alguém clica em Aprovar, o sistema **sempre**
   atualiza LOM_ORDERS?" — options read aloud: *sim* / *não* / *não dá para
   saber só por isto*.
2. "O que esta tela mostra: o que o sistema **executa**, ou o que está
   **escrito no código-fonte**?"
3. "Houve algo que você achou que existia e o sistema disse que não
   encontrou?"

`believes_graph_proves_execution = yes` if the answer to Q1 is *sim* or Q2 is
"executa", unless the participant corrects it without prompting before the
debrief. The moderator records the rule applied in `notes`.

## 8. Recording and publishing

- One row per participant per task in `sessions.csv`, plus one `EXIT` row per
  participant. Every result column starts as `PENDING`. Replace it only with
  what was observed.
- After the five sessions, fill `criteria.csv`: the measured value, `MET` or
  `NOT_MET`, and the build. A criterion with any missing session stays
  `PENDING`.
- Difficulties are fixed before the release. The fixed build is evaluated
  again for the affected tasks.
- The published result states its limits: five participants, one synthetic
  project, one build, a moderated session. It is an internal acceptance
  criterion, not a claim about customers or production estates.

## 9. Optional round 0 (does not count toward the criterion)

Before any UI exists, the same tasks can be walked on paper using the frames in
[`journey-three-steps.md`](../journey-three-steps.md). The participant points,
and the moderator turns the page. Round 0 finds wording problems early. It
produces no times and never changes the status of C1–C3.
