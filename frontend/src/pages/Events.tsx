import { useState } from 'react';
import { Availability, DateStamp, Link, LiveState, LoadState, Notice } from '../components/common';
import { fullDate, time, timezone } from '../dates';
import { useEvents, useLiveEvent, useRegister } from '../hooks/data';

export function EventList() {
  const list = useEvents();
  return (
    <main className="container">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Ближайшие встречи</p>
          <h1>Афиша</h1>
        </div>
        <p className="timezone">{timezone}</p>
      </div>
      {!list.data ? (
        <LoadState error={list.error} retry={list.retry} />
      ) : list.error ? (
        <LoadState error={list.error} retry={list.retry} />
      ) : list.data.length === 0 ? (
        <div className="empty-state">
          <h2>Пока нет мероприятий</h2>
          <p>Новые встречи появятся здесь.</p>
          <Link href="/organizer">
            Организовать мероприятие <span aria-hidden="true">↗</span>
          </Link>
        </div>
      ) : (
        <div className="event-list">
          {list.data.map((event) => (
            <article className="event-row" key={event.id}>
              <DateStamp value={event.starts_at} />
              <div className="event-row-copy">
                <h2>
                  <Link href={`/events/${event.id}`}>{event.description}</Link>
                </h2>
                <p>
                  {time(event.starts_at)} <span aria-hidden="true">/</span> Алматы
                </p>
              </div>
              <div className="event-row-action">
                <Availability event={event} />
                <Link className="text-link" href={`/events/${event.id}`}>
                  Подробнее <span aria-hidden="true">↗</span>
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}
function RegistrationForm({ id, waiting }: { id: string; waiting: boolean }) {
  const [email, setEmail] = useState('');
  const [accepted, setAccepted] = useState(false);
  const action = useRegister(id);
  return (
    <aside className="registration-box">
      <p className="eyebrow">Участие</p>
      <h2>{waiting ? 'Присоединиться к ожиданию' : 'Зарегистрироваться'}</h2>
      {accepted ? (
        <>
          <Notice>
            Запрос принят. Статус участия можно проверить по приватной ссылке из первого письма о
            регистрации.
          </Notice>
          <p className="muted">
            Письмо может прийти не сразу. Если вы регистрировались раньше, используйте прежнюю
            ссылку.
          </p>
          <button
            className="secondary"
            onClick={() => {
              setAccepted(false);
              setEmail('');
            }}
          >
            Другой email
          </button>
        </>
      ) : (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void action.run(email).then((value) => {
              if (value) setAccepted(true);
            });
          }}
        >
          <p>
            {waiting
              ? 'Места закончились. Если место освободится, первый в очереди получит его и письмо.'
              : 'Укажите email для билета и сообщений о мероприятии.'}
          </p>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            name="email"
            type="text"
            inputMode="email"
            autoComplete="email"
            maxLength={320}
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            aria-describedby={action.error ? 'registration-error' : undefined}
            disabled={action.busy}
          />
          <div id="registration-error">
            <Notice error>{action.error?.message}</Notice>
          </div>
          <button className="primary" disabled={action.busy}>
            {action.busy ? 'Отправляем…' : waiting ? 'Встать в лист ожидания' : 'Отправить заявку'}
          </button>
        </form>
      )}
    </aside>
  );
}
export function EventPage({ id }: { id: string }) {
  const event = useLiveEvent(id);
  const data = event.data;
  if (!data)
    return (
      <main className="container">
        <LoadState error={event.error} retry={event.refresh} />
      </main>
    );
  const started = Date.parse(data.starts_at) <= Date.now();
  return (
    <main className="container">
      <Link className="back-link" href="/">
        ← Все мероприятия
      </Link>
      <div className="event-detail">
        <section className="event-main">
          <div className="detail-date">
            <DateStamp value={data.starts_at} />
            <div>
              <p className="eyebrow">{time(data.starts_at)} · Алматы</p>
              <p className="muted">{fullDate(data.starts_at)}</p>
            </div>
          </div>
          <h1 className="event-description">{data.description}</h1>
          <div className="detail-meta">
            <Availability event={data} />
            <p>
              {data.confirmed} зарегистрировано · {data.waitlisted} в ожидании
            </p>
          </div>
          <LiveState status={event.live} />
        </section>
        {started ? (
          <aside className="registration-box">
            <p className="eyebrow">Участие</p>
            <h2>Регистрация завершена</h2>
            <p>
              Мероприятие уже началось. Если вы зарегистрированы, билет доступен по ссылке из
              письма.
            </p>
          </aside>
        ) : (
          <RegistrationForm id={id} waiting={data.confirmed >= data.capacity} />
        )}
      </div>
    </main>
  );
}
