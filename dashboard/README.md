# Dashboard

Next.js, Tailwind v4 and shadcn/ui. Needs [bun](https://bun.sh) and Node 24.

```bash
bun install
bun run dev        # http://localhost:3000
bun run build      # production build (all pages are static)
```

## Pages

| Page | Question it answers | Data |
|---|---|---|
| Habitat check (`/`) | Would this material keep burning in this habitat, and which change would stop it? | trained model + closest real flight tests + report findings |
| Flammability map (`/map`) | Where did flames keep burning, by oxygen and air flow? | real tests |
| Space tests (`/tests`) | Every solid-material test flown | real |
| Findings (`/findings`) | What the NASA reports concluded, with quotes | real |
| Coverage (`/coverage`) | How much evidence stands behind each material | real |

The scenario (material, habitat, oxygen, pressure, ventilation) is shared by every page.

## Data

- `data/tests.json` and `data/findings.json` are written by `uv run python src/export_dashboard_data.py`
  (repository root) from `data/processed/`, and validated in `lib/data.ts`.
- `data/model.json` is written by `uv run python ML.py` (repository root): the trained model's
  predictions and likely ranges on a grid of oxygen and air flow per material, read by `lib/model.ts`.
