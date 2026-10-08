# Components and contracts

- Dashboard: one visible screen from the existing hash navigation.
- useSection: useSyncExternalStore subscription shared by content and navigation.
- AppShell: shared navigation, moving capsule, search, notifications, profile links, responsive accessible drawer.
- Overview / Transactions: synthetic dashboard, shared semantic event table, inline details.
- Monitoring: applied filters, pagination, expandable existing anti-fraud simulation. POST /api/analyze unchanged; seven warning languages retained.
- Learning: five learning stages, server content, sequential quiz, previous/next, answer validation and results. GET /api/content and POST /api/quiz unchanged.
- PhoneChange: four-step educational wizard, separate old/new code checks, canonical number comparison; POST /api/sim remains authoritative. No real OTP or SMS integration.
- ContentScreens / education: scenario filters, searchable reading cards, guides, FAQs and settings. Educational cases are explicitly fictional.
- preferences: browser-local storage with storage-event synchronization. Compact tables, hints, contrast and reduced motion have visible effects; no server policy is changed.
- Icon: consistent lightweight outline SVG icon vocabulary, not replacement illustrations.

DemoWorkspace now composes dedicated screens instead of owning all scenario logic. Hidden scenario screens stay mounted to retain in-progress work when navigating. No backend files changed.
