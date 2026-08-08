# Git credential security

Knowledge Way stores the **credential-free** clone URL in the database. URLs with
userinfo (`https://token@…` or `https://user:token@…`), query strings, local
paths, and non-network Git protocols are rejected. Do not use a token in a URL.
Git command errors are redacted before they are recorded in indexing jobs.

## SSH deploy keys (preferred)

Create a read-only deploy key for the repository and create a `known_hosts` file
from a trusted out-of-band source (for example, your Git provider's published
host keys). Do **not** use `ssh-keyscan` as the only verification step. Mount
both as read-only secret files and configure:

```env
GIT_SSH_KEY_PATH=/run/secrets/git_deploy_key
GIT_SSH_KNOWN_HOSTS_PATH=/run/secrets/git_known_hosts
```

SSH always uses `IdentitiesOnly=yes`, `BatchMode=yes`, an explicit key, explicit
known-hosts file, and `StrictHostKeyChecking=yes`. An SSH clone fails closed if
either secret is absent or unreadable.

## HTTPS token

For providers that require HTTPS, mount a token as a file and set only its path:

```env
GIT_HTTPS_TOKEN_FILE=/run/secrets/git_https_token
GIT_HTTPS_USERNAME=x-access-token
```

The token is read at clone/fetch time by the bundled `GIT_ASKPASS` helper. It is
not included in the clone URL, database, process arguments, or Git environment
as a token value. Public HTTPS cloning works with all Git credentials unset.

## Docker Compose example

Keep actual secret files outside the repository (`chmod 0400` where supported).
Add this override to production Compose; both `api` and `worker` receive the
same paths because either process may enqueue or execute indexing work:

```yaml
# compose.git-secrets.yml
services:
  api:
    secrets:
      - git_deploy_key
      - git_known_hosts
      # Or use git_https_token instead of the SSH pair.
  worker:
    secrets:
      - git_deploy_key
      - git_known_hosts
secrets:
  git_deploy_key:
    file: /srv/knowledge-way-secrets/git_deploy_key
  git_known_hosts:
    file: /srv/knowledge-way-secrets/git_known_hosts
  # git_https_token:
  #   file: /srv/knowledge-way-secrets/git_https_token
```

Start with `docker compose -f docker-compose.yml -f compose.git-secrets.yml up`.
Docker Compose mounts declared secrets at `/run/secrets/<name>` read-only, so the
SSH environment example above applies directly. For Kubernetes, mount Secret
keys read-only at the same paths in both API and worker pods; do not inject the
token as a normal environment variable.

Rotate/redeploy the secret and restart API and worker after changing a key or
token. Restrict deploy keys/tokens to read-only access and the smallest allowed
repository scope.
