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
              ? 'Мероприятие не найдено'
              : 'Не удалось загрузить данные'}
          </h1>
          <Notice error>{error.message}</Notice>
          {retry && (
            <button className="secondary" onClick={retry}>
              Попробовать ещё раз
            </button>
          )}
          <Link href="/">Вернуться к афише</Link>
        </>
      ) : (
        <p role="status">Загружаем…</p>
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
export function Availability({ event }: { event: EventInfo }) {
  const started = Date.parse(event.starts_at) <= Date.now();
  const free = Math.max(0, event.capacity - event.confirmed);
  return (
    <span className={`availability${!started && free ? ' available' : ''}`}>
      {started ? 'Уже началось' : free ? `Свободно ${free} из ${event.capacity}` : 'Лист ожидания'}
    </span>
  );
}
export function Stats({ event }: { event: EventInfo }) {
  return (
    <dl className="stats" aria-label="Статистика мероприятия">
      {(
        [
          ['confirmed', 'Зарегистрировано'],
          ['waitlisted', 'Ожидают'],
          ['checked_in', 'Пришли'],
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
        ? 'Обновляется автоматически'
        : status === 'connecting'
          ? 'Подключаем обновления…'
          : 'Связь прервана. Переподключаемся…'}
    </p>
  );
}
