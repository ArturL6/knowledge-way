import { describe, expect, it } from 'vitest';
import { buildSearchUrl, parseSearchState, searchView } from './search-client';

describe('buildSearchUrl', () => {
  it('returns the bare path for an empty, default-mode, no-rerank search', () => {
    expect(buildSearchUrl('', 'hybrid', false)).toBe('/search');
  });

  it('includes the query', () => {
    expect(buildSearchUrl('auth', 'hybrid', false)).toBe('/search?q=auth');
  });

  it('omits mode when it is the default', () => {
    expect(buildSearchUrl('auth', 'hybrid', false)).not.toContain('mode');
  });

  it('includes a non-default mode', () => {
    expect(buildSearchUrl('auth', 'semantic', false)).toBe('/search?q=auth&mode=semantic');
  });

  it('includes rerank only when true', () => {
    expect(buildSearchUrl('auth', 'hybrid', true)).toBe('/search?q=auth&rerank=true');
    expect(buildSearchUrl('auth', 'hybrid', false)).not.toContain('rerank');
  });

  it('combines a non-default mode and rerank', () => {
    expect(buildSearchUrl('auth', 'hybrid', true)).toBe('/search?q=auth&rerank=true');
  });

  it('percent-encodes special characters in the query', () => {
    expect(buildSearchUrl('repo:backend lang:python', 'hybrid', false)).toBe('/search?q=repo%3Abackend+lang%3Apython');
  });
});

describe('parseSearchState', () => {
  it('defaults to an empty hybrid, non-reranked search when params are absent', () => {
    expect(parseSearchState(new URLSearchParams(''))).toEqual({ q: '', mode: 'hybrid', rerank: false });
  });

  it('reads back a full round trip from buildSearchUrl', () => {
    const url = buildSearchUrl('auth repo:backend', 'semantic', true);
    const params = new URLSearchParams(url.split('?')[1] ?? '');
    expect(parseSearchState(params)).toEqual({ q: 'auth repo:backend', mode: 'semantic', rerank: true });
  });

  it('treats any rerank value other than the literal string "true" as false', () => {
    expect(parseSearchState(new URLSearchParams('rerank=1'))).toMatchObject({ rerank: false });
  });
});

describe('searchView', () => {
  it('is idle before any search has run', () => {
    expect(searchView(false, 0, false)).toBe('idle');
  });

  it('is results when a search returned at least one hit', () => {
    expect(searchView(true, 3, false)).toBe('results');
  });

  it('is empty when a search completed with zero hits — distinct from idle', () => {
    expect(searchView(true, 0, false)).toBe('empty');
  });

  it('is error when the search failed, even if not yet marked searched', () => {
    expect(searchView(false, 0, true)).toBe('error');
  });
});
