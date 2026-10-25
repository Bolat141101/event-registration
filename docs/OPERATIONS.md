# Диагностика и восстановление

Core readiness проверяет только свою БД/миграции. Ни SMTP, ни Notifications не являются условием HTTP-доступности Core.

## Наблюдение без секретов

```sh
docker compose ps
docker compose exec -T worker python -m app.worker_health
docker compose exec -T notifications-sender python -m notifications_app.worker_health
docker compose exec -T worker python -m app.operations --check
docker compose exec -T notifications-sender python -m notifications_app.operations --check
```

Healthcheck worker/sender проверяет heartbeat реального цикла, PID, готовность БД и возраст <180s. Срок учитывает ограниченные сетевые операции и poll; heartbeat не означает успешную SMTP-доставку. Постоянная ошибка итерации/БД делает healthcheck unhealthy. Compose не перезапускает процесс только из-за unhealthy: нужен оператор/production alerting. При завершении процесса действует restart policy.

Queue summary выводит только счётчики статусов, до 20 failed UUID и `oldest_due_seconds`. `--check` возвращает exit1 при failed>0 или ожидании готового задания >60s. Будущие напоминания не считаются просроченными. Это возраст от available_at для готовой работы, не полная длительность с первой постановки: backoff меняет available_at. Подготовленный payload, адрес, токен и MIME не выводятся. Длительность сквозной доставки отдельно измеряет delivery_probe в тестах.

## Явный повтор failed

Сначала устранить причину и изучить безопасный last_error в своей БД. Не исправлять сохранённые payload/MIME и не генерировать новый ID.

```sh
docker compose stop worker
docker compose run --rm --no-deps worker python -m app.notifications.retry UUID --acknowledge-duplicate-risk
docker compose up -d worker

docker compose stop notifications-sender
docker compose run --rm --no-deps notifications-sender python -m notifications_app.retry UUID --acknowledge-duplicate-risk
docker compose up -d notifications-sender
```

Операция принимает только failed, сохраняет ID/границы неизменности/данные, сбрасывает attempts и планирует сейчас. Повтор на pending/sent/forwarded ничего не сбрасывает. Notifications до изменения статуса проверяет сохранённые contract/MIME/SMTP envelope; Core заново проверит контракт, актуальность и время под event-lock при prepare. При занятом mutex повтор не назначается. Повреждённые задания должны остаться failed; их нельзя «вылечить» пересозданием MIME.

## Один активный обработчик

Sender и relay оборачивают всю итерацию в session advisory mutex PostgreSQL (ключ794632801, отдельная область каждой БД). Вторая итерация другого процесса не начинает подготовку/сетевую отправку. Выделенное AUTOCOMMIT-соединение владеет mutex во время HTTP/SMTP; SQL-транзакции бизнес-операций уже закрыты. Перед возвратом в pool lock снимается; повреждённое соединение инвалидируется. Watchdog проверяет соединение каждые0.5s и отменяет текущую попытку при его потере. При SIGKILL PostgreSQL освобождает mutex при закрытии сессии.

Это сериализация, а не распределённые worker/leases. Потеря DB-сессии/failover может пересечься с уже принятым удалённым SMTP DATA до обнаружения ошибки: advisory lock не является SMTP fencing. После SMTP accept и потери ответа/сохранения результата повтор остаётся возможным, даже с прежними MIME/Message-ID. Mailpit подавляет дубликаты ID только в рамках его текущего store/настройки; произвольный SMTP exactly-once не поддерживает. Перед failover/rolling maintenance останавливать отправители; не считать mutex заменой ограничений внешней системы.

## Нагрузка и границы

SSE: один свежий SQL-снимок в секунду на мероприятие **на процесс API**, bounded queue1 для каждого подписчика. Последний disconnect удаляет producer, shutdown закрывает задачи до engine. Начальная ошибка возвращается до SSE headers; разрыв закрывает поток, reconnect получает свежий снимок. Общий broker/fan-out между процессами не нужен: PostgreSQL остаётся источником истины. `SSE_MAX_CONNECTIONS`=2000 ограничивает каждый API-процесс; `SSE_LIMIT`=2000 — весь текущий Nginx. Это ограничение ресурсов, не механизм бизнес-синхронизации.

Регистрация ограничена на Nginx по реальному remote_addr: `REGISTER_RATE`=30r/s, `REGISTER_BURST`=1000, nodelay. Большой burst допускает всплеск с общей NAT сети; маленького per-IP лимита SSE нет, используется общий бюджет. 429 содержит Retry-After и безопасный JSON. Внешние X-Forwarded-For/X-Real-IP перезаписываются; Core не публикуется напрямую. При добавлении внешнего ingress надо явно доверять только его адресам и протестировать восстановление настоящего IP. Несколько независимых Nginx не разделяют эти зоны; production потребует общего ingress/согласования бюджетов. Это не полноценная защита от распределённых ботов.

`API_WORKERS`=1 по умолчанию, можно задать2; pool и SSE producer будут отдельными. Перед увеличением числа процессов учитывать суммарный бюджет PostgreSQL connections (включая одно reserved на активный relay/sender). Блокировка мероприятия/ограничения UNIQUE/FIFO остаются в PostgreSQL, не в локальном Python mutex.

Публичный список: `GET /api/events?limit=20&offset=0` → `{items,next_offset,server_time}`; limit1..100, offset0..1000000. Сначала выбирается ограниченная страница id, потом её агрегаты. При изменениях расписания между запросами offset страницы не являются историческим snapshot: обновить список; для больших offsets/долгих списков позже рассмотреть cursor pagination.

UI берёт время только из server_time и performance.now; начальная загрузка/потеря SSE запрещают времязависимые действия до свежего снимка. Heartbeat не вызывает приватный GET каждую секунду: обновление по изменению агрегатов/даты и после reconnect, fallback раз10s для изменения участия без изменения итоговых чисел. Серверный ответ и generation всегда окончательны; fallback задерживает отображение редкого такого изменения, но не позволяет обойти правила.

Production пока требует TLS, реального SMTP с учётными данными/TLS и репутацией домена (SPF/DKIM/DMARC), backup+restore drill, мониторинга/оповещений, защищённого ingress и измерений на целевом железе. Внешний SMTP и CD в этой работе не внедряются. Mailpit/локальные замеры не являются production SLA.

Часы сервера/БД должны быть синхронизированы (NTP). UI защищён от сдвига часов устройства, но это не заменяет корректное время сервера. Локальные измерения и выявленный медленный прогон очереди: [LOAD_TESTING.md](LOAD_TESTING.md).

После временной ошибки PostgreSQL producer удаляет свой topic до очистки старых HTTP streams. Новое соединение создаёт новый producer/свежий SQL-снимок; поздний cleanup старого соединения не удаляет новую подписку. Индикатор Availability использует serverNow из SSE, а список — server_time ответа пагинации плюс performance.now; при неизвестном времени показывается «Уточняем статус».
