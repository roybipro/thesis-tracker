# Thesis Command Center — black moon

> **Working title:** Multi-echelon split-delivery optimisation under WESM price data
> **Research question (one sentence):** *write it here - if you cannot say it in one sentence, that is your first task*
> **Supervisor:** — &nbsp; **Start:** — &nbsp; **Submission:** see `databases/settings.csv`

Data lives in the GitHub repo (`databases/*.csv`). This page is the reading layer.
Weekly: export Notion → replace the CSVs → `python3 scripts/thesis.py all` → commit.

---

## 1. Where everything lives

| Database | Use it for | Update it |
|---|---|---|
| papers | citation, methodology, limitations, research gap for every paper | each paper you finish |
| reading_queue | what to read next, with priority | weekly |
| gaps | the gaps your thesis claims: G-01, G-02… | monthly |
| experiments | every model run: version, solver, result, time | every run |
| writing_tasks | chapter to-dos with due dates | weekly |
| data_inventory | which data you have, which you still need | whenever data arrives |

Drag each imported database under this heading after importing.

---

## 2. Commands that do the work

| Command | Gives you |
|---|---|
| `python3 scripts/thesis.py next` | today's list: unfinished rows, high-priority reading, overdue and blocked items |
| `python3 scripts/thesis.py validate` | errors: blank cells on papers you marked Read, broken gap links, bad dates |
| `python3 scripts/thesis.py report` | `out/REPORT.md`: progress vs 40-paper target, gap coverage, countdown |
| `python3 scripts/thesis.py matrix` | `out/literature_matrix.md`: literature review grouped by gap |
| `python3 scripts/thesis.py bibtex` | `out/refs.bib` for LaTeX |

---

## 3. Thesis phases

### Phase 0 — Scoping
- [ ] Research question in one sentence
- [ ] Confirm WESM price + node demand data actually exists
- [ ] Supervisor agrees the scope is doable

### Phase 1 — Literature review
- [ ] 25-40 rows in `papers.csv`, no blank Methodology / Limitations / Research gap
- [ ] Exactly one gap marked Confirmed and Priority 1
- [ ] Every confirmed gap evidenced by at least one paper
- [ ] Chapter 2 draft, built from `out/literature_matrix.md`

### Phase 2 — Model
- [ ] Two-echelon network figure
- [ ] Decision variables, objective, constraints written
- [ ] Baseline model (no split delivery) solves
- [ ] Split-delivery version solves

### Phase 3 — Computation
- [ ] Instances sized up until runtime hurts
- [ ] Baseline vs your model compared on total cost
- [ ] Sensitivity: prices, capacity, demand
- [ ] Chapter 4 results table

### Phase 4 — Writing and defence
- [ ] Chapter 1 problem statement
- [ ] Chapter 3 formulation
- [ ] Chapter 5 conclusion, including the limitations of your own model
- [ ] References checked against `out/refs.bib`
- [ ] Slides

---

## 4. Weekly ritual (15 minutes, same day every week)

- **Read** — one row per finished paper in `papers.csv`. No blank cells.
- **Run** — log every experiment, including failed ones. Failed runs become your limitations section.
- **Write** — close one `writing_tasks` row, or write down in the decisions log why not.
- **Check** — `python3 scripts/thesis.py validate` must be clean before you call a week done.
- **Ask** — which row in `data_inventory.csv` is still "Not started"? That is next week's blocker.

---

## 5. Reading rules

Fill four cells before you stop reading a paper. Empty cell = paper not finished.

1. **Methodology** — what did they solve, with what tool?
2. **Limitations** — what did they assume away? Synthetic data? Deterministic demand? Small instances? No split delivery?
3. **Research gap** — what did *they* say needs future work, in their words?
4. **Relevance 1-5** — 5 = your direct baseline, 3 = supports your argument, 1 = background only.

Score 1-2: one summary line and move on. Do not write a full review for them.

---

## 6. Decisions log

| Date | Decision | Why | Revisit when |
|---|---|---|---|
| — | — | — | — |

---

## 7. Supervisor meetings

Copy this block before each meeting.

> **Date:**
> **Finished since last meeting:**
> **Where I am stuck:**
> **Question I need answered:**
> **Their instructions (their words, not mine):**
> **Deadline they gave:**
> **Run `next` and paste the list here:**
