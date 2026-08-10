import { describe, expect, it } from 'vitest';
import { mapApiGraph, matchFileSymbol } from './graph-explorer';

describe('mapApiGraph', () => {
  it('maps a nodes/edges payload into GraphData with computed degree', () => {
    const payload = {
      root_symbol_id: 'sym-1',
      nodes: [
        { id: 'sym-1', name: 'Foo', kind: 'class' },
        { id: 'sym-2', qualified_name: 'Bar.baz', type: 'method' },
      ],
      edges: [{ source: 'sym-1', target: 'sym-2', relationship_type: 'calls', confidence: 0.8, resolution: 'name-match', count: 3 }],
    };
    const graph = mapApiGraph(payload);
    expect(graph.nodes).toHaveLength(2);
    expect(graph.links).toHaveLength(1);

    const root = graph.nodes.find((node) => node.id === 'sym-1');
    expect(root?.isRoot).toBe(true);
    expect(root?.label).toBe('Foo');
    expect(root?.kind).toBe('class');
    expect(root?.degree).toBe(1);

    const other = graph.nodes.find((node) => node.id === 'sym-2');
    expect(other?.isRoot).toBe(false);
    expect(other?.label).toBe('Bar.baz');
    expect(other?.kind).toBe('function');
    expect(other?.degree).toBe(1);

    expect(graph.links[0]).toMatchObject({ source: 'sym-1', target: 'sym-2', relationship: 'calls', confidence: 0.8, resolution: 'name-match', count: 3 });
  });

  it('reads nodes/links nested under a data wrapper', () => {
    const payload = { data: { nodes: [{ id: 'a' }, { id: 'b' }], links: [{ source: 'a', target: 'b' }] } };
    const graph = mapApiGraph(payload);
    expect(graph.nodes.map((n) => n.id)).toEqual(['a', 'b']);
    expect(graph.links).toEqual([{ source: 'a', target: 'b', relationship: 'related', confidence: null, resolution: null, count: 1 }]);
  });

  it('defaults resolution to null and count to 1 when the edge omits them (e.g. structural contains/defines edges)', () => {
    const payload = { nodes: [{ id: 'a' }, { id: 'b' }], edges: [{ source: 'a', target: 'b', relationship: 'contains' }] };
    const graph = mapApiGraph(payload);
    expect(graph.links[0]).toMatchObject({ relationship: 'contains', resolution: null, count: 1 });
  });

  it('maps a low-confidence ambiguous code edge and preserves its count', () => {
    const payload = { nodes: [{ id: 'a' }, { id: 'b' }], edges: [{ source: 'a', target: 'b', relationship: 'calls', resolution: 'ambiguous', count: 5 }] };
    const graph = mapApiGraph(payload);
    expect(graph.links[0]).toMatchObject({ resolution: 'ambiguous', count: 5 });
  });

  it('resolves node ids from symbol_id/node_id fallbacks', () => {
    const payload = { nodes: [{ symbol_id: 's1' }, { node_id: 'n1' }] };
    const graph = mapApiGraph(payload);
    expect(graph.nodes.map((n) => n.id)).toEqual(['s1', 'n1']);
  });

  it('drops nodes without a resolvable id', () => {
    const payload = { nodes: [{ name: 'no id here' }, { id: 'ok' }] };
    const graph = mapApiGraph(payload);
    expect(graph.nodes).toHaveLength(1);
    expect(graph.nodes[0].id).toBe('ok');
  });

  it('drops links whose endpoints do not resolve to a known node', () => {
    const payload = { nodes: [{ id: 'a' }], edges: [{ source: 'a', target: 'missing' }] };
    const graph = mapApiGraph(payload);
    expect(graph.links).toHaveLength(0);
    expect(graph.nodes[0].degree).toBe(0);
  });

  it('resolves object-shaped endpoints via their nested id', () => {
    const payload = { nodes: [{ id: 'a' }, { id: 'b' }], edges: [{ source: { id: 'a' }, target: { id: 'b' } }] };
    const graph = mapApiGraph(payload);
    expect(graph.links[0]).toMatchObject({ source: 'a', target: 'b' });
  });

  it('normalizes a 0-1 confidence value unchanged', () => {
    const payload = { nodes: [{ id: 'a' }, { id: 'b' }], edges: [{ source: 'a', target: 'b', confidence: 0.42 }] };
    expect(mapApiGraph(payload).links[0].confidence).toBe(0.42);
  });

  it('normalizes a percentage-style confidence value (>1) by dividing by 100', () => {
    const payload = { nodes: [{ id: 'a' }, { id: 'b' }], edges: [{ source: 'a', target: 'b', confidence: 80 }] };
    expect(mapApiGraph(payload).links[0].confidence).toBe(0.8);
  });

  it('clamps confidence to the [0, 1] range', () => {
    const payload = { nodes: [{ id: 'a' }, { id: 'b' }], edges: [{ source: 'a', target: 'b', confidence: 500 }] };
    expect(mapApiGraph(payload).links[0].confidence).toBe(1);
  });

  it('parses a numeric string confidence value', () => {
    const payload = { nodes: [{ id: 'a' }, { id: 'b' }], edges: [{ source: 'a', target: 'b', confidence: '0.5' }] };
    expect(mapApiGraph(payload).links[0].confidence).toBe(0.5);
  });

  it('treats a non-numeric confidence as null', () => {
    const payload = { nodes: [{ id: 'a' }, { id: 'b' }], edges: [{ source: 'a', target: 'b', confidence: 'n/a' }] };
    expect(mapApiGraph(payload).links[0].confidence).toBeNull();
  });

  it('returns an empty graph for an empty or malformed payload', () => {
    expect(mapApiGraph({})).toEqual({ nodes: [], links: [] });
    expect(mapApiGraph(null)).toEqual({ nodes: [], links: [] });
    expect(mapApiGraph('not an object')).toEqual({ nodes: [], links: [] });
  });
});

