# Dashboard

Next.js, Tailwind v4 and shadcn/ui. Needs [bun](https://bun.sh) and Node 24. Deployed on Vercel
with `dashboard` as root directory; the build runs no Python.

```bash
bun install
bun run dev     # http://localhost:3000
bun run build   # static production build
```

| Page | Shows |
|---|---|
| Habitat check (`/`) | Verdict and likely range, what would stop it, closest flight tests, report findings |
| Flammability map (`/map`) | Model chance by oxygen and by air flow, with the matching flight tests |
| Space tests (`/tests`) | The 2,100 tests the model learned from, filterable |
| Findings (`/findings`) | Report findings with quote and source, by area, material and type |
| Coverage (`/coverage`) | Tests, outcomes, oxygen and pressure ranges per fuel type and material |

Material and atmosphere are shared by every page.

Data in `data/`, all written from the repository root and validated on load:
- `tests.json`, `findings.json`: `src/export_dashboard_data.py` (read by `lib/data.ts`)
- `model.json` (coefficients and resampled refits), `flight-tests.json`: `ML.py`
  (read by `lib/model.ts` and `lib/flight-tests.ts`)
