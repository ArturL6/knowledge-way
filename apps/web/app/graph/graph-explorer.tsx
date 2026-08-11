'use client';

import dynamic from 'next/dynamic';
import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '../../lib/api';
import { apiErrorMessage } from '../../lib/repositories';
import { graphNodeKind, nodeStyles } from './graph-model';
import type { GraphData, GraphLink, GraphNode } from './graph-model';

const GraphCanvas = dynamic(() => import('./graph-canvas'), { ssr: false, loading: () => <div className="graph-state" role="status">Loading interactive graph…</div> });

/** Illustrative only — invented paths and relationships, not a real graph result. Never carries a confidence
 *  number: this repo's edges are either structural (no confidence concept) or code (confidence is a fabricated
 *  name-uniqueness artifact, see #26), so faking a number here would misrepresent both. */
const fixture: GraphData = {
  nodes: [
    { id: 'repo', label: 'demo-repo (illustrative)', kind: 'repository' }, { id: 'apps', label: 'apps', kind: 'directory' },
    { id: 'web', label: 'web', kind: 'directory' }, { id: 'api', label: 'api', kind: 'directory' },
    { id: 'search-page', label: 'search/page.tsx', kind: 'file' }, { id: 'api-main', label: 'app/main.py', kind: 'file' },
    { id: 'search-client', label: 'SearchClient', kind: 'symbol' }, { id: 'search-route', label: '/search', kind: 'symbol' },
  ],
  links: [
    { source: 'repo', target: 'apps', relationship: 'contains' }, { source: 'apps', target: 'web', relationship: 'contains' },
    { source: 'apps', target: 'api', relationship: 'contains' }, { source: 'web', target: 'search-page', relationship: 'contains' },
    { source: 'api', target: 'api-main', relationship: 'contains' }, { source: 'search-page', target: 'search-client', relationship: 'renders' },
    { source: 'search-client', target: 'search-route', relationship: 'handles' },
  ],
};

const asRecord = (value: unknown): Record<string, unknown> => value !== null && typeof value === 'object' ? value as Record<string, unknown> : {};
const stringValue = (...values: unknown[]) => values.find((value) => typeof value === 'string' || typeof value === 'number')?.toString() ?? '';
const endpointId = (value: unknown) => typeof value === 'object' && value !== null ? stringValue(asRecord(value).id) : stringValue(value);
const linkEndpointId = (value: unknown): string => endpointId(value);

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
    const resolution = typeof item.resolution === 'string' && item.resolution.trim() !== '' ? item.resolution : null;
    const countValue = item.count; const count = typeof countValue === 'number' ? countValue : typeof countValue === 'string' && countValue.trim() !== '' ? Number(countValue) : 1;
    return { ...item, source, target, relationship: stringValue(item.relationship, item.relationship_type, item.type, 'related'), confidence: normalizedConfidence, resolution, count: Number.isFinite(count) ? count : 1 };
  }).filter((link): link is GraphLink => link !== null);
  const degree = new Map<string, number>();
  for (const link of links) { degree.set(link.source, (degree.get(link.source) ?? 0) + 1); degree.set(link.target, (degree.get(link.target) ?? 0) + 1); }
  return { nodes: nodes.map((node) => ({ ...node, degree: degree.get(node.id) ?? 0 })), links };
}

type GraphStats = { totalNodes: number | null; totalEdges: number | null; returnedNodes: number | null; returnedEdges: number | null; truncated: boolean; reason: string | null };
const emptyStats: GraphStats = { totalNodes: null, totalEdges: null, returnedNodes: null, returnedEdges: null, truncated: false, reason: null };
const numberField = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;
/** Pulls the honest scalar counts (#24) off a subgraph/repo-graph response; these describe the symbol graph and
 *  are apples-to-apples, unlike `nodes.length`, which for the repo graph also includes directory/file scaffolding. */
function graphStats(response: unknown): GraphStats {
  const root = asRecord(response);
  return {
    totalNodes: numberField(root.total_nodes), totalEdges: numberField(root.total_edges),
    returnedNodes: numberField(root.returned_nodes), returnedEdges: numberField(root.returned_edges),
    truncated: root.truncated === true, reason: typeof root.reason === 'string' ? root.reason : null,
  };
}

type RepositoryOption = { id: string; name: string; indexing_status: string };

/** `/api/search/symbols` omits the symbol UUID, so a hit is resolved through its file before the graph call. */
type SymbolHit = { repository_id: string; file_id: string; path: string; start_line: number; end_line: number; symbol: string | null };
type FileSymbol = { id: string; name: string; qualified_name: string; type: string; start_line: number; end_line: number };

