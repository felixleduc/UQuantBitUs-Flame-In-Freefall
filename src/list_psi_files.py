"""List every file attached to each PSI combustion investigation, without downloading any.

The PSI repository (https://psi.nasa.gov/physci/repo) is a JavaScript app, so each public
investigation page is opened in a headless browser. This script walks the "Data files and
documents" tree of each page and records name, folder, size, date and kind (document,
image, video, archive, other) of each file. download_psi_files.py then fetches the documents.

Usage:
    uv run python src/list_psi_files.py            # all investigations
    uv run python src/list_psi_files.py 25 99      # only PSI-25 and PSI-99

Output:
    data/files.csv    one row per file, saved after each investigation; a run replaces only
                      the rows of the investigations it visits
"""

import csv
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page, Playwright, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://psi.nasa.gov/physci/repo/data/investigations/PSI-{id}"

# (PSI id, short name), grouped by how much each one says about the question
# "would this material burn in this habitat?". The grouping is the team's judgment.
INVESTIGATIONS = [
    # Core: solid fuels, the direct evidence
    (99, "SAFFIRE-II"),
    (98, "SAFFIRE-I"),
    (100, "SAFFIRE-III"),
    (25, "BASS-II"),
    (26, "BASS"),
    # Support: liquid droplets and gas flames that record oxygen, pressure and an outcome
    (69, "FLEX"),
    (68, "FLEX-2"),
    (39, "CFI"),
    (159, "CFI-G"),
    (10, "Flame-Design"),
    (20, "BRE"),
    # Detection: smoke and aerosols
    (102, "SAME"),
    (101, "SAME-R"),
    (47, "DAFT"),
    # Context: session logs with few conditions
    (107, "SPICE"),
    (106, "SLICE"),
    (22, "E-FIELD-Flames"),
    (23, "s-Flame"),
    (21, "CLD-Flame"),
]

FILES_CSV = ROOT / "data" / "files.csv"
FIELDS = ["psi_id", "name", "folder", "file", "extension", "kind", "size", "size_mb", "date_added"]
UNITS = {"B": 1 / 1024**2, "KB": 1 / 1024, "MB": 1, "GB": 1024, "TB": 1024**2}
KINDS = {
    "document": {"pdf", "doc", "docx", "xls", "xlsx", "csv", "txt", "rtf", "ppt", "pptx"},
    "video": {"mp4", "mpg", "mpeg", "avi", "mov", "wmv", "m4v", "mkv", "ts"},  # ts: MPEG transport stream
    "image": {"jpg", "jpeg", "png", "tif", "tiff", "bmp", "gif", "eps", "svg", "raw", "cr2", "nef"},
    "archive": {"zip", "tar", "gz", "tgz", "7z", "rar"},
}

ROWS = "app-geode-tree a.panel-block"

READ_ROWS = """tree => Array.from(tree.querySelectorAll('a.panel-block')).map(a => {
  const clean = e => (e ? e.textContent : '').replace(/\\s+/g, ' ').trim();
  const cells = Array.from(a.querySelectorAll('.column')).map(clean);
  return {
    depth: Number((a.className.match(/depth-(\\d+)/) || [0, 0])[1]),
    folder: !!a.querySelector('i.fa-folder, i.fa-folder-open'),
    open: !!a.querySelector('i.fa-folder-open'),
    name: clean(a.querySelector('.inline-flex')) || cells[0],
    cells: cells.slice(1),
  };
})"""


def in_fresh_browser[T](p: Playwright, label: str, job: Callable[[Page], T]) -> T:
    """Run job(page) in a new browser. A tab can crash when memory is short: retry twice."""
    for attempt in (1, 2, 3):
        browser = p.chromium.launch()
        try:
            return job(browser.new_page(viewport={"width": 1400, "height": 1000}))
        except Exception as error:
            if attempt == 3:
                raise
            print(f"{label}: {type(error).__name__}, retrying", flush=True)
            time.sleep(5)
        finally:
            browser.close()
    raise AssertionError("unreachable")


def kind_of(extension: str) -> str:
    """Kind of a file from its extension. Unlisted ones (instrument and camera formats
    such as .dat) are "other": only what is surely a document gets downloaded."""
    return next((kind for kind, extensions in KINDS.items() if extension in extensions), "other")


