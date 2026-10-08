#!/usr/bin/env python3
"""Thesis tracker toolkit.

The CSV files in ``databases/`` are the single source of truth. This script
checks them, then generates the things a thesis actually needs:

    next       what to do today (short list, plain text)
    validate   integrity checks; exits 1 on real errors
    report     out/REPORT.md  - progress vs targets, gap coverage, blockers
    bibtex     out/refs.bib   - reference file built from papers.csv
    matrix     out/literature_matrix.md - lit-review table grouped by research gap
    all        validate + report + bibtex + matrix
    add        append a paper without opening the CSV

Standard library only. Run from anywhere: python3 scripts/thesis.py <command>
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "databases"
OUT = ROOT / "out"

# ---------------------------------------------------------------- schema ----

COLUMNS = {
    "papers.csv": [
        "Paper", "BibTeX key", "BibTeX type", "Authors", "Year", "Venue",
        "DOI or link", "Method type", "Methodology", "Data used", "Key finding",
        "Limitations", "Research gap", "Linked gap ID", "Relevance (1-5)",
        "Status", "Read date",
    ],
    "reading_queue.csv": [
        "Paper", "Priority", "Why I need it", "Found from", "Found date",
        "Status", "Target gap", "Promoted to papers.csv", "Notes",
    ],
    "gaps.csv": [
        "Gap ID", "Gap statement", "Papers that prove it", "My approach",
        "Data needed", "Feasibility", "Status", "Priority", "Target chapter",
    ],
    "experiments.csv": [
        "Run ID", "Date", "Model version", "Solver", "Instance (nodes x periods)",
        "Objective value", "Solve time (s)", "MIP gap %", "Outcome",
        "Linked gap ID", "Next action",
    ],
    "writing_tasks.csv": [
        "Task", "Section", "Type", "Status", "Due date", "Word target",
        "Linked gap ID", "Blocked by", "Notes",
    ],
    "data_inventory.csv": [
        "Dataset ID", "Dataset", "Content", "Source", "Period", "Granularity",
        "Access status", "Cleaning status", "Used in version", "Linked gap ID",
    ],
}

KEY_COL = {name: cols[0] for name, cols in COLUMNS.items()}

# columns that may contain "G-01" style references to gaps.csv
GAP_REFS = {
    "papers.csv": "Linked gap ID",
    "reading_queue.csv": "Target gap",
    "experiments.csv": "Linked gap ID",
    "writing_tasks.csv": "Linked gap ID",
    "data_inventory.csv": "Linked gap ID",
}

DATE_COLS = {
    "papers.csv": ["Read date"],
    "reading_queue.csv": ["Found date"],
    "experiments.csv": ["Date"],
    "writing_tasks.csv": ["Due date"],
}

# A paper is "finished" once its reading cells must be filled in.
FINISHED_STATUSES = ("read", "cited", "cite in", "done", "closed")

# Accepted Status prefixes (lowercased), per file. Anything else warns.
ALLOWED_STATUS = {
    "papers.csv": ("not started", "to read", "reading", "read", "cite",
                   "background", "skipped"),
    "reading_queue.csv": ("not started", "to read", "reading", "done", "promoted"),
    "writing_tasks.csv": ("to do", "in progress", "blocked", "review", "done", "closed", "dropped"),
    "experiments.csv": ("not run", "running", "solved", "timeout", "failed", "infeasible", "partial"),
}


# ------------------------------------------------------------- loading ------

def read_db(name: str) -> list[dict]:
    """Rows of one CSV as dicts. Missing file returns [] (validate reports it)."""
    path = DB / name
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r.pop(None, None)  # ignore values past the last header (stray trailing comma)
    return rows


def width_problems(name: str) -> list:
    """Lines whose field count differs from the header - Notion would import junk."""
    path = DB / name
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        return []
    expected = len(rows[0])
    return [(i + 1, len(r), expected) for i, r in enumerate(rows[1:], start=1) if len(r) != expected]


def real_rows(rows: list[dict], name: str) -> list[dict]:
    """Drop empty rows and the '(placeholder row ...)' seed rows."""
    key = KEY_COL[name]
    kept = []
    for r in rows:
        label = (r.get(key) or "").strip()
        if not label or label.startswith("("):
            continue
        if not any((v or "").strip() for v in r.values()):
            continue
        kept.append(r)
    return kept


def load(name: str) -> list[dict]:
    return real_rows(read_db(name), name)


def settings() -> dict:
    out = {}
    for r in load_settings_rows():
        if r.get("key"):
            out[r["key"]] = r.get("value") or ""
    return out


def load_settings_rows() -> list[dict]:
    return [r for r in read_db("settings.csv") if (r.get("key") or "").strip()]


def gaps_ids() -> set:
    return {(r.get("Gap ID") or "").strip() for r in load("gaps.csv")} - {""}


def refs_in(text: str, pattern: str) -> list:
    return re.findall(pattern, text or "")


def parse_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return "bad"


def rel_int(row: dict) -> int:
    value = (row.get("Relevance (1-5)") or "").strip()
    return int(value) if value.isdigit() and 1 <= int(value) <= 5 else 0


def is_relevant(row: dict, minimum: int) -> bool:
    return rel_int(row) >= minimum


def status_of(row: dict, col: str = "Status") -> str:
    return (row.get(col) or "").strip().lower()


# ------------------------------------------------------------ validate -----

def validate(verbose: bool = True):
    errors, warnings = [], []
    known_gaps = gaps_ids()
    ids_by_file = {
        "data_inventory.csv": {(r.get("Dataset ID") or "").strip() for r in load("data_inventory.csv")} - {""},
        "experiments.csv": {(r.get("Run ID") or "").strip() for r in load("experiments.csv")} - {""},
    }

    for name, required in COLUMNS.items():
        raw = read_db(name)
        if not raw:
            errors.append(f"{name}: file missing or empty")
            continue
        headers = [h.strip() for h in raw[0].keys() if h is not None]
        for col in required:
            if col not in headers:
                errors.append(f"{name}: missing column '{col}'")
        rows = load(name)
        key = KEY_COL[name]

        for line, got, want in width_problems(name):
            errors.append(f"{name} line {line}: has {got} fields but the header has {want}")

        seen = {}
        for i, r in enumerate(rows, start=2):
            label = (r.get(key) or "").strip()
            if label in seen:
                errors.append(f"{name}: duplicate {key} '{label}' (rows {seen[label]} and {i})")
            else:
                seen[label] = i

            for col in DATE_COLS.get(name, []):
                if parse_date(r.get(col, "")) == "bad":
                    errors.append(f"{name} row {i} '{label[:40]}': '{col}' = '{r.get(col)}' is not YYYY-MM-DD")

            gap_col = GAP_REFS.get(name)
            allowed = ALLOWED_STATUS.get(name)
            st_raw = (r.get("Status") or "").strip()
            if allowed and st_raw and not any(st_raw.lower().startswith(a) for a in allowed):
                warnings.append(
                    f"{name} row {i} '{label[:40]}': Status '{st_raw}' is not one of "
                    f"{', '.join(allowed)}")
            if gap_col:
                for g in refs_in(r.get(gap_col, ""), r"G-\d+"):
                    if known_gaps and g not in known_gaps:
                        errors.append(f"{name} row {i} '{label[:40]}': unknown gap id {g}")

        if name == "papers.csv":
            keys_seen = {}
            for i, r in enumerate(rows, start=2):
                k = (r.get("BibTeX key") or "").strip()
                if not k:
                    continue
                if k in keys_seen:
                    errors.append(f"papers.csv: duplicate BibTeX key '{k}' "
                                  f"(rows {keys_seen[k]} and {i}) - refs.bib would break")
                else:
                    keys_seen[k] = i
            must_fill = ("Methodology", "Limitations", "Research gap")
            for i, r in enumerate(rows, start=2):
                label = (r.get("Paper") or "").strip()
                st = status_of(r)
                if any(st.startswith(s) for s in FINISHED_STATUSES):
                    empty = [c for c in must_fill if not (r.get(c) or "").strip()]
                    if empty:
                        errors.append(
                            f"papers.csv row {i} '{label[:40]}': finished paper but "
                            f"{', '.join(empty)} left blank")
                rel = (r.get("Relevance (1-5)") or "").strip()
                if rel and (not rel.isdigit() or not 1 <= int(rel) <= 5):
                    errors.append(f"papers.csv row {i} '{label[:40]}': relevance must be 1-5, got '{rel}'")
                yr = (r.get("Year") or "").strip()
                if yr and not re.fullmatch(r"\d{4}", yr):
                    errors.append(f"papers.csv row {i} '{label[:40]}': year must be 4 digits, got '{yr}'")
                if not (r.get("BibTeX key") or "").strip():
                    warnings.append(f"papers.csv row {i} '{label[:40]}': no BibTeX key, skipped by 'bibtex'")
                elif not (r.get("Authors") or "").strip():
                    warnings.append(f"papers.csv row {i} '{label[:40]}': no Authors, reference will be incomplete")
                if not refs_in(r.get("Linked gap ID", ""), r"G-\d+"):
                    warnings.append(f"papers.csv row {i} '{label[:40]}': not linked to any gap")

        if name == "writing_tasks.csv":
            for i, r in enumerate(rows, start=2):
                st = status_of(r)
                due = parse_date(r.get("Due date", ""))
                if isinstance(due, dt.date) and due < dt.date.today() and st not in ("done", "closed"):
                    warnings.append(f"writing_tasks.csv row {i}: '{(r.get("Task") or "")[:40]}' overdue since {due}")
                if st == "blocked" and not (r.get("Blocked by") or "").strip():
                    warnings.append(f"writing_tasks.csv row {i}: '{(r.get("Task") or "")[:40]}' blocked but no blocker named")
                for d in refs_in(r.get("Blocked by", ""), r"D-\d+"):
                    if known_ids("data_inventory.csv") and d not in ids_by_file["data_inventory.csv"]:
                        errors.append(f"writing_tasks.csv row {i}: blocked by unknown dataset {d}")
                for run in refs_in(r.get("Blocked by", ""), r"R-\d+"):
                    if known_ids("experiments.csv") and run not in ids_by_file["experiments.csv"]:
                        errors.append(f"writing_tasks.csv row {i}: blocked by unknown run {run}")

        if name == "gaps.csv":
            paper_gaps = set()
            for p in load("papers.csv"):
                paper_gaps.update(refs_in(p.get("Linked gap ID", ""), r"G-\d+"))
            for r in rows:
                gid = (r.get("Gap ID") or "").strip()
                if (r.get("Status") or "").lower().startswith("confirmed") and gid not in paper_gaps:
                    warnings.append(f"gaps.csv: {gid} is 'Confirmed' but no paper cites that gap id")

    if verbose:
        for w in warnings:
            print(f"warn  {w}")
        for e in errors:
            print(f"ERROR {e}")
        if not errors and not warnings:
            print("clean: all databases check out")
        elif not errors:
            print(f"ok: 0 errors, {len(warnings)} warning(s)")
    return errors, warnings


def known_ids(name: str) -> bool:
    return bool(load(name))


# --------------------------------------------------------------- report ----

def md_table(headers: list, rows: list) -> str:
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(c).replace("\n", " ") or "-" for c in r) + " |")
    return "\n".join(lines)


def bar(done: int, target: int, width: int = 20) -> str:
    if target <= 0:
        target = 1
    filled = min(width, round(width * done / target))
    return f"[{'#' * filled}{'.' * (width - filled)}] {done}/{target}"


def cmd_report() -> str:
    cfg = settings()
    papers = load("papers.csv")
    gaps = load("gaps.csv")
    queue = load("reading_queue.csv")
    runs = load("experiments.csv")
    tasks = load("writing_tasks.csv")
    data = load("data_inventory.csv")
    target = int(cfg.get("target_papers", 40) or 40)
    min_cite = int(cfg.get("min_relevance_to_cite", 4) or 4)

    finished = [p for p in papers if any(status_of(p).startswith(s) for s in FINISHED_STATUSES)]
    must_cite = [p for p in papers if is_relevant(p, min_cite)]
    overdue = [t for t in tasks
               if isinstance(parse_date(t.get("Due date")), dt.date)
               and parse_date(t["Due date"]) < dt.date.today()
               and status_of(t) not in ("done", "closed")]
    open_runs = [r for r in runs if (r.get("Objective value") or "").strip()]

    sub = parse_date(cfg.get("submission_date", ""))
    countdown = ""
    if isinstance(sub, dt.date):
        days = (sub - dt.date.today()).days
        countdown = f"{days} days to submission ({sub.isoformat()})" if days >= 0 else f"{-days} days past submission"

    lines = [f"# Thesis progress - generated {dt.date.today().isoformat()}", ""]
    if countdown:
        lines += [f"**{countdown}**", ""]
    lines += [
        "## Snapshot",
        "",
        f"- Papers logged: {bar(len(papers), target)}",
        f"- Finished reading: {bar(len(finished), target)}",
        f"- Must cite (relevance >= {min_cite}): {len(must_cite)}",
        f"- Still in queue: {len([q for q in queue if status_of(q) not in ('done', 'read')])}",
        f"- Experiments with results: {len(open_runs)}/{len(runs)}",
        f"- Writing tasks open: {len([t for t in tasks if status_of(t) not in ('done', 'closed')])}"
        f" (overdue {len(overdue)}, blocked {len([t for t in tasks if status_of(t) == 'blocked'])})",
        f"- Data ready: {len([d for d in data if (d.get('Access status') or '').lower() == 'have it'])}/{len(data)}",
        "",
        "## Gap coverage",
        "",
    ]
    paper_gaps = {}
    for p in papers:
        for g in refs_in(p.get("Linked gap ID", ""), r"G-\d+"):
            paper_gaps.setdefault(g, []).append(p)
    rows = []
    for g in sorted(gaps, key=lambda r: (r.get("Priority") or "9")):
        gid = (g.get("Gap ID") or "").strip()
        ev = paper_gaps.get(gid, [])
        rows.append([gid, (g.get("Gap statement") or "")[:70], g.get("Status"), len(ev),
                     "; ".join((p.get("BibTeX key") or "?") for p in ev) or "NONE YET"])
    lines += [md_table(["Gap", "Statement", "Status", "Papers", "Keys"], rows), ""]
    holes = [(g.get("Gap ID") or "").strip() for g in gaps
             if (g.get("Gap ID") or "").strip() not in paper_gaps]
    if holes:
        lines += [f"> Gaps with no logged paper yet: **{', '.join(holes)}**. "
                  "A gap you cannot evidence is not a gap, it is a guess.", ""]

    lines += ["## Must-cite papers", ""]
    rows = [[p.get("BibTeX key"), p.get("Paper"), p.get("Year"), p.get("Relevance (1-5)"),
             p.get("Linked gap ID"), p.get("Status")] for p in
            sorted(must_cite, key=lambda p: -rel_int(p))]
    lines += [md_table(["Key", "Paper", "Year", "Rel", "Gap", "Status"], rows) if rows
              else "_none yet_", ""]

    lines += ["## Overdue and blocked", ""]
    rows = [[t.get("Task"), t.get("Status"), t.get("Due date"), t.get("Blocked by") or "-"]
            for t in tasks if t in overdue or status_of(t) == "blocked"]
    lines += [md_table(["Task", "Status", "Due", "Blocked by"], rows) if rows
              else "_nothing overdue or blocked_", ""]

    lines += ["## Papers read but not filled in", ""]
    thin = [p for p in papers
            if any(status_of(p).startswith(s) for s in FINISHED_STATUSES)
            and not all((p.get(c) or "").strip() for c in ("Methodology", "Limitations", "Research gap"))]
    rows = [[p.get("Paper"),
             ", ".join(c for c in ("Methodology", "Limitations", "Research gap")
                       if not (p.get(c) or "").strip())] for p in thin]
    lines += [md_table(["Paper", "Missing cells"], rows) if rows
              else "_every finished paper has methodology, limitations and gap_", ""]

    OUT.mkdir(exist_ok=True)
    text = "\n".join(lines) + "\n"
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")
    print(f"wrote out/REPORT.md  ({len(papers)} papers, {len(gaps)} gaps, {len(must_cite)} must-cite)")
    return text


# --------------------------------------------------------------- bibtex ----

def bibtex_escape(text: str) -> str:
    return text or ""


def cmd_bibtex() -> int:
    cfg = settings()
    min_cite = int(cfg.get("min_relevance_to_cite", 4) or 1)
    entries, skipped = [], 0
    for p in load("papers.csv"):
        key = (p.get("BibTeX key") or "").strip()
        if not key or not (p.get("Authors") or "").strip():
            skipped += 1
            continue
        etype = (p.get("BibTeX type") or "misc").strip() or "misc"
        venue_col = "journal" if etype == "article" else "booktitle"
        fields = [
            ("title", bibtex_escape(p.get("Paper"))),
            ("author", bibtex_escape(p.get("Authors"))),
            ("year", (p.get("Year") or "").strip()),
            (venue_col, bibtex_escape(p.get("Venue"))),
            ("note", f"Relevance {p.get('Relevance (1-5)')}; gap {p.get('Linked gap ID')}".strip()),
        ]
        if (p.get("DOI or link") or "").strip():
            fields.append(("doi", p["DOI or link"].strip()))
        body = ",\n".join(f"  {name:<10}= {{{value}}}" for name, value in fields if value)
        entries.append((key, f"@{etype}{{{key},\n{body}\n}}"))
    OUT.mkdir(exist_ok=True)
    (OUT / "refs.bib").write_text("\n\n".join(v for _, v in sorted(entries)) + "\n", encoding="utf-8")
    print(f"wrote out/refs.bib  ({len(entries)} entries, {skipped} skipped for missing key/authors)")
    return len(entries)


# --------------------------------------------------------------- matrix ----

def cmd_matrix() -> int:
    cfg = settings()
    min_cite = int(cfg.get("min_relevance_to_cite", 4) or 4)
    by_gap = {}
    for p in load("papers.csv"):
        for g in refs_in(p.get("Linked gap ID", ""), r"G-\d+") or ["unlinked"]:
            by_gap.setdefault(g, []).append(p)
    gaps = {(g.get("Gap ID") or "").strip(): g for g in load("gaps.csv")}

    lines = [f"# Literature matrix - generated {dt.date.today().isoformat()}",
             "",
             "Grouped by research gap. Paste a section straight into the literature review.",
             ""]
    for gid in sorted(by_gap):
        title = gid if gid == "unlinked" else f"{gid} - {(gaps.get(gid, {}).get('Gap statement') or 'gap not defined in gaps.csv')[:90]}"
        lines += [f"## {title}", ""]
        rows = []
        for p in sorted(by_gap[gid], key=lambda x: -rel_int(x)):
            rows.append([
                f"{p.get('BibTeX key') or '?'} ({p.get('Year') or 'n.d.'})",
                p.get("Method type"), p.get("Methodology"), p.get("Limitations"),
                p.get("Research gap"), p.get("Relevance (1-5)"),
            ])
        lines += [md_table(["Paper", "Method type", "Methodology", "Limitations",
                            "Their stated gap", "Rel"], rows), ""]
    must = [p for p in load("papers.csv") if is_relevant(p, min_cite)]
    lines += [f"## Must cite (relevance >= {min_cite})", ""]
    lines += [md_table(["Paper", "Why"], [[p.get("BibTeX key"),
                                           (p.get("Key finding") or p.get("Research gap") or "")[:120]]
                                          for p in must]) if must else "_none_", ""]

    OUT.mkdir(exist_ok=True)
    (OUT / "literature_matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote out/literature_matrix.md  ({len(by_gap)} gap sections)")
    return len(by_gap)


# ----------------------------------------------------------------- next ----

def cmd_next() -> str:
    cfg = settings()
    papers, queue, tasks, gaps = (load("papers.csv"), load("reading_queue.csv"),
                                  load("writing_tasks.csv"), load("gaps.csv"))
    target = int(cfg.get("target_papers", 40) or 40)
    out = [f"Today: {dt.date.today().isoformat()}"]
    n = 0

    def item(text_line: str):
        nonlocal n
        n += 1
        out.append(f"{n}. {text_line}")

    thin = [p for p in papers
            if any(status_of(p).startswith(s) for s in FINISHED_STATUSES)
            and not all((p.get(c) or "").strip() for c in ("Methodology", "Limitations", "Research gap"))]
    if thin:
        item(f"Finish the rows for {len(thin)} paper(s) you already marked read:")
        for p in thin[:5]:
            missing = [c for c in ("Methodology", "Limitations", "Research gap") if not (p.get(c) or "").strip()]
            out.append(f"     - {(p.get('Paper') or '')[:60]} -> needs {', '.join(missing)}")
    if len(papers) < target:
        item(f"Log {target - len(papers)} more papers (have {len(papers)}, target {target})")
    hi = [q for q in queue if (q.get("Priority") or "").lower() == "high"
          and status_of(q) not in ("done", "read", "promoted")]
    if hi:
        item("Read next, high priority:")
        for q in hi[:3]:
            out.append(f"     - {(q.get('Paper') or '')[:70]} ({q.get('Target gap') or 'no gap set'})")
    overdue = [t for t in tasks
               if isinstance(parse_date(t.get("Due date")), dt.date)
               and parse_date(t.get("Due date")) < dt.date.today()
               and status_of(t) not in ("done", "closed")]
    if overdue:
        item("Overdue writing tasks: " + ", ".join((t.get("Task") or "")[:40] for t in overdue))
    blocked = [t for t in tasks if status_of(t) == "blocked"]
    if blocked:
        item("Blocked, unblock these first: " + ", ".join(
            f"{(t.get('Task') or '')[:35]} <- {(t.get('Blocked by') or 'no blocker named')}" for t in blocked))

    paper_gaps = set()
    for p in papers:
        paper_gaps.update(refs_in(p.get("Linked gap ID", ""), r"G-\d+"))
    holes = [(g.get("Gap ID") or "").strip() for g in gaps
             if (g.get("Gap ID") or "").strip() not in paper_gaps]
    if holes:
        item("Find evidence for unevidenced gaps: " + ", ".join(holes))
    if n == 0:
        item("Nothing pending - add papers to databases/papers.csv")
    text = "\n".join(out)
    print(text)
    return text


# ------------------------------------------------------------------ add ----

def make_key(paper: dict) -> str:
    first = re.split(r",| and ", (paper.get("Authors") or "").strip())[0].strip()
    surname = re.sub(r"[^a-zA-Z]", "", first).lower() or "anon"
    year = re.sub(r"\D", "", paper.get("Year") or "") or "nd"
    word = re.sub(r"[^a-zA-Z]", "", (paper.get("Paper") or "").split()[0]).lower() if paper.get("Paper") else "x"
    base = f"{surname}{year}{word[:12]}"
    existing = {p.get("BibTeX key") for p in load("papers.csv")}
    key, n = base, 2
    while key in existing:
        key = f"{base}{chr(96 + n)}"
        n += 1
    return key


def cmd_add(args) -> int:
    name = "papers.csv"
    rows = read_db(name)
    if not rows:
        print("ERROR databases/papers.csv missing", file=sys.stderr)
        return 1
    # DictReader already consumed the header, so rows[0] is the FIRST data row.
    header, body = list(rows[0].keys()), list(rows)
    paper = {
        "Paper": args.title, "BibTeX key": args.key or "", "BibTeX type": args.type,
        "Authors": args.authors or "", "Year": args.year or "", "Venue": args.venue or "",
        "DOI or link": args.link or "", "Method type": args.method_type or "",
        "Methodology": args.methodology or "", "Data used": args.data or "",
        "Key finding": args.finding or "", "Limitations": args.limitations or "",
        "Research gap": args.gap or "", "Linked gap ID": args.linked_gap or "",
        "Relevance (1-5)": args.relevance or "", "Status": args.status or "Not started",
        "Read date": args.read_date or dt.date.today().isoformat(),
    }
    if not paper["BibTeX key"]:
        paper["BibTeX key"] = make_key(paper)
    insert_at = next((i for i, r in enumerate(body)
                      if (r.get(header[0]) or "").strip().startswith("(")), None)
    if insert_at is None:
        body.append(paper)
    else:
        body.insert(insert_at, paper)
    with (DB / name).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        w.writerows(body)
    missing = [c for c in ("Methodology", "Limitations", "Research gap") if not paper[c]]
    print(f"added: {paper['Paper'][:60]}  key={paper['BibTeX key']}")
    if missing:
        print(f"  still to fill: {', '.join(missing)}")
    return 0


# ---------------------------------------------------------------- main -----

def cmd_all() -> int:
    errors, warnings = validate()
    cmd_report()
    cmd_bibtex()
    cmd_matrix()
    print(f"{'PASS' if not errors else 'FAIL'}: {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Thesis tracker toolkit")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("validate", help="check the databases")
    sub.add_parser("report", help="write out/REPORT.md")
    sub.add_parser("bibtex", help="write out/refs.bib")
    sub.add_parser("matrix", help="write out/literature_matrix.md")
    sub.add_parser("next", help="what to do today")
    sub.add_parser("all", help="validate + report + bibtex + matrix")

    a = sub.add_parser("add", help="append a paper to databases/papers.csv")
    a.add_argument("title")
    a.add_argument("--key")
    a.add_argument("--authors")
    a.add_argument("--year")
    a.add_argument("--venue")
    a.add_argument("--type", default="article",
                   help="BibTeX entry type: article, inproceedings, misc ...")
    a.add_argument("--method-type", dest="method_type")
    a.add_argument("--methodology")
    a.add_argument("--data")
    a.add_argument("--finding")
    a.add_argument("--limitations")
    a.add_argument("--gap", help="their stated research gap")
    a.add_argument("--linked-gap", dest="linked_gap", help="your gap id, e.g. G-01")
    a.add_argument("--relevance", help="1-5")
    a.add_argument("--status", default="Not started")
    a.add_argument("--read-date", dest="read_date")
    a.add_argument("--link", help="DOI or URL")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "validate":
        errors, _ = validate()
        return 1 if errors else 0
    if args.cmd == "report":
        cmd_report()
        return 0
    if args.cmd == "bibtex":
        cmd_bibtex()
        return 0
    if args.cmd == "matrix":
        cmd_matrix()
        return 0
    if args.cmd == "next":
        cmd_next()
        return 0
    if args.cmd == "all":
        return cmd_all()
    if args.cmd == "add":
        return cmd_add(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
