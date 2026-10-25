import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError, isSnapshot, request } from '../src/api/client';

afterEach(() => vi.unstubAllGlobals());
describe('HTTP boundary', () => {
  it('sends participant credentials only in Authorization and the server generation in the body', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ status: 'cancelled' }), { status: 200 }));
    vi.stubGlobal('fetch', fetch);
    await api.change('cancel', 'fake-private-token', 7);
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe('/api/registration/cancel');
    expect(options.headers.get('Authorization')).toBe('Bearer fake-private-token');
    expect(options.body).toBe('{"expected_participation_no":7}');
    expect(url).not.toContain('fake-private-token');
  });
  it('does not report registration success before the real response is received', async () => {
    let resolve!: (response: Response) => void;
    vi.stubGlobal(
      'fetch',
      () =>
        new Promise<Response>((done) => {
          resolve = done;
        })
    );
    const completed = vi.fn();
    const pending = api.register('event-id', 'User@faß.de').then(completed);
    await Promise.resolve();
    expect(completed).not.toHaveBeenCalled();
    resolve(new Response('{"message":"neutral"}', { status: 202 }));
    await pending;
    expect(completed).toHaveBeenCalledWith({ message: 'neutral' });
  });
  it('preserves conflict classification without exposing server payloads', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response('{"code":"participation_conflict","message":"fake-private-token"}', {
          status: 409,
        })
      )
    );
    await expect(api.change('cancel', 'fake-private-token', 1)).rejects.toMatchObject({
      status: 409,
      code: 'participation_conflict',
    });
    await expect(api.change('cancel', 'fake-private-token', 1)).rejects.not.toThrow(
      'fake-private-token'
    );
  });
  it('maps failed network requests to a recoverable human message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('sensitive internal URL')));
    await expect(api.events()).rejects.toMatchObject({ status: 0, code: 'network' });
    await expect(api.events()).rejects.not.toThrow('sensitive internal URL');
  });
  it('keeps user navigation aborts separate from network failures', async () => {
    const controller = new AbortController();
    controller.abort();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('aborted')));
    await expect(request('/events', { signal: controller.signal })).rejects.toMatchObject({
      name: 'AbortError',
    });
  });
  it('keeps validation errors safe even if the proxy returns non-JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('fake-secret', { status: 422 })));
    try {
      await api.events();
      throw new Error('must reject');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as Error).message).not.toContain('fake-secret');
    }
  });
});
it('accepts only a complete snapshot for the subscribed event', () => {
  const data = {
    id: 'id',
    description: 'Event',
    starts_at: '2026-12-01T12:00:00Z',
    server_time: '2026-10-23T12:00:00Z',
    capacity: 1,
    schedule_version: 1,
    confirmed: 1,
    waitlisted: 0,
    checked_in: 0,
  };
  expect(isSnapshot(data, 'id')).toBe(true);
  expect(isSnapshot(data, 'other')).toBe(false);
  expect(isSnapshot({ ...data, checked_in: -1 }, 'id')).toBe(false);
  expect(isSnapshot({ ...data, starts_at: 'bad' }, 'id')).toBe(false);
  expect(isSnapshot({ ...data, server_time: 'bad' }, 'id')).toBe(false);
});

it('does not expose malformed successful response contents as a syntax error', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response('fake-private-secret', { status: 200 }))
  );
  await expect(api.events()).rejects.toMatchObject({ code: 'invalid_response' });
});

it('requests bounded event pages and preserves the next offset', async () => {
  const fetch = vi.fn().mockResolvedValue(
    new Response('{"items":[],"next_offset":60,"server_time":"2030-01-01T00:00:00Z"}', {
      status: 200,
    })
  );
  vi.stubGlobal('fetch', fetch);
  await expect(api.events(undefined, 40)).resolves.toEqual({
    items: [],
    next_offset: 60,
    server_time: '2030-01-01T00:00:00Z',
  });
  expect(fetch.mock.calls[0][0]).toBe('/api/events?limit=20&offset=40');
});