describe('matchFileSymbol', () => {
  const symbols = [
    { id: '1', name: 'foo', qualified_name: 'Module.foo', type: 'function', start_line: 10, end_line: 20 },
    { id: '2', name: 'bar', qualified_name: 'Module.bar', type: 'function', start_line: 30, end_line: 40 },
    { id: '3', name: 'foo', qualified_name: 'Other.foo', type: 'function', start_line: 50, end_line: 60 },
  ];

  it('matches by qualified_name/name and start_line', () => {
    const hit = { repository_id: 'r', file_id: 'f', path: 'p', start_line: 10, end_line: 20, symbol: 'Module.foo' };
    expect(matchFileSymbol(symbols, hit)).toEqual(symbols[0]);
  });

  it('matches a bare name against either name or qualified_name', () => {
    const hit = { repository_id: 'r', file_id: 'f', path: 'p', start_line: 50, end_line: 60, symbol: 'foo' };
    expect(matchFileSymbol(symbols, hit)).toEqual(symbols[2]);
  });

  it('falls back to start_line/end_line when the named match has no line hit', () => {
    const hit = { repository_id: 'r', file_id: 'f', path: 'p', start_line: 30, end_line: 40, symbol: 'nonexistent' };
    expect(matchFileSymbol(symbols, hit)).toEqual(symbols[1]);
  });

  it('falls back to the first name match when no line matches at all', () => {
    const hit = { repository_id: 'r', file_id: 'f', path: 'p', start_line: 999, end_line: 999, symbol: 'foo' };
    expect(matchFileSymbol(symbols, hit)).toEqual(symbols[0]);
  });

  it('returns null when the hit has no symbol name and no line match', () => {
    const hit = { repository_id: 'r', file_id: 'f', path: 'p', start_line: 999, end_line: 999, symbol: null };
    expect(matchFileSymbol(symbols, hit)).toBeNull();
  });

  it('matches purely by line range when the hit has no symbol name', () => {
    const hit = { repository_id: 'r', file_id: 'f', path: 'p', start_line: 30, end_line: 40, symbol: null };
    expect(matchFileSymbol(symbols, hit)).toEqual(symbols[1]);
  });
});
