# Hermetic benchmark runs

HD-006 §2 governs every retrieval-scorecard run.

1. Benchmark runs must **never** score a pre-existing, developer-owned, or otherwise external API instance.
2. The benchmark job creates an ephemeral worktree at the exact refreshed `integration/roadmap-v2` SHA and provisions its own keyless stack through the packet 0.6 quickstart path.
3. It seeds the active workspace from `benchmarks/corpora.json` at each member's pinned `resolved_sha` and verifies that the served-snapshot manifest equals that pinned manifest before scoring.
4. Only then may it run the scorecard and commit the resulting artifact directly on integration. It tears down the Compose stack and removes the temporary worktree whether the run succeeds or fails.
5. A snapshot mismatch after successful self-provisioning is a real reproducibility defect: preserve diagnostics and set a direct-integration drift flag for Sol.
6. A mismatch observed on another process's server is noise. Do not score it, do not flag drift, and do not treat it as benchmark evidence.
7. Until the repository contains an executable hermetic runner that can perform this lifecycle, the benchmark scheduler must no-op rather than fall back to a live API.
