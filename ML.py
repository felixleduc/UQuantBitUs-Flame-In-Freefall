"""Train the model behind the dashboard: will a flame on this material keep burning?

Data: the solid-material flight tests of data/processed/tests.csv (BASS, BASS-II, Saffire).
Target: the flame kept burning (it burned out, or burned until the crew cut the flow or
used nitrogen) versus it went out on its own (no ignition, brief flame, self-extinguished,
blown off).
Inputs: material, sample shape, oxygen (%) and air flow (cm/s). Flow enters as log(1 + flow)
and its square, so the model can learn that both too little and too much flow put a flame out.
Pressure is not an input: every solid was flown at 0.97 to 1.01 atm, so the data cannot
teach its effect.

Validation: 5-fold cross-validation repeated 10 times, compared with always guessing the
most common outcome. Likely range: 5th and 95th percentiles of 200 models refitted on
bootstrap resamples.

Output: dashboard/data/model.json, the predicted chance (and likely range) for each material
on a grid of oxygen and flow, read by dashboard/lib/model.ts.

Usage:
    uv run python ML.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parent
TESTS = ROOT / "data" / "processed" / "tests.csv"
OUT = ROOT / "dashboard" / "data" / "model.json"

# Same rule as src/export_dashboard_data.py
SUSTAINED = {"burned", "burned out", "flow terminated", "extinguished at low flow", "extinguished by N2"}
NOT_SUSTAINED = {"no ignition", "brief flame", "self-extinguished", "blown off"}
INPUTS = ["material_family", "geometry", "o2_percent", "flow_cm_s"]

O2_GRID = np.arange(12, 40.5, 1.0)  # %
FLOW_GRID = np.arange(0, 51, 2.0)  # cm/s
BOOTSTRAPS = 200


def load() -> pd.DataFrame:
    tests = pd.read_csv(TESTS, low_memory=False)
    solids = tests[(tests.fuel_type == "solid") & tests.outcome.isin(SUSTAINED | NOT_SUSTAINED)]
    solids = solids.dropna(subset=["o2_percent", "flow_cm_s", "material_family"]).copy()
    solids["geometry"] = solids.geometry.fillna("unknown")
    solids["kept_burning"] = solids.outcome.isin(SUSTAINED).astype(int)
    return solids


def flow_terms(x) -> np.ndarray:
    log_flow = np.log1p(np.asarray(x, dtype=float))
    return np.hstack([log_flow, log_flow**2])


def make_model() -> Pipeline:
    features = ColumnTransformer([
        ("material", OneHotEncoder(handle_unknown="ignore"), ["material_family", "geometry"]),
        ("oxygen", StandardScaler(), ["o2_percent"]),
        ("flow", Pipeline([("terms", FunctionTransformer(flow_terms)), ("scale", StandardScaler())]), ["flow_cm_s"]),
    ])
    # L2 regularisation keeps materials with few tests (Ultem, silicone) from extreme values
    return Pipeline([("features", features), ("classifier", LogisticRegression(C=1.0, max_iter=2000))])


def validate(x: pd.DataFrame, y: pd.Series) -> dict:
    folds = RepeatedStratifiedKFold(n_splits=5, n_repeats=10, random_state=0)
    scores = {"balanced_accuracy": [], "roc_auc": [], "brier": []}
    for train, test in folds.split(x, y):
        model = make_model().fit(x.iloc[train], y.iloc[train])
        p = model.predict_proba(x.iloc[test])[:, 1]
        scores["balanced_accuracy"].append(balanced_accuracy_score(y.iloc[test], p >= 0.5))
        scores["roc_auc"].append(roc_auc_score(y.iloc[test], p))
        scores["brier"].append(brier_score_loss(y.iloc[test], p))
    return {
        **{k: round(float(np.mean(v)), 3) for k, v in scores.items()},
        # what always predicting the share of flames that kept burning would score
        "baseline_brier": round(float(np.mean((y - y.mean()) ** 2)), 3),
        "baseline_balanced_accuracy": 0.5,
        "baseline_roc_auc": 0.5,
    }


def grid_for(models: list[Pipeline], material: str, geometry: str) -> dict:
    o2, flow = np.meshgrid(O2_GRID, FLOW_GRID, indexing="ij")
    cells = pd.DataFrame({
        "material_family": material, "geometry": geometry,
        "o2_percent": o2.ravel(), "flow_cm_s": flow.ravel(),
    })
    shape = (len(O2_GRID), len(FLOW_GRID))
    predictions = np.array([m.predict_proba(cells)[:, 1] for m in models])

    def as_grid(values: np.ndarray) -> list:
        return np.round(values.reshape(shape), 3).tolist()

    return {
        "geometry": geometry,
        "p": as_grid(predictions[0]),
        "low": as_grid(np.percentile(predictions[1:], 5, axis=0)),
        "high": as_grid(np.percentile(predictions[1:], 95, axis=0)),
    }


def main() -> None:
    data = load()
    x, y = data[INPUTS], data.kept_burning
    print(f"{len(data)} solid flight tests, {y.mean():.0%} kept burning")

    metrics = validate(x, y)
    print("cross-validation:", metrics)

    full = make_model().fit(x, y)
    rng = np.random.default_rng(0)
    models = [full]
    while len(models) <= BOOTSTRAPS:
        sample = rng.integers(0, len(data), len(data))
        if y.iloc[sample].nunique() == 2:
            models.append(make_model().fit(x.iloc[sample], y.iloc[sample]))

    # Each material is predicted for the sample shape it was flown in most
    materials = {}
    for material, group in data.groupby("material_family"):
        geometry = group.geometry.mode().iloc[0]
        materials[material] = {"tests": int(len(group)), **grid_for(models, material, geometry)}
        print(f"  {material:<32} {len(group):>4} tests, predicted as {geometry}")

    OUT.write_text(json.dumps({
        "trained_on": int(len(data)),
        "kept_burning_share": round(float(y.mean()), 3),
        "metrics": metrics,
        "pressure_range_atm": [float(data.pressure_atm.min()), float(data.pressure_atm.max())],
        "o2": O2_GRID.tolist(),
        "flow": FLOW_GRID.tolist(),
        "materials": materials,
    }))
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
