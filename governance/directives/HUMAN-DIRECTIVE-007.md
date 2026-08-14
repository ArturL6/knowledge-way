# HUMAN-DIRECTIVE-007 — External comparator isolation

**From:** Project owner  
**To:** all Knowledge-Way scheduler roles  
**Authority:** Supersedes the in-repository comparative-benchmark implementation model.

The third-party comparator must not be present in the Knowledge-Way repository or used by its development workflow in any form. The current tree must contain no comparator-specific runner, result artifact, dependency, Docker material, bundled binary, vendored code, or product invocation.

Comparative benchmarking is an independent operational activity. It runs in `/home/hermes/external-benchmarks/comparator/`, outside every Knowledge-Way checkout and outside its Docker Compose topology. It may use a separate disposable container or other isolated runtime, clone/checkout the same pinned public corpus snapshots, and consume a read-only export of the 25 gold-task oracle set. It must never mount or modify the Knowledge-Way repository.

The external benchmark evaluates the two systems on the same changed-file oracles and `hit_at_5` / `MRR` metrics. It installs its third-party tool only for the evaluation, tears it down afterwards, and stores raw outputs plus reports outside the repository. Results are reported to the owner; any product-design proposal is a separate, human-reviewed ADR based on behavioral conclusions only.

The external operation is not a development packet and does not block or authorize repository implementation automatically. It must not write scorecards, mechanisms, or task tables into the Knowledge-Way repository.
