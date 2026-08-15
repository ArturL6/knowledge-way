'use client';

import { useEffect, useState } from 'react';

export type Workspace = { id: string; name: string; description: string | null };

const KEY = 'activeWorkspaceId';
const EVENT = 'active-workspace-changed';

/** localStorage is per-tab-invisible to itself (the `storage` event only fires in *other* tabs), so a same-tab
 *  change is broadcast manually — this is what lets the nav-adjacent picker and the search/graph pages agree. */
export function getActiveWorkspaceId(): string {
  if (typeof window === 'undefined') return '';
  return window.localStorage.getItem(KEY) ?? '';
}

export function setActiveWorkspaceId(id: string): void {
  if (id) window.localStorage.setItem(KEY, id);
  else window.localStorage.removeItem(KEY);
  window.dispatchEvent(new Event(EVENT));
}

export function useActiveWorkspaceId(): string {
  const [id, setId] = useState('');
  useEffect(() => {
    setId(getActiveWorkspaceId());
    const update = () => setId(getActiveWorkspaceId());
    window.addEventListener(EVENT, update);
    window.addEventListener('storage', update);
    return () => { window.removeEventListener(EVENT, update); window.removeEventListener('storage', update); };
  }, []);
  return id;
}
