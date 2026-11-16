"""Train the model behind the dashboard: will a flame keep burning?

Data: every flight test of data/processed/tests.csv that has a flame outcome, oxygen and
pressure: solid materials (BASS, BASS-II, Saffire), gas burners (BRE, s-Flame), normal gas-jet
flames (Flame Design, CFI-G, CLD, E-FIELD, SPICE, SLICE) and droplets (FLEX, FLEX-2, CFI).
Left out: inverse flames (their O2 is the burner jet, not the surrounding air), smoke and
aerosol tests (no flame) and aborted tests.

Target, kept burning:
    solids and gas flames: burned, burned out, flow terminated, extinguished at low flow or by
    N2, smoke point reached, lifted flame, fuel depleted, versus no ignition, brief flame,
    self-extinguished, blown off;
    droplets: burned out (the fuel was used up) versus extinction (the flame went out first).

One logistic regression for all. Each fuel type has its own oxygen response; the pressure
response is one per group:
    condensed: solids and gas burners. BRE is NASA's emulator of a burning solid and was flown
        at 0.54 to 1 atm, so solids borrow its pressure response (every solid was flown at
        about 1 atm). The burner's fuel flow is an input, so that pressure does not stand in
        for a fuel flow difference;
    jet: normal gas-jet flames;
    droplet: droplets.
Each fuel or material has its own offset, solids also by sample shape and air flow
(log(1 + flow) and its square: both too little and too much flow can put a flame out).

Validation: 5-fold cross-validation repeated 5 times; on solid tests the pooled model is
compared with a model trained on solids only. Likely range: 5th to 95th percentile of 200
refits on bootstrap resamples.

Output: dashboard/data/model.json, the coefficients the dashboard needs to predict a solid in
any oxygen, pressure and flow (dashboard/lib/model.ts), for the full fit and every refit;
dashboard/data/flight-tests.json, the tests the model learned from, with their label.

Usage:
    uv run python ML.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold

ROOT = Path(__file__).resolve().parent
TESTS = ROOT / "data" / "processed" / "tests.csv"
OUT = ROOT / "dashboard" / "data" / "model.json"
TRAINING = ROOT / "dashboard" / "data" / "flight-tests.json"  # the tests the model learned from

KEPT = {"burned", "burned out", "flow terminated", "extinguished at low flow", "extinguished by N2",
        "smoke point reached", "no smoke point", "lifted flame", "stable lifted flames", "fuel depleted"}
WENT_OUT = {"no ignition", "brief flame", "self-extinguished", "blown off"}
GROUPS = {"solid": "condensed", "gas burner": "condensed", "gas jet": "jet", "droplet": "droplet"}
O2_CENTER, O2_SCALE = 21.0, 3.0  # oxygen enters as (O2 - 21) / 3
BOOTSTRAPS = 200


def label(row) -> float | None:
    outcome = str(row.outcome)
    if row.fuel_type == "droplet":
        if outcome == "burned out":
            return 1
        return 0 if "extinction" in outcome or outcome == "no ignition" else None
    if outcome in KEPT:
        return 1
    return 0 if outcome in WENT_OUT else None


def load() -> pd.DataFrame:
    tests = pd.read_csv(TESTS, low_memory=False)
    data = tests[tests.fuel_type.isin(GROUPS) & ~tests.geometry.fillna("").str.startswith("inverse")].copy()
    data["kept_burning"] = data.apply(label, axis=1)
    data = data.dropna(subset=["kept_burning", "o2_percent"])
    # SPICE, SLICE and E-FIELD ran in the glovebox or chamber at cabin pressure without logging it
    data["pressure_atm"] = data.pressure_atm.fillna(1.0)
    data = data[(data.pressure_atm > 0.2) & (data.o2_percent > 5)]
    # Solids need an air flow; gas flames and droplets do not use it
    data = data[(data.fuel_type != "solid") | data.flow_cm_s.notna()]
    data["group"] = data.fuel_type.map(GROUPS)
    data["geometry"] = data.geometry.fillna("unknown")
    data["material_family"] = data.material_family.fillna("unknown")
    # Fuels with fewer than 5 tests share one offset per fuel type (all solids keep their own)
    counts = data.groupby(["fuel_type", "material_family"]).test_id.transform("size")
    data["fuel_key"] = np.where((data.fuel_type == "solid") | (counts >= 5),
                                data.fuel_type + ":" + data.material_family, data.fuel_type + ":other")
    data["kept_burning"] = data.kept_burning.astype(int)
    return data


def design(data: pd.DataFrame) -> pd.DataFrame:
    """The model's inputs, written out so that dashboard/lib/model.ts can rebuild them."""
    columns = {}
    for g in ["condensed", "jet", "droplet"]:
        member = (data.group == g).astype(float)
        columns[f"group:{g}"] = member
        columns[f"lnp:{g}"] = member * np.log(data.pressure_atm)
    for fuel_type in ["solid", "gas burner", "gas jet", "droplet"]:
        member = (data.fuel_type == fuel_type).astype(float)
        columns[f"o2:{fuel_type}"] = member * (data.o2_percent - O2_CENTER) / O2_SCALE
    # Burner fuel flow (slpm, N2-equivalent), read in the notes; tests without it get the median
    burner = (data.fuel_type == "gas burner").astype(float)
    fuel = data.notes.fillna("").str.extract(r"burner flow: fuel bottle ([\d.]+)")[0].astype(float)
    fuel = np.log(fuel.where(burner > 0).fillna(fuel[burner > 0].median()))
    columns["burner_fuel"] = burner * (fuel - fuel[burner > 0].mean())
    for key in sorted(data.fuel_key.unique()):
        columns[key] = (data.fuel_key == key).astype(float)
    solid = (data.fuel_type == "solid").astype(float)
    for shape in sorted(data.loc[data.fuel_type == "solid", "geometry"].unique()):
        columns[f"shape:{shape}"] = solid * (data.geometry == shape)
    log_flow = np.log1p(data.flow_cm_s.fillna(0))
    columns["flow1"] = solid * log_flow
    columns["flow2"] = solid * log_flow**2
    for diluent in ["He", "CO2"]:
        columns[f"diluent:{diluent}"] = data.diluent.fillna("").str.contains(diluent).astype(float)
    return pd.DataFrame(columns, index=data.index)


