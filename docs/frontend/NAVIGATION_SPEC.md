# Navigation specification

Four groups: main (overview, monitoring, principles), protection (planned scenarios, learning, phone), education (planned knowledge, videos, examples), system (planned settings, support). Existing destinations remain same-page anchors: #overview, #monitoring, #principles, #learning, #phone. Planned entries are disabled with visible Russian Soon labels and explanation tooltips; demo profile is informational because account functionality does not exist.

A single decorative pointer-transparent capsule lives inside the relative navigation canvas. Active anchor is synchronized on hashchange and initial load. offsetTop supplies canvas-local position, including when the sidebar scrolls. ResizeObserver, font readiness and drawer opening refresh geometry. CSS transitions transform only; dimensions update on measurement. aria-current identifies the selection. Native Tab/Enter and global focus outlines remain available.

Below 768px the sidebar is a labelled modal drawer with focus containment, inert page content, scroll lock, Escape, backdrop and close button. Dismissal restores opener focus after inert removal; destination selection focuses its section. Desktop resizing dismisses the drawer. Reduced motion and mobile disable capsule travel.

Toolbar search is limited to implemented navigation labels, not transaction contents. Ctrl/Cmd K focuses it. Notifications show an honest empty state, help opens instructions, demo mode opens the existing monitoring scenario controls. No fabricated alerts, account data or global search results.