const SYMBOL_HIT_LIMIT = 15;
/** The symbol index tokenises on words of three characters or more, so shorter queries can never match. */
const MIN_QUERY_LENGTH = 3;
const hitKey = (hit: SymbolHit) => `${hit.file_id}:${hit.start_line}:${hit.symbol ?? ''}`;

/** Serializes the deep-link-able graph view state; the default depth is omitted to keep an all-default URL as plain `/graph`. */
export function buildGraphUrl(repositoryId: string, symbolId: string, depth: string): string {
  const params = new URLSearchParams();
  if (repositoryId) params.set('repository', repositoryId);
  if (symbolId) params.set('symbol', symbolId);
  if (depth && depth !== '2') params.set('depth', depth);
  const query = params.toString();
  return query ? `/graph?${query}` : '/graph';
}

export function normalizeGraphDepth(value: string | null): string {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed >= 1 && parsed <= 2 ? String(parsed) : '2';
}

export function parseGraphState(params: { get(key: string): string | null }): { repositoryId: string; symbolId: string; depth: string } {
  return {
    repositoryId: params.get('repository') ?? '',
    symbolId: params.get('symbol') ?? '',
    depth: normalizeGraphDepth(params.get('depth')),
  };
}

/** Picks the file symbol behind a search hit; the hit carries a qualified name and start line but no UUID. */
export function matchFileSymbol(symbols: FileSymbol[], hit: SymbolHit): FileSymbol | null {
  const named = hit.symbol ? symbols.filter((symbol) => symbol.qualified_name === hit.symbol || symbol.name === hit.symbol) : [];
  return named.find((symbol) => symbol.start_line === hit.start_line)
    ?? symbols.find((symbol) => symbol.start_line === hit.start_line && symbol.end_line === hit.end_line)
    ?? named[0]
    ?? null;
}

