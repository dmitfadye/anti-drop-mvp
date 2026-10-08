> Historical collage specification. For the current overview and shared shell, use APPROVED_VISUAL_SPEC.md.

﻿# Visual specification

Approved direction: user-supplied AntiDrop references in the conversation, 2026-10-08. The third collage (four large screens) is the primary reference. Individual source images and original viewport sizes are unavailable on disk. Measurements are proportional estimates, not recovered source CSS.

| Screen/hash | Reference |
| --- | --- |
| overview | Third collage, upper left: compact heading, three metrics, events, two shortcuts |
| monitoring | Third collage, upper right: three filters, Apply, table and pagination |
| learning | Third collage, lower left: tabs, five lessons, educational panel |
| phone | Third collage, lower right: four-step verification wizard |
| principles | Second collage: three stages and educational example |
| protection | Second collage: category chips and scenario cards |
| knowledge | First collage: six category cards; second collage: search/filter controls |
| settings | First collage: inner sidebar and switches |
| guides, examples, support | Derived from the approved shell/components; no dedicated approved full-screen reference |

Desktop shell: 240px sidebar (210px below 1100px), 62px toolbar, 24px main horizontal padding, outer 24px radius. Primary blue #0066ff, ink #07123b, pale blue page surfaces. Native semantic controls; CSS Modules with BEM. Mobile below 768px uses a focus-trapped drawer. Tables scroll within their containers.

Only one screen is visible at a time. Existing hash URLs, browser back/forward and refresh are preserved. Backend business logic and contracts are unchanged. The demo mode remains explicitly labeled; synthetic metrics are not computed account statistics.
