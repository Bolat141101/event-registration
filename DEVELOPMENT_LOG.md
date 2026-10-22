# Журнал разработки

Часовой пояс: `Asia/Almaty`, `UTC+05:00`. Источник контрольных меток: инструмент часов, возвращающий UTC; для отображения добавлено 5 часов. Это фактические моменты наблюдения/фиксации результатов, а не выдуманные точные длительности команд.

Журнал начат в текущем этапе анализа. Предыдущие сообщения пользователя и первоначальный план существуют в чате, но их точное время здесь не восстановлено. Записи ниже не утверждают, что предыдущая работа началась в какое-либо придуманное время.

| Время Алматы | Фактически выполнено / наблюдение | Результат |
|---|---|---|
| 2026-10-19T22:29:41+05:00 | Получена первая контрольная метка, начато исследование workspace и инструкции PDF | В docs найден один исходный PDF; объявлено применение навыка PDF |
| 2026-10-19T22:30:34+05:00 | К этой отметке проверено начальное состояние Git, извлечены текст PDF и отдельно полные страницы 1, 2, 9; начаты отрисовка и поиск технических первоисточников | В репозитории нет коммитов; PDF уже staged пользователем/до текущей работы, main.py уже существует пустым и untracked. PyMuPDF недоступен; pypdf успешно прочитал 13 страниц. Поиск по всем страницам не обнаружил требования эссе. Вопрос Mailpi/Mailpit отправлен пользователю |
| 2026-10-19T22:31:07+05:00 | Визуально проверены отрисованные страницы 1, 2 и 9; сверены официальные сведения о блокировках PostgreSQL и настройках Mailpit; вычислен SHA-256 PDF | Общие требования и весь кейс №9 читаемы; установлено наличие настройки Mailpit подавления дублей Message-ID. Исходный PDF не изменён |
| 2026-10-19T22:33:04+05:00 | Создан REQUIREMENTS.md: матрица PDF/условий пользователя, варианты реализации и проверки, неоднозначности A01–A09; получен ответ пользователя о Mailpit | Mailpit подтверждён. Функциональные требования пока имеют только план реализации и приёмки |
| 2026-10-19T22:37:22+05:00 | Создан ARCHITECTURE.md: компоненты, структура, три таблицы, транзакции, FIFO, чекин, outbox/напоминания, SSE, API, тесты и риски; снята контрольная отметка для журнала решений | REQUIREMENTS.md — 91 строка, ARCHITECTURE.md — 308 строк на этой проверке. Git показывает новые документы, прежний staged PDF и прежний main.py. `git diff --check` не сообщил ошибок, но untracked-файлы эта команда сама не проверяет |
| 2026-10-19T22:39:18+05:00 | Созданы DECISIONS.md и DEVELOPMENT_LOG.md; выполнена отдельная проверка четырёх Markdown-файлов и состояния Git | Проверены пробелы/переводы строк и парность блоков кода; 18 G, 16 C, 7 U и 9 A имеют последовательные уникальные ID; D01–D10 присутствуют. SHA-256 PDF прежний, main.py пустой, коммитов нет. Проверки приложения не запускались |
| 2026-10-19T22:39:58+05:00 | Уточнена реактивация напоминания при повторном вступлении и неизменяемость уже подготовленного письма; повторно проверены форматирование и локальные ссылки всех четырёх документов | Проверки прошли. Запрос открытия ARCHITECTURE.md в панели Codex принят со статусом queued. Этап передаётся пользователю на согласование; реализация не начата |
| 2026-10-20T08:42:03+05:00 | Начат пересмотр архитектуры по новым замечаниям; прочитаны документы и состояние Git | Рабочая ветка теперь main с upstream origin/main; уже существует коммит ecc4273 `first_commit`. Это изменение между этапами, агент его не создавал; main.py по-прежнему untracked |
| 2026-10-20T08:43:20+05:00 | Проверены первичные документы PostgreSQL, Celery/Redis, WHATWG SSE/WebSocket, RabbitMQ и Mailpit | Уточнены гарантии изоляции, redelivery/ack и отсутствие автоматической exactly-once доставки email; собраны ссылки для сравнений |
| 2026-10-20T08:47:15+05:00 | Переработаны схема/алгоритм outbox, доступ по токену, эндпоинты, объяснение ACID/изоляции и SSE; выполнен поиск устаревших терминов | Убраны leases/processing и поддержка нескольких отправителей; Message-ID вычисляемый, prepared_at сохранён. Публичный email-запрос больше не может восстанавливать cancelled; resume требует токен и номер участия |
| 2026-10-20T08:49:34+05:00 | Добавлены сравнение трёх очередей, путь будущей миграции, границы расширения и таблица компромиссов; обновлена матрица требований | REQUIREMENTS.md дополнен U08–U10 и согласован с новой схемой. Получена отметка для новой редакции журнала решений; функциональные тесты не выполнялись |
| 2026-10-20T08:51:18+05:00 | Обновлены DECISIONS.md и журнал; выполнены автоматические проверки документов и состояния Git | Проверены форматирование, таблицы, локальные ссылки, последовательные ID G18/C16/U10/A9, разделы архитектуры 1–14, 12 полей outbox и отсутствие удалённых полей/маршрутов в актуальном контракте. Изменены только четыре Markdown-файла; HEAD ecc4273, индекс, PDF и пустой main.py неизменны. `git diff --check` прошёл |

