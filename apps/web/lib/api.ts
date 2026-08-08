const publicApi = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
const API = typeof window === 'undefined' ? (process.env.API_INTERNAL_URL || publicApi) : publicApi;

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: {'Content-Type': 'application/json', ...(init?.headers || {})},
    cache: 'no-store',
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export {API};