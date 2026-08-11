export type FileSymbol = { id: string; name: string; qualified_name: string; type: string; start_line: number; end_line: number };

export function symbolHref(repositoryId: string, symbolId: string): string {
  return `/repositories/${encodeURIComponent(repositoryId)}/symbols/${encodeURIComponent(symbolId)}`;
}

export function graphHref(repositoryId: string, symbolId: string): string {
  return `/graph?repository=${encodeURIComponent(repositoryId)}&symbol=${encodeURIComponent(symbolId)}`;
}

export function sourceHref(fileId: string, line: number): string {
  return `/files/${encodeURIComponent(fileId)}#L${line}`;
}
