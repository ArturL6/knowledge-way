'use client';

import dynamic from 'next/dynamic';
import { FormEvent, useMemo, useState } from 'react';
import type { GraphData, GraphLink, GraphNode, GraphNodeKind } from './graph-canvas';

const GraphCanvas = dynamic(() => import('./graph-canvas'), { ssr: false, loading: () => <div className="graph-state" role="status">Loading interactive graph…</div> });

const fixture: GraphData = {
  nodes: [
    { id: 'repo', label: 'knowledge-way', kind: 'repository' }, { id: 'apps', label: 'apps', kind: 'directory' },
    { id: 'web', label: 'web', kind: 'directory' }, { id: 'api', label: 'api', kind: 'directory' },
    { id: 'search-page', label: 'search/page.tsx', kind: 'file' }, { id: 'api-main', label: 'app/main.py', kind: 'file' },
    { id: 'search-client', label: 'SearchClient', kind: 'symbol' }, { id: 'search-route', label: '/search', kind: 'symbol' },
  ],
  links: [
    { source: 'repo', target: 'apps', relationship: 'contains', confidence: 1 }, { source: 'apps', target: 'web', relationship: 'contains', confidence: 1 },
    { source: 'apps', target: 'api', relationship: 'contains', confidence: 1 }, { source: 'web', target: 'search-page', relationship: 'contains', confidence: 1 },
    { source: 'api', target: 'api-main', relationship: 'contains', confidence: 1 }, { source: 'search-page', target: 'search-client', relationship: 'renders', confidence: 0.94 },
    { source: 'search-client', target: 'search-route', relationship: 'handles', confidence: 0.87 },
  ],
};

const knownKinds = new Set<GraphNodeKind>(['repository', 'directory', 'file', 'symbol', 'unknown']);
const asRecord = (value: unknown): Record<string, unknown> => value !== null && typeof value === 'object' ? value as Record<string, unknown> : {};
const stringValue = (...values: unknown[]) => values.find((value) => typeof value === 'string' || typeof value === 'number')?.toString() ?? '';
const endpointId = (value: unknown) => typeof value === 'object' && value !== null ? stringValue(asRecord(value).id) : stringValue(value);

/** Maps the future API's nodes/edges (or nodes/links) shape into react-force-graph data. */
export function mapApiGraph(payload: unknown): GraphData {
  const root = asRecord(payload);
  const body = asRecord(root.data);
  const rawNodes = Array.isArray(root.nodes) ? root.nodes : Array.isArray(body.nodes) ? body.nodes : [];
  const rawLinks = Array.isArray(root.edges) ? root.edges : Array.isArray(root.links) ? root.links : Array.isArray(body.edges) ? body.edges : Array.isArray(body.links) ? body.links : [];
  const nodes = rawNodes.map((raw): GraphNode | null => {
    const item = asRecord(raw); const id = stringValue(item.id, item.symbol_id, item.node_id);
    if (!id) return null;
    const rawKind = stringValue(item.kind, item.type, item.node_type).toLowerCase() as GraphNodeKind;
    return { ...item, id, label: stringValue(item.label, item.name, item.qualified_name, item.path, id), kind: knownKinds.has(rawKind) ? rawKind : 'unknown' };
  }).filter((node): node is GraphNode => node !== null);
  const nodeIds = new Set(nodes.map((node) => node.id));
  const links = rawLinks.map((raw): GraphLink | null => {
    const item = asRecord(raw); const source = endpointId(item.source ?? item.source_id ?? item.source_symbol_id); const target = endpointId(item.target ?? item.target_id ?? item.target_symbol_id);
    if (!source || !target || !nodeIds.has(source) || !nodeIds.has(target)) return null;
    const confidenceValue = item.confidence; const confidence = typeof confidenceValue === 'number' ? confidenceValue : typeof confidenceValue === 'string' && confidenceValue.trim() !== '' ? Number(confidenceValue) : null;
    return { ...item, source, target, relationship: stringValue(item.relationship, item.relationship_type, item.type, 'related'), confidence: Number.isFinite(confidence) ? confidence : null };
  }).filter((link): link is GraphLink => link !== null);
  return { nodes, links };
}

