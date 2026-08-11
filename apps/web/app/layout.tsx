import './globals.css';
import type { Metadata } from 'next';
import PrimaryNavigation from './primary-navigation';

export const metadata: Metadata = { title: 'knowledge-way', description: 'Code intelligence, grounded answers.' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>
    <a className="skip-link" href="#main-content">Skip to main content</a>
    <aside><h1>knowledge-way</h1><p>Code intelligence</p><PrimaryNavigation /><small>Private by design</small></aside>
    <main id="main-content" tabIndex={-1}>{children}</main>
  </body></html>;
}
