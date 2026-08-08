import {api} from '../lib/api';
import {Repository} from '../lib/repositories';
import DashboardClient from './dashboard-client';

export default async function Home() {
  let repos: Repository[] = [];
  try { repos = await api<Repository[]>('/repositories'); } catch { /* The client can still connect once the API is available. */ }
  return <>
    <h2>Repository dashboard</h2>
    <p className="muted">Index, search, and understand code across every connected repository.</p>
    <DashboardClient initialRepos={repos} />
  </>;
}
