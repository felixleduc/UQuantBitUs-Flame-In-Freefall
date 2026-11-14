"""Download the documents listed in data/files.csv: text, PDF, CSV, Excel, Word and the like.

Videos, images and archives are never downloaded, except the small metadata archive of
each investigation. Files already on disk are skipped, so the script can be run again
after an interruption. Run list_psi_files.py first: it writes data/files.csv.

Usage:
    uv run python src/download_psi_files.py                    # all investigations
    uv run python src/download_psi_files.py 25 99              # only PSI-25 and PSI-99
    uv run python src/download_psi_files.py --no-raw           # skip the "Raw Data" folders
    uv run python src/download_psi_files.py --max-mb 20        # skip files above 20 MB (default 100)

Output:
    data/raw/PSI-<id>_<name>/<folder>/<file>     (not committed: see .gitignore)
"""

import argparse
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from list_psi_files import INVESTIGATIONS, ROOT, ROWS, in_fresh_browser, kind_of, read_inventory, walk_tree

RAW = ROOT / "data" / "raw"
METADATA_FOLDER = "Investigation Metadata Files"


def destination(row: dict) -> Path:
    return RAW / f"{row['psi_id']}_{row['name']}" / row["folder"] / row["file"]


def download(page: Page, psi_id: int, wanted: dict[tuple[str, str], dict]) -> int:
    """Download the wanted files of one investigation that are not on disk yet."""
    folders = {folder for folder, _ in wanted}
    selected = page.locator("app-geode-tree .panel-heading")
    done = 0

    def on_file(index: int, row: dict, path: list[str]) -> None:
        nonlocal done
        entry = wanted.get(("/".join(path), row["name"]))
        if entry is None or destination(entry).exists():
            return
        name = page.locator(ROWS).nth(index).locator(".inline-flex")
        name.click()  # select the file: the Download button appears
        selected.filter(has_text="Selected: 1").wait_for(timeout=10_000)
        # The button opens the file's storage address in a new tab. Depending on the file,
        # the browser then downloads it or tries to display it (and fails for a PDF in a
        # headless browser), so the address is caught and fetched here instead.
        with page.context.expect_event("request", lambda r: "amazonaws.com" in r.url, timeout=60_000) as opened:
            page.locator("app-geode-tree .actions-panel button").first.click()
        response = page.context.request.get(opened.value.url, timeout=600_000)
        target = destination(entry)
        if response.ok:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.body())
            size_mb = target.stat().st_size / 1024**2
            listed = float(entry["size_mb"] or 0)
            if abs(size_mb - listed) > max(0.02 * listed, 0.01):
                print(f"  size differs from the listing ({size_mb:.2f} MB, listed {listed} MB): {target.name}", flush=True)
            done += 1
        else:  # some listed files are gone from the PSI storage: report and carry on
            print(f"  not available on the server (HTTP {response.status}): {entry['folder']}/{row['name']}", flush=True)
        response.dispose()
        for tab in page.context.pages:
            if tab != page:
                tab.close()
        name.click()  # deselect
        selected.filter(has_text="Selected: 0").wait_for(timeout=10_000)
        time.sleep(0.5)  # stay polite with the NASA server

    def enter(path: list[str]) -> bool:
        here = "/".join(path)
        return any(folder == here or folder.startswith(here + "/") for folder in folders)

    walk_tree(page, psi_id, on_file, enter)
    return done


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("ids", nargs="*", type=int, help="PSI ids (default: all)")
    parser.add_argument("--no-raw", action="store_true", help='skip the "Raw Data" folders')
    parser.add_argument("--max-mb", type=float, default=100, help="skip larger files (default: 100)")
    args = parser.parse_args()

    inventory = read_inventory()
    for row in inventory:  # kinds follow the current rules, even for an older inventory
        row["kind"] = kind_of(row["extension"])
    with sync_playwright() as p:
        for psi_id, name in INVESTIGATIONS:
            if args.ids and psi_id not in args.ids:
                continue
            rows = [
                r for r in inventory
                if r["psi_id"] == f"PSI-{psi_id}"
                and (r["kind"] == "document" or r["folder"] == METADATA_FOLDER)
                and not (args.no_raw and r["folder"].startswith("Raw Data"))
            ]
            too_big = [r for r in rows if float(r["size_mb"] or 0) > args.max_mb]
            wanted = {(r["folder"], r["file"]): r for r in rows if r not in too_big}
            missing = [r for r in wanted.values() if not destination(r).exists()]
            done = 0
            if missing:
                # After a crash the retry skips what is already on disk.
                done = in_fresh_browser(p, f"PSI-{psi_id}", lambda page: download(page, psi_id, wanted))
            left = sum(not destination(r).exists() for r in wanted.values())
            print(f"PSI-{psi_id:<4} {name:<15} {done:>4} downloaded, {len(wanted) - len(missing):>4} already there, "
                  f"{left} missing, {len(too_big)} above {args.max_mb:g} MB", flush=True)
            for r in too_big:
                print(f"  skipped ({r['size']}): {r['folder']}/{r['file']}", flush=True)


if __name__ == "__main__":
    main()
