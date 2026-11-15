"""List the files of each PSI combustion investigation that are worth downloading.

The PSI repository (https://psi.nasa.gov/physci/repo) is a JavaScript app, so each public
investigation page is opened in a headless browser. This script walks the "Data files and
documents" tree of each page (about 66,000 files, 12 TB, mostly videos and images) and keeps
the ones useful for the dashboard: verdict "yes", or "maybe" for the few nobody has opened.
The verdict comes from the USEFUL rules below. Nothing is downloaded here:
download_psi_files.py fetches the listed files.

Usage:
    uv run python src/list_psi_files.py            # all investigations
    uv run python src/list_psi_files.py 25 99      # only PSI-25 and PSI-99

Output:
    data/files.csv    one row per kept file: folder, name, kind, verdict, what it contains,
                      size and date. Saved after each investigation; a run replaces only the
                      rows of the investigations it visits.
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
FIELDS = ["psi_id", "name", "folder", "file", "extension", "kind", "useful", "content", "size", "size_mb", "date_added"]
UNITS = {"B": 1 / 1024**2, "KB": 1 / 1024, "MB": 1, "GB": 1024, "TB": 1024**2}
KINDS = {
    "document": {"pdf", "doc", "docx", "xls", "xlsx", "csv", "txt", "rtf", "ppt", "pptx"},
    "video": {"mp4", "mpg", "mpeg", "avi", "mov", "wmv", "m4v", "mkv", "ts"},  # ts: MPEG transport stream
    "image": {"jpg", "jpeg", "png", "tif", "tiff", "bmp", "gif", "eps", "svg", "raw", "cr2", "nef"},
    "archive": {"zip", "tar", "gz", "tgz", "7z", "rar"},
}

# Is a file useful for the dashboard? Each rule is (pattern searched in "<investigation>/<folder>/<file>",
# verdict, what the file is); the first match wins. Written after opening examples of every type.
# Verdicts: "yes", "no", or "maybe" for the few files nobody opened.
USEFUL = [
    (r"/Investigation Metadata Files/", "yes", "NASA's description of the experiment: DOI, objectives, publications"),
    (r"^[^/]+/Experimental table/", "yes", "summary table of all tests"),
    # Hardware bookkeeping, photo indexes, duplicates
    (r"Cama?era_Sett+ings|CameraConfigure|_Exposures\.txt|_CAM\d_Exp|Filter_Positions|LCTF_Wavelen", "no", "camera and optics settings"),
    (r"Test_?p\w*nt_Settings|_from_log\.txt", "no", "test-point hardware settings"),
    (r"Comment|MissingImageData|_Readme\.txt|Readme-Test", "no", "notes on image downlink and data handling"),
    (r"Proof_?Sheet|Contact_?Sheet|PictureBook|pic_info|_num\.txt|Image[ _]Directory|ImageFrameSizes|Image Organization"
     r"|MergeResult|Images_From|DAFT Images|/(\d{2,3}CH4_[\d._]+|\d{4}_\d{4})\.pdf$|Soot_Image|BacklitSample|nikon"
     r"|^SAME-R/Raw Data/.*\.(pptx?|pdf)$|\.txt\.docx$", "no", "photo index, thumbnails or image samples"),
    (r"TM graphs|Figure for TM|StitchedCO|Thermocouple Placement", "no", "pictures of plots or diagrams"),
    (r"TestSheet\.rtf", "no", "duplicate of the .txt test sheet"),
    (r"(PTrk|DTrk)\d+\.txt", "yes", "particle counts recorded by the instruments"),
    (r"Chamber_(Gases|Contents)|_Mixture\.txt", "yes", "gas composition of the chamber for the test"),
    (r"^(FLEX-2|CFI)/.*Chamber_Readings", "yes", "chamber pressure and temperature during the test"),
    (r"_data[ ()\d]*\.csv|mfcSetpoints|Radiometer_Readings|Chamber_Readings|HKPData|Raw telemetry|RadiometerData"
     r"|Cool_Flames\.txt|PTandMFC|_Radiometer\.pdf|Pressure_Temperature\.pdf", "no", "raw instrument log"),
    (r"/(PSI-\d+_[A-Za-z ]+_)?[A-Za-z0-9]*\d[A-Z]\.txt$", "no", "image time stamps of one camera"),
    (r"/(PSI-\d+_[A-Za-z ]+_)?(as run)?[A-Za-z0-9]+(_\d)?\.txt$|_BRE\.txt|_VoltageSweep\.txt", "yes",
     "test-point definition or log: commanded flows, fuel concentration, voltages, igniter settings, average pressure"),
    (r"_TP\.txt", "yes", "timing of the test: ignition, extinction detected, flows off"),
    (r"Event_Log_entry", "no", "operator log entries without extractable text"),
    (r"test sheets\.pdf", "yes", "scanned handwritten science sheet per test: conditions and flame behaviour (needs a vision model or manual reading)"),
    (r"flow traces", "yes", "daily notes per test (ignition success or failure, settings) with flow plots"),
    (r"test param\w* notes|test point log\.pdf|velocity traces|_MFCA_all\.pdf|^CLD-Flame/Raw Data/.*/(PSI-21_Raw Data_)?\d{5}\.pdf$",
     "no", "scanned parameter printouts, image-count logs or plots"),
    (r"Operations\.pdf|SFS-W-|Offgassing|Crew Training|Crew Interface|Software|ACME-DOC-010|Procedure|VIDEO OVERLAY|Operations Manual"
     r"|_Ops\.|Hardware Presentation|Engineering Req|ERD\.|EIRD|Drawing|AcceptanceReview|DesignReview", "no", "operations, software or hardware paperwork"),
    (r"fact[ _]sheet|info[ _]sheet|Unlocking|Researchers[ _]Guide|benefits|TaskbookPubs|Presentation|Symposium|ASGSR|CSSCI|Conference",
     "no", "outreach or presentation material"),
    # Conditions, results and explanations
    (r"As Run_Test Matrix", "yes", "as-run test matrix: conditions and observation notes for every test"),
    (r"Test\.Matrices|Planned_Test Matrix", "no", "same columns as the experimental table, or planned values"),
    (r"(calibration|Flow Duct Cal|MASS_FLOW|Airflow_Test|Flow settings|FlowCalculator|RawDataConversion)[^/]*$", "yes",
     "calibration: converts instrument settings into physical units"),
    (r"Sensor Data|Sensors\.xlsx|Telemetry Data|Data_Table[^/]*EU\.csv", "yes", "measured oxygen, CO2, airflow, pressure and temperatures during the burn"),
    (r"Read ?me\.docx|data[ _]interpretation|data[ _]file[ _]description|DoD\.|Sample descriptions", "yes", "explains the data files and how to read them"),
    (r"/Reports/|Final[ _]?R(e)?p(or)?t|Summary Report|Dissertation|30-?Day|YearReport|TaskbookRpts", "yes", "report: results and conclusions in prose"),
    (r"DataSummary|Test_Summary|Retrieved Data Summary|Results\.xlsx|Daily Test Point Log[^/]*\.xlsx", "yes", "results table covering all tests"),
    (r"TestSheet\.(txt|pdf)|DropletData|DropletHistory|LLUVData|ColorCamData|CoolFlameData|Summary|DropHist|DLDanalysis|Results\.(xls|pdf)"
     r"|Radial_Intensity|BurningHistory|Profiles\.pdf|/(PSI-69_Raw Data_)?FLEX-\d+\.pdf$",
     "yes", "per-test conditions and analysed droplet and flame results"),
    (r"Chamber Calculator", "yes", "chamber gas composition for each test"),
    (r"Coagulation", "yes", "smoke particle concentration and size before and after ageing"),
    (r"/Analyzed Data/.*(testlog| log\b)", "no", "command log of the instrument"),
    (r"/Analyzed Data/", "yes", "analysed measurements"),
    (r"SRD|SCR|ISRD|SORD|Requirements|Test_Plan|Concept Description|DLD", "no", "requirements and plans written before the flight"),
    (r"/Science Documents/", "yes", "science document"),
    (r"/Engineering Documents/|/Reference Data/", "no", "hardware, software and engineering documents"),
    # Not opened one by one: kept, to be judged by whoever uses them
    (r"/Raw Data/.*\.(xlsx?|csv)$", "maybe", "data spreadsheet, not reviewed (probably measurements or calibration)"),
    (r"", "maybe", "other document, not reviewed (mostly published papers)"),
]

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


def usefulness(row: dict) -> tuple[str, str]:
    """(verdict, what the file is) for a row that has name, folder, file and kind."""
    if row["kind"] != "document" and "Investigation Metadata Files" not in row["folder"]:
        return "no", {"other": "instrument or camera format", "archive": "archive of images or videos"}.get(row["kind"], row["kind"])
    path = f"{row['name']}/{row['folder']}/{row['file']}"
    return next((verdict, what) for pattern, verdict, what in USEFUL if re.search(pattern, path, re.IGNORECASE))


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
    for row in rows:  # the verdicts always follow the current rules, even for an older inventory
        row["kind"] = kind_of(row["extension"])
        row["useful"], row["content"] = usefulness(row)
    return [row for row in rows if row["useful"] != "no"]


def main() -> None:
    wanted = {int(a) for a in sys.argv[1:]}
    todo = [inv for inv in INVESTIGATIONS if not wanted or inv[0] in wanted]
    rows = read_inventory()

    with sync_playwright() as p:
        for psi_id, name in todo:
            files = in_fresh_browser(p, f"PSI-{psi_id}", lambda page: list_files(page, psi_id))
            total = sum(f["size_mb"] or 0 for f in files)
            print(f"PSI-{psi_id:<4} {name:<15} {len(files):>5} files on the page, {total / 1024:>8.2f} GB", flush=True)
            # Replace the rows of this investigation and save at once, so a crash later loses nothing.
            rows = [r for r in rows if r["psi_id"] != f"PSI-{psi_id}"]
            for f in files:
                row = {"psi_id": f"PSI-{psi_id}", "name": name, **f}
                row["useful"], row["content"] = usefulness(row)
                if row["useful"] != "no":  # the files judged not useful are left out of the list
                    rows.append(row)
            with open(FILES_CSV, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            time.sleep(1.5)  # stay polite with the NASA server


if __name__ == "__main__":
    main()
