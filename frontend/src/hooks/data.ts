import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError, isSnapshot } from '../api/client';
import type { EventInfo, Participation, Snapshot } from '../api/client';
import { inputToISO } from '../dates';

export function useEvents() {
  const [data, setData] = useState<EventInfo[] | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [revision, setRevision] = useState(0);
  const [offset, setOffset] = useState(0);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [serverNow, setServerNow] = useState<number | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let anchor: { epoch: number; received: number } | null = null;
    setError(null);
    setData(null);
    setServerNow(null);
    void api
      .events(controller.signal, offset)
      .then((page) => {
        if (controller.signal.aborted) return;
        const epoch = Date.parse(page.server_time);
        if (!Number.isFinite(epoch)) throw new Error('Could not verify server time.');
        anchor = { epoch, received: performance.now() };
        setServerNow(epoch);
        setData(page.items);
        setNextOffset(page.next_offset);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason);
      });
    const timer = window.setInterval(() => {
      if (anchor) setServerNow(anchor.epoch + performance.now() - anchor.received);
    }, 250);
    const offline = () => {
      anchor = null;
      setServerNow(null);
    };
    const online = () => setRevision((value) => value + 1);
    window.addEventListener('offline', offline);
    window.addEventListener('online', online);
    return () => {
      controller.abort();
      clearInterval(timer);
      window.removeEventListener('offline', offline);
      window.removeEventListener('online', online);
    };
  }, [revision, offset]);
  return {
    data,
    error,
    offset,
    nextOffset,
    serverNow,
    setOffset,
    retry: () => setRevision((value) => value + 1),
  };
}

export function useLiveEvent(id: string | undefined) {
  const [data, setData] = useState<EventInfo | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [live, setLive] = useState<'connecting' | 'connected' | 'offline'>('connecting');
  const [tick, setTick] = useState(0);
  const [serverNow, setServerNow] = useState<number | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    setData((previous) => (previous?.id === id ? previous : null));
    setError(null);
    setLive('connecting');
    setServerNow(null);
    if (!id) return;
    const controller = new AbortController();
    let source: EventSource | null = null;
    let privateSignature = '';
    let privateReadAt = 0;
    let lastMessage = performance.now();
    let anchor: { epoch: number; received: number } | null = null;
    const loseTime = () => {
      anchor = null;
      setServerNow(null);
    };
    const connect = () => {
      if (controller.signal.aborted || !navigator.onLine) return;
      source?.close();
      privateSignature = '';
      source = new EventSource(`/api/events/${id}/stream`); // Public data: no credentials in URL.
      source.addEventListener('stats', (message: MessageEvent<string>) => {
        if (controller.signal.aborted) return;
        try {
          const snapshot: unknown = JSON.parse(message.data);
          if (!isSnapshot(snapshot, id)) throw new Error('Invalid snapshot');
          lastMessage = performance.now();
          anchor = { epoch: Date.parse(snapshot.server_time), received: lastMessage };
          setServerNow(anchor.epoch);
          setData(snapshot as Snapshot);
          setError(null);
          setLive('connected');
          const signature = JSON.stringify([
            snapshot.starts_at,
            snapshot.schedule_version,
            snapshot.confirmed,
            snapshot.waitlisted,
            snapshot.checked_in,
          ]);
          if (signature !== privateSignature || lastMessage - privateReadAt >= 10000) {
            privateSignature = signature;
            privateReadAt = lastMessage;
            setTick((value) => value + 1);
          }
        } catch {
          setLive('offline');
          loseTime();
          source?.close();
        }
      });
      source.onerror = () => {
        if (!controller.signal.aborted) {
          setLive('offline');
          loseTime();
        }
      };
    };
    void api
      .event(id, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) {
          setData(value);
          connect();
        }
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) {
          setError(reason);
          setLive('offline');
          if (reason instanceof ApiError && (reason.status === 0 || reason.status === 503))
            connect();
        }
      });
    const watchdog = window.setInterval(() => {
      if (anchor) setServerNow(anchor.epoch + performance.now() - anchor.received);
      if (source && navigator.onLine && performance.now() - lastMessage > 8000) {
        setLive('offline');
        loseTime();
        lastMessage = performance.now();
        connect();
      }
    }, 250);
    const focus = () => {
      if (source) {
        lastMessage = performance.now();
        connect();
      } else if (!controller.signal.aborted) {
        setRevision((value) => value + 1);
      }
    };
    const offline = () => {
      loseTime();
      source?.close();
      setLive('offline');
    };
    window.addEventListener('offline', offline);
    window.addEventListener('online', focus);
    window.addEventListener('focus', focus);
    return () => {
      controller.abort();
      source?.close();
      clearInterval(watchdog);
      window.removeEventListener('offline', offline);
      window.removeEventListener('online', focus);
      window.removeEventListener('focus', focus);
    };
  }, [id, revision]);
  return {
    data,
    error,
    live,
    tick,
    serverNow,
    refresh: () => setRevision((value) => value + 1),
    replace: setData,
  };
}

