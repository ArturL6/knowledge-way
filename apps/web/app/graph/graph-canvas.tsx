'use client';

import ForceGraph2D from 'react-force-graph-2d';
import { useEffect, useRef, useState } from 'react';

export type GraphNode = {
  id: string;
  label: string;
  kind: 'repository' | 'directory' | 'file' | 'symbol';
};

export type GraphLink = {
  source: string;
  target: string;
  relationship: string;
};

export type GraphData = {
  nodes: GraphNode[];
  links: GraphLink[];
};

const nodeColors: Record<GraphNode['kind'], string> = {
  repository: '#9ee7ff',
  directory: '#9370db',
  file: '#5cd6a8',
  symbol: '#ffcc66',
};

export default function GraphCanvas({ data }: { data: GraphData }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 760, height: 520 });

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const resize = () => {
      setDimensions({
        width: container.clientWidth,
        height: Math.max(420, Math.min(620, window.innerHeight - 260)),
      });
    };

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="graph-canvas" ref={containerRef}>
      <ForceGraph2D
        graphData={data}
        width={dimensions.width}
        height={dimensions.height}
        backgroundColor="#0c1427"
        nodeLabel={(node) => {
          const graphNode = node as GraphNode;
          return `${graphNode.label} (${graphNode.kind})`;
        }}
        nodeColor={(node) => nodeColors[(node as GraphNode).kind]}
        nodeRelSize={6}
        linkLabel={(link) => (link as GraphLink).relationship}
        linkColor={() => '#53698f'}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkWidth={1.5}
      />
    </div>
  );
}