export default function GraphExplorer() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialState = parseGraphState(searchParams);
  const [repositoryId, setRepositoryId] = useState(initialState.repositoryId); const [symbolId, setSymbolId] = useState(initialState.symbolId); const [depth, setDepth] = useState(initialState.depth);
  const [repositories, setRepositories] = useState<RepositoryOption[]>([]);
  const [graph, setGraph] = useState<GraphData>({ nodes: [], links: [] }); const [source, setSource] = useState<'fixture' | 'api' | 'empty'>('empty');
  const [loading, setLoading] = useState(false); const [error, setError] = useState(''); const [selected, setSelected] = useState<GraphNode | null>(null);
  const [relationship, setRelationship] = useState('all');
  const [symbolQuery, setSymbolQuery] = useState(''); const [hits, setHits] = useState<SymbolHit[] | null>(null); const [symbolLabel, setSymbolLabel] = useState('');
  const [resolving, setResolving] = useState(''); const [searching, setSearching] = useState(false); const [stats, setStats] = useState<GraphStats>(emptyStats);
  const graphRequestVersion = useRef(0);
  const relationshipTypes = useMemo(() => [...new Set(graph.links.map((link) => link.relationship))].sort(), [graph]);
  const presentKinds = useMemo(() => [...new Set(graph.nodes.map((node) => node.kind))].filter((kind) => kind !== 'unknown'), [graph]);
  const filteredGraph = useMemo(() => {
    const links = graph.links.filter((link) => relationship === 'all' || link.relationship === relationship);
    const connected = new Set(links.flatMap((link) => [linkEndpointId(link.source), linkEndpointId(link.target)]));
    return { links, nodes: graph.nodes.filter((node) => connected.has(node.id) || graph.links.length === 0) };
  }, [graph, relationship]);

  async function requestGraph(repository = repositoryId, symbol = symbolId, requestedDepth = depth) {
    const version = ++graphRequestVersion.current;
    setError(''); setSelected(null); setGraph({ nodes: [], links: [] });
    if (!repository.trim() || !symbol.trim()) { setError('Enter both a repository ID and a symbol ID to load the API graph, or use the fixture demo.'); return; }
    setLoading(true);
    try {
      const boundedDepth = String(Math.max(1, Math.min(2, Number(requestedDepth) || 1)));
      const response = await api<unknown>(`/repositories/${encodeURIComponent(repository.trim())}/symbols/${encodeURIComponent(symbol.trim())}/subgraph?depth=${boundedDepth}`);
      if (version !== graphRequestVersion.current) return;
      setGraph(mapApiGraph(response)); setStats(graphStats(response)); setSource('api'); setRelationship('all');
    } catch (cause) { if (version === graphRequestVersion.current) setError(cause instanceof Error ? cause.message : 'Unable to load graph data.'); }
    finally { if (version === graphRequestVersion.current) setLoading(false); }
  }
  async function findSymbols(event: FormEvent) {
    event.preventDefault(); setError(''); setHits(null); setSymbolId(''); setSymbolLabel('');
    const query = symbolQuery.trim();
    if (!repositoryId) { setError('Choose an indexed repository first.'); return; }
    if (query.length < MIN_QUERY_LENGTH) { setError(`Enter at least ${MIN_QUERY_LENGTH} characters — the symbol index ignores shorter words.`); return; }
    setSearching(true);
    try {
      const repository = repositories.find((item) => item.id === repositoryId);
      // ponytail: `/search/symbols` takes only `q`, and its `repo:` filter is applied in Python *after* the SQL
      // LIMIT, so both it and the check below can only narrow an already-truncated global window. Good enough at
      // one repository; once several are indexed this under-returns and needs server-side scope pushdown.
      const scope = repository && !/\s/.test(repository.name) ? ` repo:${repository.name}` : '';
      const response = await api<{ results: SymbolHit[] }>(`/search/symbols?q=${encodeURIComponent(query + scope)}`);
      setHits(response.results.filter((hit) => hit.repository_id === repositoryId).slice(0, SYMBOL_HIT_LIMIT));
    } catch (cause) { setError(apiErrorMessage(cause)); }
    finally { setSearching(false); }
  }
  async function chooseSymbol(hit: SymbolHit) {
    setError(''); setResolving(hitKey(hit));
    try {
      const fileSymbols = await api<FileSymbol[]>(`/files/${encodeURIComponent(hit.file_id)}/symbols`);
      const match = matchFileSymbol(fileSymbols, hit);
      if (!match) { setError('That search hit has no indexed symbol to anchor a graph. Pick another hit.'); return; }
      setSymbolId(match.id); setSymbolLabel(match.qualified_name || match.name);
    } catch (cause) { setError(apiErrorMessage(cause)); }
    finally { setResolving(''); }
  }
  useEffect(() => { api<RepositoryOption[]>('/repositories').then((items) => { setRepositories(items.filter((item) => item.indexing_status === 'ready')); }).catch(() => {}); }, []);
  // The URL is authoritative. This applies shared links and browser Back/Forward as well as in-app navigation.
  useEffect(() => {
    const state = parseGraphState(searchParams);
    setRepositoryId(state.repositoryId); setSymbolId(state.symbolId); setDepth(state.depth); setSymbolLabel('');
    if (state.repositoryId && state.symbolId) void requestGraph(state.repositoryId, state.symbolId, state.depth);
    else if (state.repositoryId) void requestOverview(state.repositoryId);
    else { setGraph({ nodes: [], links: [] }); setSource('empty'); setStats(emptyStats); setSelected(null); }
  }, [searchParams]);
  function navigateGraph(nextRepositoryId: string, nextSymbolId: string, nextDepth: string) {
    router.push(buildGraphUrl(nextRepositoryId, nextSymbolId, nextDepth), { scroll: false });
  }
  async function requestOverview(repository = repositoryId) {
    const version = ++graphRequestVersion.current;
    setError(''); setSelected(null); setGraph({ nodes: [], links: [] });
    if (!repository.trim()) { setError('Choose an indexed repository first.'); return; }
    setLoading(true);
    try {
      const response = await api<unknown>(`/repositories/${encodeURIComponent(repository.trim())}/graph?max_nodes=100`);
      if (version !== graphRequestVersion.current) return;
      setGraph(mapApiGraph(response)); setStats(graphStats(response)); setSource('api'); setRelationship('all');
    }
    catch (cause) { if (version === graphRequestVersion.current) setError(cause instanceof Error ? cause.message : 'Unable to load repository graph data.'); }
    finally { if (version === graphRequestVersion.current) setLoading(false); }
  }
  function loadFixture() { setGraph(fixture); setSource('fixture'); setError(''); setSelected(null); setRelationship('all'); setStats(emptyStats); }

  const reasonLabel = stats.reason === 'node_cap' ? 'node cap' : stats.reason === 'edge_budget' ? 'edge budget' : null;
  const summaryCounts = source === 'api' && stats.totalNodes != null && stats.totalEdges != null && stats.returnedNodes != null && stats.returnedEdges != null
    ? `showing ${stats.returnedNodes} of ${stats.totalNodes} symbols · ${stats.returnedEdges} of ${stats.totalEdges} relationships${stats.truncated ? ` · truncated (${reasonLabel ?? 'unknown reason'})` : ''}`
    : `${filteredGraph.nodes.length} nodes · ${filteredGraph.links.length} relationships`;

  return <>
    <div className="page-heading"><div><h2>Code graph</h2><p className="muted">Explore repository structure and symbol relationships. Select a node from the accessible node list or click it in the visual graph; dragging pins a visual node.</p></div></div>
    <form className="card graph-controls" onSubmit={findSymbols}>
      <label>Repository<select value={repositoryId} onChange={(event) => navigateGraph(event.target.value, '', depth)} required><option value="">Choose an indexed repository</option>{repositories.map((repository) => <option key={repository.id} value={repository.id}>{repository.name}</option>)}</select></label>
      <label>Symbol<input value={symbolQuery} onChange={(event) => setSymbolQuery(event.target.value)} placeholder="search by name, e.g. Agent" autoComplete="off" /></label>
      <label>Depth<input type="number" min="1" max="2" value={depth} onChange={(event) => navigateGraph(repositoryId, symbolId, event.target.value)} /></label>
      <div className="graph-actions"><button type="button" onClick={() => navigateGraph(repositoryId, '', depth)} disabled={loading}>{loading ? 'Loading…' : 'Repository map'}</button><button type="submit" className="secondary-button" disabled={searching || !symbolQuery.trim()}>{searching ? 'Searching…' : 'Find symbol'}</button><button type="button" className="secondary-button" onClick={() => navigateGraph(repositoryId, symbolId, depth)} disabled={loading || !symbolId}>Focus symbol</button><button type="button" className="secondary-button" onClick={loadFixture} disabled={loading}>Fixture</button></div>
    </form>
    {error && <div className="graph-message graph-error" role="alert">{error}</div>}
    {symbolId !== '' && <div className="card symbol-selected"><span>Anchored on <strong>{symbolLabel || 'the linked symbol'}</strong> <code className="citation">{symbolId}</code></span><button type="button" className="secondary-button" onClick={() => navigateGraph(repositoryId, '', depth)}>Clear</button></div>}
    {hits !== null && <div className="card symbol-hits" aria-live="polite">{hits.length === 0 ? <p className="muted">No indexed symbol matched that name in this repository.</p> : <ul>{hits.map((hit) => <li key={hitKey(hit)}><button type="button" className="symbol-hit" disabled={resolving !== ''} onClick={() => void chooseSymbol(hit)}><span className="symbol-hit-name">{hit.symbol ?? hit.path}</span><span className="muted">{hit.path}:{hit.start_line}{resolving === hitKey(hit) ? ' · resolving…' : ''}</span></button></li>)}</ul>}</div>}
    <section className="card graph-card">
      <div className="graph-summary">{presentKinds.map((kind) => <span key={kind}><i className="legend-dot" style={{ background: nodeStyles[kind].color }} />{nodeStyles[kind].label}</span>)}<span className="muted">{source === 'fixture' ? 'Demo (illustrative)' : source === 'api' ? 'API result' : 'No graph loaded'} · {summaryCounts}</span></div>
      <div className="graph-filters"><span className="graph-edge-key"><i className="edge-sample contains" />Contains</span><span className="graph-edge-key"><i className="edge-sample defines" />Defines</span><span className="graph-edge-key"><i className="edge-sample calls" />Calls / references</span><label>Relationship<select value={relationship} onChange={(event) => setRelationship(event.target.value)}><option value="all">All types</option>{relationshipTypes.map((type) => <option key={type} value={type}>{type}</option>)}</select></label></div>
      {loading ? <div className="graph-state" role="status">Requesting graph data…</div> : filteredGraph.nodes.length > 0 ? <><div className="graph-hint">Tip: use the accessible node list below to select a node with the keyboard. Dragging a visual node pins it so dense graphs stay readable.</div><GraphCanvas data={filteredGraph} onNodeClick={setSelected} selectedNodeId={selected?.id} /></> : <div className="graph-state"><strong>No graph data to display.</strong><p className="muted">{source === 'empty' ? 'Choose a repository and symbol to load a graph, or load the fixture demo.' : graph.links.length > 0 ? 'The selected filters returned no connected nodes. Adjust filters or load the fixture demo.' : 'This selection returned no graph relationships.'}</p></div>}
    </section>
    <aside className="graph-detail" aria-labelledby="node-details-heading"><h3 id="node-details-heading">Node details</h3><p className="visually-hidden" aria-live="polite">{selected ? `Selected ${selected.label}` : 'No node selected'}</p>{selected ? <dl><dt>Label</dt><dd>{selected.label}</dd><dt>ID</dt><dd className="citation">{selected.id}</dd><dt>Kind</dt><dd>{selected.kind}</dd>{Object.entries(selected).filter(([key]) => !['id', 'label', 'kind', 'x', 'y', 'vx', 'vy', 'index', '__indexColor'].includes(key)).map(([key, value]) => <span key={key}><dt>{key}</dt><dd>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd></span>)}</dl> : <p className="muted">Select a node from the accessible node list or click it in the visual graph to inspect its identifier and metadata.</p>}</aside>
  </>;
}
