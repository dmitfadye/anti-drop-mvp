# Translation checklist

One checklist per message key per locale. A reviewer ticks a box only after doing
the thing, and every tick has a name or a content hash recorded — no raw
personal data in this file, in the pack, or in the log.

**Current state: no row below is approved. Both packs are `draft`.**

## How to use

1. Open `locales/<locale>.json` and the matching `templates/*.json`.
2. Read each message aloud in the target language, then check the rows.
3. Record the reviewer in `reviewers[]` with `role: native_reviewer` and a
   pseudonym or content hash. Set `status: native_reviewed` only when the
   language column is complete and the legal column is untouched.
4. Legal review is a separate pass: `docs/legal_text_review_checklist.md`.

## Per-message checklist

| # | Key | Meaning preserved | No accusation | No block promise | No legal characterisation | Next step clear | Short | Placeholders correct | Native reviewed | Legal reviewed | Version / status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `alert.red.title` | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 2 | `alert.red.body` | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 3 | `alert.yellow.title` | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 4 | `alert.yellow.body` | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 5 | `cta.help` | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 6 | `cta.sandbox_notice` | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 7 | `legal.disclaimer` | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |
| 8 | `privacy.notice` | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ |

## What each column means

- **Meaning preserved** — a reader who speaks only this language reaches the same
  conclusion as a Russian reader. Not a literal word-for-word translation.
- **No accusation** — the text does not imply the client knew, agreed or
  participated in anything. Compare with the RU control sentence by sentence.
- **No block promise** — the text does not say or imply that a transfer was
  blocked, frozen, declined or will be. This is the single most dangerous class
  of error for the bank.
- **No legal characterisation** — no article numbers, no fixed penalties, no
  statement about criminal liability.
- **Next step clear** — a reader can say what to do next without guessing.
- **Short** — under about 40 words for a body message. Warnings are read once,
  often on a phone, in a moment of stress.
- **Placeholders correct** — `{amount}`, `{currency}`, `{reason_short}`,
  `{next_step}`, `{lang_name}` only, spelled identically to the pack, and the
  surrounding grammar still reads correctly when each value is substituted.
- **Native reviewed** — a native speaker with relevant financial-services
  familiarity signed the whole message.
- **Legal reviewed** — `docs/legal_text_review_checklist.md` completed.
- **Version / status** — `version` bumped, `status` reflects the actual stage.

## Known open items

- `uz-UZ` has no `privacy.notice`; it resolves through the `ru-RU` fallback. This
  must be translated, not left to fall back, because the fallback crosses a
  language boundary. Recorded in `used_fallback_keys` until it is fixed.
- `uz-UZ` copy is a machine draft. Nobody has read it aloud yet.
- Neither locale has a legal reviewer, so `legal_reviewed` and `approved` are
  unreachable today, by design.

## Anti-patterns a reviewer must reject

| Pattern | Why it fails |
|---|---|
| «Ваш счёт заблокирован» | Promises a bank action the system does not perform |
| «Деньги заморожены» | Same, plus a factual claim about money state |
| «Вам грозит 6 лет» | Fixed sentencing; a bank and a regulator would object |
| «Вы соучастник» | Accusation; also not established by any rule |
| «OTP подтверждён» | States a verification that never happened |
| «Кешбэк начислен» | States a benefit that does not exist in this layer |
| «Поддержка ответит за 2 минуты» | Service-level promise nobody can keep |
| Machine translation of legal wording | Legal terms are locale-specific and legally reviewed |

## Recording the review

```json
"reviewers": [
  {
    "role": "native_reviewer",
    "reviewed_at": "2026-10-20T09:15:00Z",
    "review_hash_or_pseudonym": "native-rev-01"
  },
  {
    "role": "legal_reviewer",
    "reviewed_at": "2026-10-21T11:40:00Z",
    "review_hash_or_pseudonym": "legal-rev-01"
  }
]
```

Use a pseudonym or a hash of the review, not a name, an email or a phone number.