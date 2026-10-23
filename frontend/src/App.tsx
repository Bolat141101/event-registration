import { useEffect, useRef, useState } from 'react';
import { Link } from './components/common';
import { takePrivateToken } from './dates';
import { EventList, EventPage } from './pages/Events';
import { OrganizerEvent, OrganizerHome, OrganizerLogin } from './pages/Organizer';
import { ParticipationPage } from './pages/Participation';

// Consume before StrictMode mounts effects; never persist the token in storage/history.
const initialPrivateToken = takePrivateToken();
export function App() {
  const [path, setPath] = useState(window.location.pathname);
  const [organizerKey, setOrganizerKey] = useState('');
  const [privateToken, setPrivateToken] = useState(initialPrivateToken);
  const previousPath = useRef(path);
  useEffect(() => {
    const changed = () => {
      setPath(window.location.pathname);
      if (new URLSearchParams(window.location.hash.slice(1)).has('token'))
        setPrivateToken(takePrivateToken());
    };
    window.addEventListener('popstate', changed);
    window.addEventListener('hashchange', changed);
    return () => {
      window.removeEventListener('popstate', changed);
      window.removeEventListener('hashchange', changed);
    };
  }, []);
  useEffect(() => {
    if (previousPath.current !== path) {
      document.getElementById('page-start')?.focus({ preventScroll: true });
      previousPath.current = path;
    }
  }, [path]);
  let content;
  const event = /^\/events\/([^/]+)$/.exec(path);
  const organizer = /^\/organizer\/events\/([^/]+)(\/check-in)?$/.exec(path);
  if (path === '/') content = <EventList />;
  else if (event) content = <EventPage key={event[1]} id={event[1]} />;
  else if (path === '/registration')
    content = <ParticipationPage key={privateToken} token={privateToken} />;
  else if (path === '/organizer' || organizer)
    content = !organizerKey ? (
      <OrganizerLogin unlock={setOrganizerKey} />
    ) : organizer ? (
      <OrganizerEvent
        key={`${organizer[1]}-${organizer[2] ?? ''}`}
        id={organizer[1]}
        organizerKey={organizerKey}
        checkin={Boolean(organizer[2])}
      />
    ) : (
      <OrganizerHome organizerKey={organizerKey} />
    );
  else
    content = (
      <main className="container narrow">
        <h1>Такой страницы нет</h1>
        <Link href="/">Вернуться к афише</Link>
      </main>
    );
  return (
    <>
      <a className="skip-link" href="#page-start">
        К содержимому
      </a>
      <header className="site-header">
        <div className="container header-inner">
          <Link className="brand" href="/" aria-label="События — афиша">
            <span aria-hidden="true" className="brand-mark" />
            События<span className="brand-caption">Афиша встреч</span>
          </Link>
          <nav aria-label="Основная навигация">
            <Link href="/" aria-current={path === '/' ? 'page' : undefined}>
              Афиша
            </Link>
            <Link
              href="/organizer"
              aria-current={path.startsWith('/organizer') ? 'page' : undefined}
            >
              Организатору
            </Link>
            {organizerKey && (
              <button className="text-button" onClick={() => setOrganizerKey('')}>
                Выйти
              </button>
            )}
          </nav>
        </div>
      </header>
      <div id="page-start" tabIndex={-1}>
        {content}
      </div>
      <footer className="site-footer container">
        <span>События · регистрация на мероприятия</span>
        <span>Все даты — по времени Алматы</span>
      </footer>
    </>
  );
}
