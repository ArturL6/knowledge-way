import './globals.css'; import type { Metadata } from 'next';
export const metadata:Metadata={title:'knowledge-way',description:'Code intelligence, grounded answers.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><aside><h1>knowledge-way</h1><p>Code intelligence</p><nav><a href="/">Dashboard</a><a href="/search">Search</a><a href="/graph">Code graph</a><a href="/chat">AI Chat</a></nav><small>Private by design</small></aside><main>{children}</main></body></html>}
