'use client';

import dynamic from 'next/dynamic';
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { api } from '../../lib/api';
import { graphNodeKind, nodeStyles } from './graph-model';
import type { GraphData, GraphLink, GraphNode, GraphNodeKind } from './graph-model';

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

const asRecord = (value: unknown): Record<string, unknown> => value !== null && typeof value === 'object' ? value as Record<string, unknown> : {};
const stringValue = (...values: unknown[]) => values.find((value) => typeof value === 'string' || typeof value === 'number')?.toString() ?? '';
const endpointId = (value: unknown) => typeof value === 'object' && value !== null ? stringValue(asRecord(value).id) : stringValue(value);

/** Maps the API's nodes/edges (or nodes/links) shape into react-force-graph data. */
export function mapApiGraph(payload: unknown): GraphData {
  const root = asRecord(payload);
  const body = asRecord(root.data);
  const rawNodes = Array.isArray(root.nodes) ? root.nodes : Array.isArray(body.nodes) ? body.nodes : [];
  const rawLinks = Array.isArray(root.edges) ? root.edges : Array.isArray(root.links) ? root.links : Array.isArray(body.edges) ? body.edges : Array.isArray(body.links) ? body.links : [];
  const rootSymbolId = stringValue(root.root_symbol_id, body.root_symbol_id);
  const nodes = rawNodes.map((raw): GraphNode | null => {
    const item = asRecord(raw); const id = stringValue(item.id, item.symbol_id, item.node_id);
    if (!id) return null;
    return { ...item, id, label: stringValue(item.qualified_name, item.label, item.name, item.path, id), kind: graphNodeKind(item.kind ?? item.type ?? item.node_type), isRoot: id === rootSymbolId };
  }).filter((node): node is GraphNode => node !== null);
  const nodeIds = new Set(nodes.map((node) => node.id));
  const links = rawLinks.map((raw): GraphLink | null => {
    const item = asRecord(raw); const source = endpointId(item.source ?? item.source_id ?? item.source_symbol_id); const target = endpointId(item.target ?? item.target_id ?? item.target_symbol_id);
    if (!source || !target || !nodeIds.has(source) || !nodeIds.has(target)) return null;
    const confidenceValue = item.confidence; const confidence = typeof confidenceValue === 'number' ? confidenceValue : typeof confidenceValue === 'string' && confidenceValue.trim() !== '' ? Number(confidenceValue) : null;
    const normalizedConfidence = Number.isFinite(confidence) ? Math.max(0, Math.min(1, confidence! > 1 ? confidence! / 100 : confidence!)) : null;
    return { ...item, source, target, relationship: stringValue(item.relationship, item.relationship_type, item.type, 'related'), confidence: normalizedConfidence };
  }).filter((link): link is GraphLink => link !== null);
  const degree = new Map<string, number>();
  for (const link of links) { degree.set(link.source, (degree.get(link.source) ?? 0) + 1); degree.set(link.target, (degree.get(link.target) ?? 0) + 1); }
  return { nodes: nodes.map((node) => ({ ...node, degree: degree.get(node.id) ?? 0 })), links };
}

type RepositoryOption = { id: string; name: string; indexing_status: string };

