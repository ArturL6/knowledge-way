import './globals.css'; import type { Metadata } from 'next';
import Link from 'next/link';
export const metadata:Metadata={title:'knowledge-way',description:'Code intelligence, grounded answers.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><aside><h1>knowledge-way</h1><p>Code intelligence</p><nav><Link href="/">Dashboard</Link><Link href="/search">Search</Link><Link href="/graph">Code graph</Link><Link href="/chat">AI Chat</Link></nav><small>Private by design</small></aside><main>{children}</main></body></html>}
