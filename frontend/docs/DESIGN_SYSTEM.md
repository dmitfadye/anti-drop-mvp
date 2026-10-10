# Design system

Semantic custom properties live in app/globals.css: canvas #EEF3FA, surface #FFFFFF, ink #172C50, muted #52637E, primary #2458CB, hover #1946AC, soft #E9F0FF, border #DCE4EF, focus #0D47A1. Text/action pairs target WCAG AA; do not use pale palette shades for body text. States require visible wording, never color alone. No operational risk states are shown before analysis exists.

Spacing follows a 4px base: 4/8/12/16/20/24/32/40/48/64. Radii: 8 controls, 16 medium surfaces, 24 primary surface. Quiet surface shadow only. System Segoe UI / Arial supports Cyrillic without a network font request. Body 16px; compact metadata 10–12px; heading 40–64px, restrained negative tracking.

Layout: 248px desktop sidebar, bounded 1280px content, 48px desktop padding. Literal media thresholds 1440/1024/768px; CSS custom properties cannot be used in media queries. At tablet width the empty state stacks; below 768px navigation becomes a wrapped top row, padding 20px. Controls prefer 44px minimum. No motion except optional smooth anchor scrolling, disabled for reduced motion.

Global CSS contains reset and tokens only. CSS Modules use BEM and bracket access. Native details/summary is the working disclosure; no client component or library is needed. Shield is an original decorative inline SVG with aria-hidden. Links use real in-page sections.
