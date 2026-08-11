export type Repository = {
  id: string;
  name: string;
  clone_url: string;
  indexing_status: string;
  indexing_progress?: Record<string, unknown> | null;
  indexed_commit_sha?: string | null;
  latest_detected_commit_sha?: string | null;
  indexed_branch?: string | null;
  error_message?: string | null;
  last_indexed_at?: string | null;
};

/** Accept only the Git HTTPS and SSH clone URL formats supported by the API. */
export function isSafeCloneUrl(value: string): boolean {
  const url = value.trim();
  if (!url || /\s|\.\./.test(url)) return false;
  if (/^https:\/\/[A-Za-z0-9][A-Za-z0-9.-]*(?::\d+)?\/[A-Za-z0-9._~:/@%+=,-]+(?:\.git)?\/?$/i.test(url)) return true;
  if (/^[A-Za-z0-9._-]+@[A-Za-z0-9.-]+:[A-Za-z0-9._~/-]+(?:\.git)?$/i.test(url)) return true;
  if (/^ssh:\/\/[A-Za-z0-9._-]+@[A-Za-z0-9.-]+(?::\d+)?\/[A-Za-z0-9._~/-]+(?:\.git)?$/i.test(url)) return true;
  return false;
}

export function cloneUrlError(value: string): string | null {
  return isSafeCloneUrl(value) ? null : 'Enter a safe Git HTTPS or SSH clone URL (for example https://github.com/org/repo.git or git@github.com:org/repo.git).';
}

export function progressLabel(progress?: Record<string, unknown> | null): string {
  if (!progress || Object.keys(progress).length === 0) return 'Waiting to start';
  const phase = typeof progress.phase === 'string' ? progress.phase : 'Working';
  const files = typeof progress.files === 'number' ? ` · ${progress.files} files` : '';
  return `${phase}${files}`;
}

export function apiErrorMessage(error: unknown): string {
  if (!(error instanceof Error) || !error.message) return 'Something went wrong. Please try again.';
  try {
    const body = JSON.parse(error.message);
    return typeof body.detail === 'string' ? body.detail : error.message;
  } catch {
    return error.message;
  }
}
