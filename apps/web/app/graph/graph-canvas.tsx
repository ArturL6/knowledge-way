'use client';

import ForceGraph2D from 'react-force-graph-2d';
import { useEffect, useRef, useState } from 'react';

export type GraphNodeKind = 'repository' | 'directory' | 'file' | 'symbol' | 'unknown';

export type GraphNode = {
  id: string;
  label: string;
  kind: GraphNodeKind;
  [key: string]: unknown;
};

export type GraphLink = {
  source: string;
  target: string;
  relationship: string;
  confidence?: number | null;
  [key: string]: unknown;
};

export type GraphData = { nodes: GraphNode[]; links: GraphLink[] };

const nodeColors: Record<GraphNodeKind, string> = {
  repository: '#9ee7ff', directory: '#9370db', file: '#5cd6a8', symbol: '#ffcc66', unknown: '#9babca',
};

export default function GraphCanvas({ data, onNodeClick }: { data: GraphData; onNodeClick: (node: GraphNode) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 760, height: 520 });

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const resize = () => setDimensions({ width: container.clientWidth, height: Math.max(420, Math.min(620, window.innerHeight - 300)) });
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  return <div className="graph-canvas" ref={containerRef}>
    <ForceGraph2D
      graphData={data}
      width={dimensions.width}
      height={dimensions.height}
      backgroundColor="#0c1427"
      nodeLabel={(node) => { const item = node as GraphNode; return `${item.label} (${item.kind})`; }}
      nodeColor={(node) => nodeColors[(node as GraphNode).kind] ?? nodeColors.unknown}
      nodeRelSize={6}
      linkLabel={(link) => { const item = link as GraphLink; return item.confidence == null ? item.relationship : `${item.relationship} (${Math.round(item.confidence * 100)}%)`; }}
      linkColor={() => '#53698f'}
      linkDirectionalArrowLength={4}
      linkDirectionalArrowRelPos={1}
      linkWidth={1.5}
      onNodeClick={(node) => onNodeClick(node as GraphNode)}
    />
  </div>;
}
