"""Download the useful files listed in data/files.csv.

By default only the files marked useful = yes or maybe are fetched: test tables, measured
conditions, analysed results, calibrations, reports and the documents that explain them,
plus the few nobody has reviewed (the rules are USEFUL in list_psi_files.py). With --all, every document is fetched (PDF,
Word, Excel, PowerPoint, CSV, text). Videos, images, archives and camera formats never are.

The work is spread over several browsers running side by side (8 by default), each taking
its own share of the folders. Files already on disk are skipped, so the script can be
interrupted and run again. Run list_psi_files.py first: it writes data/files.csv.

Usage:
    uv run python src/download_psi_files.py                    # useful files, all investigations
    uv run python src/download_psi_files.py --all              # every document, useful or not
    uv run python src/download_psi_files.py 25 99              # only PSI-25 and PSI-99
    uv run python src/download_psi_files.py --workers 4        # fewer browsers (less memory)
    uv run python src/download_psi_files.py --max-mb 20        # skip files above 20 MB (default 100)
    uv run python src/download_psi_files.py --part 2/3         # one machine out of 3: only the
                                                               # second third of the folders

Output:
    data/raw/PSI-<id>_<name>/<folder>/<file>     (not committed: see .gitignore)
"""

import argparse
import html
import os
import re
import subprocess
import sys
import time
import zlib
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from list_psi_files import INVESTIGATIONS, ROOT, ROWS, in_fresh_browser, read_inventory, walk_tree

RAW = ROOT / "data" / "raw"
Share = tuple[int, int]  # (k, n): the k-th of n equal shares of the folders


def safe(name: str, limit: int = 150) -> str:
    """A folder or file name every system accepts: some PSI folders are named after a whole
    article citation, too long for a file system and with characters Windows refuses."""
    name = re.sub(r'[<>:"\\|?*]', "_", html.unescape(name)).strip(" .")
    if len(name) > limit:
        stem, dot, extension = name.rpartition(".")
        name = f"{stem[:limit - len(extension) - 1]}.{extension}" if dot and len(extension) <= 5 else name[:limit]
    return name.strip(" .")


def destination(row: dict) -> Path:
    folders = [safe(part) for part in row["folder"].split("/")]
    return RAW.joinpath(f"{row['psi_id']}_{row['name']}", *folders, safe(row["file"]))


def select(inventory: list[dict], psi_id: int, max_mb: float, share: Share, everything: bool = False) -> tuple[dict, list[dict]]:
    """Files of one investigation to download in this share: ({(folder, file): row}, too big)."""
    k, n = share
    rows = [
        r for r in inventory
        if r["psi_id"] == f"PSI-{psi_id}"
        and (r["useful"] in ("yes", "maybe") or (everything and r["kind"] == "document"))
        # A folder always falls in the same share, whatever the machine.
        and zlib.crc32(f"{psi_id}/{r['folder']}".encode()) % n == k - 1
    ]
    too_big = [r for r in rows if float(r["size_mb"] or 0) > max_mb]
    return {(r["folder"], r["file"]): r for r in rows if r not in too_big}, too_big


def download(page: Page, psi_id: int, wanted: dict[tuple[str, str], dict]) -> None:
    """Download the wanted files of one investigation that are not on disk yet."""
    # Only the folders that still miss a file are opened: a rerun goes straight to them.
    folders = {folder for (folder, _), entry in wanted.items() if not destination(entry).exists()}
    selected = page.locator("app-geode-tree .panel-heading")

    def on_file(index: int, row: dict, path: list[str]) -> None:
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
        else:  # some listed files are gone from the PSI storage: report and carry on
            print(f"  not available on the server (HTTP {response.status}): "
                  f"PSI-{psi_id} {entry['folder']}/{row['name']}", flush=True)
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


