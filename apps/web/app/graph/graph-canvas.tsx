'use client';

import ForceGraph2D from 'react-force-graph-2d';
import { useEffect, useRef, useState } from 'react';
import { nodeStyles } from './graph-model';
import type { GraphData, GraphLink, GraphNode } from './graph-model';

const shortLabel = (label: string) => label.length > 34 ? `${label.slice(0, 31)}…` : label;

export default function GraphCanvas({ data, onNodeClick, selectedNodeId }: { data: GraphData; onNodeClick: (node: GraphNode) => void; selectedNodeId?: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [dimensions, setDimensions] = useState({ width: 760, height: 520 });

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const resize = () => setDimensions({ width: container.clientWidth, height: Math.max(460, Math.min(680, window.innerHeight - 260)) });
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  return <div className="graph-canvas" ref={containerRef}>
    <ForceGraph2D
      ref={graphRef}
      graphData={data}
      width={dimensions.width}
      height={dimensions.height}
      backgroundColor="#0c1427"
      nodeLabel={(node) => { const item = node as GraphNode; return `${item.label} (${nodeStyles[item.kind].label})`; }}
      nodeCanvasObject={(rawNode, ctx, globalScale) => {
        const node = rawNode as GraphNode & { x?: number; y?: number };
        if (node.x == null || node.y == null) return;
        const style = nodeStyles[node.kind] ?? nodeStyles.unknown;
        const radius = node.isRoot ? 10 : Math.min(7, 4 + Math.sqrt(node.degree ?? 0));
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
        ctx.fillStyle = style.color;
        ctx.shadowColor = style.color;
        ctx.shadowBlur = node.isRoot ? 16 : 7;
        ctx.fill();
        ctx.shadowBlur = 0;
        if (node.isRoot) { ctx.lineWidth = 2; ctx.strokeStyle = '#ffffff'; ctx.stroke(); }
        const showLabel = node.isRoot || node.id === selectedNodeId || node.id === hoveredNodeId || (globalScale >= 1.65 && (node.degree ?? 0) >= 4);
        if (showLabel) {
          const fontSize = Math.max(10 / globalScale, 2.8);
          ctx.font = `${node.isRoot || node.id === selectedNodeId ? 600 : 450} ${fontSize}px Inter, system-ui, sans-serif`;
          ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
          ctx.fillStyle = '#e7edf7';
          ctx.fillText(shortLabel(node.label), node.x + radius + 4 / globalScale, node.y);
        }
      }}
      nodePointerAreaPaint={(rawNode, color, ctx) => {
        const node = rawNode as GraphNode & { x?: number; y?: number };
        if (node.x == null || node.y == null) return;
        ctx.fillStyle = color; ctx.beginPath(); ctx.arc(node.x, node.y, node.isRoot ? 13 : 10, 0, 2 * Math.PI); ctx.fill();
      }}
      linkLabel={(link) => { const item = link as GraphLink; return item.confidence == null ? item.relationship : `${item.relationship} (${Math.round(item.confidence * 100)}%)`; }}
      linkColor={() => '#6386bd'}
      linkDirectionalArrowLength={5}
      linkDirectionalArrowRelPos={1}
      linkWidth={(link) => ((link as GraphLink).confidence ?? 0) >= 0.9 ? 1.8 : 1.2}
      d3AlphaDecay={0.035}
      d3VelocityDecay={0.3}
      cooldownTicks={180}
      onEngineStop={() => graphRef.current?.zoomToFit(350, 70)}
      onNodeHover={(node) => setHoveredNodeId(node ? (node as GraphNode).id : null)}
      onNodeClick={(node) => onNodeClick(node as GraphNode)}
    />
  </div>;
}
