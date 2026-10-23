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

## Переход Core API на AsyncSession/asyncpg — 2026-10-22

Время ниже — контрольные отметки реально выполненной работы, Asia/Almaty (UTC+05:00). История предыдущих этапов сохранена. Начальное рабочее дерево чистое, HEAD `9a5694a`, staged diff пуст. Прямое разрешение пользователя: перевести существующий Core API на async, сохранить бизнес-операции и контракты; прежние revisions и данные не менять.

| Время Алматы | Фактически выполнено к отметке | Результат |
|---|---|---|
| 2026-10-22T16:06:25+05:00 | Начало работы: проверка git status/diff/log, актуального кода, миграций и тестов | Исходный этап 2 сохранён пользователем в 9a5694a. Перед правками дополнительно сохранены OpenAPI и SHA256 моделей/двух revision-файлов для сравнения |
| 2026-10-22T16:18:31+05:00 | DB-операции, endpoints, dependency и worker переведены на asyncpg/AsyncSession; адаптированы фикстуры, конкурентные тесты и Alembic env; локальные Ruff/format/Mypy прошли | Первое сравнение OpenAPI совпало. Создан отдельный Compose-проект event-registration-async-check-20261022; test-db в tmpfs, случайный loopback-порт 55012. Основная БД не используется |
| 2026-10-22T16:20:48+05:00 | Выполнен первый полный PostgreSQL Pytest; исправлены ошибки адаптации тестов и запущен повтор | Первый результат: 122 passed, 2 failed и teardown error из-за неawaited callback; наблюдатель pg_stat_activity также читал закэшированный снимок. Добавлены await operation() и pg_stat_clear_snapshot в наблюдателе, проверки не ослаблены |
| 2026-10-22T16:23:34+05:00 | Повторный локальный полный Pytest и check прошли; завершены контейнерные Ruff/format/Mypy, свежий TypeScript/Vite build и запуск изолированного полного стека | 124 passed за 8.13s, без skip/xfail; No new upgrade operations detected. Чистая БД отдельного приложения, migrate exit 0; api/db/frontend/Mailpit healthy, worker запущен |
| 2026-10-22T16:24:25+05:00 | Завершён штатный контейнерный CI-прогон и настоящий HTTP smoke через frontend; OpenAPI и SHA256 сравнены повторно | 124 passed за 6.19s, без skip/xfail. Все маршруты этапа 2 и 200/201/202/401/404/409/422 подтверждены. OpenAPI идентичен; models.py и revision-файлы побайтно прежние |
| 2026-10-22T16:26:03+05:00 | Явные CLI downgrade base → upgrade head → current → check выполнены только в пустой *_test; PostgreSQL подтвердил 24 поля; проверены недоступность/восстановление изолированной БД и SIGTERM worker | head=0002_simplify_schema; events=5, registrations=9, email_outbox=10. Во время остановки БД health/events=503, затем health=200. Первая команда рестарта без POSTGRES_PORT=0 конфликтовала с занятым 5433; повтор с динамическим портом успешен. Основной контейнер/volume не затронут. Worker вывел Worker stopped, без принудительного kill |

### Реализованные изменения

- `backend/app/db/session.py`: create_async_engine + async_sessionmaker; READ COMMITTED, pool_pre_ping, hide_parameters и expire_on_commit=False сохранены. connect timeout=3s и server_settings lock_timeout=2s/statement_timeout=3s адаптированы к asyncpg.
- `backend/app/api/{events,registrations,health,dependencies}.py`, `backend/app/main.py`: async endpoints, async session dependency, awaited readiness и закрытие engine в lifespan. API-схемы/маршруты/коды успешных операций не менялись.
- `backend/app/services/{common,events,registrations,checkins}.py`, `backend/app/db/waitlist.py`, `backend/app/notifications/outbox.py`: явные await для SQL/flush/refresh и async transaction contexts. Event-first lock, отдельный MAX statement, FIFO-продвижение, idempotency/версии, токены/билеты, одно напоминание и неизменность prepared outbox сохранены. Helpers не делают собственный commit.
- `backend/app/api/errors.py`: временные ошибки asyncpg, включая OSError/TimeoutError до SQLAlchemy wrapper, connection_invalidated и SQLSTATE недоступности, переводятся в прежний безопасный 503. SQL/параметры/секреты не логируются.
- `backend/app/worker.py`: asyncio.Event и ожидание интервала/сигнала без threading.Event.wait; awaited DB readiness и dispose. Это всё ещё инфраструктурная проверка, не реализация доставки.
- `backend/migrations/env.py`: AsyncEngine + официальный run_sync-адаптер Alembic; только в тестовом harness синхронные публичные Alembic commands запускаются через asyncio.to_thread, чтобы не вкладывать asyncio.run в AnyIO. SQL использует asyncpg. Новых migrations нет, файлы versions и модели не менялись.
- `backend/pyproject.toml`, оба requirements lock, `backend/app/config.py`, `compose.yaml`: sqlalchemy[asyncio], asyncpg 0.32.0, DSN postgresql+asyncpg; psycopg/psycopg-binary убраны из зависимостей. Остальные закреплённые версии сохранены, greenlet остаётся необходимым адаптером SQLAlchemy.
- `backend/tests/conftest.py`, integration fixtures/support и все integration tests: AnyIO/asyncio, AsyncEngine/AsyncSession, отдельная сессия каждой конкурентной задаче, функция-фикстура engine без передачи asyncpg-пула между event loop. В тестах миграций пул очищается после внешнего DDL.
- Семь дополнительных проверок: отказ от sync DSN (1), чтение/health во время реального event-lock (1), OSError/TimeoutError API (2), отмена задачи с rollback регистрации+outbox и освобождением lock (1), ошибки соединения health (2). Все прежние 117 проверок сохранены; предупреждения остаются ошибками.
- README/ARCHITECTURE/DECISIONS/docs/WORKER_EVOLUTION обновлены: текущая async-модель, смена DSN без пересоздания БД, адаптация Alembic, владение сессией и будущие границы worker. Исторические решения не переписаны задним числом.

### Фактические команды и результаты

Для контейнерных команд ниже общий префикс P: `docker compose --env-file .env.example -f compose.yaml -f /tmp/MadDevs-async-test-port.yaml -p event-registration-async-check-20261022 --profile test`. Временный override только публикует test-db как `127.0.0.1:0:5432` для локального Pytest. Он не меняет сервисы основного проекта. При запуске всего стека заданы `POSTGRES_PORT=0 FRONTEND_PORT=0 MAILPIT_PORT=0`; основные volumes не используются. `P …` в таблице — сокращённая запись фактически выполненного полного префикса с аргументами. Первые lint/build команды выполнялись также без временного override, который к ним не относится.

