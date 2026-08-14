import { describe, expect, it } from 'vitest';
import { graphHref, sourceHref, symbolHref } from './file-navigation';

describe('file navigation', () => {
  it('links an indexed file symbol to its detail, source and bounded graph', () => {
    expect(symbolHref('repo/a', 'symbol b')).toBe('/repositories/repo%2Fa/symbols/symbol%20b');
    expect(graphHref('repo/a', 'symbol b')).toBe('/graph?repository=repo%2Fa&symbol=symbol%20b');
    expect(sourceHref('file/a', 42)).toBe('/files/file%2Fa#L42');
  });
});
