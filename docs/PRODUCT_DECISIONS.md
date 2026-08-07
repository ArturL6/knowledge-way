# Product decisions

## Scope boundaries

Knowledge-way is a self-hosted code intelligence tool, not a Sourcegraph feature clone. The initial product optimizes for a trusted developer/team indexing a manageable repository set, then evolves toward larger multi-repository installations.

## Retrieval principles

- Vector similarity does not replace lexical or symbol search.
- Static references are advisory and always carry a confidence level.
- Code-specific answers must be grounded in current retrieved chunks.
- Line citations are stable only for the indexed commit recorded with each source.

## Data and AI boundary

Repository content is sensitive and untrusted. Only minimal retrieved context should be sent to an external model, never a full checkout. Comments, documentation, code strings, and generated text are data—not instructions to the model.

## Credentials

The database stores credential references only. Credential acquisition and storage belong to deployment-specific secret-management integrations. Public repositories are the initial supported path; private repository support must use deploy keys, credential helpers, or secret manager references.
