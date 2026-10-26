import { useEffect, useState } from 'react';
import { Link, LiveState, LoadState, Notice } from '../components/common';
import { fullDate, time, timezone } from '../dates';
import { useLiveEvent, useParticipation } from '../hooks/data';

export function ParticipationPage({ token }: { token: string }) {
  const participant = useParticipation(token);
  const event = useLiveEvent(participant.data?.event_id);
  const [copyMessage, setCopyMessage] = useState('');
  useEffect(() => {
    if (event.tick) void participant.refresh();
  }, [event.tick, participant.refresh]);
  const data = participant.data;
  if (!token)
    return (
      <main className="container narrow">
        <p className="eyebrow">My participation</p>
        <h1>Open the link from your email</h1>
        <p>
          Use the private link from your first registration email. Open it again after reloading
          this page.
        </p>
        <Link href="/">Browse events</Link>
      </main>
    );
  if (!data)
    return (
      <main className="container narrow">
        <LoadState
          error={participant.error}
          retry={() => {
            void participant.refresh();
          }}
        />
      </main>
    );
  const timeReady = event.serverNow !== null && event.data !== null;
  const started = timeReady && Date.parse(event.data!.starts_at) <= event.serverNow!;
  const checked = data.checked_in_at !== null;
  const status =
    data.status === 'confirmed'
      ? checked
        ? 'You are checked in'
        : 'Participation confirmed'
      : data.status === 'waitlisted'
        ? 'You are on the waitlist'
        : 'Participation cancelled';
  return (
    <main className="container narrow">
      <Link className="back-link" href={event.data ? `/events/${data.event_id}` : '/'}>
        ← Event details
      </Link>
      <p className="eyebrow">My participation</p>
      <h1>{status}</h1>
      {event.data ? (
        <div className="participation-event">
          <p className="serif">{event.data.description}</p>
          <p>
            {fullDate(event.data.starts_at)} · {time(event.data.starts_at)}
          </p>
          <p className="muted">{timezone}</p>
        </div>
      ) : (
        <Notice error>{event.error?.message ?? 'Loading event…'}</Notice>
      )}
      <Notice error>{participant.error?.message}</Notice>
      <Notice>{participant.notice}</Notice>
      {data.status === 'confirmed' && data.ticket_code && (
        <section className="ticket" aria-labelledby="ticket-title">
          <div className="ticket-heading">
            <h2 id="ticket-title">Your ticket</h2>
            <span>{checked ? 'Used' : 'Valid'}</span>
          </div>
          <p>{checked ? 'This ticket has already been used.' : 'Show this code at the entrance'}</p>
          <code data-testid="ticket-code">{data.ticket_code}</code>
          <button
            className="secondary"
            onClick={() => {
              if (!navigator.clipboard) {
                setCopyMessage('Select the code and copy it manually.');
                return;
              }
              void navigator.clipboard
                .writeText(data.ticket_code!)
                .then(() => setCopyMessage('Code copied.'))
                .catch(() => setCopyMessage('Could not copy. Select the code manually.'));
            }}
          >
            Copy code
          </button>
          <p className="muted" role="status">
            {copyMessage}
          </p>
          {checked && (
            <p>
              Checked in on {fullDate(data.checked_in_at!)} at {time(data.checked_in_at!)} · Almaty
            </p>
          )}
        </section>
      )}
      {data.status === 'waitlisted' && (
        <p className="participation-note">
          When a place becomes available, it goes to the first person waiting. You will receive a
          ticket email when your place is confirmed.
        </p>
      )}
      {data.status === 'cancelled' && (
        <p className="participation-note">
          This ticket is no longer valid. You can rejoin before the event starts: take an available
          place or join the end of the waitlist.
        </p>
      )}
      {!timeReady && <Notice>Checking server time. Reconnect to change your participation.</Notice>}
      <div className="participation-actions">
        {!started && !checked && (
          <button
            className={data.status === 'cancelled' ? 'primary' : 'secondary'}
            disabled={participant.busy || !timeReady}
            onClick={() => {
              void participant.change(data.status === 'cancelled' ? 'resume' : 'cancel');
            }}
          >
            {participant.busy
              ? 'Saving…'
              : data.status === 'cancelled'
                ? 'Rejoin event'
                : 'Cancel participation'}
          </button>
        )}
        <button
          className="text-button"
          disabled={participant.busy}
          onClick={() => {
            void participant.refresh();
          }}
        >
          Refresh status
        </button>
      </div>
      {started && !checked && (
        <p className="muted">The event has started. Participation can no longer be changed.</p>
      )}
      <LiveState status={event.live} />
    </main>
  );
}
