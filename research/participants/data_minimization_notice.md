# Data minimisation notice

What we collect, what we refuse to collect, and why. Applies to interviews, to the
sandbox demonstrator, and to any operator export.

**The demonstrator collects nothing from anyone.** There is no account, no signup,
no analytics and no third-party script. This notice describes the rules that hold
for the research that has not happened yet, and for any pilot that would.

## Never collected — any context

| Category | Examples |
|---|---|
| Identity | full name, first/last name, username |
| Contact | phone number, email, address, messenger handle |
| Accounts | card number, account number, IBAN, partial digits, CVV |
| Credentials | OTP, PIN, password, one-time codes |
| Payments | full transaction details, counterparty names, statements, receipts |
| Documents | passport, SNILS, INN, driver licence, any scan |
| Location | GPS, address, city-level precision, workplace |
| Biometrics | face, voice, fingerprint |
| Demographics used as risk | language, nationality, citizenship, ethnicity, name |

The last row is also a **product** rule: language, citizenship, ethnicity and name
are not risk factors in the detector, and `RiskSnapshotV1` has no field for any of
them. Attempting to send one is rejected, and
`reports/evaluation/report.md` records an injection check proving it.

## Collected — research context

| Field | Why | Retention |
|---|---|---|
| participant pseudonym `pNN` | to link a participant's own answers without identifying them | with the notes |
| interview date | to check for drift over the study period | with the notes |
| interview language | the core variable of H1 | with the notes |
| coded answers | the questions being asked | with the notes |
| free-text comment | nuance a code cannot carry | scrubbed, then stored |

## Collected — sandbox demonstrator

| Field | Why |
|---|---|
| `sub_<hash>`, `cp_<hash>`, `evt_<hash>`, `case_<hash>` | opaque pseudonymous refs so the flow can be demonstrated without identity |
| `level`, `score`, `reason_codes` | to explain the decision |
| `rule_version`, `threshold_version`, `template_id`, `locale` | reproducibility |
| synthetic scenario transactions | the whole fixture set is fabricated with a fixed seed |

The sandbox store lives in process memory and dies with the process.

## Local event sink

When `ANTI_DROP_OPERATOR_LOG` is set, events are appended to a local JSON-lines
file. Each event is validated against a closed allowlist before it is written, so
PII-shaped fields are rejected rather than stored. The file grows until an operator
deletes it; there is no automatic retention policy here.

## Exports

`/api/operator/export` keeps an allowlist of columns and masks digit runs that
could be a phone or a card. Exports must be treated as pseudonymous personal data
and handled accordingly — masking is a backstop, not a proof of anonymisation.

## Third parties

None. No analytics, no CDN, no fonts, no telemetry, no outbound requests from the
application code. Verified by test.

## Questions

A data protection owner must be named before any of this becomes real. Until then
this notice describes an implementation, not a compliant processing activity. See
`docs/security_privacy_gate_checklist.md`.