# Notifications → Mailpit: MIME, SMTP и восстановление

Реализован один последовательный `notifications-sender` (`python -m notifications_app.worker`) отдельно от HTTP API. Используется aiosmtplib 5.1.3, AsyncSession и asyncpg. Зависимость SMTP добавлена только в Notifications; инфраструктурный test-only Docker target устанавливает его lock-файл для сквозных тестов. Core не знает об SMTP и не читает БД Notifications. Схемы и прежние миграции не изменены: Core 24 колонки, Notifications 7.

## Две границы неизменности

1. **Core: `email_outbox.prepared_at`.** В event-locked транзакции проверяются статус участия, participation_no, schedule_version и срок. До фиксации допускаются отмена/обновление payload и срока. Перед HTTP сохраняется неизменяемый envelope v1. После commit нельзя менять ID/JSON даже при неизвестном HTTP-исходе. Core остаётся единственным источником бизнес-истины и готовности задания.
2. **Notifications: `notification_jobs.mime IS NOT NULL`.** При первой SMTP-попытке валидируется принятый envelope и формируются UTF-8 text/plain MIME-байты. MIME, attempts и следующий available_at фиксируются **одним commit до сети**. Поле mime обозначает готовность MIME, а не отправку или lease; отдельный prepared_at не нужен. При повторе renderer не вызывается. Из сохранённых From/To извлекается прежний SMTP envelope, Date и Message-ID не пересоздаются. Изменение SMTP_FROM, PUBLIC_APP_URL, шаблона или времени после рестарта не изменит уже сохранённое письмо.

Message-ID: `<Core-outbox-UUID@домен-From>`, например `<uuid@example.test>`. Date — UTC-время первой подготовки MIME. Получатель зафиксирован в Core payload и MIME To; IDN-домен переводится в ASCII, SMTPUTF8 не используется. CR/LF/U+0000 и несколько адресатов отклоняются. Произвольное описание попадает только в тело, не в заголовки. Шаблоны ticket/waitlist/reminder/rescheduled показывают версию, поколение участия и исторический смысл; rescheduled содержит прежнюю/новую дату, ticket — код, начальное письмо — приватную ссылку управления. Полноценного UI для этой ссылки пока нет.

Обе границы обеспечиваются прикладными путями записи и тестами, не триггером PostgreSQL. Оператор с SQL-доступом может испортить данные: не редактировать ID, payload или сохранённый MIME. Некорректные legacy payload/MIME остаются в failed с нейтральной ошибкой; sender не угадывает адрес/содержимое и не удаляет строки.

## Отмена, восстановление, сроки и версии

Notifications не запрашивает Core, не вычисляет starts_at − 24h и не переносит письма самостоятельно. Его available_at — первая готовность принятого задания (по умолчанию now), далее срок retry. Будущий reminder до своего срока остаётся в Core. Core отменяет неподготовленный reminder при отказе, обновляет срок/контекст при переносе и реактивирует ту же строку при допустимом resume. Логический reminder один на всю жизнь регистрации, для confirmed/waitlisted; при поздней регистрации — сейчас до начала события. После начала неподготовленный reminder отменяется. Эти прежние правила не менялись.

| Момент бизнес-изменения | Поведение |
|---|---|
| Отмена до Core freeze | Core cancelled; в Notifications задания нет, SMTP не вызывается |
| Перенос до Core freeze | Неподготовленные ticket/reminder получают актуальные данные/срок; отдельный rescheduled содержит свой исторический перенос |
| Отмена/перенос после Core freeze, до Notifications MIME | Уже принятый снимок не переписывается; renderer сохраняет его исторический смысл |
| Отмена/перенос после MIME, в том числе после SMTP-ошибки | Повтор использует прежние байты; Core-состояние участия/билета не изменяется от доставки |
| Resume | Новое участие/билет от Core, старый билет недействителен; прежние задания не перезаписываются и не оживляют состояние Core |
| Поздний HTTP повтор того же ID | Только сравнение payload/202; не сбрасывает sent/failed, attempts, срок, last_error или MIME |
| Тот же ID с заменённой версией/содержимым | 409; прежняя запись не меняется |
| Разные корректные ID/версии приходят не по порядку | Сохраняются отдельные исторические сообщения; нет latest-wins, чтобы не потерять начальную ссылку и отдельные переносы |

