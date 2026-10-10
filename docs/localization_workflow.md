# Localization workflow

One extra language, done properly, beats seven claimed languages. This document
describes the path a message takes from a machine draft to a translation the bank
could actually ship — and the places where it currently stops.

## Status ladder

| Status | Meaning | May be shown as approved? | May enter an experiment treatment arm? |
|---|---|---|---|
| `draft` | machine draft, no human has read it | no | no |
| `native_reviewed` | a native speaker signed off | no | no |
| `legal_reviewed` | legal/compliance signed the wording | no | no |
| `approved` | bank owner accepted it for use | yes | yes |
| `deprecated` | withdrawn from circulation | no | no |

`src/localization.py` enforces the ladder in code:

- a pack claiming `native_reviewed` without a `native_reviewer` entry is rejected;
- a pack claiming `legal_reviewed` without a `legal_reviewer` entry is rejected;
- `approved` additionally requires `approved_at` and a pseudonymised attestation
  for every reviewer;
- anything below `approved` produces a mandatory UI badge.

## Current state

| Locale | Script / direction | Status | Note |
|---|---|---|---|
| `ru-RU` | Cyrl / ltr | `draft` | control language; copy still needs bank legal review |
| `uz-UZ` | Latn / ltr | `draft` | treatment language; **not** reviewed by a native speaker |

`uz-UZ` is deliberately missing `privacy.notice`. The key resolves through the
`ru-RU` fallback and the response reports it in `used_fallback_keys`, so the gap
is visible in the UI and in the event stream as `translation_fallback` instead of
silently changing the meaning.

## Step by step

1. **Add the pack.** Create `locales/<locale>.json` from `locales/ru-RU.json`.
   Keep the same eight keys. The validator rejects HTML, entities, unknown keys
   and unknown placeholders.
2. **Create the variants.** One `templates/<name>_<locale>_<arm>_v1.json` per
   risk level. `risk_level` must match the decision it renders; `render_warning`
   refuses a mismatch.
3. **Run the validators.**

   ```bash
   PYTHONPATH=app python -m scripts.validate_localization   # or: PYTHONPATH=app python -c "from src.localization import validate_packs; print(validate_packs())"
   PYTHONPATH=app python -c "from src.templates import validate_templates; print(validate_templates())"
   ```

4. **Native review.** A native speaker fills in `docs/translation_checklist.md`
   and is recorded in `reviewers[]` with a pseudonym or a content hash — never a
   name.
5. **Legal review.** `docs/legal_text_review_checklist.md`, recorded in the same
   `reviewers[]` array with `legal_reviewer`.
6. **Set `status: approved`.** Only after both. The templates follow.
7. **Re-run evaluation and the smoke suite.** Copy changed; contracts did not.

## Hard rules enforced by the code

- messages are plain text: no HTML, no entities, no `javascript:`;
- interpolation only through `{amount}`, `{currency}`, `{reason_short}`,
  `{next_step}`, `{lang_name}`;
- forbidden phrases are rejected on **load and on render**, so a later copy edit
  cannot bypass the guard. The list covers categorical blocking/freeze claims,
  fixed sentencing, accusation of complicity, verified OTP and granted cashback;
- language never reaches the rules. `RiskSnapshotV1` has no language field at all,
  and `reports/evaluation/report.md` records an injection check that proves it.

## Fallback

`LocalizationRegistry.render` falls back key by key. A fallback is never silent:

- `ResolvedMessage.used_fallback` is true,
- `RenderedWarning.used_fallback_keys` lists the keys,
- the API response sets `language_note.translation_fallback_used`,
- the communication layer emits a `translation_fallback` event,
- the UI prints `translation_fallback: <keys>` next to the template metadata.

Because a fallback crosses a language boundary, the text shown must still be
legible to the reader. That is why a missing key is a *defect to fix*, not a
convenient degradation.

## RTL

Direction is data, not an assumption: `direction` and `script` live in the pack.
`RenderedWarning.direction` flows into the `dir` attribute of the alert element,
and `static/css/app.css` is written with CSS logical properties
(`margin-inline-start`, `padding-inline`, `inset-inline-start`, `text-align:
start`) so nothing depends on left/right.

No current locale is RTL. `ar` exists only in the legacy P0 alert dictionary and
is **not** part of the P1 pack catalog. Before adding an RTL locale:

1. add the pack with `direction: rtl` and `script: Arab`;
2. verify the alert card, operator table, filters and buttons under `dir="rtl"`;
3. verify numerals and the `{amount}` placeholder stay readable;
4. run `docs/accessibility_checklist.md`.

## What is still missing

- no native reviewer has been recorded for either locale;
- no legal reviewer, so nothing is `approved`;
- no approved treatment template, so the experiment treatment arm is refused by
  default (`resolve_pair` returns `treatment_available: false`);
- a machine draft is not a translation review. The badge exists precisely because
  that gap must stay visible.