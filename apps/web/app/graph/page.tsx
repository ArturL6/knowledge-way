import { Suspense } from 'react';
import GraphExplorer from './graph-explorer';

export default function GraphPage() {
  return <Suspense fallback={<div className="graph-state" role="status">Loading graph…</div>}><GraphExplorer /></Suspense>;
}
