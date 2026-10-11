# Security boundary

Current scope: loopback synthetic sandbox. Addressed threats: forged subjects, object ownership bypass, concurrent replay, oversized/invalid input, false success on storage failure, validation input leakage and excessive DB privilege. Credentials are locally generated/ignored, not printed. No real payment/support/SMS connector exists.

Residual risks: demo tokens lack expiry/rotation service; no bank gateway, rate limiting, TLS termination, SIEM, production vault, remote immutable audit, pentest or restore drill. Stateless legacy analysis is unauthenticated synthetic functionality. Docker administrators can inspect environment secrets. Do not expose Compose publicly or enter real personal data. Health probes process availability, not DB readiness.

Pilot requires bank-issued short-lived identity, audience/issuer checks, bank-owned TLS gateway, minimal read-only feature feed, private network, secret store, outbound restrictions, centralized redacted events, signed/versioned rules, quotas/timeouts, restore drill, incident owner, tenant isolation and kill switch. Disconnected installation needs approved internal package/image registries. Evaluation has no external model calls.

Bank legal/security owners must assess applicability. 152-FZ/bank secrecy matter if identifiable customer/account data enters processing. 161-FZ/payment security and115-FZ/AML responsibilities depend on actual integration/purpose; this rule score is neither AML adjudication nor a blocking instruction. CBR requirements depend on system/entity classification. This engineering checklist is not compliance certification. Sources: [competition conditions](https://fintechacademy.ru/task-1), [CBR security](https://www.cbr.ru/information_security/).
