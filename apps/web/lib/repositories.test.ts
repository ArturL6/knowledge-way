import { describe, expect, it } from 'vitest';
import { apiErrorMessage, cloneUrlError, isSafeCloneUrl, progressLabel } from './repositories';

describe('isSafeCloneUrl', () => {
  it('accepts a plain https clone URL', () => {
    expect(isSafeCloneUrl('https://github.com/org/repo.git')).toBe(true);
  });

  it('accepts an https URL without the .git suffix', () => {
    expect(isSafeCloneUrl('https://github.com/org/repo')).toBe(true);
  });

  it('accepts an https URL with a port', () => {
    expect(isSafeCloneUrl('https://git.example.com:8443/org/repo.git')).toBe(true);
  });

  it('accepts the scp-like SSH shorthand', () => {
    expect(isSafeCloneUrl('git@github.com:org/repo.git')).toBe(true);
  });

  it('accepts an explicit ssh:// URL', () => {
    expect(isSafeCloneUrl('ssh://git@github.com:2222/org/repo.git')).toBe(true);
  });

  it('rejects http (non-HTTPS)', () => {
    expect(isSafeCloneUrl('http://github.com/org/repo.git')).toBe(false);
  });

  it('rejects a local filesystem path', () => {
    expect(isSafeCloneUrl('/home/user/repo')).toBe(false);
  });

  it('rejects a file:// URL', () => {
    expect(isSafeCloneUrl('file:///home/user/repo')).toBe(false);
  });

  it('rejects a relative path', () => {
    expect(isSafeCloneUrl('./repo')).toBe(false);
  });

  it('rejects a URL containing a directory traversal sequence', () => {
    expect(isSafeCloneUrl('https://github.com/org/../repo.git')).toBe(false);
  });

  it('rejects a URL containing whitespace', () => {
    expect(isSafeCloneUrl('https://github.com/org/ repo.git')).toBe(false);
  });

  it('rejects an empty or blank string', () => {
    expect(isSafeCloneUrl('')).toBe(false);
    expect(isSafeCloneUrl('   ')).toBe(false);
  });

  it('trims surrounding whitespace before validating', () => {
    expect(isSafeCloneUrl('  https://github.com/org/repo.git  ')).toBe(true);
  });
});

describe('cloneUrlError', () => {
  it('returns null for a safe URL', () => {
    expect(cloneUrlError('https://github.com/org/repo.git')).toBeNull();
  });

  it('returns a helpful message for an unsafe URL', () => {
    expect(cloneUrlError('/etc/passwd')).toMatch(/safe Git HTTPS or SSH clone URL/);
  });
});

describe('progressLabel', () => {
  it('reports waiting when progress is missing', () => {
    expect(progressLabel(undefined)).toBe('Waiting to start');
    expect(progressLabel(null)).toBe('Waiting to start');
  });

  it('reports waiting when progress is an empty object', () => {
    expect(progressLabel({})).toBe('Waiting to start');
  });

  it('falls back to "Working" when phase is not a string', () => {
    expect(progressLabel({ files: 3 })).toBe('Working · 3 files');
  });

  it('uses the phase string when present', () => {
    expect(progressLabel({ phase: 'Parsing' })).toBe('Parsing');
  });

  it('appends the file count when it is a number', () => {
    expect(progressLabel({ phase: 'Indexing', files: 42 })).toBe('Indexing · 42 files');
  });

  it('omits the file count when files is not a number', () => {
    expect(progressLabel({ phase: 'Indexing', files: '42' })).toBe('Indexing');
  });
});

describe('apiErrorMessage', () => {
  it('returns a generic message for non-Error values', () => {
    expect(apiErrorMessage('boom')).toBe('Something went wrong. Please try again.');
    expect(apiErrorMessage(null)).toBe('Something went wrong. Please try again.');
    expect(apiErrorMessage(undefined)).toBe('Something went wrong. Please try again.');
  });

  it('returns a generic message for an Error with an empty message', () => {
    expect(apiErrorMessage(new Error(''))).toBe('Something went wrong. Please try again.');
  });

  it('extracts the detail field from a JSON error body', () => {
    const error = new Error(JSON.stringify({ detail: 'Repository not found' }));
    expect(apiErrorMessage(error)).toBe('Repository not found');
  });

  it('falls back to the raw message when detail is not a string', () => {
    const error = new Error(JSON.stringify({ detail: { nested: true } }));
    expect(apiErrorMessage(error)).toBe(error.message);
  });

  it('falls back to the raw message when the body is not JSON', () => {
    const error = new Error('Internal Server Error');
    expect(apiErrorMessage(error)).toBe('Internal Server Error');
  });
});