def run_share(inventory: list[dict], ids: list[int], max_mb: float, share: Share, everything: bool) -> None:
    """Download one share of the folders, one investigation after the other, in one browser."""
    with sync_playwright() as p:
        for psi_id in ids:
            wanted, _ = select(inventory, psi_id, max_mb, share, everything)
            if any(not destination(r).exists() for r in wanted.values()):
                # After a crash the retry skips what is already on disk.
                in_fresh_browser(p, f"PSI-{psi_id}", lambda page: download(page, psi_id, wanted))


def run_workers(ids: list[int], max_mb: float, parts: list[int], of: int, everything: bool, count_on_disk) -> None:
    """Run these parts (out of `of`) at once, each in its own process, restarting those that crash."""
    def start(part: int) -> subprocess.Popen:
        command = [sys.executable, __file__, *map(str, ids), "--max-mb", str(max_mb), "--part", f"{part}/{of}", "--child"]
        command += ["--all"] if everything else []
        return subprocess.Popen(command, env={**os.environ, "PYTHONUNBUFFERED": "1"})

    running = {}
    restarts = dict.fromkeys(parts, 0)
    try:
        for part in parts:
            running[part] = start(part)
            time.sleep(2)
        last_report = time.time()
        while running:
            time.sleep(2)
            for part, process in list(running.items()):
                code = process.poll()
                if code is None:
                    continue
                del running[part]
                if code != 0 and restarts[part] < 5:  # typically a browser crash when memory is short
                    restarts[part] += 1
                    print("  a browser stopped, restarting it", flush=True)
                    running[part] = start(part)
            if time.time() - last_report > 60:
                last_report = time.time()
                have, total = count_on_disk()
                print(f"{have} of {total} files on disk", flush=True)
    finally:
        for process in running.values():  # Ctrl-C: stop the browsers too
            process.terminate()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("ids", nargs="*", type=int, help="PSI ids (default: all)")
    parser.add_argument("--all", action="store_true", help="every document, not only those marked useful")
    parser.add_argument("--workers", type=int, default=8, help="browsers running side by side (default: 8)")
    parser.add_argument("--max-mb", type=float, default=100, help="skip larger files (default: 100)")
    parser.add_argument("--part", default="1/1", metavar="K/N",
                        help="only the K-th of N equal shares of the folders, to split the work between machines")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)  # one of the browsers of a run
    args = parser.parse_args()
    k, n = (int(x) for x in args.part.split("/"))
    ids = [psi_id for psi_id, _ in INVESTIGATIONS if not args.ids or psi_id in args.ids]
    inventory = read_inventory()

    if args.child or args.workers <= 1:
        run_share(inventory, ids, args.max_mb, (k, n), args.all)
        if args.child:
            return
    else:
        selections = [select(inventory, psi_id, args.max_mb, (k, n), args.all)[0] for psi_id in ids]

        def count_on_disk() -> tuple[int, int]:
            rows = [r for wanted in selections for r in wanted.values()]
            return sum(destination(r).exists() for r in rows), len(rows)

        have, total = count_on_disk()
        print(f"{total} files wanted, {have} already on disk, {args.workers} browsers", flush=True)
        # Part k of n is cut again into one share per browser: the folders whose number,
        # modulo n * workers, is k - 1, k - 1 + n, k - 1 + 2n, ...
        parts = [(k - 1) + j * n + 1 for j in range(args.workers)]
        run_workers(ids, args.max_mb, parts, n * args.workers, args.all, count_on_disk)

    for psi_id, name in INVESTIGATIONS:
        if psi_id not in ids:
            continue
        wanted, too_big = select(inventory, psi_id, args.max_mb, (k, n), args.all)
        missing = [r for r in wanted.values() if not destination(r).exists()]
        print(f"PSI-{psi_id:<4} {name:<15} {len(wanted) - len(missing):>5} of {len(wanted):>5} files on disk"
              + (f", {len(too_big)} above {args.max_mb:g} MB skipped" if too_big else ""), flush=True)
        for r in too_big:
            print(f"  skipped ({r['size']}): {r['folder']}/{r['file']}", flush=True)
        for r in missing[:20]:
            print(f"  missing: {r['folder']}/{r['file']}", flush=True)
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more missing", flush=True)


if __name__ == "__main__":
    main()