## Проверенные первоисточники

- Локальный PDF: `docs/Задания Agentic Developer (2).pdf`; страницы 1–2 и 9 прочитаны полностью; визуальная сверка этих трёх страниц завершена.
- [PostgreSQL — Explicit Locking](https://www.postgresql.org/docs/current/explicit-locking.html).
- [PostgreSQL — Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html).
- [Mailpit — Runtime options](https://mailpit.axllent.org/docs/configuration/runtime-options/).
- [Mailpit — Importing messages](https://mailpit.axllent.org/docs/integration/importing/).

Веб-источники использованы для проверки технических свойств предложений. Это не runtime-зависимости будущего приложения и не дополнительные требования задания.

## Технические детали этого этапа

- Прочитаны инструкции навыков PDF и openai-docs; для описания фактического инструмента использован доступный контекст, точная версия модели не выдумана. Детали — DECISIONS.md.
- Использован bundled Python с pypdf и Poppler pdftoppm. Неудачная попытка импорта pymupdf не означала недоступность PDF; запасной способ чтения сработал без установки пакетов.
- Временные изображения для визуальной проверки находятся вне проекта: `/tmp/maddevs-requirements-review/`. Они не являются сдаваемыми артефактами и не добавляются в Git.
- Поиск не нашёл применимых AGENTS.md в workspace и проверенных родительских каталогах.
- Исходный PDF, пустой main.py и индекс Git сохранены. Команды git add/commit/push не выполнялись; приложение, Compose, миграции и тесты не создавались.

## Состояние после CI-этапа (историческая запись)

Этап: настройка GitHub Actions CI для уже существующего инфраструктурного каркаса. Добавлен workflow, проверки локально выполнены. Backend/frontend, миграции, Mailpit, README и базовые тесты присутствуют; бизнес-функции регистрации/FIFO/чекина/доставки/SSE ещё не реализованы. Исторические записи выше описывают состояние на момент их создания. HEAD ecc4273 сохранён; агент не создавал коммитов и не выполнял push. Запуск CI на GitHub пока не подтверждён.

Следующим действием на момент CI-этапа было показать результаты и дождаться подтверждения пользователя. Запрет push на этом этапе сохранён; позднее пользователь отдельно разрешил упрощение схемы, см. новые записи ниже.

## Проверка CI от 2026-10-20

Метки ниже получены инструментом часов в текущем этапе и преобразованы из UTC в Asia/Almaty. Пропущенные в текущем файле записи предыдущих этапов не восстанавливаются задним числом.

| Время Алматы | Фактически выполнено | Результат |
|---|---|---|
| 2026-10-20T15:09:43+05:00 | Прочитаны manifests, Compose, Dockerfile, тесты и состояние Git; начато изучение официального синтаксиса GitHub Actions | Workflow ещё не существовал. Обнаружена сохранённая пользователем публикация порта DB 5433; принято сохранить её значение по умолчанию |
| 2026-10-20T15:12:08+05:00 | Создан .github/workflows/ci.yml; POSTGRES_PORT добавлен в Compose/.env.example; начата локальная валидация | Триггеры push/PR main, один job, существующие образы/зависимости, изолированный CI-проект, health и cleanup |
| 2026-10-20T15:13:09+05:00 | Actionlint 1.7.12 завершился без ошибок; проверены фильтры/permissions и bash-синтаксис всех run-блоков; начат локальный запуск точных команд/environment workflow | YAML прочитан стандартным Ruby Psych после обнаружения отсутствия PyYAML; зависимости приложения не менялись. Скрипт воспроизведения создан только в /tmp |
| 2026-10-20T15:14:14+05:00 | Полный локальный CI-прогон завершился кодом 0; проверена поддержка Linux amd64 закреплёнными Docker digest | Ruff/format и Mypy прошли; 30 tests passed за 0.54s; Alembic round-trip и check прошли; frontend image собран; Compose поднялся с новыми volumes; health вернул точный ожидаемый JSON. Все контейнеры/volumes CI-проекта удалены |
| 2026-10-20T15:15:40+05:00 | README и журнал решений обновлены; выполнена итоговая проверка diff/Git и изоляции окружений | `git diff --check` прошёл, HEAD ecc4273 и индекс неизменны. CI-контейнеров/volumes нет, обычные сервисы работают и health даёт 200. Git push и запуск GitHub Actions не выполнялись; следующий этап не начат |

## Упрощение схемы до 24 колонок — 2026-10-21

Метки текущего этапа получены по UTC-часам и переведены в Asia/Almaty (`+05:00`). Это новые записи фактических действий, без восстановления пропущенной истории.

| Время Алматы | Фактически выполнено | Результат |
|---|---|---|
| 2026-10-21T21:23:51+05:00 | Начата проверка файлов, зависимостей, истории Git и области реализации | HEAD eb34b8c, исходное дерево чистое. Реализованы инфраструктура и health, бизнес-сервисы отсутствуют |
| 2026-10-21T21:26:32+05:00 | Проверены работающие Compose-сервисы и число записей в трёх таблицах | Все прикладные таблицы пусты; обычные сервисы работают. Схема до изменения содержит 34 поля |
| 2026-10-21T21:31:06+05:00 | К этой отметке изменены модели, добавлены 0002 и helper очереди; расширены тесты; пройдены локальные Ruff/format/Mypy; начата сборка контейнеров | Модели 5+9+10. Первоначальные замечания Ruff по длине строк и вложенным with исправлены, проверки повторены успешно. 0001 не редактировалась; подготовлены проверки сохранности данных и конкурентного MAX |
| 2026-10-21T21:31:30+05:00 | Обновлены ARCHITECTURE/REQUIREMENTS/README; запущен полный PostgreSQL Pytest и frontend build без кэша; сохранён pre-upgrade дамп | Дамп /tmp/MadDevs-before-0002-20261021.dump вне Git. Результаты ещё выполняющихся проверок на этой отметке не объявлены успешными |
| 2026-10-21T21:32:46+05:00 | К этой отметке получены результаты PostgreSQL Pytest, новой миграции и frontend build; начаты запуск основного окружения и контейнерные проверки | 43 passed, 0 skipped; npm run build выполнял tsc --noEmit и Vite без кэша. Ruff/format контейнера прошли; Mypy на этой отметке ещё выполнялся |
| 2026-10-21T21:34:07+05:00 | Получены результаты Mypy, запуска Compose, SQL-подсчёта и HTTP smoke; выполнен check основной БД | Mypy: 13 файлов без ошибок; db/api/frontend/Mailpit healthy, worker запущен, migrate exit 0; схема 0002, 5+9+10=24; health/OpenAPI/frontend HTTP 200, JSON health ok/ready; основная БД соответствует моделям |
| 2026-10-21T21:35:28+05:00 | Завершён отдельный CLI Alembic downgrade base → upgrade head → check на выделенной тестовой БД; проверены diff, логи и отсутствие изменений 0001 | Все команды exit 0, check: No new upgrade operations detected. Populated downgrade отдельно проверен тестом: явный отказ без частичных DDL-изменений. Неисправленных ошибок проверок нет |

### Выполненные команды и результаты этого этапа

Все команды из корня репозитория, кроме локальных Ruff/Mypy (`backend/`). Полный Pytest выполнялся внутри test-контейнера с TEST_DATABASE_URL на настоящем PostgreSQL 17; интеграционные проверки не пропускались.

| Проверка | Реально выполненная команда | Результат |
|---|---|---|
| Ruff lint | `docker compose --profile test run --rm --no-deps test ruff check .` | PASS |
| Ruff format | `docker compose --profile test run --rm --no-deps test ruff format --check .` | PASS, 22 файла |
| Mypy | `docker compose --profile test run --rm --no-deps test mypy app` | PASS, 13 файлов |
| Pytest + upgrade/check | `docker compose --profile test run --rm --build test` | PASS, 43 tests за 1.45s (35 integration + 8 unit), без skip/xfail; сервисная команда: `alembic upgrade head && pytest && alembic check` |
| Alembic CLI downgrade | `docker compose --profile test run --rm --no-deps test alembic downgrade base` | PASS на пустой тестовой БД, обе ревизии сняты |
| Alembic CLI upgrade | `docker compose --profile test run --rm --no-deps test alembic upgrade head` | PASS с base до 0002 |
| Alembic CLI check | `docker compose --profile test run --rm --no-deps test alembic check` | PASS, No new upgrade operations detected |
| Alembic основной БД | `docker compose exec -T api alembic check` | PASS |
| Compose config | `docker compose config --quiet` | PASS |
| Сборка образов | `docker compose --profile test build api test frontend` | PASS |
| TypeScript/Vite | `docker compose build --no-cache frontend` | PASS, фактически выполнены npm ci и npm run build → tsc --noEmit + vite build |
| Полный запуск | `docker compose up --build -d --wait --wait-timeout 120 db mailpit migrate api worker frontend` | PASS, миграция exit 0, доступные healthchecks зелёные; worker только probe, собственного healthcheck нет |
| Health HTTP | `curl --fail --silent --show-error --max-time 10 --write-out '\nHTTP %{http_code}\n' http://127.0.0.1:8080/api/health` | PASS, 200, {"status":"ok","database":"ready"} |
| OpenAPI HTTP | `curl --fail --silent --show-error --max-time 10 --output /tmp/MadDevs-schema-openapi.json --write-out 'OpenAPI HTTP %{http_code}\n' http://127.0.0.1:8080/api/openapi.json` | PASS, 200; JSON дополнительно проверен Python: единственный бизнес-маршрут пока GET /api/health |
| Frontend HTTP | `curl --fail --silent --show-error --max-time 10 --output /tmp/MadDevs-schema-index.html --write-out 'Frontend HTTP %{http_code}\n' http://127.0.0.1:8080/` | PASS, 200, проверено название в HTML |

SQL выполнен через `docker compose exec -T db` → psql в основной БД:

```sql
SELECT COALESCE(table_name, 'TOTAL') AS table_name, count(*) AS columns
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('events', 'registrations', 'email_outbox')
GROUP BY ROLLUP(table_name)
ORDER BY table_name;
-- TOTAL=24, email_outbox=10, events=5, registrations=9
SELECT version_num FROM alembic_version;
-- 0002_simplify_schema
```

Тесты очереди проверяют ожидание реального event-lock через pg_blocking_pids и чтение MAX после чужого commit, FIFO-сортировку, повторное использование хвоста/пустой очереди и rollback. Тесты схемы проверяют нормализацию/повтор email, cancelled без даты, совместимость хранения нового участия, уникальность билета, допустимость checked_in_at только у confirmed, уникальность логического outbox и sent только после подготовки. Миграционный тест сохраняет данные всех трёх статусов, токен/билет/чекин, обе версии и подготовленный payload/ID/dedup_key/attempts/ошибку.

Это не тесты отсутствующих HTTP-сервисов или доставки SMTP: последнее место, автоматическое продвижение при отмене, авторизованный resume, однократный чекин, реальные email/напоминания/переносы и SSE ещё не реализованы. Их дальнейшая разработка и приёмка остаются отдельными этапами. GitHub CI удалённо не запускался; commit/push не выполнялись.

### Состояние после этого этапа

Контрольная отметка: `2026-10-21T21:36:40+05:00`. В основной PostgreSQL проверены все имена/nullable колонок: events=5, registrations=9, email_outbox=10. Схема соответствует варианту 3. Доступны обновлённые Compose-сервисы, health/OpenAPI/frontend, ORM-нормализация и транзакционная функция номера очереди; полнофункциональная регистрация и обработка outbox ещё впереди. Тестовая БД после проверок остановлена, основные volumes сохранены. `git diff --check` и проверка пустого staged diff прошли; HEAD eb34b8c сохранён, 0001 неизменна. Добавлены три новых пока untracked файла: waitlist.py, 0002_simplify_schema.py, test_waitlist.py; обычный `git diff --stat` их не учитывает. Ошибок в выполненных проверках не осталось. Следующий этап не начат; commit/push не выполнены. После отчёта ожидается решение пользователя.

## Backend-сервисы, HTTP и транзакционная постановка outbox — 2026-10-22

Метки получены по текущим UTC-часам и переведены в Asia/Almaty. Вложения пользователя прочитаны до изменений. На этом этапе SMTP/SSE/UI не реализуются.

| Время Алматы | Фактически выполнено | Результат |
|---|---|---|
| 2026-10-22T11:10:42+05:00 | Прочитано приложенное задание, проверены git status/diff и необходимые модели/сервисы/контракты | Рабочее дерево и staged diff пусты; HEAD 2649399 refactor db. Предыдущая схема и helper очереди уже сохранены пользователем; бизнес-сервисов нет |
| 2026-10-22T11:11:12+05:00 | Сверены API/доступ/напоминания с архитектурой и manifests | Схема 24 колонки достаточна; решено не менять миграции, использовать существующий MAX helper и один event-lock |
| 2026-10-22T11:17:29+05:00 | К этой отметке созданы сервисы, постановка outbox, HTTP/доступ и обработчики ошибок; начата установка email-validator и локальные проверки | Первичные замечания Ruff — формат/неиспользуемые импорты; Mypy до завершения установки сообщил об отсутствующем email_validator. Проверки после установки повторены успешно |
| 2026-10-22T11:21:19+05:00 | Локальные Ruff/Mypy прошли; запущен первый PostgreSQL прогон с сервисными тестами | Реальные конкурентные транзакции, без worker и SQLite; подготовлены rollback/time/version/outbox проверки |
| 2026-10-22T11:24:41+05:00 | Получен успешный первый прогон 67 тестов; добавлены HTTP и дополнительные конкурентные/временные проверки, запущен полный прогон | Все существующие тесты сохранены. Новые сценарии вызывают сервисы/API; prepared состояния задаются только как начальные фикстуры будущего sender |
| 2026-10-22T11:27:00+05:00 | Обновлены README/ARCHITECTURE/REQUIREMENTS; получен результат расширенного прогона | 108 passed, 1 failed из 109: тест отката переноса сравнивал счётчик confirmed со снимком до регистрации. HTTP/доступ/реальный lock timeout прошли |
| 2026-10-22T11:27:56+05:00 | Исправлен исходный снимок в тесте отката; fault injection усилен сбоем после flush outbox; повторён запуск всех тестов | Ruff/format/Mypy прошли. Проверены Compose config и отсутствие существующих volumes под новым именем smoke-проекта; никаких пользовательских volumes не удалено |
| 2026-10-22T11:31:23+05:00 | Получен повторный полный результат, создано и запущено отдельное Compose-окружение с новыми volumes | 109 passed за 3.87s, 0 skipped. Изолированный проект event-registration-business-check-20261022, динамические host-порты, чистая PostgreSQL, migrate exit 0 |
| 2026-10-22T11:32:48+05:00 | Завершён первый настоящий HTTP smoke через frontend proxy; контейнерные Ruff/format/Mypy прошли; отдельный CLI downgrade завершён, upgrade запущен | Создание/регистрация/FIFO/resume/перенос/чекин и коды 200/201/202/401/404/409/422 подтверждены. Итоговые счётчики 1/1/1, схема 24, по одному reminder на запись. SMTP не вызывается |
| 2026-10-22T11:35:22+05:00 | CLI upgrade и check завершены, обычное окружение обновлено с сохранением данных; при ревью замечена утечка наличия email после начала | Команды exit 0. Различие 202 существующего / 409 нового адреса признано несогласованным с нейтральным ответом; принято убрать различие кодов, сохранив запрет вставки |
| 2026-10-22T11:36:03+05:00 | Исправлен публичный ответ после начала, добавлен HTTP regression test, уточнены временные тесты и документация; запущен полный повтор | Новая поздняя регистрация не создаётся, ответ такой же нейтральный 202; Ruff/format/Mypy локально прошли. На этой отметке новый Pytest ещё выполнялся |
| 2026-10-22T11:38:24+05:00 | Получен окончательный полный прогон после исправления приватности; повторный HTTP smoke запущен на свежей БД | 110 passed за 4.13s, без skip/xfail; Alembic check прошёл |
| 2026-10-22T11:40:20+05:00 | Повторный HTTP smoke завершился успешно; Ruff/format/Mypy контейнера прошли; проверен обычный proxy после обновления | Выявлен отдельный HTTP 502 через Nginx при здоровом API, Alembic check основной БД прошёл. Тестовая БД остановлена; smoke-volumes удалялись только у созданного текущим этапом проекта |
| 2026-10-22T11:41:09+05:00 | Причина 502 подтверждена логом: соединение со старым IP upstream; добавлен динамический Docker DNS resolver в Nginx | Изменение только nginx.conf, без пользовательских экранов. Прочитаны официальные Nginx proxy_pass/resolver; запущена пересборка и проверка |
| 2026-10-22T11:42:36+05:00 | Пересборка/запуск обычного frontend завершились; nginx -t и HTTP health прошли; создано свежее изолированное окружение для регрессии proxy | Синтаксис OK, health 200 ok/ready. Backend после 110 passing tests не менялся; повторяются затронутые HTTP/Compose проверки |
| 2026-10-22T11:45:05+05:00 | Проверено восстановление proxy после фактической смены IP API без пересоздания frontend; повторный полный HTTP smoke с новым Nginx запущен; основная схема проверена read-only | API IP в изолированном проекте изменился с 192.168.16.4 на 192.168.16.5, frontend container ID прежний, health 200. Основная БД: events=5, registrations=9, email_outbox=10, revision=0002 |

### Команды и окончательные результаты backend-этапа

Команды запускались из корня репозитория. Для контейнерных тестов TEST_DATABASE_URL указывает на PostgreSQL event_registration_test. В root test-db worker не запускался, обычный worker подключён к другой БД. Ни одна основная прикладная таблица не очищалась. Удалялись только новые volumes изолированного smoke-проекта, созданные текущим этапом.

| Проверка | Реально выполненная команда | Результат |
|---|---|---|
| Ruff lint | `docker compose --profile test run --rm --no-deps test ruff check .` | PASS |
| Ruff format | `docker compose --profile test run --rm --no-deps test ruff format --check .` | PASS, 40 Python-файлов |
| Mypy | `docker compose --profile test run --rm --no-deps test mypy app` | PASS, 25 файлов |
| Полный Pytest + upgrade/check | `docker compose --profile test run --rm --build test` | PASS, 110 tests за 4.13s: 102 integration + 8 unit; 0 skip/xfail. Внутри: alembic upgrade head && pytest && alembic check |
| Отдельный CLI downgrade | `docker compose --profile test run --rm --no-deps test alembic downgrade base` | PASS на пустой отдельной тестовой БД |
| Отдельный CLI upgrade | `docker compose --profile test run --rm --no-deps test alembic upgrade head` | PASS, обе прежние миграции |
| Отдельный CLI check | `docker compose --profile test run --rm --no-deps test alembic check` | PASS, No new upgrade operations detected |
| Check основной БД | `docker compose exec -T api alembic check` | PASS |
| Compose config | `docker compose config --quiet` | PASS |
| Сборка и старт обычного окружения | `docker compose up --build -d --wait --wait-timeout 120 db mailpit migrate api worker frontend` | PASS; после обнаруженного stale-IP proxy исправлен и повторно собран frontend |
| Применение исправленного proxy | `docker compose up --build -d --wait --wait-timeout 120 frontend` | PASS |
| Nginx config | `docker compose exec -T frontend nginx -t` | PASS |
| Обычный health, read-only | `curl --fail --silent --show-error http://127.0.0.1:8080/api/health` | Первоначально FAIL 502, причина исправлена; повтор PASS, ok/ready |
| Изолированный build/start | `COMPOSE_PROJECT_NAME=event-registration-business-check-20261022 COMPOSE_ENV_FILES=.env.example POSTGRES_PORT=0 FRONTEND_PORT=0 MAILPIT_PORT=0 docker compose up --build -d --wait --wait-timeout 120 db mailpit migrate api worker frontend` | PASS с чистыми volumes; frontend TS/Vite слои переиспользованы из кэша, собственный новый typecheck в этом этапе не заявляется |
| Настоящий HTTP smoke новых API | `COMPOSE_PROJECT_NAME=event-registration-business-check-20261022 COMPOSE_ENV_FILES=.env.example POSTGRES_PORT=0 FRONTEND_PORT=0 MAILPIT_PORT=0 docker compose exec -T -e ALLOW_ISOLATED_SMOKE=yes api python - < /tmp/MadDevs-backend-smoke.py` | PASS всех новых маршрутов и ожидаемых 200/201/202/401/404/409/422; counter=1/1/1, один reminder на запись, два rescheduled для двух активных записей; SMTP не используется |
| Регрессия proxy после API recreate | `COMPOSE_PROJECT_NAME=event-registration-business-check-20261022 COMPOSE_ENV_FILES=.env.example POSTGRES_PORT=0 FRONTEND_PORT=0 MAILPIT_PORT=0 backend/.venv/bin/python /tmp/MadDevs-proxy-recovery.py` | PASS, реальная смена IP, frontend не перезапускался, health снова 200. Скрипт внутри выполняет compose up --no-build --no-deps -d --force-recreate --wait --wait-timeout 60 api worker |
| Проверка diff/миграций | `git diff --check` и `git diff --exit-code HEAD -- backend/migrations backend/app/db/models.py backend/app/db/waitlist.py` | PASS, миграции/схема/helper не изменены |

110 тестов включают 37 HTTP-проверок и 30 проверок бизнес-сервисов, плюс все 43 существовавших теста. Реальная конкуренция проверена отдельными транзакциями, ожидающими event-lock в PostgreSQL: последнее место, один нормализованный email, отмена против нового участника, две отмены, два resume, два чекина и чтение текущего времени после ожидания блокировки. Проверены FIFO A/B/C без worker, версии участия/переносов, rollback после записи outbox, prepared pending/sent без переписывания, late reminder, hash/доступ/валидация/отсутствие секретов в ответах и логах. Неподготовленный failed notice обновляется без автоматического retry.

Схема по-прежнему 24 колонки, users не добавлена, новые миграции не потребовались. SMTP/MIME/retries отправки/SSE/полноценные экраны не реализованы намеренно по границам этапа. Нет полноценной авторизации/нескольких организаторов, recovery потерянного токена и отдельного idempotency key создания события. При неопределённом результате COMMIT нельзя гарантировать откат. GitHub Actions удалённо не запускался; команды CI выполнены локально в контейнерах. Коммитов/push нет.

### Состояние после backend-этапа

Контрольная отметка `2026-10-22T11:47:42+05:00`: все 110 тестов и требуемые проверки завершены успешно, исправленный proxy прошёл повторный полный HTTP smoke. Неисправленных ошибок выполненных проверок нет. Основные db/api/frontend/Mailpit healthy, worker запущен (собственного healthcheck нет), migrate exit 0. Выделенная test-db остановлена; все созданные этим этапом smoke-контейнеры/volumes удалены, пользовательские volumes сохранены. Схема/миграции/существующий MAX-helper не изменены. git diff --check и пустой staged diff проверены, HEAD 2649399 сохранён. Добавлены 18 новых пока untracked файлов; обычный git diff --stat их не учитывает. Коммитов/push нет, следующий этап не начат. SMTP/SSE/UI остаются отдельно согласуемой работой.

## Исправление граничных дат и U+0000 — 2026-10-22

| Время Алматы | Фактически выполнено | Результат |
|---|---|---|
| 2026-10-22T12:18:34+05:00 | Проверены status/diff и существующий незакоммиченный backend-этап; прочитаны UTC-преобразование, схемы ввода, API-тесты и README | Существующие изменения сохранены. Причины ошибок: OverflowError в astimezone и отсутствие проверки NUL в описании |
| 2026-10-22T12:21:04+05:00 | Добавлены UTCDateTime с AfterValidator(as_utc), преобразование OverflowError в ValueError и проверка U+0000 в API/сервисе; добавлены семь API-регрессий и исправлен README | Верхняя/нижняя границы для create и schedule отклоняются до сервиса; ошибочный перенос не меняет событие/версию/outbox. Замечание Ruff по длине строки исправлено форматтером; Ruff/format/Mypy повторены успешно |
| 2026-10-22T12:21:54+05:00 | Получен результат полного прогона на отдельной PostgreSQL с актуальными app/tests в read-only mount; проверены diff и неизменность моделей/миграций | 117 passed за 4.38s, без skip/xfail; Alembic check: No new upgrade operations detected. Основная БД и volumes не затронуты |

Команды Ruff/Mypy выполнены из backend: `.venv/bin/ruff check .` — PASS; `.venv/bin/ruff format --check .` — PASS (40 файлов); `.venv/bin/mypy app` — PASS (25 файлов).

Полный PostgreSQL-прогон из корня: `docker compose --profile test run --rm --volume /Users/billcarter/Documents/MadDevs/backend/app:/app/app:ro --volume /Users/billcarter/Documents/MadDevs/backend/tests:/app/tests:ro test`. Использован существующий test-образ с прежними зависимостями и текущими исходниками; внутри выполнены `alembic upgrade head && pytest && alembic check`. Тесты работают только с event_registration_test; тестовая БД затем останавливается, команды удаления volumes не используются.

README больше не относит регистрацию/FIFO/чекин к будущим задачам, описывает реализованные services/outbox и оставшиеся SMTP/SSE/экраны. API возвращает validation_error/422 для `0001-01-01T00:00:00+01:00`, `9999-12-31T23:59:59-01:00` и описаний с NUL; бизнес-сервис не вызывается. Схема/миграции/зависимости не менялись, commit/push не выполнялись.
