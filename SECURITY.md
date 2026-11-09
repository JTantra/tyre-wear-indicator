# Security and publication boundary

Private GitHub is not a safe dump of a production workspace. Explicit allowlist and content checks precede Git staging; no keys/passwords/verifiers/cookies/tokens/capabilities/provider-imagepayloads/productionlogs/identityreceipts are included. Report suspected leaks to the repository owner through an existing private channel; do not open a public issue containing secrets or photos. No invented reporting email.

Run tools/check_publication.py before staging and inspect all staged blob contents independently. It fails closed on integrity drift, unexpected files and secret/privacy rules, printing only path/rule, never matched values. Tests include negative leakfixtures. This scanner is defense-in-depth, not certification against all secrets or customer context. Cold independent Ops review remains required before private push.

Cloud execution is separately opt-in, needs fresh consent/approval/config/receipts; copied historical authorization reconciliation is disabled. No CI deployment or hosted upload activation. Production and local export budgets/receipts are never migrated/reset. Raw provider replies, training.jsonl, source dataset, photos, locally generated weights/heads and runtime feedback remain ignored. Do not bypass exclusion by adding a ZIP or joblib under a new name.

Source app preserves client/server upload validation, origin/CSRF/session boundaries, explicit consent, atomic stores/revision checks and fail-closed durable publicmode. Local development SQLite feedback/volatile jobs/loopback is not a production persistence or distributed brute-force guarantee. Credentials should come from an approved secret manager/environment, never example literals or committed runtime readbacks.
