'use client';

import { useEffect } from 'react';

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { console.error(error); }, [error]);
  return (
    <div className="graph-message graph-error" role="alert">
      <strong>Something went wrong.</strong>
      <p className="muted">{error.message || 'An unexpected error occurred.'}</p>
      <button type="button" onClick={reset}>Try again</button>
    </div>
  );
}