| Проверка | Реально выполненная команда | Итог |
|---|---|---|
| Ruff локально | из backend: `.venv/bin/ruff check .` | PASS |
| Форматирование локально | из backend: `.venv/bin/ruff format --check .` | PASS, 40 файлов |
| Mypy локально | из backend: `.venv/bin/mypy app` | PASS, 25 файлов |
| Полный локальный PostgreSQL Pytest | из backend: `.venv/bin/pytest -q`; DATABASE_URL/TEST_DATABASE_URL указывали на выделенную event_registration_test через 127.0.0.1:55012, драйвер asyncpg | PASS, 124 за 8.13s; первый неуспешный прогон описан выше |
| Локальный Alembic | из backend: `.venv/bin/alembic upgrade head`, `.venv/bin/alembic check` с тем же тестовым DSN | PASS |
| Compose config | `docker compose --env-file .env.example -p event-registration-async-check-20261022 --profile test config --quiet` | PASS |
| Backend/test/frontend images | `docker compose --env-file .env.example -p event-registration-async-check-20261022 --profile test build api test frontend`; затем актуальные api/test пересобраны | PASS; frontend первоначально использовал кэш, далее сборка выполнена заново отдельной командой |
| Ruff/format/Mypy контейнера | `P run --rm --no-deps test ruff check .`; `P run --rm --no-deps test ruff format --check .`; `P run --rm --no-deps test mypy app` | PASS, включая повтор в окончательном test image |
| Штатный CI database step | `P build test`, `P run --rm test`; внутри `alembic upgrade head && pytest && alembic check` | PASS, 124 за 6.19s, без skip/xfail |
| Отдельный round-trip CLI | `P run --rm --no-deps test alembic downgrade base`; затем `alembic upgrade head`, `alembic current`, `alembic check` с тем же префиксом | PASS, head 0002; check без расхождений |
| Свежие TypeScript/Vite | `docker build --target build -t event-registration-async-frontend-check:local frontend`; `docker run --rm --network none event-registration-async-frontend-check:local npm run build` | PASS: tsc --noEmit + Vite 8.3.4, 17 modules, built in 2.53s |
| Чистая БД и полный Compose | `P up --no-build -d --wait --wait-timeout 120 db mailpit migrate api worker frontend`; `P ps --all` | PASS, migrate=0, сервисы готовы; worker не имеет своего healthcheck |
| HTTP health через proxy | `curl --fail --silent --show-error http://127.0.0.1:55015/api/health` | 200, ok/ready |
| Настоящий HTTP Core smoke | `P exec -T -e ALLOW_ISOLATED_SMOKE=yes api python - < /tmp/MadDevs-async-smoke.py` | PASS, все имеющиеся бизнес-маршруты, FIFO/resume/перенос/checkin; счётчики 1/1/1, два reminder на две регистрации, два уведомления переноса; PostgreSQL снова подтвердил 24 поля |
| Отказ и восстановление БД | `P stop db`, HTTP GET health/events через urllib, затем `P up --no-deps -d --wait --wait-timeout 60 db` с переменными динамических портов | PASS: 503/503 без секретов → 200 health; конфликт порта первой команды исправлен |
| Остановка worker | `P stop worker`; `P logs --no-color --tail 12 worker` | PASS, INFO Worker stopped |
| Неизменность контрактов/схемы | сравнение OpenAPI и SHA256 с сохранёнными до правок; `git diff --exit-code HEAD -- backend/migrations/versions backend/app/db/models.py` | PASS; без новых колонок/revisions |
| Diff | `git diff --check`, `git status --short --branch`, `git diff --stat` | PASS; изменения не staged, commit/push отсутствуют |

Все проверки выполнены локально; GitHub Actions удалённо не запускался. Существующий workflow не менялся: команды и сервисы прежние, DSN/dependency изменены в Compose/образах. Ошибки тестовой адаптации и команды рестарта исправлены, проверки не отключались. SMTP, MIME, отправочные retries, SSE и полноценный UI остаются будущими этапами; этот переход их не реализует. Async не увеличивает число одновременных мутаций одного события под event-lock и не устраняет неопределённость исхода при потере соединения в момент COMMIT.


Контрольная отметка завершения проверок и уборки: `2026-10-22T16:28:28+05:00` (22 минуты 3 секунды от начальной отметки). Выполнен `P down --remove-orphans` **без --volumes**: временные контейнеры и сеть удалены, оба созданных проверкой volumes оставлены. Основные api/db/frontend/Mailpit остались healthy, прежний worker работает, исходная test-db осталась остановленной. Основное приложение не пересоздавалось, его данные и volumes не изменялись. Список прежних test-функций сопоставлен с HEAD: все сохранены, только название теста sync DSN заменено на asyncpg. На последней проверке неустранённых падений нет; рабочее дерево содержит изменения этого перехода, индекс пуст, HEAD 9a5694a сохранён. Git-коммитов и push нет.

## Валидация ticket_code и HTTP-конкуренция двух процессов — 2026-10-22

| Время Алматы | Фактически выполнено к отметке | Результат |
|---|---|---|
| 2026-10-22T17:10:29+05:00 | Проверены актуальные status/diff, схемы ввода, API-тесты, async-сервисы и фикстуры | Незакоммиченный async-переход сохранён. Перед правками записаны SHA256 services/db/migrations для контроля отсутствия изменений бизнес-логики |
| 2026-10-22T17:14:02+05:00 | Добавлен валидатор CheckIn.ticket_code, три API-регрессии NUL; исправлена проверка результата HTTP-регистрации; добавлен test_api_processes.py | Код билета отклоняется до SQL; результат POST читается из PostgreSQL без business.join. Два spawned Uvicorn-процесса имеют разные PID, порты, lifespan, engines и пулы. Начат полный Pytest на отдельной PostgreSQL; первоначальная команда с неподдерживаемым Compose run --no-build не запускалась, флаг убран |
| 2026-10-22T17:15:22+05:00 | Первый полный PostgreSQL-прогон и Alembic check прошли; доработан teardown всех дочерних процессов и сравнение билета API с БД; повтор запущен | 129 passed за 10.24s; Ruff/format/Mypy проходят. Проверки не отключались |
| 2026-10-22T17:15:45+05:00 | Завершён повтор всего Pytest/Alembic после окончательных правок; сопоставлены SHA256 бизнес-кода и AST исправленного HTTP-теста | 129 passed за 9.81s, без skip/xfail; No new upgrade operations detected. Services, db и migrations не изменялись в этом этапе; в проверяемом HTTP-тесте нет вызова join |

Изменения этого запроса:

- `backend/app/api/schemas.py`, CheckIn.no_null_character: U+0000 в любом месте ticket_code вызывает ValueError входной схемы и прежний validation_error/HTTP 422. Другие допустимые коды и бизнес-правила чекина сохранены.
- `backend/tests/integration/test_api.py`: после регистрационного POST выполняются только SELECT для проверки одной регистрации и двух outbox-записей ticket/reminder. Проверяются статус, номер участия, нормализованный email, ticket_code, dedup_key, pending-состояние и hash токена из первого payload. Последующие cancel/resume выполняются через API как раньше. Добавлены три запроса с NUL в начале/середине/всём коде; чекин уже доступен по времени, ответ 422 и сохранённое состояние проверяются на PostgreSQL.
- Новый `backend/tests/integration/test_api_processes.py`: два настоящих HTTP API-процесса через multiprocessing spawn; никакого ASGITransport для конкурентных действий. Перед выпуском event-lock наблюдатель PostgreSQL с обновляемым статистическим снимком подтверждает две ожидающие транзакции. Для capacity=1 проверяются 202/202, ровно 1 confirmed + 1 waitlisted, один билет, FIFO-позиция 1 и четыре уникальных outbox-задания. Для одного билета проверяются 200/409, единственное сохранённое время, повторы 409 через оба процесса и счётчик checked_in=1. Подготовка участника для checkin выполняется до проверяемых HTTP-запросов; результат чекина не создаётся вспомогательными сервисами. В teardown завершаются оба процесса, принудительный kill считается ошибкой теста.
- README дополнен фактически выполненной проверкой двух процессов. Новых зависимостей, миграций и инфраструктурных сервисов нет.

Фактические проверки:

| Команда | Результат |
|---|---|
| `backend/.venv/bin/ruff check backend` | PASS |
| `backend/.venv/bin/ruff format --check backend` | PASS, 41 Python-файл |
| `backend/.venv/bin/mypy --config-file backend/pyproject.toml backend/app` | PASS, 25 файлов |
| `docker compose --env-file .env.example -p event-registration-async-check-20261022 --profile test run --rm --volume /Users/billcarter/Documents/MadDevs/backend/app:/app/app:ro --volume /Users/billcarter/Documents/MadDevs/backend/tests:/app/tests:ro test` | PASS: alembic upgrade head && pytest && alembic check; окончательно 129 passed за 9.81s, без skip/xfail. Использован существующий test image с неизменными asyncpg-зависимостями и актуальными исходниками в read-only mount |
| SHA256 services/db/migrations против начала текущего запроса | PASS, бизнес-логика/схема/миграции сохранены |
| `git diff --check` | PASS |