В контракте v1 нет команды отзыва уже переданного уведомления. Поэтому письмо, зафиксированное Core до отмены, может прийти позднее — даже если MIME ещё не был подготовлен. Нельзя обещать немедленную отмену такой доставки, не меняя согласованный протокол. Это не возвращает отменённую регистрацию/уведомление Core в pending. Получатель должен считать письмо снимком; действительность билета проверяет Core. Порядок фактической доставки разных версий при backoff не гарантируется. Повтор HTTP никогда не служит ручным retry failed-письма.

## Алгоритм и состояния

1. Короткая read session выбирает первое due pending по `(available_at, id)`.
2. Новая транзакция блокирует одну notification_jobs, перепроверяет статус/срок/бюджет. Готовит MIME один раз или загружает сохранённый. Сохраняет попытку и `available_at = now + min(cap, base × 2^(attempts−1))`, commit.
3. Вне DB-сессии/транзакции выполняется async SMTP: connect, sendmail сохранённых bytes, close. Задан явный local_hostname (без синхронного getfqdn), локальный Mailpit без TLS/auth; внешний SMTP не настроен. Один asyncio deadline охватывает всю сеть, дополнительно заданы таймауты SMTP-клиента. QUIT не требуется для успеха: SMTP DATA 250 уже означает принятие, разрыв при закрытии не должен его отменять.
4. Новая короткая транзакция пишет sent только после успешного SMTP DATA. Это принятие Mailpit, не чтение письма или доставка внешнему почтовому ящику. Core forwarded по-прежнему означает только HTTP acceptance.
5. Таймауты, disconnect/OSError и временные SMTP-ответы → pending с backoff от завершения ошибки. SMTP 5xx → failed без автоматического retry. При исчерпании бюджета → failed, запись/MIME сохраняются. Неожиданные DB/programming ошибки не маскируются под sent; worker пишет только класс ошибки и делает паузу. Пустая очередь также даёт паузу, без busy loop.

Каждая начатая попытка расходует бюджет, даже если процесс умер до SMTP. После смерти на последней попытке очередной проход переводит задачу в failed, не отправляя сверх бюджета. `last_error` содержит только постоянный текст/тип ошибки/код SMTP, без ответа сервера, адреса, токена или тела. Логи worker также не содержат payload или exception text. Mailpit работает с MP_QUIET=true; debug SMTP-трассировку не включать.

| Переменная | Default | Назначение |
|---|---|---|
| SMTP_HOST / SMTP_PORT | mailpit / 1025 | В Compose только локальная SMTP-сеть |
| SMTP_FROM | events@example.test | До первой фиксации MIME |
| PUBLIC_APP_URL | http://localhost:8080 | HTTP(S) origin для приватной ссылки; при смене frontend port установить явно |
| SENDER_TIMEOUT | 5 s | Общий deadline + SMTP timeout, >0…60 |
| SENDER_POLL_INTERVAL | 5 s | Пауза при пустой очереди/ошибке DB, >0…60 |
| SENDER_MAX_ATTEMPTS | 8 | Начатые попытки, 1…100 |
| SENDER_BACKOFF_BASE / SENDER_BACKOFF_CAP | 1 / 60 s | Экспоненциальная задержка с пределом |

В штатном малом наборе задержка включает два poll interval (Core relay и Notifications sender), сеть и backlog; жёсткого SLA ≤5s текущая архитектура не даёт. Не запускать две реплики sender; старый процесс должен завершиться до запуска нового. API не запускает sender в lifespan, поэтому масштабирование HTTP не создаёт дополнительных SMTP-процессов. Leases/SKIP LOCKED остаются [будущим переходом](WORKER_EVOLUTION.md).

## Безопасный ручной retry

После устранения причины оператор проверяет конкретное failed-задание и принимает риск позднего исторического/дублирующего письма. Остановить sender, вызвать **один ID**, затем запустить его снова:

