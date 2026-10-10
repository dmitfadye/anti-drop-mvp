# P0 validation

62 Python unittest tests passed (41 existing + 21 new); 8 existing browser integration tests passed against the restarted backend. Live strict risk API returned 200 and RiskDecisionV1. Invalid contract cases return 422 in API tests.

Generator produced 21 valid synthetic episodes, 8 invalid contract fixtures, and an unlabelled review template. CLI evaluation generated all required artifacts, a separate legitimate-negative report and per-episode decisions. Example TP=2, FP=1, TN=18, FN=0. These are pipeline results on synthetic placeholders, not bank accuracy.

No new runtime dependency added for P0. Existing FastAPI test-client deprecation warning remains. Full report manifest records the code commit and worktree state during generation.