Запускался только test-db из отдельного проекта в tmpfs. Основная PostgreSQL, её данные и volumes не использовались. Существующие незакоммиченные изменения не откатывались; Git add/commit/push не выполнялись. Новый test_api_processes.py пока untracked и не входит в обычный git diff --stat; его статистика выводится отдельно через git diff --no-index /dev/null.

Дополнительная контрольная отметка `2026-10-22T17:17:57+05:00`: часы двух API-процессов разнесены на одну секунду. Тест теперь сравнивает checked_in_at с часами именно выигравшего процесса, затем проверяет отсутствие перезаписи после проигравшего и повторных запросов. После изменения снова выполнены Ruff, format, Mypy и полный PostgreSQL-прогон той же командой: **129 passed за 8.73s**, без skip/xfail, Alembic check — No new upgrade operations detected. SHA256 services/db/migrations повторно совпали. Это окончательный результат текущего запроса; прежние прогоны 10.24s/9.81s сохранены выше как история.

## Инфраструктурное разделение Core + Notifications — 2026-10-22

Разрешение пользователя: только инфраструктура. Core — бизнес-данные/неизменяемый payload; Notifications в дальнейшем формирует и сохраняет MIME. HTTP relay, приём заданий, SMTP и новый UI не реализовывать. Исходное рабочее дерево чистое; HEAD `6c20757`. Все tracked backend/frontend файлы и OpenAPI сохранены в контрольных SHA256/JSON до правок.

| Время Алматы | Фактически выполнено к контрольной отметке | Результат |
|---|---|---|
| 2026-10-22T22:24:48+05:00 | Проверены status/diff, Compose, Core, Alembic, существующие тесты/CI и runtime-роли | Core использовал суперпользователя events. Выбран отдельный bootstrap и две обычные роли; исходный volume не пересоздаётся |
| 2026-10-22T22:31:02+05:00 | Созданы Notifications, его модель/миграция/тесты, bootstrap и Compose; зафиксированы собственные зависимости на прежних проверенных версиях | Локальные Ruff/format/Mypy Notifications прошли. Начаты сборка образов и полный Core Pytest |
| 2026-10-22T22:33:48+05:00 | Получены первые полные результаты; сохранены приватные дампы/хеши основной БД; подготовлена заполненная изолированная Core DB | Core: 129 passed за 9.09s, Alembic check PASS. Notifications: 21 passed за 0.86s. Основная БД на момент снимка имела 0 строк; поэтому сохранение непустых данных дополнительно проверялось на отдельном постоянном volume |
| 2026-10-22T22:35:34+05:00 | Проверен Core под обычной ролью и повторный bootstrap с заполненными обеими БД; после дампа bootstrap применён к основной установке | Core: 129 passed за 13.64s под core_app_test. В изолированной БД до изменения владельцев: 2 events, 4 registrations, 5 outbox, включая версии/очередь/билеты/чекин/payload и ошибки; после первого и повторного bootstrap все хеши совпали. Notifications payload/MIME также сохранены. PostgreSQL container/volume прежние |
| 2026-10-22T22:36:56+05:00 | Оба сервиса запущены на основном существующем volume; выполнены реальные проверки ролей/изоляции/head/check и независимости Core | core_app/event_registration и notifications_app/event_notifications: обе непривилегированные; чужое подключение=42501. Core head=0002, Notifications head=0001, оба check PASS. Core health/events=200 при остановленном Notifications. На изолированном стеке в этом состоянии через HTTP созданы событие, confirmed+waitlisted и четыре pending outbox |
| 2026-10-22T22:41:22+05:00 | Дополнительные реальные health-тесты выявили raw asyncpg ошибки; после исправления обнаружен конфликт имён двух test_health.py при collection | Исходный точечный результат: own=PASS, чужая/отсутствующая БД/неверный пароль — 3 FAIL. Health Notifications исправлен: любая ошибка собственного readiness-подключения даёт 503, логируется только имя класса. Конфликт collection устранён обычными tests-пакетами __init__.py; тесты не удалялись/не отключались |
| 2026-10-22T22:42:22+05:00 | Все Notifications-тесты повторены после исправлений, собран окончательный test image; проверены SHA256/Core OpenAPI | 25 passed за 0.71s, Alembic check без расхождений. Весь Core/frontend и старые миграции побайтно прежние, OpenAPI совпал |
| 2026-10-22T22:43:55+05:00 | Штатный прогон окончательного Notifications image без bind mounts, контейнерные lint/types и свежие TS/Vite завершены; основная установка обновлена исправленным Notifications | 25 passed за 1.51s; Ruff/format/Mypy PASS (Notifications 18 Python-файлов, app=6). Core Ruff/format/Mypy также PASS (41/25). Vite 8.3.4: 17 modules, 1.21s; Notifications после обновления healthy, HTTP 200 |

### Изменения

- `notifications/`: отдельный проект FastAPI/AsyncSession/asyncpg, собственные pyproject/lock-файлы/Dockerfile/Alembic/tests. Namespace notifications_app исключает смешивание с Core app. Runtime не содержит SMTP/HTTP-relay зависимостей; новые пакеты-инфраструктура не вводились.
- Модель NotificationJob и новая revision `0001_notification_jobs`: семь полей id/payload/mime/status/attempts/available_at/last_error. Внешний UUID без нового генератора, nullable BYTEA под будущий MIME, JSON-object/state/attempts/MIME constraints и частичный pending index. Downgrade блокируется на непустой таблице. Это storage, не обработка заданий.
- `infrastructure/postgres/{bootstrap.sh,databases.sql,schema.sql}`: повторяемое создание второй БД и обычных ролей, отзыв PUBLIC/чужого CONNECT, владение собственной схемой/известными таблицами. Нет initdb, DROP, удаления строк или REASSIGN OWNED кластера. Старый events остаётся администратором. psql variables/format обеспечивают quoting; секреты не выводятся.
- `compose.yaml`: Core использует core_app; Notifications — свою БД/роль и healthcheck. Одноразовые bootstrap/две миграции, отдельный test service. Существующие Core/test/frontend/worker/Mailpit сохранены; ни Core API, ни его health не зависят от процесса Notifications.
- `.env.example`: отдельные прикладные credentials с локальными defaults для совместимости старого .env. Сам пользовательский .env не менялся.
- CI: все прежние Core/frontend шаги сохранены, добавлены Notifications lint/format/Mypy/Pytest/migrations, runtime health и проверка stop-service independence. Удалённый GitHub Actions не запускался.
- README/ARCHITECTURE/DECISIONS/WORKER_EVOLUTION и новый docs/NOTIFICATIONS_INFRASTRUCTURE: текущая инфраструктура, владение payload/MIME, безопасное обновление существующего volume, ограничения и команды. Исторические записи решений/журнала сохранены.

### Реальные команды и результаты

P ниже — сокращённая запись `docker compose --env-file .env.example -p event-registration-notifications-check-20261022 --profile test`. Для runtime-стека использован тот же проект без --profile test, с POSTGRES_PORT=0 FRONTEND_PORT=0 MAILPIT_PORT=0. Это отдельный PostgreSQL instance для проверок, не второй PostgreSQL основного приложения. Рабочий проект запускается обычным docker compose с существующим .env.

