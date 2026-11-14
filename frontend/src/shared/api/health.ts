export interface Health {
  status: 'ok';
  service: string;
  version: string;
}

export async function getHealth(signal?: AbortSignal): Promise<Health> {
  const baseUrl = (
    import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
  ).replace(/\/$/, '');
  const response = await fetch(`${baseUrl}/health`, {
    signal: signal
      ? AbortSignal.any([signal, AbortSignal.timeout(8000)])
      : AbortSignal.timeout(8000),
  });
  if (!response.ok) throw new Error(`API: HTTP ${response.status}`);
  const data: unknown = await response.json();
  if (
    typeof data !== 'object' ||
    data === null ||
    !('status' in data) ||
    data.status !== 'ok' ||
    !('service' in data) ||
    typeof data.service !== 'string' ||
    !('version' in data) ||
    typeof data.version !== 'string'
  )
    throw new Error('Respuesta de salud inválida');
  return data as Health;
}
