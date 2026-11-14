"""Download the experimental tables and page metadata of each PSI combustion investigation.

The PSI repository (https://psi.nasa.gov/physci/repo) is a JavaScript app, so each
public investigation page is rendered in a headless browser and read from the DOM.

Usage:
    uv run python src/fetch_psi.py            # all investigations
    uv run python src/fetch_psi.py 25 99      # only PSI-25 and PSI-99

Output:
    data/raw/PSI-<id>_<name>/<table>.csv     each experimental table as published (blank lines dropped),
                                             under its PSI file name; some investigations have several
    data/raw/PSI-<id>_<name>/metadata.json   title, DOI, description, publications, file list
    data/catalog.csv                         one row per table
"""

import csv
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import Locator, Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
BASE_URL = "https://psi.nasa.gov/physci/repo/data/investigations/PSI-{id}"

# (PSI id, short name, hardware family, fuel phase, role for the question
# "would this material burn in this habitat?"). The role is the team's judgment:
#   core       solid fuels, the direct evidence
#   support    liquid or gas tests that record oxygen, pressure and an outcome
#   detection  smoke and aerosol tests
#   context    session logs with few conditions
INVESTIGATIONS = [
    (99, "SAFFIRE-II", "Saffire (Cygnus)", "solid", "core"),
    (98, "SAFFIRE-I", "Saffire (Cygnus)", "solid", "core"),
    (100, "SAFFIRE-III", "Saffire (Cygnus)", "solid", "core"),
    (25, "BASS-II", "MSG flow duct", "solid", "core"),
    (26, "BASS", "MSG flow duct", "solid", "core"),
    (69, "FLEX", "CIR + MDCA", "liquid", "support"),
    (68, "FLEX-2", "CIR + MDCA", "liquid", "support"),
    (39, "CFI", "CIR + MDCA", "liquid", "support"),
    (159, "CFI-G", "CIR + ACME", "gas", "support"),
    (10, "Flame-Design", "CIR + ACME", "gas", "support"),
    (20, "BRE", "CIR + ACME", "gas", "support"),
    (102, "SAME", "MSG aerosols", "smoke", "detection"),
    (101, "SAME-R", "MSG aerosols", "smoke", "detection"),
    (47, "DAFT", "MSG aerosols", "dust", "detection"),
    (107, "SPICE", "MSG flow duct", "gas", "context"),
    (106, "SLICE", "MSG flow duct", "gas", "context"),
    (22, "E-FIELD-Flames", "CIR + ACME", "gas", "context"),
    (23, "s-Flame", "CIR + ACME", "gas", "context"),
    (21, "CLD-Flame", "CIR + ACME", "gas", "context"),
]

READ_PANELS = """() => {
  const clean = e => (e ? (e.innerText || '') : '').trim();
  const out = {};
  for (const p of document.querySelectorAll('mat-expansion-panel')) {
    const title = clean(p.querySelector('mat-panel-title')).split('\\n').pop().trim();
    const body = p.querySelector('.mat-expansion-panel-body') || p;
    out[title] = (body.innerText || body.textContent || '').replace(/[ \\t]+/g, ' ').replace(/\\s*\\n\\s*/g, '\\n').trim();
  }
  const h1 = document.querySelector('h1');
  return {heading: clean(h1).replace(/\\s+/g, ' '), panels: out, text: document.body.innerText};
}"""

READ_TABLE = """panel => {
  const clean = e => (e.textContent || '').replace(/\\s+/g, ' ').trim();
  const table = panel.querySelector('table');
  return {
    head: Array.from(table.querySelectorAll('th')).map(clean),
    rows: Array.from(table.querySelectorAll('tr')).map(tr => Array.from(tr.querySelectorAll('td')).map(clean)).filter(r => r.length),
    label: clean(panel.querySelector('.mat-mdc-paginator-range-label, .mat-paginator-range-label') || panel.querySelector('mat-paginator')),
  };
}"""

Table = tuple[list[str], list[list[str]]]  # (header, rows)


def open_investigation(page: Page, url: str) -> Locator:
    """Load an investigation page and return its Experimental Table panel, expanded."""
    page.goto(url, wait_until="networkidle", timeout=90_000)
    page.wait_for_selector("mat-expansion-panel", timeout=60_000)
    page.wait_for_timeout(2_000)
    panel = page.locator("mat-expansion-panel").filter(
        has=page.locator("mat-panel-title", has_text="Experimental Table")
    ).first
    if "mat-expanded" not in (panel.get_attribute("class") or ""):
        panel.locator("mat-expansion-panel-header").click()
        page.wait_for_timeout(500)
    return panel