| Проверка | Фактически выполненная команда | Итог |
|---|---|---|
| Compose | `docker compose --env-file .env.example config --quiet` | PASS |
| Сборка обоих сервисов и тестов | `P build api test notifications notifications-test frontend` | PASS; после исправления Notifications его образы пересобраны |
| Core lint/format/types | `backend/.venv/bin/ruff check backend`; `backend/.venv/bin/ruff format --check backend`; `backend/.venv/bin/mypy --config-file backend/pyproject.toml backend/app` | PASS, 41 Python-файл / 25 app-файлов |
| Core проверки в образе | `P run --rm --no-deps test ruff check .`; `ruff format --check .`; `mypy app` с тем же префиксом | PASS |
| Все существующие Core tests | `P run --rm test` | PASS, 129 tests за 9.09s, 0 skipped; внутри upgrade/Pytest/check |
| Core tests под обычной ролью | `P run --rm --no-deps -e DATABASE_URL=postgresql+asyncpg://core_app_test:core_database_password_local_only@test-db:5432/event_registration_test -e TEST_DATABASE_URL=postgresql+asyncpg://core_app_test:core_database_password_local_only@test-db:5432/event_registration_test test sh -c 'alembic upgrade head && pytest && alembic check'` | PASS, 129 tests за 13.64s; учётные данные здесь только отдельной тестовой БД |
| Notifications lint/format/types | `backend/.venv/bin/ruff check notifications`; `backend/.venv/bin/ruff format --check notifications`; `backend/.venv/bin/mypy --config-file notifications/pyproject.toml notifications/notifications_app` | PASS, 18 Python-файлов / 6 app-файлов |
| Notifications окончательный образ | `P run --rm notifications-test`; затем `P run --rm --no-deps notifications-test ruff check .`, `ruff format --check .`, `mypy notifications_app` | PASS, 25 tests за 1.51s; Alembic upgrade/check и guard/round-trip включены |
| TS/Vite свежий запуск | `docker build --target build -t event-registration-notifications-frontend-check:local frontend`; `docker run --rm --network none event-registration-notifications-frontend-check:local npm run build` | PASS, tsc --noEmit и Vite 1.21s; исходники frontend не менялись |
| Дамп до основного bootstrap | `docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'` и `pg_dumpall --globals-only` с локальным redirect вне репозитория; затем pg_restore --list | PASS; /tmp/MadDevs-notifications-backup-20261022, права 0600. Пароли/данные дампа не выводились |
| Повторный bootstrap заполненного volume | В изолированном проекте `docker compose ... run --rm --no-deps db-bootstrap`; до/после SELECT count + md5(string_agg(to_jsonb(row)... ORDER BY id)) | PASS: Core 2/4/5 и Notifications payload/MIME побайтно сохранены; cmp снимков/container mount ID успешен |
| Основной bootstrap и запуск | `docker compose run --rm --no-deps db-bootstrap`; `docker compose up --no-build -d --wait --wait-timeout 120 db mailpit migrate api worker frontend notifications-migrate notifications` | PASS, bootstrap/обе миграции exit 0; исходный db container и postgres-data mount прежние |
| Основной schema check | `docker compose exec -T api alembic current/check`; `docker compose exec -T notifications alembic current/check` (current и check отдельными командами) | PASS, Core 0002_simplify_schema, Notifications 0001_notification_jobs; No new upgrade operations detected |
| Основная изоляция | `docker compose exec -T -e OTHER_DB=... api/notifications python - < /tmp/MadDevs-check-database-boundary.py` | PASS в обоих направлениях: собственная БД доступна, все пять административных flags=false, чужая БД=42501 |
| Основной Core без Notifications | `docker compose stop notifications`; curl /api/health и /api/events на 127.0.0.1:8080; `docker compose up --no-build --no-deps -d --wait --wait-timeout 60 notifications` | PASS, 200 ok/ready и 200 []; Notifications восстановлен healthy |
| Бизнес-запись без Notifications | На изолированном стеке stop notifications + HTTP POST event/два registration через frontend, затем SELECT Core own-role | PASS 201/202/202, confirmed=1/waitlisted=1, четыре pending outbox и prepared_at=NULL; основная БД не заполнялась тестовыми данными |
| Неизменность основной БД | Сравнение снимков строк Core и docker inspect container/mount до/после | PASS. Исходные три таблицы пусты и остались пустыми; отдельно доказано сохранение заполненных таблиц на постоянном тестовом volume |
| Неизменность кода/контрактов | SHA256 всех tracked backend/frontend против начала этапа, сравнение OpenAPI JSON; `git diff --check` | PASS |

Две БД основного приложения находятся в прежнем PostgreSQL. Core сохранил 24 колонки и старые миграции; Notifications добавил одну прикладную таблицу с 7 колонками и собственную Alembic-служебную таблицу. Наличие jobs/mime/status не означает реализацию HTTP handover, подготовки MIME, retries или SMTP. Принудительный downgrade рабочей БД, очистка данных, удаление volumes, git add/commit/push не выполнялись.

Итоговая контрольная отметка `2026-10-22T22:46:27+05:00`: Core api/db/frontend/Mailpit и Notifications healthy, инфраструктурный worker работает; db-bootstrap и обе миграции exit 0. Подтверждены 24 Core колонки и 7 Notifications колонок, конечные хеши основных строк и ID db container/volume совпадают с исходными. Временный проект проверки остановлен через down --remove-orphans **без --volumes**; все его named volumes сохранены. Исходный пользовательский .env и индекс Git не менялись. Ошибки health/collection исправлены, неустранённых падений выполненных проверок нет. 29 новых файлов пока untracked и не входят в обычный git diff --stat; их статистика выведена отдельно без git add. Этап завершён, relay/SMTP/UI не начаты; commit/push отсутствуют.
### Обычная роль Core в CI и регрессия повторного bootstrap — 2026-10-22

Все отметки ниже — Asia/Almaty (UTC+05:00), получены из реальных контрольных вызовов часов. Ранее незакоммиченные изменения инфраструктурного разделения сохранены.

- `2026-10-22T22:59:20+05:00`: начало анализа git status/diff, Compose, CI, bootstrap, миграций и тестов. Установлено: роль core_app_test уже создаётся, но штатный Core test всё ещё использует администратора events_test.
- `2026-10-22T23:04:52+05:00`: конфигурация переключена на core_app_test, добавлена проверка роли в Core fixture и отдельный bootstrap-test. Запущена сборка образов только нового проекта event-registration-bootstrap-check-20261022. Для db/mailpit использован временный override с удалением volume mounts из конфигурации (`volumes: !reset []`) и tmpfs, а не удалением существующих volumes. Собственные теги образов Core/Notifications исключают перезапись основных local-тегов.
- `2026-10-22T23:06:05+05:00`: Core 129/129 под core_app_test (11.32s), Notifications 25/25 (1.14s), upgrade/check и migration round-trip успешны. Найден и исправлен порядок импортов Ruff в изменённой фикстуре; тестовые образы пересобраны.
- `2026-10-22T23:08:02+05:00`: новый тест повторного bootstrap прошёл (1/1, 2.68s). Первый запуск выявил ошибку диагностического запроса самого теста: системный тип PostgreSQL relkind возвращался asyncpg как bytes; исправлено явным `relkind::text`. Проверки сохранены полностью. Strict Mypy нового теста проходит без подавления ошибок: для ошибки подключения проверяется точный SQLSTATE 42501 независимо от наличия обёртки SQLAlchemy.
- `2026-10-22T23:09:28+05:00`: повторный полный Core прогон на окончательном образе — 129/129, 10.43s, без skips. Все статические проверки, явные tsc/Vite, startup/health и независимость Core при остановленном Notifications прошли. Обе runtime-схемы изолированного CI-стека прошли alembic check.

Автоматический инфраструктурный тест создаёт событие с schedule_version=3, регистрации confirmed/waitlisted/cancelled с participation_no=2, билет/чекин/хеши, очередь с номером 7, три outbox-записи sent/pending/failed и три задания Notifications с payload, MIME и диагностикой попыток. Два повторных вызова настоящего bootstrap.sh сравнивают полные строки всех прикладных таблиц и alembic_version, владельцев БД/схем/таблиц/индексов, ACL, определения индексов/constraints. Проверяются READ COMMITTED, обычные роли без членства, собственные DML/DDL-права, отсутствие PUBLIC/чужих DB-привилегий и реальные отказы подключения 42501 в обоих направлениях до/после повторов. Очистка удаляет только UUID этого теста.

