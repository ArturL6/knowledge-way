import { Suspense } from 'react';
import SearchClient from './search-client';

export default function SearchPage() {
  return <Suspense fallback={<div className="graph-state" role="status">Loading search…</div>}><SearchClient /></Suspense>;
}