// The same pending/error lifecycle is used by five independent forms.
export function useAction<A, R>(operation: (args: A) => Promise<R>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const locked = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  async function run(args: A): Promise<R | undefined> {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError(null);
    try {
      const result = await operation(args);
      return mounted.current ? result : undefined;
    } catch (reason) {
      if (mounted.current)
        setError(reason instanceof Error ? reason : new Error('Could not complete the action.'));
    } finally {
      locked.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  return { run, busy, error };
}
export const useRegister = (id: string) => useAction((email: string) => api.register(id, email));
export const useLogin = () => useAction((key: string) => api.verify(key));
export const useCreate = (key: string) =>
  useAction((body: { description: string; starts_at: string; capacity: number }) =>
    api.create({ ...body, starts_at: inputToISO(body.starts_at) }, key)
  );
export const useReschedule = (id: string, key: string, version: number) =>
  useAction((date: string) => api.reschedule(id, inputToISO(date), version, key));
export const useCheckin = (id: string, key: string) =>
  useAction((code: string) => api.checkin(id, code, key));

export function useParticipation(token: string) {
  const [data, setData] = useState<Participation | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const mutating = useRef(false);
  const reading = useRef(false);
  const mounted = useRef(true);
  const refresh = useCallback(async () => {
    if (!token || mutating.current || reading.current) return;
    reading.current = true;
    controller.current?.abort();
    const pending = new AbortController();
    controller.current = pending;
    const current = ++generation.current;
    try {
      const value = await api.participation(token, pending.signal);
      if (mounted.current && current === generation.current) {
        setData(value);
        setError(null);
      }
    } catch (reason) {
      if (mounted.current && !pending.signal.aborted && current === generation.current)
        setError(reason as Error);
    } finally {
      if (current === generation.current) reading.current = false;
    }
  }, [token]);
  useEffect(() => {
    mounted.current = true;
    reading.current = false;
    void refresh();
    const focus = () => {
      void refresh();
    };
    window.addEventListener('focus', focus);
    return () => {
      mounted.current = false;
      ++generation.current;
      controller.current?.abort();
      window.removeEventListener('focus', focus);
    };
  }, [refresh]);
  async function change(kind: 'cancel' | 'resume') {
    if (!data || mutating.current) return;
    mutating.current = true;
    reading.current = false;
    ++generation.current;
    controller.current?.abort();
    setBusy(true);
    setError(null);
    setNotice('');
    try {
      const value = await api.change(kind, token, data.participation_no);
      if (mounted.current) {
        setData(value);
        setNotice(kind === 'cancel' ? 'Participation cancelled.' : 'Participation restored.');
      }
    } catch (reason) {
      if (mounted.current) {
        if (reason instanceof ApiError && reason.status === 409) {
          mutating.current = false;
          await refresh();
          setNotice(reason.message);
        } else setError(reason as Error);
      }
    } finally {
      mutating.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  return { data, error, busy, notice, change, refresh };
}