Для команд ниже `C` означает `/tmp/maddevs-bootstrap-ci-compose`, созданный для этого прогона shell-wrapper:

```sh
export COMPOSE_PROJECT_NAME=event-registration-bootstrap-check-20261022
export COMPOSE_ENV_FILES=.env.example COMPOSE_PROFILES=test
export POSTGRES_PORT=0 FRONTEND_PORT=0 MAILPIT_PORT=0
docker compose -f compose.yaml -f /tmp/maddevs-bootstrap-ci.override.yaml "$@"
```

Override только для этого прогона: db tmpfs=/var/lib/postgresql/data, mailpit tmpfs=/data, их volumes mounts сброшены; api/worker/migrate image=event-registration-bootstrap-check-core:local, notifications/notifications-migrate image=event-registration-bootstrap-check-notifications:local. Основные сервисы/БД и прежние volumes не использовались. Ни down --volumes, ни prune не выполнялись.

| Проверка | Реально выполненная команда | Итог |
|---|---|---|
| Compose config | `C config --quiet` (с теми же параметрами wrapper, до его создания) | PASS |
| Build | `C build api test notifications notifications-test bootstrap-test frontend`; после исправления импортов `C build test bootstrap-test` | PASS |
| Core Ruff/format/Mypy | `C run --rm --no-deps test sh -c 'ruff check . && ruff format --check . && mypy app tests/conftest.py'` | PASS; 41 отформатированный Python-файл, Mypy 26 файлов (приложение + изменённая фикстура) |
| Core Pytest/Alembic | `C run --rm test` | PASS; 129/129, окончательно 10.43s, 0 skipped; внутри upgrade head, весь Pytest (включая downgrade/base/upgrade и data-preserving migration), check |
| Notifications Ruff/format/Mypy | `C run --rm --no-deps notifications-test sh -c 'ruff check . && ruff format --check . && mypy notifications_app'` | PASS; 18 Python-файлов / 6 app-файлов Mypy |
| Notifications Pytest/Alembic | `C run --rm notifications-test` | PASS; 25/25, 1.14s, 0 skipped; upgrade, migration round-trip в Pytest, check |
| Bootstrap Ruff/format/Mypy | `C run --rm --no-deps bootstrap-test sh -c 'ruff check --config /app/pyproject.toml /bootstrap-tests && ruff format --check --config /app/pyproject.toml /bootstrap-tests && mypy --config-file /app/pyproject.toml /bootstrap-tests'` | PASS; 1 новый типизированный тестовый файл |
| Repeat bootstrap | `C run --rm bootstrap-test` | PASS; 1/1, 2.68s; реальные скрипты и PostgreSQL, два повтора после заполнения обеих БД |
| TypeScript/Vite | `docker build --target build -t event-registration-bootstrap-check-frontend-build:local frontend`; `docker run --rm --network none event-registration-bootstrap-check-frontend-build:local npm run build` | PASS; реально выполнены npm run typecheck (tsc --noEmit) и Vite, 17 modules, 1.53s |
| Runtime startup | `C up --no-build -d --wait --wait-timeout 120 db mailpit migrate api worker frontend notifications-migrate notifications` | PASS; оба migrate и bootstrap exit 0; API/Notifications/frontend/PostgreSQL/Mailpit healthy, worker Up |
| Runtime Alembic | `C exec -T api alembic check`; `C exec -T notifications alembic check` | PASS; no new upgrade operations |
| HTTP | `address=$(C port frontend 80)`; `curl --fail --silent --show-error --max-time 10 http://${address}/api/health` и `/api/events`; `C exec -T notifications python -c 'import json,urllib.request; response=urllib.request.urlopen("http://localhost:8000/health",timeout=5); body=json.load(response); assert response.status == 200 and body == {"status":"ok","database":"ready"},body; print("Notifications /health: HTTP 200",body)'` | PASS; Core health/events=200, Notifications health=200; health body status=ok/database=ready |
| Core independence | `C stop notifications`; те же curl health/events; `C up --no-build --no-deps -d --wait --wait-timeout 60 notifications` | PASS; Core health/events=200 во время остановки Notifications |
| Сохранность Core бизнес-кода и миграций/frontend | `git diff --exit-code -- backend/app backend/migrations frontend`; `git diff --check` | PASS; изменений этих tracked файлов нет |

Итого: 155 тестов (129 Core + 25 Notifications + 1 bootstrap), ни один не отключён. Изменены только тестовая инфраструктура/фикстура, workflow и документация; SQL bootstrap, бизнес-схема и прежние миграции не менялись. Реальный удалённый GitHub Actions не запускался: выполнены локальные эквиваленты всех его проверок. Коммиты и push не выполнялись.

Контроль завершения `2026-10-22T23:12:53+05:00`: docker inspect только db/test-db/mailpit нового проекта подтвердил tmpfs и 0 named volumes для каждого. `C ps --all` перед остановкой показал здоровые сервисы и успешно завершённые миграции. Выполнен `C down --remove-orphans`, exit 0: удалены только временные контейнеры/сеть, без --volumes. `git diff --stat` включает прежнюю незакоммиченную работу; новый infrastructure/tests/test_bootstrap.py остаётся untracked и в обычный diff --stat не входит. Основные файлы этого запроса: compose.yaml, .github/workflows/ci.yml, backend/tests/conftest.py, backend/Dockerfile, infrastructure/tests/test_bootstrap.py и документация.

### Асинхронный HTTP relay и надёжный inbox Notifications — 2026-10-22

Часовой пояс всех отметок — Asia/Almaty (UTC+05:00). Это реальные контрольные отметки, а не восстановленная задним числом история команд.

- `2026-10-22T23:24:43+05:00`: проверены git status/diff (рабочее дерево чистое), Compose, предыдущие миграции, Core outbox/worker, Notifications, тесты и документация. Core worker был только DB probe; приёма заданий не было.
- `2026-10-22T23:29:10+05:00`: добавлены v1 DTO, async HTTP relay, commit-before-ACK inbox и новая Core revision 0003_outbox_forwarded. Существующие бизнес-сервисы/API/outbox scheduling не менялись. httpx 0.28.1 перенесён из dev в runtime; lock-файлы пересобраны pip-compile, dev с constraint=requirements.lock, без изменения закреплённых версий.
- `2026-10-22T23:33:23+05:00`: исходники проходят Core strict Mypy; созданы PostgreSQL/API regression-тесты, схема JSON v1 и отдельный тестовый Compose-проект.
- `2026-10-22T23:36:12+05:00`: Notifications 48/48. Первый Core upgrade выявил повторное применение naming convention к имени CHECK; исправлена только новая 0003 через op.f. Старые миграции не редактировались, PostgreSQL откатил неуспешный DDL. Далее Core 149/149, затем добавлена отдельная проверка data-preserving 0003/downgrade guard.
- `2026-10-22T23:43:59+05:00`: пройдены реальные HTTP-проверки отказа Notifications и восстановления после SIGKILL relay; concurrent duplicate=202, conflict=409, no token=401. Реальный TCP proxy разорвал ответ после Notifications commit: Core остался pending, после рестарта получателя/relay повтор завершился forwarded. Введён общий asyncio deadline сверх phase timeouts httpx.
- `2026-10-22T23:48:01+05:00`: Core 152/152, включая deadline и crash после prepare до HTTP; статические проверки Core/Notifications проходят. Подготовлены контракт/правила исторических снимков и обновлены README/архитектура. Затем ISO-валидация v1 усилена запретом числовых дат, чтобы соответствовать JSON Schema.
- `2026-10-22T23:53:58+05:00`: окончательный Core 152/152 (28.09s), Ruff/format/Mypy Core/Notifications/infrastructure успешны; повторён реальный smoke на окончательных образах.
- `2026-10-22T23:55:54+05:00`: Notifications 52/52 (1.30s), infrastructure 3/3 (3.88s), без skips. Проверены реальные PostgreSQL: Core 24 колонки, 4 forwarded + 4 будущих reminder pending, sent=0; Notifications 7 колонок, ровно 4 unique jobs, все pending/mime=NULL/attempts=0. Обе runtime-схемы прошли alembic check.