export default function GraphExplorer() {
  const [repositoryId, setRepositoryId] = useState(''); const [symbolId, setSymbolId] = useState(''); const [depth, setDepth] = useState('2');
  const [graph, setGraph] = useState<GraphData>(fixture); const [source, setSource] = useState<'fixture' | 'api'>('fixture');
  const [loading, setLoading] = useState(false); const [error, setError] = useState(''); const [selected, setSelected] = useState<GraphNode | null>(null);
  const [relationship, setRelationship] = useState('all'); const [minimumConfidence, setMinimumConfidence] = useState('0');
  const relationshipTypes = useMemo(() => [...new Set(graph.links.map((link) => link.relationship))].sort(), [graph]);
  const filteredGraph = useMemo(() => {
    const minimum = Number(minimumConfidence);
    const links = graph.links.filter((link) => (relationship === 'all' || link.relationship === relationship) && (link.confidence == null || link.confidence >= minimum));
    const connected = new Set(links.flatMap((link) => [link.source, link.target]));
    return { links, nodes: graph.nodes.filter((node) => connected.has(node.id) || graph.links.length === 0) };
  }, [graph, relationship, minimumConfidence]);

  async function loadGraph(event: FormEvent) {
    event.preventDefault(); setError(''); setSelected(null);
    if (!repositoryId.trim() || !symbolId.trim()) { setError('Enter both a repository ID and a symbol ID to load the API graph, or use the fixture demo.'); return; }
    setLoading(true);
    try {
      const boundedDepth = String(Math.max(1, Math.min(2, Number(depth) || 1)));
      const apiBase = process.env.NEXT_PUBLIC_API_URL || '/api';
      const response = await fetch(`${apiBase}/repositories/${encodeURIComponent(repositoryId.trim())}/symbols/${encodeURIComponent(symbolId.trim())}/subgraph?depth=${boundedDepth}`, { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`Graph API returned ${response.status}.`);
      const nextGraph = mapApiGraph(await response.json()); setGraph(nextGraph); setSource('api'); setRelationship('all');
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load graph data.'); }
    finally { setLoading(false); }
  }
  function loadFixture() { setGraph(fixture); setSource('fixture'); setError(''); setSelected(null); setRelationship('all'); }

  return <>
    <div className="page-heading"><div><h2>Code graph</h2><p className="muted">Explore a repository subgraph by symbol, or use the explicit fixture demo without calling the API.</p></div></div>
    <form className="card graph-controls" onSubmit={loadGraph}>
      <label>Repository ID<input value={repositoryId} onChange={(event) => setRepositoryId(event.target.value)} placeholder="repository UUID" autoComplete="off" /></label>
      <label>Symbol ID<input value={symbolId} onChange={(event) => setSymbolId(event.target.value)} placeholder="symbol UUID" autoComplete="off" /></label>
      <label>Depth<input type="number" min="1" max="10" value={depth} onChange={(event) => setDepth(event.target.value)} /></label>
      <div className="graph-actions"><button type="submit" disabled={loading}>{loading ? 'Loading…' : 'Load graph'}</button><button type="button" className="secondary-button" onClick={loadFixture} disabled={loading}>Use fixture demo</button></div>
    </form>
    {error && <div className="graph-message graph-error" role="alert">{error}</div>}
    <section className="card graph-card">
      <div className="graph-summary"><span><i className="legend-dot repository" />Repository</span><span><i className="legend-dot directory" />Directory</span><span><i className="legend-dot file" />File</span><span><i className="legend-dot symbol" />Symbol</span><span className="muted">{source === 'fixture' ? 'Fixture demo' : 'API result'} · {filteredGraph.nodes.length} nodes · {filteredGraph.links.length} relationships</span></div>
      <div className="graph-filters"><label>Relationship<select value={relationship} onChange={(event) => setRelationship(event.target.value)}><option value="all">All types</option>{relationshipTypes.map((type) => <option key={type} value={type}>{type}</option>)}</select></label><label>Minimum confidence<select value={minimumConfidence} onChange={(event) => setMinimumConfidence(event.target.value)}><option value="0">Any confidence</option><option value="0.5">50% or higher</option><option value="0.75">75% or higher</option><option value="0.9">90% or higher</option></select></label></div>
      {loading ? <div className="graph-state" role="status">Requesting graph data…</div> : filteredGraph.nodes.length > 0 ? <GraphCanvas data={filteredGraph} onNodeClick={setSelected} /> : <div className="graph-state"><strong>No graph data to display.</strong><p className="muted">The selected filters returned no connected nodes. Adjust filters or load the fixture demo.</p></div>}
    </section>
    <aside className="graph-detail" aria-live="polite"><h3>Node details</h3>{selected ? <dl><dt>Label</dt><dd>{selected.label}</dd><dt>ID</dt><dd className="citation">{selected.id}</dd><dt>Kind</dt><dd>{selected.kind}</dd>{Object.entries(selected).filter(([key]) => !['id', 'label', 'kind', 'x', 'y', 'vx', 'vy', 'index', '__indexColor'].includes(key)).map(([key, value]) => <span key={key}><dt>{key}</dt><dd>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd></span>)}</dl> : <p className="muted">Click a node to inspect its identifier and metadata.</p>}</aside>
  </>;
}