```sh
docker compose stop notifications-sender
docker compose run --rm --no-deps notifications-sender python -m notifications_app.retry UUID --acknowledge-duplicate-risk
docker compose up --no-deps -d notifications-sender
```

CLI использует только обычную роль Notifications. В транзакции FOR UPDATE меняется только failed → pending, attempts=0 и available_at=now. ID/payload/MIME и прежний last_error сохраняются до нового результата; sent/pending/отсутствующий/некорректный job не реактивируются. Повтор команды на уже pending не сбрасывает бюджет второй раз. Не обнулять MIME и не создавать новый ID ради retry. Core outbox retry — отдельная операция, описанная в [HTTP-протоколе](NOTIFICATION_PROTOCOL.md).

## Сбои и пределы дедупликации

| Сбой | Последствие |
|---|---|
| До commit MIME | Изменения откатываются; SMTP ещё не начат |
| После commit MIME до SMTP | После рестарта тот же MIME/ID, ранее сохранённый срок/бюджет |
| SMTP не принял / 4xx / disconnect | Повтор после backoff; при disconnect исход может быть неизвестен |
| SMTP принял, ответ потерян | Pending повторяет тот же MIME; SMTP мог уже сохранить письмо |
| SMTP DATA 250 получен, crash до sent commit | То же окно возможного дубликата |
| Последняя попытка прервана | Failed при следующем due-проходе, требуется явный retry |
| Core HTTP повтор после sent/failed | Только 202; ничего не активируется заново |

**Exactly-once SMTP не обеспечивается.** PostgreSQL и SMTP не имеют общей транзакции. Mailpit с `MP_IGNORE_DUPLICATE_IDS=true` подавляет повтор по Message-ID в своём сохранённом хранилище; fault-тест подтверждает это на текущем закреплённом образе. Он не сверяет payload и не заменяет идемпотентность Notifications. После удаления письма, очистки/потери/смены Mailpit-хранилища, отключения опции или перехода на другой SMTP такой защиты может не быть. Два SMTP accept не превращаются в одну попытку; sent не доказывает единственную физическую доставку.

Основания для SMTP-адаптера: [aiosmtplib raw bytes](https://aiosmtplib.readthedocs.io/en/stable/usage.html#sending-raw-messages), [SMTP.sendmail](https://aiosmtplib.readthedocs.io/en/stable/reference.html#aiosmtplib.SMTP.sendmail); Mailpit описывает опцию как подавление по Message-ID: [runtime options](https://mailpit.axllent.org/docs/configuration/runtime-options/).

## Запуск и проверка

Обычный `docker compose up --build -d --wait` теперь запускает notifications-sender. Ни API, ни sender не зависят в depends_on от Mailpit: его простой не блокирует бизнес-операции/HTTP-приём, задания остаются в БД. Обновление использует прежний PostgreSQL volume, без миграции/перезаписи строк; перед эксплуатационным обновлением нужна обычная резервная копия. Существующий .env не перезаписывать.

Тестовый профиль имеет отдельный test-mailpit в tmpfs без host ports; Core и Notifications тесты используют прежний test-db/раздельные обычные роли. Наборы выполняются последовательно из-за миграционных тестов. Проверяются MIME/границы, расписание/поколения, SMTP 4xx/5xx/timeout/disconnect, рестарты, лимит/ручной retry, отсутствие idle DB-транзакции во время SMTP, отмена/перенос до/после MIME, полный Core → HTTP inbox → реальный test-mailpit.

CI дополнен `infrastructure/checks/smtp_smoke.py`: реальные процессы и runtime Mailpit; pause Mailpit сохраняет хранилище даже в tmpfs, SIGKILL sender, восстановление; затем SMTP TCP proxy передаёт DATA в настоящий Mailpit и теряет ответ после accept. Новый sender повторяет прежний MIME, проверяются заголовки/тело и одна сохранённая копия. Сценарий выполняется только с явным test/CI project guard. SMTP sender и новый UI/SSE не смешиваются: UI/SSE в этом этапе не добавлены.
