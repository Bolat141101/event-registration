import type { AnchorHTMLAttributes, ReactNode } from 'react';
import type { EventInfo } from '../api/client';
import { ApiError } from '../api/client';
import { day, fullDate, month, time } from '../dates';

export function navigate(path: string) {
  window.history.pushState(null, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
  window.scrollTo(0, 0);
}
export function Link(props: AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a
      {...props}
      onClick={(event) => {
        props.onClick?.(event);
        if (
          !event.defaultPrevented &&
          event.button === 0 &&
          !event.metaKey &&
          !event.ctrlKey &&
          !event.shiftKey &&
          !event.altKey &&
          props.href?.startsWith('/') &&
          !props.target
        ) {
          event.preventDefault();
          navigate(props.href);
        }
      }}
    />
  );
}
export function Notice({ children, error = false }: { children: ReactNode; error?: boolean }) {
  if (!children) return null;
  return (
    <div className={`notice${error ? ' notice-error' : ''}`} role={error ? 'alert' : 'status'}>
      {children}
    </div>
  );
}
export function LoadState({ error, retry }: { error: Error | null; retry?: () => void }) {
  return (
    <div className="load-state">
      {error ? (
        <>
          <h1>
            {error instanceof ApiError && error.status === 404
              ? 'Event not found'
              : 'Could not load data'}
          </h1>
          <Notice error>{error.message}</Notice>
          {retry && (
            <button className="secondary" onClick={retry}>
              Try again
            </button>
          )}
          <Link href="/">Back to events</Link>
        </>
      ) : (
        <p role="status">Loading…</p>
      )}
    </div>
  );
}
export function DateStamp({ value }: { value: string }) {
  return (
    <time className="date-stamp" dateTime={value} aria-label={`${fullDate(value)}, ${time(value)}`}>
      <strong>{day(value)}</strong>
      <span>{month(value)}</span>
    </time>
  );
}
export function Availability({ event, serverNow }: { event: EventInfo; serverNow: number | null }) {
  if (serverNow === null) return <span className="availability">Checking status</span>;
  const started = Date.parse(event.starts_at) <= serverNow;
  const free = Math.max(0, event.capacity - event.confirmed);
  return (
    <span className={`availability${!started && free ? ' available' : ''}`}>
      {started ? 'Already started' : free ? `Available ${free} of ${event.capacity}` : 'Waitlist'}
    </span>
  );
}
export function Stats({ event }: { event: EventInfo }) {
  return (
    <dl className="stats" aria-label="Event statistics">
      {(
        [
          ['confirmed', 'Registered'],
          ['waitlisted', 'Waiting'],
          ['checked_in', 'Checked in'],
        ] as const
      ).map(([key, label]) => (
        <div key={key}>
          <dt>{label}</dt>
          <dd data-testid={`stat-${key}`}>{event[key]}</dd>
        </div>
      ))}
    </dl>
  );
}
export function LiveState({ status }: { status: 'connecting' | 'connected' | 'offline' }) {
  return (
    <p className={`live-state ${status}`} role="status">
      <span aria-hidden="true" />
      {status === 'connected'
        ? 'Updates automatically'
        : status === 'connecting'
          ? 'Connecting to live updates…'
          : 'Connection lost. Reconnecting…'}
    </p>
  );
}
