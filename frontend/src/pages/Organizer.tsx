import { Pagination } from '../components/Pagination';
import { useEffect, useRef, useState } from 'react';
import type { EventInfo } from '../api/client';
import {
  DateStamp,
  Link,
  LiveState,
  LoadState,
  Notice,
  Stats,
  navigate,
} from '../components/common';
import { dateInput, fullDate, time, timezone } from '../dates';
import {
  useCheckin,
  useCreate,
  useEvents,
  useLiveEvent,
  useLogin,
  useReschedule,
} from '../hooks/data';

export function OrganizerLogin({ unlock }: { unlock: (key: string) => void }) {
  const [key, setKey] = useState('');
  const action = useLogin();
  return (
    <main className="container narrow">
      <p className="eyebrow">Workspace</p>
      <h1>Organizer</h1>
      <p className="intro">Manage events, participants and check-in.</p>
      <form
        className="access-form"
        onSubmit={(event) => {
          event.preventDefault();
          void action.run(key).then((value) => {
            if (value) {
              unlock(key);
              setKey('');
            }
          });
        }}
      >
        <label htmlFor="organizer-key">Organizer key</label>
        <input
          id="organizer-key"
          name="organizer-key"
          type="password"
          autoComplete="off"
          required
          maxLength={256}
          value={key}
          onChange={(event) => setKey(event.target.value)}
          disabled={action.busy}
          aria-describedby="access-help"
        />
        <p id="access-help" className="muted">
          Access stays in this tab until you reload it.
        </p>
        <Notice error>{action.error?.message}</Notice>
        <button className="primary" disabled={action.busy}>
          {action.busy ? 'Checking…' : 'Open workspace'}
        </button>
      </form>
    </main>
  );
}
function CreateForm({ organizerKey }: { organizerKey: string }) {
  const [description, setDescription] = useState('');
  const [starts, setStarts] = useState('');
  const [capacity, setCapacity] = useState('');
  const action = useCreate(organizerKey);
  return (
    <form
      className="create-form"
      onSubmit={(event) => {
        event.preventDefault();
        void action
          .run({ description, starts_at: starts, capacity: Number(capacity) })
          .then((value) => {
            if (value) navigate(`/organizer/events/${value.id}`);
          });
      }}
    >
      <h2>New event</h2>
      <label htmlFor="description">Description</label>
      <textarea
        id="description"
        required
        rows={4}
        maxLength={10000}
        value={description}
        onChange={(event) => setDescription(event.target.value)}
        disabled={action.busy}
      />
      <label htmlFor="starts-at">Date and time · Almaty (UTC+5)</label>
      <input
        id="starts-at"
        type="datetime-local"
        step="1"
        required
        value={starts}
        onChange={(event) => setStarts(event.target.value)}
        disabled={action.busy}
      />
      <label htmlFor="capacity">Capacity</label>
      <input
        id="capacity"
        type="number"
        inputMode="numeric"
        min={1}
        max={2147483647}
        step={1}
        required
        value={capacity}
        onChange={(event) => setCapacity(event.target.value)}
        disabled={action.busy}
      />
      <Notice error>{action.error?.message}</Notice>
      <button className="primary" disabled={action.busy}>
        {action.busy ? 'Creating…' : 'Create event'}
      </button>
    </form>
  );
}
export function OrganizerHome({ organizerKey }: { organizerKey: string }) {
  const list = useEvents();
  return (
    <main className="container">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Workspace</p>
          <h1>Events</h1>
        </div>
        <p className="timezone">{timezone}</p>
      </div>
      <div className="workspace">
        <section>
          <h2 className="section-label">All events</h2>
          {!list.data || list.error ? (
            <LoadState error={list.error} retry={list.retry} />
          ) : list.data.length === 0 ? (
            <p className="muted">No events yet. Create your first event.</p>
          ) : (
            <div className="organizer-list">
              {list.data.map((event) => (
                <article key={event.id}>
                  <DateStamp value={event.starts_at} />
                  <div>
                    <h3>
                      <Link href={`/organizer/events/${event.id}`}>{event.description}</Link>
                    </h3>
                    <p className="muted">
                      {time(event.starts_at)} · {event.confirmed} of {event.capacity} registered
                    </p>
                  </div>
                  <Link
                    href={`/organizer/events/${event.id}`}
                    aria-label={`Manage: ${event.description}`}
                  >
                    Open
                  </Link>
                </article>
              ))}
            </div>
          )}
          <Pagination list={list} />
        </section>
        <CreateForm organizerKey={organizerKey} />
      </div>
    </main>
  );
}
function ScheduleForm({
  event,
  organizerKey,
  saved,
  refresh,
  serverNow,
}: {
  event: EventInfo;
  organizerKey: string;
  saved: (event: EventInfo) => void;
  refresh: () => void;
  serverNow: number | null;
}) {
  const [value, setValue] = useState(dateInput(event.starts_at));
  const [notice, setNotice] = useState('');
  const action = useReschedule(event.id, organizerKey, event.schedule_version);
  useEffect(() => {
    setValue(dateInput(event.starts_at));
  }, [event.starts_at]);
  const started = serverNow !== null && Date.parse(event.starts_at) <= serverNow;
  return (
    <form
      className="schedule-form"
      onSubmit={(submit) => {
        submit.preventDefault();
        setNotice('');
        void action.run(value).then((result) => {
          if (result) {
            saved(result);
            setNotice('Date saved.');
          } else refresh();
        });
      }}
    >
      <h2>Event date</h2>
      {serverNow === null && <Notice>Checking server time. Reconnect to change the date.</Notice>}
      <p className="muted">Participants will receive an email about the new date.</p>
      <label htmlFor="new-date">New date and time · Almaty (UTC+5)</label>
      <div className="inline-form">
        <input
          id="new-date"
          type="datetime-local"
          step="1"
          required
          value={value}
          onChange={(change) => setValue(change.target.value)}
          disabled={action.busy || serverNow === null || started}
        />
        <button className="secondary" disabled={action.busy || serverNow === null || started}>
          {action.busy ? 'Saving…' : 'Save date'}
        </button>
      </div>
      {started && <p className="muted">The event has started. Rescheduling is unavailable.</p>}
      <Notice error>{action.error?.message}</Notice>
      <Notice>{notice}</Notice>
    </form>
  );
}
function CheckinForm({
  event,
  organizerKey,
  serverNow,
}: {
  event: EventInfo;
  organizerKey: string;
  serverNow: number | null;
}) {
  const [code, setCode] = useState('');
  const [result, setResult] = useState('');
  const input = useRef<HTMLInputElement>(null);
  const action = useCheckin(event.id, organizerKey);
  const started = serverNow !== null && Date.parse(event.starts_at) <= serverNow;
  return (
    <section className="checkin-panel">
      <p className="eyebrow">Event entrance</p>
      <h2>Check a ticket</h2>
      {serverNow === null && (
        <Notice>Checking server time. Reconnect to check in participants.</Notice>
      )}
      <p>Enter the code from the participant ticket.</p>
      <form
        onSubmit={(submit) => {
          submit.preventDefault();
          setResult('');
          void action.run(code.trim()).then((value) => {
            if (value) {
              setResult('Participant checked in. You can check the next ticket.');
              setCode('');
            }
            requestAnimationFrame(() => input.current?.focus());
          });
        }}
      >
        <label htmlFor="ticket-code">Ticket code</label>
        <input
          ref={input}
          id="ticket-code"
          name="ticket-code"
          className="code-input"
          type="text"
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          required
          maxLength={256}
          value={code}
          onChange={(change) => {
            setCode(change.target.value);
          }}
          disabled={action.busy || !started}
          aria-describedby="checkin-result"
        />
        <button className="primary" disabled={action.busy || !started}>
          {action.busy ? 'Checking…' : 'Check in participant'}
        </button>
      </form>
      {!started && (
        <p className="muted">
          Check-in opens on {fullDate(event.starts_at)} at {time(event.starts_at)} · Almaty.
        </p>
      )}
      <div id="checkin-result" className="checkin-result">
        <Notice error>{action.error?.message}</Notice>
        <Notice>{result}</Notice>
      </div>
    </section>
  );
}
export function OrganizerEvent({
  id,
  organizerKey,
  checkin = false,
}: {
  id: string;
  organizerKey: string;
  checkin?: boolean;
}) {
  const live = useLiveEvent(id);
  const event = live.data;
  if (!event)
    return (
      <main className="container">
        <LoadState error={live.error} retry={live.refresh} />
      </main>
    );
  return (
    <main className="container">
      <Link className="back-link" href="/organizer">
        ← All events
      </Link>
      <div className="work-heading">
        <div>
          <p className="eyebrow">{checkin ? 'Check-in' : 'Manage event'}</p>
          <h1>{event.description}</h1>
          <p className="muted">
            {fullDate(event.starts_at)} · {time(event.starts_at)} · Almaty (UTC+5)
          </p>
        </div>
        <Link
          className="secondary button-link"
          href={checkin ? `/organizer/events/${id}` : `/organizer/events/${id}/check-in`}
        >
          {checkin ? 'Manage event' : 'Open check-in'}
        </Link>
      </div>
      <Stats event={event} />
      <LiveState status={live.live} />
      {checkin ? (
        <CheckinForm event={event} organizerKey={organizerKey} serverNow={live.serverNow} />
      ) : (
        <div className="work-body">
          <ScheduleForm
            event={event}
            organizerKey={organizerKey}
            saved={live.replace}
            refresh={live.refresh}
            serverNow={live.serverNow}
          />
          <aside className="public-link">
            <h2>Participant page</h2>
            <p>Description, registration and availability.</p>
            <Link href={`/events/${id}`}>
              Open page <span aria-hidden="true">↗</span>
            </Link>
          </aside>
        </div>
      )}
    </main>
  );
}
