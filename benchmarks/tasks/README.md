# Packet 0.2 gold tasks

Each JSON record is one closed upstream issue resolved by a merged fix PR in the permanent `fastapi-stack` workspace. `description` is copied from the issue body; it is never synthesized from PR text.

Traceability is retained in `source_issue` (issue URL/number) and `fix_pr` (PR URL/number, merge commit SHA, and PR head SHA). `gold.files` is the GitHub merged-PR changed-file list, `gold.tests` is its mechanically selected test-path subset, and `gold.symbols` contains Python definitions added in the PR patch. Empty symbol/test lists are intentional when a merged PR did not touch an added Python definition or test file.

Validate offline with:

```bash
python benchmarks/validate_tasks.py
```

A reviewer can independently sample any ten records by opening the source issue and PR URLs, then comparing the saved commit and changed-file metadata with GitHub.
