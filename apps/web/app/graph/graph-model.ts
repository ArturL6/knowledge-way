export type GraphNodeKind = 'repository' | 'directory' | 'file' | 'class' | 'function' | 'declaration' | 'symbol' | 'unknown';

export type GraphNode = {
  id: string;
  label: string;
  kind: GraphNodeKind;
  degree?: number;
  isRoot?: boolean;
  [key: string]: unknown;
};

export type GraphLink = {
  source: string;
  target: string;
  relationship: string;
  confidence?: number | null;
  /** 'name-match' | 'ambiguous' for code edges; absent for structural (contains/defines) edges. */
  resolution?: string | null;
  /** Parallel edges of the same relationship collapsed into one; >=1. */
  count?: number;
  [key: string]: unknown;
};

export type GraphData = { nodes: GraphNode[]; links: GraphLink[] };

export function graphNodeKind(value: unknown): GraphNodeKind {
  const kind = `${value ?? ''}`.toLowerCase().replace(/[ _-]/g, '');
  if (kind === 'method' || kind === 'function' || kind === 'functiondefinition') return 'function';
  if (kind === 'class' || kind === 'classdefinition' || kind === 'interface') return 'class';
  if (kind === 'declaration' || kind === 'variable' || kind === 'constant') return 'declaration';
  return (['repository', 'directory', 'file', 'symbol'] as const).includes(kind as 'repository' | 'directory' | 'file' | 'symbol') ? kind as GraphNodeKind : 'unknown';
}

export const nodeStyles: Record<GraphNodeKind, { color: string; label: string }> = {
  repository: { color: '#66d9ef', label: 'Repository' },
  directory: { color: '#a78bfa', label: 'Directory' },
  file: { color: '#5cd6a8', label: 'File' },
  class: { color: '#60a5fa', label: 'Class' },
  function: { color: '#fbbf24', label: 'Function' },
  declaration: { color: '#fb923c', label: 'Declaration' },
  symbol: { color: '#e879f9', label: 'Symbol' },
  unknown: { color: '#9babca', label: 'Unknown' },
};
