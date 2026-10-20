export interface Health {
  status: 'ok' | 'unavailable';
  database: 'ready' | 'unavailable';
}

export async function getHealth(signal: AbortSignal): Promise<Health> {
  const response = await fetch('/api/health', { signal });
  if (!response.ok) throw new Error('Сервис временно недоступен');
  const body: unknown = await response.json();
  if (
    typeof body !== 'object' || body === null ||
    !('status' in body) || body.status !== 'ok' ||
    !('database' in body) || body.database !== 'ready'
  ) throw new Error('Неожиданный ответ сервера');
  return { status: body.status, database: body.database };
}
