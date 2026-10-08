# thesis-tracker

Literature-review and thesis-progress tracker for **black moon** — a multi-echelon
split-delivery optimisation model driven by WESM price data.

Plain CSV files are the database. Notion is the view. A small Python tool turns the CSVs into
the things a thesis eats: a literature matrix, a BibTeX file, a progress report, and a
"what do I do today" list.

```
databases/            the master data (edit these, or edit Notion and export back)
  papers.csv          one row per paper: citation, methodology, limitations, research gap
  gaps.csv            your research gaps, numbered G-01... - the thesis claim
  reading_queue.csv   what to read next
  experiments.csv     every model run, including failed ones
  writing_tasks.csv   chapter to-dos with dates
  data_inventory.csv  which data you have vs still waiting for
  settings.csv        targets: paper count, weekly reading, submission date
scripts/thesis.py     validate / report / bibtex / matrix / next / add
notion/               page + import instructions for the Notion side
out/                  generated: REPORT.md, refs.bib, literature_matrix.md
.github/workflows/    CI that validates every push
```

No dependencies. Python 3.8+ standard library only.

## Commands

```bash
python3 scripts/thesis.py next        # what to do today
python3 scripts/thesis.py validate    # data integrity; exits 1 on errors
python3 scripts/thesis.py report      # out/REPORT.md  - progress vs targets
python3 scripts/thesis.py bibtex      # out/refs.bib   - for LaTeX
python3 scripts/thesis.py matrix      # out/literature_matrix.md - grouped by gap
python3 scripts/thesis.py all         # validate + all three outputs

python3 scripts/thesis.py add "Paper title" --authors "Crevier, F. and Laporte, G." \
  --year 2007 --venue "EJOR" --linked-gap G-01 --relevance 4 --status Read \
  --methodology "..." --limitations "..." --gap "their stated future work"
```

## What `validate` checks

- missing columns, rows with the wrong number of fields, duplicate paper or gap IDs
- papers linked to a gap that does not exist in `gaps.csv`
- **a paper marked Read but with Methodology, Limitations or Research gap still blank**
- relevance outside 1-5, years that are not 4 digits, dates that are not `YYYY-MM-DD`
- status values outside the agreed vocabulary
- writing tasks blocked on a dataset (`D-01`) or run (`R-001`) that does not exist
- confirmed gaps that no logged paper evidences

The point is the third bullet: an unread paper and a half-read paper look identical in memory.
They do not look identical here.

## Weekly loop

1. Read papers → one row each in `papers.csv` (or Notion, then export back).
2. `python3 scripts/thesis.py all` → commit, CI validates.
3. `out/REPORT.md` tells you: papers vs target, which gaps have no evidence, what is overdue,
   what is blocked, and which data is still missing.
4. Before the supervisor meeting: `python3 scripts/thesis.py next`.

## The reading rule

Fill four cells before you stop reading a paper:

| Cell | Question it answers |
|---|---|
| Methodology | what exactly did they solve, with what tool? |
| Limitations | what did they assume away - synthetic data, deterministic demand, small instances? |
| Research gap | what did *they* say needs future work, in their words? |
| Relevance 1-5 | 5 = your direct baseline, 1 = background only |

Your whole literature review is then generated from those four columns:
`python3 scripts/thesis.py matrix`.

## Set your own targets

`databases/settings.csv` holds `target_papers`, `weekly_reading_target`,
`min_relevance_to_cite` and `submission_date`. The report counts down from them.

## Notion

See `notion/Import guide.md`. Short version: import the CSVs, set the property types, make a
Board view grouped by Status. Keep `Linked gap ID` as text - CSV import cannot create Notion
relations, and the scripts use those IDs to cross-check the tables.

## Seed rows

Two real reference papers ship as examples (Pirkwieser & Raidl 2006, Crevier et al. 2007) plus
placeholder rows marked `(edit me` / `(placeholder`. Edit or delete them; they are structure,
not your bibliography.
