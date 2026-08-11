'use client';

import Link from 'next/link';
import {usePathname} from 'next/navigation';

const items = [
  {href: '/', label: 'Dashboard'},
  {href: '/workspaces', label: 'Workspaces'},
  {href: '/search', label: 'Search'},
  {href: '/graph', label: 'Code graph'},
  {href: '/chat', label: 'AI Chat'},
] as const;

export default function PrimaryNavigation() {
  const pathname = usePathname();
  return <nav aria-label="Primary navigation">
    {items.map(({href, label}) => <Link key={href} href={href} aria-current={pathname === href ? 'page' : undefined}>{label}</Link>)}
  </nav>;
}