def fit(x: pd.DataFrame, y: pd.Series) -> LogisticRegression:
    return LogisticRegression(C=1.0, max_iter=5000).fit(x, y)


def coefficients(model: LogisticRegression, names: list[str]) -> dict:
    """Only what the dashboard needs to predict a solid."""
    weights = dict(zip(names, model.coef_[0]))
    keep = [n for n in names if n.startswith(("solid:", "shape:")) or n in
            {"group:condensed", "o2:solid", "lnp:condensed", "flow1", "flow2"}]
    return {"intercept": round(float(model.intercept_[0]), 4), **{n: round(float(weights[n]), 4) for n in keep}}


def validate(data: pd.DataFrame, x: pd.DataFrame, y: pd.Series) -> dict:
    folds = RepeatedStratifiedKFold(n_splits=5, n_repeats=5, random_state=0)
    strata = data.group + y.astype(str)
    pooled, solid_only, truth, by_group = [], [], [], {g: ([], []) for g in ["condensed", "jet", "droplet"]}
    solid_rows = (data.fuel_type == "solid").to_numpy()
    for train, test in folds.split(x, strata):
        model = fit(x.iloc[train], y.iloc[train])
        p = model.predict_proba(x.iloc[test])[:, 1]
        for g, (ps, ys) in by_group.items():
            mask = (data.group.iloc[test] == g).to_numpy()
            ps.extend(p[mask]); ys.extend(y.iloc[test][mask])
        # solid test rows: pooled model against a model that only saw solids
        test_solid = test[solid_rows[test]]
        train_solid = train[solid_rows[train]]
        if len(test_solid) and y.iloc[train_solid].nunique() == 2:
            alone = fit(x.iloc[train_solid], y.iloc[train_solid])
            pooled.extend(model.predict_proba(x.iloc[test_solid])[:, 1])
            solid_only.extend(alone.predict_proba(x.iloc[test_solid])[:, 1])
            truth.extend(y.iloc[test_solid])

    def score(ys, ps):
        return {"roc_auc": round(float(roc_auc_score(ys, ps)), 3), "brier": round(float(brier_score_loss(ys, ps)), 3)}

    return {
        "by_group": {g: {"tests": int((data.group == g).sum()), **score(ys, ps)} for g, (ps, ys) in by_group.items()},
        "solids_pooled": score(truth, pooled),
        "solids_only_model": score(truth, solid_only),
        "solids_baseline_brier": round(float(np.mean((np.array(truth) - np.mean(truth)) ** 2)), 3),
    }