Временные статические ошибки также исправлены: Ruff импортов/форматирование; Mypy внешнего source namespace Notifications устранён явным MYPYPATH только для инфраструктурного тестового контейнера, без ignore. Дополнительных платных сервисов, Redis/Kafka/Celery, leases, SMTP или новых экранов нет.

#### Изменённые компоненты

| Файл / основные функции | Что изменено и зачем |
|---|---|
| backend/app/notifications/relay.py — Relay.prepare/run_once/finish/backoff | Один async relay, event-lock и fresh reads; freeze до HTTP; отсутствие DB-транзакции во время сети; устойчивые retry/limit/backoff; валидация ACK; forwarded вместо sent |
| backend/app/notifications/contract.py; notifications/notifications_app/contract.py | Независимые DTO одного JSON v1: ID, тип, версии/поколения, ISO UTC, ограничения и безопасные поля; артефакт docs/notification-contract-v1.schema.json фиксируется контрактным тестом |
| backend/app/worker.py — run | Реальный последовательный relay с AsyncClient, завершением по сигналу и безопасной диагностикой; SMTP не вызывается |
| backend/app/db/models.py; backend/migrations/versions/0003_outbox_forwarded.py | Состояние forwarded и два CHECK, без новых колонок/переписывания строк; downgrade запрещён, если потеряет accepted-состояние |
| notifications/notifications_app/inbox.py — accept_message | INSERT ON CONFLICT DO NOTHING + отдельный READ COMMITTED SELECT; сравнение JSON; commit до возврата; неизменность уже принятого job |
| notifications/notifications_app/api.py; main.py | Защищённый POST /internal/v1/notifications, 202/409/401, 422 без исходного payload/секретов; собственная DB/session factory |
| backend/app/config.py; notifications/notifications_app/config.py; .env.example; compose.yaml | Общий внутренний секрет только relay/Notifications; timeout/retry settings, тестовые mount/path; worker больше не зависит от Mailpit; API не зависит от Notifications |
| backend/pyproject.toml; requirements*.lock | httpx runtime с прежней закреплённой версией; одинаковая сортировка импортов app в разных test-контекстах |
| backend/tests/integration/test_relay.py; test_relay_migration.py | 22 сценария relay + миграция/запрет потери forwarded; все прежние Core tests сохранены |
| notifications/tests/integration/test_inbox.py; tests/unit/test_config.py; tests/conftest.py | Commit-before-ACK, конкурентные дубликаты/конфликты, auth/валидация, loss-after-commit и restart, исторические версии; секрет для fixtures |
| infrastructure/tests/test_notification_contract.py; test_relay_delivery.py; test_bootstrap.py | Контракт обеих DTO, сквозной потерянный ACK с двумя БД и новыми компонентами, прежний повторный bootstrap с новыми auth-настройками миграций |
| infrastructure/checks/relay_smoke.py; .github/workflows/ci.yml | Реальные HTTP/TCP отказы и рестарты в CI, без Docker socket в сервисах; отдельные lint/format/strict Mypy сценария |
| README.md; ARCHITECTURE.md; DECISIONS.md; docs/NOTIFICATION_PROTOCOL.md; docs/NOTIFICATIONS_INFRASTRUCTURE.md; docs/WORKER_EVOLUTION.md | Фактическая готовность, контракт v1, исторические снимки, failed/manual retry, различие HTTP/SMTP, будущий конкурентный worker |

#### Выполненные проверки

Ниже `C` означает реальный wrapper `/tmp/maddevs-relay-compose`:

```sh
export COMPOSE_PROJECT_NAME=event-registration-relay-check-20261022
export COMPOSE_ENV_FILES=.env.example COMPOSE_PROFILES=test
export POSTGRES_PORT=0 FRONTEND_PORT=0 MAILPIT_PORT=0
docker compose -f compose.yaml -f /tmp/maddevs-relay-ci.override.yaml "$@"
```

Override: db и mailpit volumes mounts сброшены `!reset []`, вместо них tmpfs (/var/lib/postgresql/data и /data). Собственные теги Core/Notifications — event-registration-relay-check-core:local / event-registration-relay-check-notifications:local. Для ускорения реального smoke только в локальном override worker_poll_interval=0.2, retry cap=10/max_attempts=20; обычные defaults 5/60/8 зафиксированы в Settings. test-db из основного Compose уже использует tmpfs. Основная установка не использовалась.

| Проверка | Реальная команда | Фактический итог |
|---|---|---|
| Compose | `C config --quiet` | PASS |
| Build | `C build api test notifications notifications-test bootstrap-test frontend`; финально повторены изменённые backend/test images | PASS |
| Core Ruff/format/Mypy | `C run --rm --no-deps test sh -c 'ruff check . && ruff format --check . && mypy app tests/conftest.py'` | PASS; 46 Python-файлов / 28 Mypy source files |
| Все Core tests + migrations | `C run --rm test` | PASS; 152/152, 28.09s; upgrade head, полный Pytest, check; внутри round-trip base/0001/0002/head и guarded downgrade 0003 |
| Notifications Ruff/format/Mypy | `C run --rm --no-deps notifications-test sh -c 'ruff check . && ruff format --check . && mypy notifications_app'` | PASS; 22 Python-файла / 9 Mypy source files |
| Все Notifications tests + migrations | `C run --rm notifications-test` | PASS; 52/52, 1.30s; upgrade, round-trip и check |
| Infrastructure Ruff/format/Mypy | `C run --rm --no-deps bootstrap-test sh -c 'ruff check --config /app/pyproject.toml /bootstrap-tests /checks && ruff format --check --config /app/pyproject.toml /bootstrap-tests /checks && mypy --config-file /app/pyproject.toml /bootstrap-tests /checks'` | PASS; все 4 Python-файла |
| Bootstrap/contract/two-DB delivery | `C run --rm bootstrap-test` | PASS; 3/3, 3.88s; повторный bootstrap и существующие данные/права, общий контракт, loss-after-commit на двух БД |
| Полный runtime | `C up --no-build -d --wait --wait-timeout 120 db mailpit migrate api worker frontend notifications-migrate notifications`; после финальных rebuild `C up --no-build --no-deps -d --wait --wait-timeout 60 api worker notifications` | PASS |
| Runtime migrations | `C exec -T api alembic check`; `C exec -T notifications alembic check` | PASS; no new upgrade operations |
| Real HTTP/TCP smoke | `C run --rm --no-deps -T -e RELAY_SMOKE_PROJECT=event-registration-relay-check-20261022 worker python - PHASE < infrastructure/checks/relay_smoke.py` с фазами create/outage/recover/lost-response/recover и командами stop/kill/up/restart, как в workflow | PASS; повторён полностью после финальной сборки; Core 201/202 при outage, durable retry/SIGKILL, concurrent 202, conflict409, unauthorized401, TCP loss после commit и restart обоих процессов |
| Собственные DB-снимки runtime | `C exec -T api python -` и `C exec -T notifications python -` с SQL SELECT information_schema.columns / статусов outbox / job status,mime,attempts | PASS; Core 24 колонки и 0 sent; Notifications 7 колонок/4 unique jobs, SMTP не начат |
| HTTP health | `address=$(C port frontend 80)`; `curl --fail --silent --show-error --retry 5 --retry-connrefused --retry-delay 2 --max-time 10 http://${address}/api/health`; `C exec -T notifications python -c 'import json,urllib.request; response=urllib.request.urlopen("http://localhost:8000/health",timeout=5); body=json.load(response); assert response.status==200 and body=={"status":"ok","database":"ready"}; print("Notifications: HTTP 200",body)'` | PASS; оба HTTP 200, status=ok/database=ready |
| Сохранность бизнес-кода/старых миграций/frontend | `git diff --exit-code -- backend/app/services backend/app/api backend/app/notifications/outbox.py backend/migrations/versions/0001_initial_schema.py backend/migrations/versions/0002_simplify_schema.py notifications/migrations frontend`; `git diff --check` | PASS; нет изменений этих файлов/ошибок diff |