export default function GraphExplorer() {
  const searchParams = useSearchParams();
  const initialRepositoryId = searchParams.get('repository') ?? '';
  const initialSymbolId = searchParams.get('symbol') ?? '';
  const [repositoryId, setRepositoryId] = useState(initialRepositoryId); const [symbolId, setSymbolId] = useState(initialSymbolId); const [depth, setDepth] = useState('2');
  const [repositories, setRepositories] = useState<RepositoryOption[]>([]);
  const [graph, setGraph] = useState<GraphData>({ nodes: [], links: [] }); const [source, setSource] = useState<'fixture' | 'api' | 'empty'>('empty');
  const [loading, setLoading] = useState(false); const [error, setError] = useState(''); const [selected, setSelected] = useState<GraphNode | null>(null);
  const [relationship, setRelationship] = useState('all'); const [minimumConfidence, setMinimumConfidence] = useState('0');
  const relationshipTypes = useMemo(() => [...new Set(graph.links.map((link) => link.relationship))].sort(), [graph]);
  const presentKinds = useMemo(() => [...new Set(graph.nodes.map((node) => node.kind))].filter((kind) => kind !== 'unknown'), [graph]);
  const filteredGraph = useMemo(() => {
    const minimum = Number(minimumConfidence);
    const links = graph.links.filter((link) => (relationship === 'all' || link.relationship === relationship) && (link.confidence == null || link.confidence >= minimum));
    const connected = new Set(links.flatMap((link) => [link.source, link.target]));
    return { links, nodes: graph.nodes.filter((node) => connected.has(node.id) || graph.links.length === 0) };
  }, [graph, relationship, minimumConfidence]);

  async function requestGraph(repository = repositoryId, symbol = symbolId) {
    setError(''); setSelected(null);
    if (!repository.trim() || !symbol.trim()) { setError('Enter both a repository ID and a symbol ID to load the API graph, or use the fixture demo.'); return; }
    setLoading(true);
    try {
      const boundedDepth = String(Math.max(1, Math.min(2, Number(depth) || 1)));
      const response = await api<unknown>(`/repositories/${encodeURIComponent(repository.trim())}/symbols/${encodeURIComponent(symbol.trim())}/subgraph?depth=${boundedDepth}`);
      const nextGraph = mapApiGraph(response); setGraph(nextGraph); setSource('api'); setRelationship('all');
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load graph data.'); }
    finally { setLoading(false); }
  }
  function loadGraph(event: FormEvent) { event.preventDefault(); void requestGraph(); }
  useEffect(() => { api<RepositoryOption[]>('/repositories').then((items) => { const ready = items.filter((item) => item.indexing_status === 'ready'); setRepositories(ready); if (!repositoryId && ready[0]) setRepositoryId(ready[0].id); }).catch(() => {}); }, []);
  useEffect(() => { if (initialRepositoryId && initialSymbolId) void requestGraph(initialRepositoryId, initialSymbolId); else if (initialRepositoryId) void requestOverview(); }, [initialRepositoryId, initialSymbolId]);
  async function requestOverview() {
    setError(''); setSelected(null);
    if (!repositoryId.trim()) { setError('Choose an indexed repository first.'); return; }
    setLoading(true);
    try { const response = await api<unknown>(`/repositories/${encodeURIComponent(repositoryId.trim())}/graph?max_nodes=100`); setGraph(mapApiGraph(response)); setSource('api'); setRelationship('all'); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to load repository graph data.'); }
    finally { setLoading(false); }
  }
  function loadFixture() { setGraph(fixture); setSource('fixture'); setError(''); setSelected(null); setRelationship('all'); }

  return <>
    <div className="page-heading"><div><h2>Code graph</h2><p className="muted">Start with a bounded repository overview, then focus a symbol for its local call graph.</p></div></div>
    <form className="card graph-controls" onSubmit={loadGraph}>
      <label>Repository<select value={repositoryId} onChange={(event) => setRepositoryId(event.target.value)} required><option value="">Choose an indexed repository</option>{repositories.map((repository) => <option key={repository.id} value={repository.id}>{repository.name}</option>)}</select></label>
      <label>Symbol (optional for overview)<input value={symbolId} onChange={(event) => setSymbolId(event.target.value)} placeholder="symbol UUID for local graph" autoComplete="off" /></label>
      <label>Depth<input type="number" min="1" max="2" value={depth} onChange={(event) => setDepth(event.target.value)} /></label>
      <div className="graph-actions"><button type="button" onClick={() => void requestOverview()} disabled={loading}>{loading ? 'Loading…' : 'Repository map'}</button><button type="submit" className="secondary-button" disabled={loading || !symbolId.trim()}>Focus symbol</button><button type="button" className="secondary-button" onClick={loadFixture} disabled={loading}>Fixture</button></div>
    </form>
    {error && <div className="graph-message graph-error" role="alert">{error}</div>}
    <section className="card graph-card">
      <div className="graph-summary">{presentKinds.map((kind) => <span key={kind}><i className="legend-dot" style={{ background: nodeStyles[kind].color }} />{nodeStyles[kind].label}</span>)}<span className="muted">{source === 'fixture' ? 'Fixture demo' : source === 'api' ? 'API result' : 'No graph loaded'} · {filteredGraph.nodes.length} nodes · {filteredGraph.links.length} relationships</span></div>
      <div className="graph-filters"><label>Relationship<select value={relationship} onChange={(event) => setRelationship(event.target.value)}><option value="all">All types</option>{relationshipTypes.map((type) => <option key={type} value={type}>{type}</option>)}</select></label><label>Minimum confidence<select value={minimumConfidence} onChange={(event) => setMinimumConfidence(event.target.value)}><option value="0">Any confidence</option><option value="0.5">50% or higher</option><option value="0.75">75% or higher</option><option value="0.9">90% or higher</option></select></label></div>
      {loading ? <div className="graph-state" role="status">Requesting graph data…</div> : filteredGraph.nodes.length > 0 ? <GraphCanvas data={filteredGraph} onNodeClick={setSelected} selectedNodeId={selected?.id} /> : <div className="graph-state"><strong>No graph data to display.</strong><p className="muted">The selected filters returned no connected nodes. Adjust filters or load the fixture demo.</p></div>}
    </section>
    <aside className="graph-detail" aria-live="polite"><h3>Node details</h3>{selected ? <dl><dt>Label</dt><dd>{selected.label}</dd><dt>ID</dt><dd className="citation">{selected.id}</dd><dt>Kind</dt><dd>{selected.kind}</dd>{Object.entries(selected).filter(([key]) => !['id', 'label', 'kind', 'x', 'y', 'vx', 'vy', 'index', '__indexColor'].includes(key)).map(([key, value]) => <span key={key}><dt>{key}</dt><dd>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd></span>)}</dl> : <p className="muted">Click a node to inspect its identifier and metadata.</p>}</aside>
  </>;
}
