# Importing these databases into Notion

The CSVs in `databases/` are the master copy. Notion is a viewing layer on top.

## Import

1. Notion → **Import** → **CSV & Excel**, or drag each file onto a page:

| File | Becomes |
|---|---|
| `papers.csv` | Papers Read - your main table |
| `reading_queue.csv` | To Read Queue |
| `gaps.csv` | Research Gap Map |
| `experiments.csv` | Experiments Log |
| `writing_tasks.csv` | Writing Tasks |
| `data_inventory.csv` | Data Inventory |

2. Import `Thesis Command Center.md` as a **Markdown** file for the main page.
3. Delete the rows that start with `(placeholder` or `(edit me`.

## Set the property types

CSV import makes every column plain text. One click each:

| Column | Type | Options |
|---|---|---|
| Status | Select | Not started / Reading / Read / Cite in Ch2 / Background only / Skipped |
| Priority | Select | High / Medium / Low |
| Relevance (1-5) | Number | 1-5 |
| Year | Number | 4 digits |
| Read date, Found date, Due date, Date | Date | |
| Method type | Multi-select | OR / exact, OR / heuristic, ML, survey, case study |
| Feasibility | Select | Low / Low-Medium / Medium / High |
| Linked gap ID | Text | keep as text: `G-01 G-02` style |

## Views worth making on Papers Read

- **Board** grouped by `Status` — your reading pipeline.
- **Table** filtered `Relevance >= 4` — the papers you must cite.
- **Table** sorted by `Linked gap ID` — literature review, one gap at a time.

## Which side do I edit?

- **Fast and safe:** edit Notion, then **Export → Markdown & CSV**, unzip, replace the files in
  `databases/`, run `python3 scripts/thesis.py all`, commit. Do this weekly.
- **Or edit CSVs in the repo** (or `python3 scripts/thesis.py add "Title" ...`) and re-import to
  Notion when you want a fresh copy.

Pick one direction per week. Do not edit both sides in the same week — Notion cannot merge.

`Linked gap ID` stays text rather than a Notion Relation because CSV import cannot create
relations. The IDs (`G-01`, `D-01`, `R-001`) are what the scripts use to cross-check everything,
so keep them spelled the same way in both places.
