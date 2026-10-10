# Accessibility checklist

Scope: `static/index.html`, `static/js/app.js`, `static/operator.html`,
`static/js/operator.js`, `static/css/app.css`. Vanilla HTML/CSS/JS, no
framework, no CDN, no external font.

Automated checks live in `tests/test_frontend_assets.py`. This file covers what
a machine cannot verify.

## Structure and semantics

- [x] one `<h1>`, headings descend without gaps;
- [x] landmarks: `<header>`, `<main>`, `<footer>`; tab panels use `role="tab"`
      / `role="tabpanel"` with `aria-controls` / `aria-labelledby`;
- [x] every table has a `<caption>` and `scope="col"` headers;
- [x] lists are real `<ul>`/`<li>`, not styled divs;
- [x] skip link is the first focusable element and targets `#main`.

## Keyboard

- [x] every control is reachable and operable with Tab / Shift+Tab / Enter / Space;
- [x] radio groups use a real `name` group, so arrow keys move within the question;
- [x] focus is visible: `:focus-visible` draws a 3px outline with 2px offset;
- [x] focus is never trapped and never removed;
- [x] tab order follows the visual order, including in RTL;
- [x] modals: none in this build, so no focus trap is required.

## Forms

- [x] every input and select has a `<label for>` pointing at its `id`;
- [x] no placeholder is used as the only label;
- [x] the language `<select>` is wired to `#langStatus` via `aria-describedby`;
- [x] inline errors use `role="alert"`; status text uses `role="status"` +
      `aria-live="polite"`;
- [x] form state survives a failed request: the scenario `<select>`, the language
      `<select>` and the phone inputs are never re-rendered from a response.

## Live regions

- [x] `#levelBadge` — `role="status"`, `aria-live="polite"`, announces the level
      with text, not just colour;
- [x] `#reasons`, `#reasonCodes` — `aria-live="polite"`, updated after a decision;
- [x] `#requestState` — announces loading, not just the spinner;
- [x] `#alertBox` — `role="alert"`; the sandbox banner repeats the "no banking
      action" fact in text;
- [x] `#ticket` — announces the created case id and the sandbox disclaimer;
- [x] operator `#metrics`, `#casesNote`, `#detailNote` — `aria-live="polite"`.

## Colour is never the only signal

- [x] GREEN / YELLOW / RED are rendered as icon + text + score, not a colour
      alone: `✅ ЗЕЛЁНЫЙ — признаков риска нет score 0/100`;
- [x] reason codes are text;
- [x] the draft-translation badge is text;
- [x] operator levels and statuses are text cells;
- [x] `prefers-contrast: more` raises border and muted-text contrast;
- [x] body text on `--ad-bg` is `#f1f5f9` (contrast > 12:1); muted text
      `#cbd5e1` (> 8:1); level colours on their own dark backgrounds > 7:1.

## Motion

- [x] `prefers-reduced-motion: reduce` cuts animation and transition duration to
      ~0 and disables smooth scrolling;
- [x] no animation is required to understand any state;
- [x] the loading state is a text message, not a spinner only.

## Motion-safe async behaviour

- [x] every request has a 15s `AbortController` timeout;
- [x] each request carries a sequence number; a stale response is discarded
      instead of overwriting newer state (`state.requestSeq`);
- [x] buttons are disabled for the duration of a request, so a double click
      cannot fire two calls;
- [x] errors are rendered as text; no error is injected as markup;
- [x] `AbortError` is reported as a timeout that changed nothing.

## Security-adjacent DOM rules

- [x] no `innerHTML` for data anywhere: reason codes, translations, case ids,
      timestamps, scores and statuses all use `textContent` or
      `createElement`;
- [x] `innerHTML` does not appear in `static/js/*.js` at all — verified by test;
- [x] quiz answers are never present in the served HTML; verification is
      server-side;
- [x] links to `/docs` carry `rel="noopener"`.

## Mobile

- [x] `viewport` meta present, no user scaling disabled;
- [x] tap targets ≥ 44×44 CSS px (`.btn`, `.tab-btn`);
- [x] tables scroll inside `.table-scroll`, so no horizontal page overflow;
- [x] below 30rem the controls stack full width;
- [x] operator filters reflow into a single column grid.

## RTL

- [x] `dir` comes from the pack (`direction`), applied to `<html>` and to the
      alert element;
- [x] `lang` is set on the alert element to the rendered locale;
- [x] layout uses logical properties: `margin-inline`, `padding-inline`,
      `inset-inline-start`, `text-align: start`;
- [x] no `left`/`right` positioning in the layout that would break mirrored
      reading order;
- [x] bullet lists use `padding-inline-start`;
- [x] the operator table and filter grid stay usable under `dir="rtl"`.

No current locale is RTL. `ar` is only a legacy P0 alert key and is not part of
the P1 catalog. Re-run this checklist when an RTL pack is added.

## Not verified

- No screen-reader run (NVDA / JAWS / VoiceOver) has been performed. The markup
  is written to the rules above; the runtime behaviour is **NOT VERIFIED**.
- No automated axe/Lighthouse audit was run in this repository.
- Contrast ratios were computed by hand from the palette, not measured in a
  rendering engine.
- Keyboard testing was reasoning plus unit checks, not a physical session with
  every browser and operating system.

A checklist that says "done" without a screen reader is a claim, not a result.