def main() -> None:
    data = load()
    x, y = design(data), data.kept_burning
    names = list(x.columns)
    print(f"{len(data)} flight tests with a flame outcome, oxygen and pressure:")
    print(data.groupby(["group", "fuel_type"]).kept_burning.agg(tests="size", kept_burning="mean").round(2).to_string())

    metrics = validate(data, x, y)
    print("cross-validation:", json.dumps(metrics, indent=1))

    full = fit(x, y)
    rng = np.random.default_rng(0)
    refits = []
    while len(refits) < BOOTSTRAPS:
        sample = rng.integers(0, len(data), len(data))
        if y.iloc[sample].nunique() == 2:
            refits.append(coefficients(fit(x.iloc[sample], y.iloc[sample]), names))

    w = coefficients(full, names)
    print(f"solids: O2 {w['o2:solid']:+.2f} per 3 points; condensed ln(pressure) {w['lnp:condensed']:+.2f}")

    solids = data[data.fuel_type == "solid"]
    burners = data[data.fuel_type == "gas burner"]
    OUT.write_text(json.dumps({
        "trained_on": int(len(data)),
        "tests_by_type": {k: int(v) for k, v in data.fuel_type.value_counts().items()},
        "metrics": metrics,
        "o2_center": O2_CENTER,
        "o2_scale": O2_SCALE,
        "solids": {
            "tests": int(len(solids)),
            "o2_range": [float(solids.o2_percent.min()), float(solids.o2_percent.max())],
            "pressure_range_atm": [round(float(solids.pressure_atm.min()), 2), round(float(solids.pressure_atm.max()), 2)],
            "dominant_shape": solids.groupby("material_family").geometry.agg(lambda s: s.mode().iloc[0]).to_dict(),
        },
        "pressure_source": {
            "investigations": sorted(burners.investigation.unique()),
            "pressure_range_atm": [round(float(burners.pressure_atm.min()), 2), round(float(burners.pressure_atm.max()), 2)],
            "o2_range": [round(float(burners.o2_percent.min()), 1), round(float(burners.o2_percent.max()), 1)],
        },
        "coefficients": w,
        "refits": refits,
    }))
    columns = ["psi_id", "investigation", "test_id", "fuel_type", "material_family", "geometry",
               "o2_percent", "pressure_atm", "flow_cm_s", "outcome", "kept_burning"]
    rows = data[columns].assign(pressure_atm=data.pressure_atm.round(3), o2_percent=data.o2_percent.round(2))
    TRAINING.write_text(json.dumps([{k: v for k, v in r.items() if pd.notna(v)} for r in rows.to_dict("records")]))
    print(f"wrote {TRAINING.relative_to(ROOT)} ({TRAINING.stat().st_size / 1024:.0f} KB, {len(rows)} tests)")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
