# Thematic quiz cards and encoding repair

All eight topics now use the same accessible ScenarioCard for practice, final quiz and article questions. The illustrations are rendered assets, not screenshot placeholders. Course IDs select a presentation theme in `frontend/components/learning-theme.ts`; question text, options, grading and server authority remain unchanged. Generic legacy questions show the existing module summary as topic context, not a fabricated personal transaction. Call/message questions retain their authored scenarios.

| Topic | Illustration | Accent | Actual desktop screenshot |
| --- | --- | --- | --- |
| Safe transfers | transfers.png | Blue | [View](screenshots/themes/m1_safe_transfers-1440.png) |
| Asked to forward | messages.png | Violet | [View](screenshots/themes/m2_asked_forward-1440.png) |
| Unexpected transfer | transfers.png | Cyan | [View](screenshots/themes/m3_unexpected-1440.png) |
| Normal vs suspicious | safety-shield.png | Mint | [View](screenshots/themes/m4_normal_vs_suspicious-1440.png) |
| Bank warning | messages.png | Amber | [View](screenshots/themes/m5_bank_warning-1440.png) |
| Digital hygiene | security.png | Blue | [View](screenshots/themes/m6_digital_hygiene-1440.png) |
| Contact the bank | support.png | Mint | [View](screenshots/themes/m7_contact_bank-1440.png) |
| Calls under pressure | scenario-phone.png / messages.png | Blue | [View](screenshots/themes/m8_phone_fraud-1440.png) |

Mobile images use the same topic names with `-390.png`. All eight actual API quiz views were checked at 390/768/1024/1440 px (32 view checks). Call scenes use content-driven height: long text is not clipped to a fixed phone canvas. The neutral caller heading deliberately does not contradict the familiar displayed number in card 5. Option letters supplement native radio controls; feedback uses text, borders and icons as well as color. Practice/final grading remain separate.

## Fixed defects

The earlier Windows shell-to-Python update replaced Cyrillic literals in m8 card 4 and parts of card 5 with question marks. The persisted JSON itself was damaged; changing fonts would not fix it. These fields were restored with UTF-8-safe patching. Catalog version is now `2026-11-01.v4`, phone content `2026-11-01.phone.v3`. Previous damaged drafts are not applied to new content. Existing server replay records were not rewritten.

Backend loading rejects corrupted displayed prose; frontend also rejects damaged API responses, including historical replay, instead of showing unreadable text or a false success. Tests inspect the shipped catalog rather than only clean injected fixtures. Draft restoration rejects skipped prior answers and ignores contradictory feedback before allowing it to lock the current answer. A rejected response retains the idempotency key for a safe retry.

See [fixed card 4, mobile](screenshots/fixed-card-4-390.png), [fixed feedback 4](screenshots/fixed-feedback-4-390.png), [fixed card 5](screenshots/fixed-card-5-390.png), [fixed feedback 5](screenshots/fixed-feedback-5-390.png).

## Generated asset prompts

Built-in ImageGen was used, with transparency requested and the existing `safety-shield.png` as visual reference. Results were copied into `frontend/public/images/learning/`; no paid API key or external asset service was used. These are decorative illustrations, not bank status indicators.

`transfers.png`:

> One single isolated premium 3D educational illustration: a friendly pale white and electric blue bank card with a subtle chip, two curved cyan arrows indicating a transfer around it, a tiny mint confirmation tile. NO letters, digits, amounts, logos, currency, UI panels or background scene. Soft white ceramic and translucent pale-blue glass with cobalt #0066ff edges, brighter cyan/mint accents, rounded controlled forms, refined studio lighting and soft ambient shadow. Transparent background. Object at slight perspective, fills center with breathing room. Match reference shield's craftsmanship and AntiDrop banking palette. This is a reusable illustration for a financial-safety quiz, not a whole screenshot.

`messages.png`:

> One single isolated premium 3D educational illustration: two substantial rounded chat bubbles, one white ceramic and one electric azure blue, a small warm amber alert badge with a simple exclamation mark on the front. NO words, letters, numbers, avatars, brands, actual messages or UI screens. Cobalt #0066ff, soft cyan and white with restrained amber accent. Friendly refined 3D banking app art, softly beveled glass/ceramic, slight perspective, good legibility at small size, soft studio lighting. Transparent background. Match reference shield style. Single centered composition.

`security.png`:

> One single isolated premium 3D educational illustration: a beautiful substantial padlock in white ceramic and luminous cobalt blue translucent glass, with a subtle circular mint shield behind it. No words, digits, passwords, branding, UI screen or background. Bright but restrained blue-white financial app aesthetic, soft rounded geometry, slightly angled toward viewer, precise highlights, soft studio lighting and ambient shadow. Transparent background, centered object with breathing room, match provided shield's material and visual style.

`support.png`:

> One single isolated premium 3D educational illustration: friendly white and azure blue customer-support headset beside a small rounded white shield with blue checkmark, backed by a subtle cyan circular halo. No face, person, words, letters, branding, UI screen or background. Cobalt #0066ff and white ceramic with frosted pale blue glass, tiny mint accent, rounded polished geometry, slight perspective, soft studio light. Transparent background. Single centered coherent composition, match provided safety shield style, suitable for an educational quiz about independently contacting an official support channel.
