"""List every file attached to each PSI combustion investigation, without downloading any.

Opens the "Data files and documents" tree of each public investigation page, expands
all its folders and records name, folder, size and date of each file.

Usage:
    uv run python src/list_psi_files.py            # all investigations
    uv run python src/list_psi_files.py 25 99      # only PSI-25 and PSI-99

Output:
    data/files.csv    one row per file (a partial run replaces only the rows of the ids given)
"""

import csv
import re
import sys
import time

from playwright.sync_api import Page, sync_playwright

from fetch_psi import BASE_URL, INVESTIGATIONS, ROOT

FILES_CSV = ROOT / "data" / "files.csv"
FIELDS = ["psi_id", "name", "folder", "file", "extension", "size", "size_mb", "date_added"]
UNITS = {"B": 1 / 1024**2, "KB": 1 / 1024, "MB": 1, "GB": 1024, "TB": 1024**2}

CLOSED_FOLDER = "app-geode-tree a.panel-block i.fa-folder"

READ_ROWS = """tree => Array.from(tree.querySelectorAll('a.panel-block')).map(a => {
  const clean = e => (e ? e.textContent : '').replace(/\\s+/g, ' ').trim();
  const cells = Array.from(a.querySelectorAll('.column')).map(clean);
  return {
    depth: Number((a.className.match(/depth-(\\d+)/) || [0, 0])[1]),
    folder: !!a.querySelector('i.fa-folder, i.fa-folder-open'),
    name: clean(a.querySelector('.inline-flex')) || cells[0],
    cells: cells.slice(1),
  };
})"""


def size_in_mb(size: str) -> float | None:
    match = re.match(r"([\d.,]+)\s*([KMGT]?B)", size, re.IGNORECASE)
    if not match:
        return None
    return round(float(match.group(1).replace(",", "")) * UNITS[match.group(2).upper()], 3)


def list_files(page: Page, psi_id: int) -> list[dict]:
    page.goto(BASE_URL.format(id=psi_id), wait_until="networkidle", timeout=90_000)
    page.wait_for_selector("app-geode-tree a.panel-block", timeout=60_000)
    page.wait_for_timeout(2_000)

    # Open closed folders until none is left (opening one can reveal more).
    # A folder opens on a click on its icon, not on its row.
    closed = page.locator(CLOSED_FOLDER)
    rows = page.locator("app-geode-tree a.panel-block")
    for _ in range(2_000):
        state = (closed.count(), rows.count())
        if not state[0]:
            break
        closed.first.click()
        for _ in range(100):  # the folder is open once the tree has changed
            page.wait_for_timeout(100)
            if (closed.count(), rows.count()) != state:
                break
        else:
            raise RuntimeError("a folder of the file tree did not open")
    else:
        raise RuntimeError("the file tree keeps showing closed folders")
    page.wait_for_timeout(500)

    files = []
    path: list[str] = []
    for row in page.locator("app-geode-tree").first.evaluate(READ_ROWS):
        del path[row["depth"]:]
        if row["folder"]:
            path.append(row["name"])
            continue
        size = next((c for c in row["cells"] if re.match(r"[\d.,]+\s*[KMGT]?B$", c, re.IGNORECASE)), "")
        date = next((c for c in row["cells"] if re.search(r"\d{4}", c) and c != size), "")
        extension = row["name"].rsplit(".", 1)[-1].lower() if "." in row["name"] else ""
        files.append({
            "folder": "/".join(path[1:]),  # without the "PSI-<id>" root
            "file": row["name"],
            "extension": extension,
            "size": size,
            "size_mb": size_in_mb(size),
            "date_added": date,
        })
    return files


def main() -> None:
    wanted = {int(a) for a in sys.argv[1:]}
    todo = [inv for inv in INVESTIGATIONS if not wanted or inv[0] in wanted]
    done = {f"PSI-{inv[0]}" for inv in todo}
    rows = []
    if wanted and FILES_CSV.exists():
        with open(FILES_CSV, newline="", encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r["psi_id"] not in done]

    with sync_playwright() as p:
        for psi_id, name, *_ in todo:
            for attempt in (1, 2, 3):  # a tab can crash when memory is short: retry in a fresh browser
                browser = p.chromium.launch()
                try:
                    files = list_files(browser.new_page(viewport={"width": 1400, "height": 1000}), psi_id)
                    break
                except Exception as error:
                    if attempt == 3:
                        raise
                    print(f"PSI-{psi_id}: {type(error).__name__}, retrying", flush=True)
                    time.sleep(5)
                finally:
                    browser.close()
            total = sum(f["size_mb"] or 0 for f in files)
            print(f"PSI-{psi_id:<4} {name:<15} {len(files):>5} files, {total / 1024:>8.2f} GB", flush=True)
            rows.extend({"psi_id": f"PSI-{psi_id}", "name": name, **f} for f in files)
            time.sleep(1.5)  # stay polite with the NASA server

    with open(FILES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