Итого **207 Pytest-тестов, 0 skipped** (152 Core + 52 Notifications + 3 infrastructure) и отдельный реальный HTTP/TCP smoke. Новые состояния/колонки не выдаются за SMTP-доставку: Core forwarded означает только durable acceptance, Notifications пока ничего не отправляет. После 8 default попыток failed требует явного retry с прежним ID/JSON; задания не удаляются. Prepared снимок может исторически устареть, поскольку после неизвестного HTTP-исхода его нельзя переписать. Нет распределённого singleton/leases и SMTP exactly-once.

Удалённый GitHub Actions не запускался, push/коммит не выполнялись. Выполнены локальные проверки, включая новый сетевой CI-шаг. Подробный протокол/правила обновления версии и безопасного retry — docs/NOTIFICATION_PROTOCOL.md.

Контроль завершения `2026-10-22T23:58:48+05:00`: оба health вернули HTTP 200, финальный git diff --check успешен. docker inspect подтвердил только tmpfs/0 named volumes у db/test-db/mailpit проекта event-registration-relay-check-20261022. Выполнен `C down --remove-orphans`, exit 0, без --volumes: временные контейнеры и сеть удалены. Основная БД/volumes не использовались. Git diff --stat показан; он не включает 14 новых untracked файлов. Никаких commit/push не выполнялось.


### Head-of-line blocking Core relay — 2026-10-23

Все временные отметки ниже — реальные контрольные чтения часов, Asia/Almaty (UTC+05:00).

- `2026-10-23T08:38:01+05:00`: проверены git status/diff и актуальные relay/worker/тесты. В дереве уже были 20 изменённых tracked и 14 untracked путей предыдущего этапа HTTP relay; они сохранены, история не переписывалась.
- `2026-10-23T08:44:13+05:00`: добавлена ограниченная выборка голов разных событий, UUID-курсор/cutoff и NOWAIT; 55P03 обрабатывается после rollback отдельной prepare-транзакции. Другие DB-ошибки распространяются. Схема/API/FIFO не менялись.
- `2026-10-23T08:50:07+05:00`: начата сборка отдельного Compose-проекта event-registration-relay-check-hol-20261023: свои image tags, db/test-db/mailpit в tmpfs, случайные порты, без основных volumes.
- `2026-10-23T08:54:32+05:00`: первоначальный полный Core 160/160; запущены остальные наборы и отрицательный контроль старого алгоритма.
- `2026-10-23T08:57:46+05:00`: Notifications 52/52, infrastructure 3/3; 8 новых PostgreSQL регрессий проходят. Старая выборка, временно подставленная только read-only mount тестового контейнера, ожидаемо провалила регрессию по TimeoutError (1.68s); рабочий исходник не заменялся. Затем повторены все 8 тестов с новой реализацией: PASS.
- `2026-10-23T09:00:57+05:00`: на реальных сервисах при PostgreSQL lock A уведомление B forwarded; после unlock A также forwarded. Затем запущен полный прежний сетевой CI smoke отказа/рестартов/потерянного ACK.
- `2026-10-23T09:02:39+05:00`: реальный HTTP/TCP smoke завершился успешно. Расширенный strict Mypy нового тестового модуля обнаружил два nullable-обращения в импортируемом прежнем test_relay.py; добавлен assert row is not None, без suppressions/отключения проверок.
- `2026-10-23T09:04:36+05:00`: окончательные Core 160/160 (16.52s), Core Ruff/format/strict Mypy успешны; runtime Alembic check обеих БД без новых операций.
- `2026-10-23T09:06:53+05:00`: проверены окончательные diff/status, настройки Compose и документация; результаты внесены в журнал решений.

#### Изменения этого исправления

| Файл / основные функции | Изменение |
|---|---|
| backend/app/notifications/relay.py — Relay._candidates/prepare/run_once/_deliver | DISTINCT ON event heads, конечный обход с cutoff/курсором, ограниченная страница; NOWAIT и безопасный skip 55P03 после rollback; прежний HTTP-код выделен в _deliver |
| backend/app/config.py — Settings; .env.example; compose.yaml | RELAY_CANDIDATE_LIMIT=20 с ограничением 1–100 и передачей в worker |
| backend/tests/integration/test_relay_blocking.py | 8 новых сценариев: pending/prepared, несколько писем события, несколько занятых страниц, настоящий lock_timeout/rollback, другие ошибки БД, новые сообщения/idle/restart |
| backend/tests/integration/test_relay.py | Явная проверка существования DB-строки перед доступом к полям в прежнем тесте |
| .github/workflows/ci.yml | Новый регрессионный модуль добавлен к strict Mypy Core |
| README.md; ARCHITECTURE.md; docs/NOTIFICATION_PROTOCOL.md; DECISIONS.md; DEVELOPMENT_LOG.md | Реальная схема обхода, пределы справедливости/задержки, настройки и результаты |

#### Фактически выполненные проверки

Здесь C = `/tmp/maddevs-hol-compose`, wrapper для `docker compose -f compose.yaml -f /tmp/maddevs-hol-ci.override.yaml` с COMPOSE_PROJECT_NAME=event-registration-relay-check-hol-20261023, COMPOSE_ENV_FILES=.env.example, COMPOSE_PROFILES=test, POSTGRES_PORT/FRONTEND_PORT/MAILPIT_PORT=0. Override удаляет volume mounts db/mailpit через !reset [], использует tmpfs и отдельные image tags event-registration-hol-check-core:local / event-registration-hol-check-notifications:local. Только в тестовом worker poll=0.2, backoff cap=10/max attempts=20 для сетевого smoke.

| Проверка | Реальная команда | Результат |
|---|---|---|
| Compose | `C config --quiet` | PASS, в том числе после окончательных настроек |
| Сборка | `C build api test notifications notifications-test bootstrap-test frontend`; затем `C build test` после финальных тестовых правок | PASS |
| Core Ruff/format/Mypy | `C run --rm --no-deps test sh -c 'ruff check . && ruff format --check . && mypy app tests/conftest.py tests/integration/test_relay_blocking.py'` | PASS, 47 formatted files / 29 Mypy source files |
| Полный Core Pytest/Alembic | `C run --rm test` | PASS, 160 passed, 16.52s; upgrade/check и миграционные round-trip/downgrade guard |
| Notifications Ruff/format/Mypy | `C run --rm --no-deps notifications-test sh -c 'ruff check . && ruff format --check . && mypy notifications_app'` | PASS, 22 formatted files / 9 Mypy source files |
| Полный Notifications Pytest/Alembic | `C run --rm notifications-test` | PASS, 52 passed, 3.81s; upgrade/check/round-trip |
| Infrastructure Ruff/format/Mypy | `C run --rm --no-deps bootstrap-test sh -c 'ruff check --config /app/pyproject.toml /bootstrap-tests /checks && ruff format --check --config /app/pyproject.toml /bootstrap-tests /checks && mypy --config-file /app/pyproject.toml /bootstrap-tests /checks'` | PASS, 4 source files |
| Bootstrap/контракт/две БД | `C run --rm bootstrap-test` | PASS, 3 passed, 5.75s, повторный bootstrap/владельцы/права/изоляция/сохранность данных |
| Только новые регрессии | `C run --rm --no-deps test pytest -q tests/integration/test_relay_blocking.py` | PASS, 8 passed, 0.90s; затем входят в окончательные 160 |
| Frontend TypeScript/Vite | `docker build --target build -t event-registration-hol-check-frontend-build:local frontend`; `docker run --rm --network none event-registration-hol-check-frontend-build:local npm run build` | PASS, tsc --noEmit и Vite (17 modules) |
| Runtime startup | `C up --no-build -d --wait --wait-timeout 120 db mailpit migrate api worker frontend notifications-migrate notifications` | PASS, migrations/bootstrap exit 0; все healthchecks успешны |
| Runtime Alembic | `C exec -T api alembic check`; `C exec -T notifications alembic check` | PASS, no new upgrade operations |
| Реальный HOL HTTP | `C stop worker`; `C run --rm --no-deps -T worker python - < /tmp/maddevs-hol-real.py`; `C up --no-deps -d worker` | PASS, занятое A unchanged/pending, независимое B forwarded; после unlock A forwarded с attempts=1 |
| Реальный CI HTTP/TCP smoke | `C run --rm --no-deps -T -e RELAY_SMOKE_PROJECT=event-registration-relay-check-hol-20261023 worker python - PHASE < infrastructure/checks/relay_smoke.py` | PASS, фазы create/outage/recover/lost-response/recover: остановка Notifications, SIGKILL relay, рестарт, настоящий разрыв ACK после commit, concurrent duplicate202/conflict409/auth401 |
| Health и независимость Core | curl `/api/health` через `C port frontend 80`; HTTP `/health` внутри Notifications; при остановленном Notifications также Core health/events | PASS, HTTP 200; Core create/register=201/202 при outage |
| Сохранность бизнес-кода/миграций/frontend | `git diff --exit-code -- backend/app/services backend/app/api backend/app/notifications/outbox.py backend/migrations/versions/0001_initial_schema.py backend/migrations/versions/0002_simplify_schema.py notifications/migrations frontend`; `git diff --check` | PASS |