def read_table(page: Page, panel: Locator) -> Table:
    """Read the table on screen, walking through every page of it."""
    panel.locator("mat-paginator mat-select").click()
    largest = page.locator("mat-option").last
    size = int(largest.inner_text())
    largest.click()

    next_button = panel.locator("button[aria-label='Next page'], button.mat-mdc-paginator-navigation-next").first
    rows: list[list[str]] = []
    expected_start = 1
    while True:
        # Wait until the page of the table we expect is fully rendered.
        for _ in range(80):
            part = panel.evaluate(READ_TABLE)
            numbers = re.search(r"(\d+)\D+(\d+)\s+of\s+(\d+)", part["label"])  # "1 - 100 of 274"
            if numbers:
                start, end, total = map(int, numbers.groups())
                if (start == expected_start and end == min(start + size - 1, total)
                        and len(part["rows"]) == end - start + 1):
                    break
            page.wait_for_timeout(250)
        else:
            raise RuntimeError(f"table page did not settle: {part['label']!r}, {len(part['rows'])} rows on screen")
        rows.extend(part["rows"])
        if end >= total:
            break
        expected_start = end + 1
        next_button.click()
    if len(rows) != total:
        raise RuntimeError(f"read {len(rows)} rows, the page announces {total}")
    # The published tables end with blank lines: they carry no data.
    return part["head"], [r for r in rows if any(r)]


def table_names(page: Page, panel: Locator) -> list[str]:
    """File names offered by the "Select Experimental Table" dropdown."""
    if not panel.locator("table").count():
        return []
    panel.locator("mat-select:not(mat-paginator mat-select)").first.click()
    page.wait_for_timeout(300)
    names = [n.strip() for n in page.locator("mat-option").all_inner_texts()]
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    return names


def read_tables(page: Page, url: str, panel: Locator) -> dict[str, Table]:
    """Return {csv file name: table}. Each table is read from a fresh page load."""
    names = table_names(page, panel)
    if len(names) <= 1:
        return {name: read_table(page, panel) for name in names}

    tables: dict[str, Table] = {}
    for name in names:
        panel = open_investigation(page, url)
        shown = panel.evaluate(READ_TABLE)
        panel.locator("mat-select:not(mat-paginator mat-select)").first.click()
        # By name: the order of the options changes from one page load to the next.
        page.get_by_role("option", name=name, exact=True).click()
        # The page shows one of the tables by default, in no fixed order. Wait for the
        # display to change; if it does not, the table asked for was already on screen.
        for _ in range(32):
            if panel.evaluate(READ_TABLE) != shown:
                break
            page.wait_for_timeout(250)
        page.wait_for_timeout(500)
        tables[name] = read_table(page, panel)
    if len({json.dumps(t) for t in tables.values()}) != len(tables):
        raise RuntimeError("two tables came back identical: a table switch was missed")
    return tables


def fetch(page: Page, psi_id: int, name: str) -> dict:
    url = BASE_URL.format(id=psi_id)
    panel = open_investigation(page, url)
    info = page.evaluate(READ_PANELS)
    tables = read_tables(page, url, panel)
    doi = re.search(r"10\.\d{4,9}/[A-Za-z0-9._-]+", info["text"])

    folder = RAW / f"PSI-{psi_id}_{name}"
    folder.mkdir(parents=True, exist_ok=True)
    for file_name, (header, rows) in tables.items():
        with open(folder / file_name, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)
    metadata = {
        "psi_id": f"PSI-{psi_id}",
        "name": name,
        "url": url,
        "doi": doi.group(0).rstrip(".") if doi else None,
        "heading": info["heading"],
        "fetched": time.strftime("%Y-%m-%d"),
        "tables": list(tables),
        "panels": {k: v for k, v in info["panels"].items() if k != "Experimental Table"},
    }
    (folder / "metadata.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"url": url, "doi": metadata["doi"], "tables": tables, "folder": folder}


def main() -> None:
    wanted = {int(a) for a in sys.argv[1:]}
    todo = [inv for inv in INVESTIGATIONS if not wanted or inv[0] in wanted]
    catalog = []
    with sync_playwright() as p:
        for psi_id, name, family, phase, role in todo:
            for attempt in (1, 2, 3):  # a tab can crash when memory is short: retry in a fresh browser
                browser = p.chromium.launch()
                try:
                    page = browser.new_page(viewport={"width": 1400, "height": 1000})
                    result = fetch(page, psi_id, name)
                    break
                except Exception as error:
                    if attempt == 3:
                        raise
                    print(f"PSI-{psi_id}: {type(error).__name__}, retrying", flush=True)
                    time.sleep(5)
                finally:
                    browser.close()
            for file_name, (header, rows) in result["tables"].items():
                print(f"PSI-{psi_id:<4} {name:<15} {len(rows):>4} rows, {len(header):>2} columns  {file_name}", flush=True)
                catalog.append({
                    "psi_id": f"PSI-{psi_id}",
                    "name": name,
                    "family": family,
                    "fuel_phase": phase,
                    "role": role,
                    "rows": len(rows),
                    "n_columns": len(header),
                    "columns": " | ".join(header),
                    "doi": result["doi"],
                    "url": result["url"],
                    "table": str((result["folder"] / file_name).relative_to(ROOT)),
                })
            time.sleep(1.5)  # stay polite with the NASA server

    if not wanted:  # a partial run must not overwrite the full catalog
        with open(ROOT / "data" / "catalog.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(catalog[0]))
            writer.writeheader()
            writer.writerows(catalog)


if __name__ == "__main__":
    main()