def size_in_mb(size: str) -> float | None:
    match = re.match(r"([\d.,]+)\s*([KMGT]?B)", size, re.IGNORECASE)
    if not match:
        return None
    return round(float(match.group(1).replace(",", "")) * UNITS[match.group(2).upper()], 6)


def file_record(row: dict, path: list[str]) -> dict:
    size = next((c for c in row["cells"] if re.match(r"[\d.,]+\s*[KMGT]?B$", c, re.IGNORECASE)), "")
    date = next((c for c in row["cells"] if re.search(r"\d{4}", c) and c != size), "")
    extension = row["name"].rsplit(".", 1)[-1].lower() if "." in row["name"] else ""
    return {
        "folder": "/".join(path),
        "file": row["name"],
        "extension": extension,
        "kind": kind_of(extension),
        "size": size,
        "size_mb": size_in_mb(size),
        "date_added": date,
    }


def walk_tree(
    page: Page,
    psi_id: int,
    on_file: Callable[[int, dict, list[str]], None],
    enter: Callable[[list[str]], bool] = lambda path: True,
) -> None:
    """Walk the file tree of an investigation, one folder at a time.

    Calls on_file(row index, row, folder path) for each file, and skips the folders for
    which enter(folder path) is false. Each folder is closed again once visited: the page
    crashes when a few thousand rows are open together (FLEX has many more).
    """
    page.goto(BASE_URL.format(id=psi_id), wait_until="networkidle", timeout=90_000)
    page.wait_for_selector(ROWS, timeout=60_000)
    page.wait_for_timeout(2_000)
    tree = page.locator("app-geode-tree").first

    def toggle(index: int, want_open: bool) -> list[dict]:
        """Open or close the folder at this row (a click on its icon) and return the new rows."""
        page.locator(ROWS).nth(index).locator("i").first.click()
        previous = None
        for _ in range(150):
            page.wait_for_timeout(100)
            rows = tree.evaluate(READ_ROWS)
            if rows[index]["open"] == want_open and rows == previous:  # switched, and stable
                return rows
            previous = rows
        raise RuntimeError(f"folder {rows[index]['name']!r} did not {'open' if want_open else 'close'}")

    def walk(index: int, rows: list[dict], path: list[str]) -> list[dict]:
        """Visit what is under the open folder at this row; return the rows as they are after."""
        depth = rows[index]["depth"]
        child = index + 1
        while child < len(rows) and rows[child]["depth"] > depth:
            row = rows[child]
            if not row["folder"]:
                on_file(child, row, path)
            elif enter(path + [row["name"]]):
                rows = toggle(child, True)
                rows = walk(child, rows, path + [row["name"]])
                rows = toggle(child, False)
            child += 1
        return rows

    walk(0, tree.evaluate(READ_ROWS), [])  # row 0 is the "PSI-<id>" root, already open


def list_files(page: Page, psi_id: int) -> list[dict]:
    files: list[dict] = []
    walk_tree(page, psi_id, lambda index, row, path: files.append(file_record(row, path)))
    return files


def read_inventory() -> list[dict]:
    if not FILES_CSV.exists():
        return []
    with open(FILES_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:  # inventories written before the "kind" column existed
        row.setdefault("kind", kind_of(row["extension"]))
    return rows


def main() -> None:
    wanted = {int(a) for a in sys.argv[1:]}
    todo = [inv for inv in INVESTIGATIONS if not wanted or inv[0] in wanted]
    rows = read_inventory()

    with sync_playwright() as p:
        for psi_id, name in todo:
            files = in_fresh_browser(p, f"PSI-{psi_id}", lambda page: list_files(page, psi_id))
            total = sum(f["size_mb"] or 0 for f in files)
            print(f"PSI-{psi_id:<4} {name:<15} {len(files):>5} files, {total / 1024:>8.2f} GB", flush=True)
            # Replace the rows of this investigation and save at once, so a crash later loses nothing.
            rows = [r for r in rows if r["psi_id"] != f"PSI-{psi_id}"]
            rows.extend({"psi_id": f"PSI-{psi_id}", "name": name, **f} for f in files)
            with open(FILES_CSV, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            time.sleep(1.5)  # stay polite with the NASA server


if __name__ == "__main__":
    main()
