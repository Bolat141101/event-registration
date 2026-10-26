import { Pagination } from '../components/Pagination';
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
          <p className="eyebrow">Upcoming events</p>
          <h1>Events</h1>
        </div>
        <p className="timezone">{timezone}</p>
      </div>
      {!list.data || list.error ? (
        <LoadState error={list.error} retry={list.retry} />
      ) : list.data.length === 0 ? (
        <div className="empty-state">
          <h2>No events yet</h2>
          <p>New events will appear here.</p>
          <Link href="/organizer">
            Create an event <span aria-hidden="true">↗</span>
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
                  {time(event.starts_at)} <span aria-hidden="true">/</span> Almaty
                </p>
              </div>
              <div className="event-row-action">
                <Availability event={event} serverNow={list.serverNow} />
                <Link className="text-link" href={`/events/${event.id}`}>
                  Details <span aria-hidden="true">↗</span>
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
      <Pagination list={list} />
    </main>
  );
}
function RegistrationForm({
  id,
  waiting,
  ready,
}: {
  id: string;
  waiting: boolean;
  ready: boolean;
}) {
  const [email, setEmail] = useState('');
  const [accepted, setAccepted] = useState(false);
  const action = useRegister(id);
  return (
    <aside className="registration-box">
      <p className="eyebrow">Participation</p>
      {!ready && <Notice>Checking server time. Actions will be available once connected.</Notice>}
      <h2>{waiting ? 'Join the waitlist' : 'Register'}</h2>
      {accepted ? (
        <>
          <Notice>
            Request accepted. Check your participation using the private link from your first
            registration email.
          </Notice>
          <p className="muted">
            Email may take a little time. If you registered before, use your original private link.
          </p>
          <button
            className="secondary"
            onClick={() => {
              setAccepted(false);
              setEmail('');
            }}
          >
            Another email
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
              ? 'No places left. If one becomes available, the first person waiting receives it and an email.'
              : 'Enter your email for your ticket and event updates.'}
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
            disabled={action.busy || !ready}
          />
          <div id="registration-error">
            <Notice error>{action.error?.message}</Notice>
          </div>
          <button className="primary" disabled={action.busy || !ready}>
            {action.busy ? 'Sending…' : waiting ? 'Join waitlist' : 'Submit registration'}
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
  const started = event.serverNow !== null && Date.parse(data.starts_at) <= event.serverNow;
  return (
    <main className="container">
      <Link className="back-link" href="/">
        ← All events
      </Link>
      <div className="event-detail">
        <section className="event-main">
          <div className="detail-date">
            <DateStamp value={data.starts_at} />
            <div>
              <p className="eyebrow">{time(data.starts_at)} · Almaty</p>
              <p className="muted">{fullDate(data.starts_at)}</p>
            </div>
          </div>
          <h1 className="event-description">{data.description}</h1>
          <div className="detail-meta">
            <Availability event={data} serverNow={event.serverNow} />
            <p>
              {data.confirmed} registered · {data.waitlisted} waiting
            </p>
          </div>
          <LiveState status={event.live} />
        </section>
        {started ? (
          <aside className="registration-box">
            <p className="eyebrow">Participation</p>
            <h2>Registration closed</h2>
            <p>
              The event has started. If you registered, open your ticket using the link in your
              email.
            </p>
          </aside>
        ) : (
          <RegistrationForm
            id={id}
            waiting={data.confirmed >= data.capacity}
            ready={event.serverNow !== null}
          />
        )}
      </div>
    </main>
  );
}