Итого **215 Pytest-тестов, 0 skipped** (160 Core + 52 Notifications + 3 infrastructure), плюс реальные сетевые проверки. Отрицательный контроль старого алгоритма — отдельный ожидаемый FAIL; окончательная реализация проходит весь набор. Тесты не отключались. HTTP idempotency/prepared payload/версии и поведение при рестарте проверены прежними и новыми тестами. Новых миграций/колонок, изменений контрактов/участников FIFO нет.

Ограничение: сохраняется один relay. Глобальный приоритет старейшего письма между разными событиями заменён UUID round-robin; внутри события выбирается прежняя голова среди ready по available_at/id. Полностью занятая страница даёт паузу poll_interval перед следующей, поэтому большой занятый набор увеличивает задержку, но курсор не возвращает постоянно только первый префикс. Новые поступления за cutoff ждут следующего обхода. SMTP не реализован этим исправлением. Удалённый GitHub Actions не запускался; выполнены его локальные проверки. Commit/push не выполнялись.

Контроль завершения `2026-10-23T09:08:44+05:00`: docker inspect подтвердил tmpfs и отсутствие named volume mounts у db/test-db/mailpit только тестового проекта. `C down --remove-orphans` завершился exit 0 без --volumes; удалены временные контейнеры/сеть. Основная БД и volumes не использовались. `git diff --check` успешен; `git diff --stat` показан (включает прежнюю незакоммиченную работу и не учитывает 15 untracked файлов). Новых commit/push нет.


### Повторная независимая проверка исправления — 2026-10-23

- `2026-10-23T09:11:41+05:00`: по просьбе пользователя повторно проверены git status/diff, актуальные relay/worker, PostgreSQL-настройки, регрессионные тесты и CI. Существующее dirty tree сохранено. Прикладной код не изменялся.
- `2026-10-23T09:12:59+05:00`: заново собраны api/test/notifications/notifications-test/bootstrap-test/frontend через прежний изолированный wrapper C=/tmp/maddevs-hol-compose. Полный `C run --rm test`: **160 passed (13.58s)**, Alembic check без операций; проходят миграционные round-trip и downgrade guards, конкурентные API-процессы, FIFO, cancel/resume/checkin и все relay tests. Core Ruff/format/Mypy: PASS (47/29 файлов).
- `2026-10-23T09:13:41+05:00`: `C run --rm notifications-test`: **52 passed (1.18s)**, Alembic check успешен; `C run --rm bootstrap-test`: **3 passed (3.99s)**. Notifications Ruff/format/Mypy PASS (22/9), infrastructure PASS (4 файла). Статические команды совпадают с таблицей предыдущего исправления; Core Mypy включает tests/integration/test_relay_blocking.py. `docker run --rm --network none event-registration-hol-check-frontend-build:local npm run build`: tsc/Vite PASS. Полный Compose startup с --wait успешен.
- `2026-10-23T09:13:41+05:00`: повторён реальный HOL через `C stop worker`, `C run --rm --no-deps -T worker python - < /tmp/maddevs-hol-real.py`, затем запуск worker. Под lock A остаётся pending/attempts=0/prepared=NULL, B forwarded; после unlock A forwarded/attempts=1.
- `2026-10-23T09:14:23+05:00`: весь реальный HTTP/TCP smoke CI снова PASS: create/outage/recover/lost-response/recover, остановка Notifications, Core health/events=200 и create/register=201/202 при outage, SIGKILL relay, рестарты, loss-after-commit, duplicate202/conflict409/auth401. Выполнен прежней командой worker python - PHASE с RELAY_SMOKE_PROJECT=event-registration-relay-check-hol-20261023 и infrastructure/checks/relay_smoke.py.
- `2026-10-23T09:15:19+05:00`: `C run --rm --no-deps test sh -c 'for pass in 1 2 3 4 5; do pytest -q tests/integration/test_relay_blocking.py tests/integration/test_api_processes.py || exit; done'`: **5 × 10 passed**, времена 4.15/4.21/4.13/4.43/3.62s. Это повторение уже включённых в 215 тестов, не дополнительные уникальные тесты. Runtime `C exec -T api alembic check` и Notifications аналог: PASS. Core outbox SELECT: 4 forwarded + 4 будущих pending, нет failed/sent. HTTP health обоих сервисов и frontend proxy=200; HTML/JS/CSS=200; Mailpit=200/0 писем. Все 7 тестовых контейнеров running, все имеющиеся healthchecks healthy, worker logs без Relay iteration failed. docker inspect подтвердил tmpfs/отсутствие named mounts у db/test-db/mailpit.
- `2026-10-23T09:15:38+05:00`: собственный SELECT Notifications подтвердил ровно 4 уникальных задания, все pending/mime=NULL/attempts=0. В первом одноразовом проверочном скрипте был ошибочный импорт notifications_app.db.models; после исправления импорта на notifications_app.models/db скрипт прошёл. Это ошибка проверочного скрипта, исходники сервиса не менялись.

Вывод проверки: исходный HOL-дефект не воспроизводится; новых сбоев в проверенных сценариях не найдено. **215/215 уникальных Pytest-тестов, 0 skips**, дополнительно 50 повторных выполнений конкурентных тестов. Текущий алгоритм ограничивает попытки prepare за проход, выбирает одну ready-голову на событие по available_at/id, делает полный rollback перед skip55P03, сохраняет курсор до следующего poll и возвращается к занятым событиям. Prepared JSON/ID, API и бизнес-правила не менялись. Глобальная сортировка между независимыми событиями по-прежнему заменена UUID round-robin; строгая доставка всех писем по порядку после backoff не обещается. Проект ещё не завершён целиком: SMTP/MIME sender, SSE и полноценные пользовательские экраны отсутствуют согласно текущему этапу. Удалённый GitHub Actions не запускался. Из файлов проекта в этой проверке изменён только этот журнал; commit/push не выполнялись.

Завершение повторной проверки `2026-10-23T09:16:26+05:00`: `C down --remove-orphans` exit 0, без --volumes; временные контейнеры/сеть удалены. Основная установка не затронута. git diff --check успешен, git diff --stat показан.
