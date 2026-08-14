import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="graph-state">
      <strong>Page not found.</strong>
      <p className="muted">That page doesn’t exist. <Link href="/">Back to the dashboard</Link></p>
    </div>
  );
}
