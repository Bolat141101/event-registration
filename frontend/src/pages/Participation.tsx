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
        <p className="eyebrow">Моё участие</p>
        <h1>Откройте ссылку из письма</h1>
        <p>
          Для доступа нужна приватная ссылка из первого письма о регистрации. После перезагрузки
          страницы откройте её заново.
        </p>
        <Link href="/">К афише</Link>
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
  const started = event.data ? Date.parse(event.data.starts_at) <= Date.now() : true;
  const checked = data.checked_in_at !== null;
  const status =
    data.status === 'confirmed'
      ? checked
        ? 'Вы уже отмечены на входе'
        : 'Участие подтверждено'
      : data.status === 'waitlisted'
        ? 'Вы в листе ожидания'
        : 'Участие отменено';
  return (
    <main className="container narrow">
      <Link className="back-link" href={event.data ? `/events/${data.event_id}` : '/'}>
        ← К мероприятию
      </Link>
      <p className="eyebrow">Моё участие</p>
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
        <Notice error>{event.error?.message ?? 'Загружаем мероприятие…'}</Notice>
      )}
      <Notice error>{participant.error?.message}</Notice>
      <Notice>{participant.notice}</Notice>
      {data.status === 'confirmed' && data.ticket_code && (
        <section className="ticket" aria-labelledby="ticket-title">
          <div className="ticket-heading">
            <h2 id="ticket-title">Ваш билет</h2>
            <span>{checked ? 'Использован' : 'Действующий'}</span>
          </div>
          <p>{checked ? 'Этот билет уже использован.' : 'Покажите этот код на входе'}</p>
          <code data-testid="ticket-code">{data.ticket_code}</code>
          <button
            className="secondary"
            onClick={() => {
              if (!navigator.clipboard) {
                setCopyMessage('Выделите код и скопируйте вручную.');
                return;
              }
              void navigator.clipboard
                .writeText(data.ticket_code!)
                .then(() => setCopyMessage('Код скопирован.'))
                .catch(() => setCopyMessage('Не удалось скопировать. Выделите код вручную.'));
            }}
          >
            Скопировать код
          </button>
          <p className="muted" role="status">
            {copyMessage}
          </p>
          {checked && (
            <p>
              Отмечен {fullDate(data.checked_in_at!)} в {time(data.checked_in_at!)} · Алматы
            </p>
          )}
        </section>
      )}
      {data.status === 'waitlisted' && (
        <p className="participation-note">
          Если место освободится, оно перейдёт первому в очереди. При подтверждении участия вам
          придёт письмо с билетом.
        </p>
      )}
      {data.status === 'cancelled' && (
        <p className="participation-note">
          Билет больше не действует. До начала мероприятия можно вернуться: при наличии места
          участие подтвердится, иначе вы попадёте в конец листа ожидания.
        </p>
      )}
      <div className="participation-actions">
        {!started && !checked && (
          <button
            className={data.status === 'cancelled' ? 'primary' : 'secondary'}
            disabled={participant.busy}
            onClick={() => {
              void participant.change(data.status === 'cancelled' ? 'resume' : 'cancel');
            }}
          >
            {participant.busy
              ? 'Сохраняем…'
              : data.status === 'cancelled'
                ? 'Восстановить участие'
                : 'Отказаться от участия'}
          </button>
        )}
        <button
          className="text-button"
          disabled={participant.busy}
          onClick={() => {
            void participant.refresh();
          }}
        >
          Обновить статус
        </button>
      </div>
      {started && !checked && (
        <p className="muted">Мероприятие началось. Изменить участие уже нельзя.</p>
      )}
      <LiveState status={event.live} />
    </main>
  );
}
