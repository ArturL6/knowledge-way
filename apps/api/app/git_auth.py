"""Safe, shared Git invocation configuration for API and RQ worker processes."""
from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from urllib.parse import urlsplit

from app.config import settings

# Git's URL parser accepts many local and helper forms. Only permit network Git URLs.
_SCP_SSH_URL = re.compile(r"^git@(?P<host>[A-Za-z0-9][A-Za-z0-9.-]*):(?P<path>[^\s:][^\s]*)$")
_SENSITIVE_URL = re.compile(r"(?P<scheme>https?://)(?P<userinfo>[^\s/@:]+(?::[^\s/@]*)?@)")


class GitConfigurationError(RuntimeError):
    """A required credential secret is absent or unsafe to use."""


def validate_clone_url(value: str) -> str:
    """Return a safe network clone URL or raise ValueError.

    Credentials in a URL are deliberately rejected: repository URLs are stored in
    the database and may be returned from the API.
    """
    if not isinstance(value, str) or not value or len(value) > 2048 or any(c.isspace() for c in value):
        raise ValueError("Git clone URL must be a non-empty network URL")
    match = _SCP_SSH_URL.fullmatch(value)
    if match:
        if ".." in Path(match.group("path")).parts:
            raise ValueError("Git clone URL path is invalid")
        return value
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "ssh"} or not parsed.hostname or parsed.password:
        raise ValueError("Git clone URL must be HTTPS or SSH without embedded credentials")
    if parsed.scheme == "https" and (parsed.username or parsed.query or parsed.fragment):
        raise ValueError("HTTPS Git clone URL must not contain credentials, a query, or fragment")
    if parsed.scheme == "ssh" and parsed.username != "git":
        raise ValueError("SSH Git clone URL must use the git user")
    if not parsed.path or parsed.path == "/" or ".." in Path(parsed.path).parts:
        raise ValueError("Git clone URL path is invalid")
    return value


def _required_file(path: str | None, label: str) -> str:
    if not path:
        raise GitConfigurationError(f"{label} is required for SSH Git URLs")
    candidate = Path(path)
    if not candidate.is_file() or not os.access(candidate, os.R_OK):
        raise GitConfigurationError(f"{label} is not a readable regular file")
    return str(candidate)


def git_environment(clone_url: str) -> dict[str, str]:
    """Build the only environment passed to Git; never puts a token in a URL."""
    validate_clone_url(clone_url)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", "/tmp"),
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_ASKPASS": os.devnull,
    }
    if clone_url.startswith(("git@", "ssh://")):
        key = _required_file(settings.git_ssh_key_path, "GIT_SSH_KEY_PATH")
        hosts = _required_file(settings.git_ssh_known_hosts_path, "GIT_SSH_KNOWN_HOSTS_PATH")
        env["GIT_SSH_COMMAND"] = (
            f"ssh -i {shlex.quote(key)} -o IdentitiesOnly=yes -o BatchMode=yes "
            f"-o StrictHostKeyChecking=yes -o UserKnownHostsFile={shlex.quote(hosts)}"
        )
    elif settings.git_https_token_file:
        token_file = Path(settings.git_https_token_file)
        if not token_file.is_file() or not os.access(token_file, os.R_OK):
            raise GitConfigurationError("GIT_HTTPS_TOKEN_FILE is not a readable regular file")
        env["GIT_ASKPASS"] = settings.git_https_askpass_path
        env["GIT_HTTPS_TOKEN_FILE"] = str(token_file)
        env["GIT_HTTPS_USERNAME"] = settings.git_https_username
    return env


def redact_git_error(message: str) -> str:
    """Remove URL userinfo and configured secret values before persistence/logging."""
    redacted = _SENSITIVE_URL.sub(r"\g<scheme>***@", message)
    token_path = settings.git_https_token_file
    if token_path:
        try:
            token = Path(token_path).read_text(encoding="utf-8").strip()
            if token:
                redacted = redacted.replace(token, "***")
        except OSError:
            pass
    # Common Git/curl authorization output should never become a job error either.
    return re.sub(r"(?i)(authorization:\s*)([^\r\n]+)", r"\1***", redacted)
