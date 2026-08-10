'use client';

import ForceGraph2D from 'react-force-graph-2d';
import { useEffect, useMemo, useRef, useState } from 'react';
import { nodeStyles } from './graph-model';
import type { GraphData, GraphLink, GraphNode } from './graph-model';

type PositionedNode = GraphNode & { x?: number; y?: number; fx?: number; fy?: number };
type GraphEndpoint = string | { id?: unknown };

const shortLabel = (label: string) => label.length > 34 ? `${label.slice(0, 31)}…` : label;
const endpointId = (endpoint: unknown) => typeof endpoint === 'object' && endpoint !== null ? `${(endpoint as { id?: unknown }).id ?? ''}` : `${endpoint ?? ''}`;
const nodeRadius = (node: GraphNode) => node.isRoot ? 12 : Math.min(9, 5 + Math.sqrt(node.degree ?? 0));
const relationshipStyle = (link: GraphLink) => {
  if (link.relationship === 'contains') return { color: '#8f7bea', width: 1.5, dash: [3, 3], arrow: 0 };
  if (link.relationship === 'defines') return { color: '#54d2a0', width: 1.8, dash: [5, 2], arrow: 0 };
  return { color: '#74a7ff', width: (link.confidence ?? 0) >= 0.9 ? 2.4 : 1.5, dash: [], arrow: 5 };
};

export default function GraphCanvas({ data, onNodeClick, selectedNodeId }: { data: GraphData; onNodeClick: (node: GraphNode) => void; selectedNodeId?: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const hasFitRef = useRef(false);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [dimensions, setDimensions] = useState({ width: 760, height: 540 });

  const graphData = useMemo<GraphData>(() => ({
    nodes: data.nodes.map((node) => ({ ...node })),
    links: data.links.map((link) => ({ ...link, source: endpointId(link.source as GraphEndpoint), target: endpointId(link.target as GraphEndpoint) })),
  }), [data]);

  useEffect(() => { hasFitRef.current = false; }, [graphData]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const resize = () => setDimensions({ width: container.clientWidth, height: Math.max(500, Math.min(720, window.innerHeight - 230)) });
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    graph.d3Force('charge')?.strength(-180);
    graph.d3Force('link')?.distance((link: GraphLink) => link.relationship === 'contains' ? 54 : 86);
  }, [graphData]);

  return <div className="graph-canvas" ref={containerRef}>
    <ForceGraph2D
      ref={graphRef}
      graphData={graphData}
      width={dimensions.width}
      height={dimensions.height}
      backgroundColor="#0a1224"
      nodeLabel={(node) => { const item = node as GraphNode; return `${item.label} (${nodeStyles[item.kind]?.label ?? nodeStyles.unknown.label})`; }}
      nodeCanvasObject={(rawNode, ctx, globalScale) => {
        const node = rawNode as PositionedNode;
        if (node.x == null || node.y == null) return;
        const style = nodeStyles[node.kind] ?? nodeStyles.unknown;
        const radius = nodeRadius(node);
        const isActive = node.isRoot || node.id === selectedNodeId || node.id === hoveredNodeId;

        ctx.beginPath();
        ctx.arc(node.x, node.y, radius + (isActive ? 4 : 0), 0, 2 * Math.PI);
        ctx.fillStyle = isActive ? `${style.color}33` : 'rgb(255 255 255 / 0.06)';
        ctx.fill();

        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
        ctx.fillStyle = style.color;
        ctx.shadowColor = style.color;
        ctx.shadowBlur = isActive ? 18 : 9;
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.lineWidth = isActive ? 2.2 : 1.2;
        ctx.strokeStyle = isActive ? '#ffffff' : 'rgb(255 255 255 / 0.38)';
        ctx.stroke();

        const showLabel = isActive || globalScale >= 1.25 || (node.degree ?? 0) >= 3;
        if (showLabel) {
          const fontSize = Math.max(11 / globalScale, 3.2);
          const label = shortLabel(node.label);
          ctx.font = `${isActive ? 700 : 500} ${fontSize}px Inter, system-ui, sans-serif`;
          const labelX = node.x + radius + 6 / globalScale;
          const labelWidth = ctx.measureText(label).width;
          const padX = 5 / globalScale;
          const padY = 3 / globalScale;
          ctx.fillStyle = isActive ? 'rgb(11 18 36 / 0.92)' : 'rgb(11 18 36 / 0.72)';
          ctx.fillRect(labelX - padX, node.y - fontSize / 2 - padY, labelWidth + padX * 2, fontSize + padY * 2);
          ctx.textAlign = 'left';
          ctx.textBaseline = 'middle';
          ctx.fillStyle = '#eef5ff';
          ctx.fillText(label, labelX, node.y);
        }
      }}
      nodePointerAreaPaint={(rawNode, color, ctx, globalScale) => {
        const node = rawNode as PositionedNode;
        if (node.x == null || node.y == null) return;
        const radius = nodeRadius(node);
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius + 10, 0, 2 * Math.PI);
        ctx.fill();
        const label = shortLabel(node.label);
        const fontSize = Math.max(11 / globalScale, 3.2);
        ctx.font = `600 ${fontSize}px Inter, system-ui, sans-serif`;
        ctx.fillRect(node.x + radius, node.y - fontSize, ctx.measureText(label).width + 14 / globalScale, fontSize * 2);
      }}
      linkLabel={(link) => { const item = link as GraphLink; return item.confidence == null ? item.relationship : `${item.relationship} (${Math.round(item.confidence * 100)}%)`; }}
      linkColor={(link) => relationshipStyle(link as GraphLink).color}
      linkLineDash={(link) => relationshipStyle(link as GraphLink).dash}
      linkDirectionalArrowLength={(link) => relationshipStyle(link as GraphLink).arrow}
      linkDirectionalArrowRelPos={1}
      linkWidth={(link) => relationshipStyle(link as GraphLink).width}
      d3AlphaDecay={0.028}
      d3VelocityDecay={0.34}
      cooldownTicks={220}
      onEngineStop={() => { if (!hasFitRef.current) { graphRef.current?.zoomToFit(450, 80); hasFitRef.current = true; } }}
      onNodeHover={(node) => setHoveredNodeId(node ? (node as GraphNode).id : null)}
      onNodeClick={(node) => onNodeClick(node as GraphNode)}
      onNodeDragEnd={(node) => { const item = node as PositionedNode; item.fx = item.x; item.fy = item.y; }}
    />
  </div>;
}
