import { useEffect, useState } from 'react';
import { getHealth } from './api/health';

export function App() {
  const [status, setStatus] = useState('Проверяем подключение…');
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    void getHealth(controller.signal).then(() => {
      setReady(true);
      setStatus('Сервер доступен, база данных готова');
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) {
        setReady(false);
        setStatus(error instanceof Error ? error.message : 'Не удалось подключиться');
      }
    });
    return () => controller.abort();
  }, []);

  return (
    <main>
      <p className="eyebrow">Мероприятия</p>
      <h1>Встречи начинаются здесь</h1>
      <p className="intro">Сервис регистрации участников и управления местами.</p>
      <section aria-labelledby="stage-title">
        <h2 id="stage-title">Подготовка сервиса</h2>
        <p role="status" className={ready ? 'status ready' : 'status'}>{status}</p>
        <p>Сейчас готова инфраструктура. Создание мероприятий и регистрация появятся на следующем этапе.</p>
      </section>
    </main>
  );
}
