from pathlib import Path

import pytest

from app import git_auth


@pytest.mark.parametrize("url", [
    "https://github.com/acme/private.git",
    "git@github.com:acme/private.git",
    "ssh://git@git.example.test:2222/team/repo.git",
])
def test_accepts_network_credential_free_clone_urls(url):
    assert git_auth.validate_clone_url(url) == url


@pytest.mark.parametrize("url", [
    "https://token@github.com/acme/repo.git",
    "https://user:token@github.com/acme/repo.git",
    "https://github.com/acme/repo.git?access_token=nope",
    "file:///tmp/repo", "git://github.com/acme/repo.git", "ssh://root@host/repo.git",
    "https://github.com/acme/../secret.git", "git@host:../repo.git",
])
def test_rejects_unsafe_or_credential_bearing_urls(url):
    with pytest.raises(ValueError):
        git_auth.validate_clone_url(url)


def test_https_token_uses_askpass_not_url_or_environment_token(monkeypatch, tmp_path):
    token = tmp_path / "token"; token.write_text("super-secret-token\n")
    monkeypatch.setattr(git_auth.settings, "git_https_token_file", str(token))
    monkeypatch.setattr(git_auth.settings, "git_https_username", "oauth2")
    env = git_auth.git_environment("https://github.com/acme/private.git")
    assert env["GIT_ASKPASS"] == git_auth.settings.git_https_askpass_path
    assert env["GIT_HTTPS_TOKEN_FILE"] == str(token)
    assert "super-secret-token" not in " ".join(env.values())
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_CONFIG_GLOBAL"] == "/dev/null"


def test_ssh_requires_key_and_known_hosts_and_enforces_strict_checking(monkeypatch, tmp_path):
    key = tmp_path / "key"; hosts = tmp_path / "known_hosts"
    key.write_text("not-a-real-key"); hosts.write_text("github.com ssh-ed25519 placeholder")
    monkeypatch.setattr(git_auth.settings, "git_ssh_key_path", str(key))
    monkeypatch.setattr(git_auth.settings, "git_ssh_known_hosts_path", str(hosts))
    env = git_auth.git_environment("git@github.com:acme/private.git")
    assert f"-i {key}" in env["GIT_SSH_COMMAND"]
    assert f"UserKnownHostsFile={hosts}" in env["GIT_SSH_COMMAND"]
    assert "StrictHostKeyChecking=yes" in env["GIT_SSH_COMMAND"]


def test_redaction_removes_url_credentials_and_mounted_token(monkeypatch, tmp_path):
    token = tmp_path / "token"; token.write_text("top-secret")
    monkeypatch.setattr(git_auth.settings, "git_https_token_file", str(token))
    message = "fatal: https://user:pass@host/repo failed; token=top-secret\nAuthorization: Bearer visible-value"
    safe = git_auth.redact_git_error(message)
    assert "pass" not in safe and "top-secret" not in safe
    assert "visible-value" not in safe
    assert "https://***@host/repo" in safe
