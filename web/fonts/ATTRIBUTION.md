# Self-hosted fonts

All three typefaces are licensed under the SIL Open Font License 1.1 (OFL),
which permits bundling and self-hosting. Only the latin `wght` variable subset
is vendored here (one woff2 per family) to keep the payload small and the CSP
clean (fonts served same-origin, `font-src 'self'`). Loaded via `next/font/local`.

| File | Family | Designer | License | Source |
|---|---|---|---|---|
| `archivo-latin-wght-normal.woff2` | Archivo (Variable) | Omnibus-Type | OFL 1.1 | Google Fonts / Fontsource |
| `hanken-grotesk-latin-wght-normal.woff2` | Hanken Grotesk (Variable) | Alfredo Marco Pradil | OFL 1.1 | Google Fonts / Fontsource |
| `spline-sans-mono-latin-wght-normal.woff2` | Spline Sans Mono (Variable) | Anthony Sinh Cao / SolType | OFL 1.1 | Google Fonts / Fontsource |

Roles in VayuDrishti: Archivo = display / instrument headers, Hanken Grotesk =
body / UI, Spline Sans Mono = numeric readouts (timestamps, coordinates, metrics).
Deliberately not the Inter / Space Grotesk / JetBrains Mono default stack.
