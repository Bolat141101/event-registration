export interface EventInfo {
  id: string;
  description: string;
  starts_at: string;
  capacity: number;
  schedule_version: number;
  confirmed: number;
  waitlisted: number;
  checked_in: number;
}
export interface EventPage {
  items: EventInfo[];
  next_offset: number | null;
  server_time: string;
}
export interface Snapshot extends EventInfo {
  server_time: string;
}
export interface Participation {
  id: string;
  event_id: string;
  status: 'confirmed' | 'waitlisted' | 'cancelled';
  participation_no: number;
  waitlist_seq: number | null;
  ticket_code: string | null;
  checked_in_at: string | null;
}
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string
  ) {
    super(message);
  }
}
const messages: Record<string, string> = {
  invalid_email: 'Enter a valid email.',
  invalid_organizer_token: 'The organizer key is incorrect.',
  invalid_participant_token: 'Invalid link. Open the link from your first registration email.',
  authentication_required: 'Open the private link from your email.',
  event_not_found: 'Event not found.',
  already_checked_in: 'This ticket has already been checked in.',
  ticket_not_found: 'No valid ticket found for this event.',
  checkin_not_started: 'Check-in opens when the event starts.',
  event_started: 'The event has started. This action is no longer available.',
  invalid_start_time: 'Choose a future date and time.',
  participation_conflict: 'Participation changed. Check the current details before trying again.',
  schedule_version_conflict: 'The date changed. Refresh the details and check the new time.',
  rate_limited: 'Too many requests. Please wait a moment and try again.',
  database_unavailable: 'The service is temporarily unavailable. Please try again.',
};
export async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      headers,
      cache: 'no-store',
      signal: AbortSignal.any([
        AbortSignal.timeout(10000),
        ...(options.signal ? [options.signal] : []),
      ]),
    });
  } catch {
    if (options.signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    throw new ApiError(
      0,
      'network',
      'No connection to the server. Check your connection and try again.'
    );
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { code?: string };
    const code = typeof body.code === 'string' ? body.code : 'unknown';
    throw new ApiError(
      response.status,
      code,
      messages[code] ??
        (response.status === 422
          ? 'Check the description, email, capacity and date.'
          : response.status === 404
            ? 'Page not found.'
            : response.status === 401
              ? 'Access denied. Check your key.'
              : 'Could not complete the action. Refresh and try again.')
    );
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(
      response.status,
      'invalid_response',
      'Could not read the server response. Refresh and try again.'
    );
  }
}
const json = (value: unknown) => JSON.stringify(value);
export const api = {
  events: (signal?: AbortSignal, offset = 0) =>
    request<EventPage>(`/events?limit=20&offset=${offset}`, { signal }),
  event: (id: string, signal?: AbortSignal) => request<EventInfo>(`/events/${id}`, { signal }),
  register: (id: string, email: string) =>
    request<{ message: string }>(`/events/${id}/registrations`, {
      method: 'POST',
      body: json({ email }),
    }),
  participation: (token: string, signal?: AbortSignal) =>
    request<Participation>('/registration', { signal }, token),
  change: (kind: 'cancel' | 'resume', token: string, no: number) =>
    request<Participation>(
      `/registration/${kind}`,
      { method: 'POST', body: json({ expected_participation_no: no }) },
      token
    ),
  verify: (key: string) => request<{ status: string }>('/organizer/access', {}, key),
  create: (body: { description: string; starts_at: string; capacity: number }, key: string) =>
    request<EventInfo>('/events', { method: 'POST', body: json(body) }, key),
  reschedule: (id: string, starts_at: string, version: number, key: string) =>
    request<EventInfo>(
      `/events/${id}/schedule`,
      { method: 'PATCH', body: json({ starts_at, expected_schedule_version: version }) },
      key
    ),
  checkin: (id: string, ticket_code: string, key: string) =>
    request<Participation>(
      `/events/${id}/check-ins`,
      { method: 'POST', body: json({ ticket_code }) },
      key
    ),
};
export function isSnapshot(value: unknown, id: string): value is Snapshot {
  if (!value || typeof value !== 'object') return false;
  const item = value as Record<string, unknown>;
  return (
    item.id === id &&
    typeof item.description === 'string' &&
    typeof item.starts_at === 'string' &&
    Number.isFinite(Date.parse(item.starts_at)) &&
    typeof item.server_time === 'string' &&
    Number.isFinite(Date.parse(item.server_time)) &&
    ['capacity', 'schedule_version', 'confirmed', 'waitlisted', 'checked_in'].every(
      (name) =>
        typeof item[name] === 'number' &&
        Number.isInteger(item[name]) &&
        (item[name] as number) >= 0
    )
  );
}
