# Pitch content and demo

Content only: no finished deck, video or public deployment is claimed.

## 90-second verified route

0..15s: fictional unfamiliar-transfer request, synthetic label. 15..35s: `uv run python scripts/demo_sandbox.py`, show RED85/reasons; points not probability, example includes outgoing transfer already. 35..55s: committed case, explicit no-bank-dispatch message, same-key replay. 55..75s: restart PG/API and `--verify-existing`; exact case survives. 75..90s: next proof is Next integration, generic/contextual comparison and approved shadow. CLI is current verified full route; any separately shown Next screen is not connected to cases.

Preflight: Docker/port8010 ready, already downloaded images for offline runtime. Never show .env, bearer token or environment. On DB failure show503/no case success, never fabricate completion.

## Twelve-slide outline

1. Problem: unfamiliar transfer/request and verification uncertainty.
2. Evidence: sector context, explicit lack of completed interviews.
3. JTBD: understand signals and verify independently.
4. Audience: recruitable adult segment without stereotypes.
5. Solution: signal -> explanation -> safe action -> test case.
6. Working MVP: live HTTP/PG replay; 24 handmade fixtures, not production accuracy.
7. Differentiation: contextual explanations vs existing guidance; benefit unproven.
8. Metrics: matched tasks, comprehension/action guardrails, reviewed language.
9. Market: unknown bank reach; explicitly assumed exposure calculations.
10. Economics: negative base, break-even evidence needed.
11. Pilot: synthetic -> approved shadow -> controlled warnings.
12. Team: verified human roles/commitment and feasibility feedback ask.

## Jury questions

| Question | Honest answer | Supporting evidence |
|---|---|---|
| Why does VTB need it? | Retail safety/CX fit; actual incremental need unvalidated | E01, PRODUCT_DISCOVERY |
| Replaces existing anti-fraud? | Complementary communication hypothesis, no blocking connector | PILOT_PROTOCOL, src/sandbox.py |
| Where is user research? | Not conducted; protocol only | E09, PRODUCT_DISCOVERY |
| What works now? | Owned persistent evaluation/case/replay over HTTP, not connected Next | architecture/VERIFICATION |
| What is simulated? | Financial input, support registration, SIM change, reward | KNOWN_LIMITATIONS, main.py |
| Is85 an85% probability; why trust score? | No, deterministic auditable points, uncalibrated efficacy | src/policy.py, adapter.py, metrics.json |
| False positives? | Legitimate rent collection alerts; no automatic enforcement; reviewed holdout needed | legitimate_negatives_report.md |
| Safer than conventional warnings? | Not measured; matched-task comparison planned | PRODUCT_DISCOVERY |
| Stops first transfer? | Unproven, current showcase includes outgoing transfer | scripts/init_sandbox.py, KNOWN_LIMITATIONS |
| Why no AI? | Current deterministic task needs no inference | src/detector.py, official track E01 |
| Why PostgreSQL? | Durable ownership, atomic case/event/key and concurrent replay | DATABASE, test_postgres.py |
| How protected are identities? | Token-derived opaque subject, owned reads; local auth not bank IAM | src/sandbox.py, SECURITY |
| How is idempotency guaranteed? | Scoped digest/fingerprint, advisory lock, unique constraint, transaction | src/sandbox.py, test_postgres.py |
| API failure? | UI integration must withhold success/retry same intent; not yet wired | API_CONTRACTS |
| PostgreSQL failure? | Persistent endpoints503, transaction rollback, no memory success | test_postgres.py |
| On-prem possible? | No external runtime inference; internal registry/IAM/TLS/operations pending | Dockerfile, SECURITY, PILOT_PROTOCOL |
| Measured economic benefit? | None; base scenario negative | FINANCIAL_MODEL |
| Required for VTB pilot? | Sponsor, approvals, minimal feed, IAM and staged gates | PILOT_PROTOCOL |
| How will team scale it? | Human ownership unknown; load/CI/operational plan required | ROADMAP, E12 |
| Why select this project? | Inspectable working sandbox and falsifiable value hypothesis; efficacy must follow | VERIFICATION, JURY_SCORECARD |
| Sent to VTB? | No, explicit no-bank-dispatch next step | src/sandbox.py NEXT_STEP |
| Seven validated languages? | Drafts, no native/legal review | src/alerts.py, KNOWN_LIMITATIONS |
| Detection accuracy? | Only two positive handmade labels, no holdout | evaluation_manifest.json, metrics.json |
| Who maintains it? | Real human roles/availability unconfirmed, agents do not qualify | E12 |

Submission still needs cloud-linked PPTX/PDF, demo/video, source and analytics links per [official format](https://fintechacademy.ru/task-1). Markdown is not a submitted deck. No cloud links fabricated. Registration/submission dates require team action.
