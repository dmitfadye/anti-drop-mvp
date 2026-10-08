# Font specification

Downloaded directly from the user-specified Asket source on 2026-10-08. Bundled Asket fonts are local, loaded with next/font/local, and have Cyrillic and U+20BD verified with fontTools. The main UI now uses the installed system font stack at the user's request. No external runtime font services or new npm dependencies.

| Role | Actual file | Actual weight |
| --- | --- | --- |
| Navigation, forms, tables, body | Segoe UI / system-ui (installed, no redistributed binary) | 400 |
| Page descriptions | Asket-Extended-Light.otf | 300 |
| Titles, prominent figures, strong text | Asket-Extrabold.otf | 800 |

font-synthesis is disabled. No static font is declared as variable. Asket Narrow Light has been removed from the UI font loader because the user found it unpleasant at small sizes. Its binary is retained as an unused supplied asset. Asket Extended Light remains for page descriptions. Third-party attribution is in frontend/public/fonts/ATTRIBUTION.md and Settings > About.

Requested Halvar Breitschrift is NOT installed. The user-provided WebFonts download redirects to a fontsloader URL returning 404. The foundry sells Halvar with separate web licensing (https://www.typemates.com/fonts/halvar/buy). No purchase was made. Asket ExtraBold is an explicitly temporary heading substitute; this is a material visual difference. Normal-width Asket Light/Regular were also not in the freely downloadable four-style bundle.

Once the intended Halvar and normal-width Asket files become available, inspect real weights/cmap, change the local font declarations, then retune line wraps and repeat screenshots. Do not silently rename a substitute to Halvar.

## Readability revision

On 2026-10-08 the user explicitly requested replacing the small main font. Navigation, tables, forms, buttons and captions now use Segoe UI/system-ui at regular weight 400. Heading typography stays unchanged. Verified by lint, typecheck, build and all 16 E2E tests; refreshed screenshots cover five widths.
