'use client';

import dynamic from 'next/dynamic';
import { useState } from 'react';
import type { GraphData } from './graph-canvas';

const GraphCanvas = dynamic(() => import('./graph-canvas'), {
  ssr: false,
  loading: () => <div className="graph-state" role="status">Loading interactive graph…</div>,
});

const fixture: GraphData = {
  nodes: [
    { id: 'repo', label: 'knowledge-way', kind: 'repository' },
    { id: 'apps', label: 'apps', kind: 'directory' },
    { id: 'web', label: 'web', kind: 'directory' },
    { id: 'api', label: 'api', kind: 'directory' },
    { id: 'search-page', label: 'search/page.tsx', kind: 'file' },
    { id: 'api-main', label: 'app/main.py', kind: 'file' },
    { id: 'search-client', label: 'SearchClient', kind: 'symbol' },
    { id: 'search-route', label: '/search', kind: 'symbol' },
  ],
  links: [
    { source: 'repo', target: 'apps', relationship: 'contains' },
    { source: 'apps', target: 'web', relationship: 'contains' },
    { source: 'apps', target: 'api', relationship: 'contains' },
    { source: 'web', target: 'search-page', relationship: 'contains' },
    { source: 'api', target: 'api-main', relationship: 'contains' },
    { source: 'search-page', target: 'search-client', relationship: 'renders' },
    { source: 'search-client', target: 'search-route', relationship: 'handles' },
  ],
};

const emptyGraph: GraphData = { nodes: [], links: [] };

export default function GraphExplorer() {
  const [showFixture, setShowFixture] = useState(true);
  const graph = showFixture ? fixture : emptyGraph;

  return (
    <>
      <div className="page-heading">
        <div>
          <h2>Code graph</h2>
          <p className="muted">KW-005 proof of concept — static fixture data only; no graph API is connected.</p>
        </div>
        <button type="button" onClick={() => setShowFixture((current) => !current)}>
          {showFixture ? 'Show empty state' : 'Load fixture graph'}
        </button>
      </div>

      <section className="card graph-card">
        <div className="graph-summary">
          <span><i className="legend-dot repository" />Repository</span>
          <span><i className="legend-dot directory" />Directory</span>
          <span><i className="legend-dot file" />File</span>
          <span><i className="legend-dot symbol" />Symbol</span>
          <span className="muted">{graph.nodes.length} nodes · {graph.links.length} relationships</span>
        </div>
        {graph.nodes.length > 0 ? (
          <GraphCanvas data={graph} />
        ) : (
          <div className="graph-state">
            <strong>No graph data to display.</strong>
            <p className="muted">Load the fixture graph to preview the visualisation. A future slice will supply repository graph data.</p>
          </div>
        )}
      </section>
    </>
  );
}
