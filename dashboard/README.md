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
| Habitat check (`/`) | Would this material keep burning in this habitat, and which change would stop it? | demo model + closest real flight tests + report findings |
| Flammability map (`/map`) | Where are the real tests, and where is the line between burning and going out? | real tests + demo model line |
| Space tests (`/tests`) | Every solid-material test flown | real |
| Findings (`/findings`) | What the NASA reports concluded, with quotes | real |
| Coverage (`/coverage`) | How much evidence stands behind each material | real |

The scenario (material, habitat, oxygen, pressure, ventilation) is shared by every page.

## Data

- `data/tests.json` and `data/findings.json` are written by `uv run python src/export_dashboard_data.py`
  (repository root) from `data/processed/`, and validated in `lib/data.ts`.
- `lib/demo-model.ts` holds invented coefficients. Replace `burnProbability` with the trained model
  (same inputs, a probability from 0 to 1) and remove the "Demo model" badges.
