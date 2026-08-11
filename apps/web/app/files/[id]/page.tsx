import Link from 'next/link';
import { api } from '../../../lib/api';
import { graphHref, sourceHref, symbolHref, type FileSymbol } from '../file-navigation';

type FileDetail = { id: string; repository_id: string; path: string; language: string; content: string; indexed_commit_sha: string };

export default async function FilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const file = await api<FileDetail>(`/files/${encodeURIComponent(id)}`);
  const symbols = await api<FileSymbol[]>(`/files/${encodeURIComponent(id)}/symbols`);
  const repositoryHref = '/';

  return <>
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      <Link href="/">Repositories</Link><span aria-hidden="true">/</span>
      <Link href={repositoryHref}>Repository {file.repository_id.slice(0, 8)}</Link><span aria-hidden="true">/</span>
      <span aria-current="page">{file.path}</span>
    </nav>
    <div className="page-heading"><div><h2>{file.path}</h2><p className="muted">{file.language} · commit {file.indexed_commit_sha?.slice(0, 12)}</p></div></div>
    <div className="repository-actions"><Link href={repositoryHref}>Open repository →</Link><a href="#symbols">Browse symbols ↓</a></div>
    <section className="card file-source-section" aria-labelledby="source-heading"><h3 id="source-heading">Source</h3><pre className="file-source">{file.content}</pre></section>
    <section className="card file-symbols" id="symbols" aria-labelledby="symbols-heading"><h3 id="symbols-heading">Symbols ({symbols.length})</h3>{symbols.length === 0 ? <p className="muted">No indexed symbols in this file.</p> : <ul>{symbols.map(symbol => <li key={symbol.id}><Link href={symbolHref(file.repository_id, symbol.id)}>{symbol.qualified_name || symbol.name}</Link><span className="muted"> · {symbol.type} · lines {symbol.start_line}–{symbol.end_line}</span><span className="file-symbol-actions"><Link href={sourceHref(file.id, symbol.start_line)}>Source</Link><Link href={graphHref(file.repository_id, symbol.id)}>Graph</Link></span></li>)}</ul>}</section>
  </>;
}
