# Канонический email: Core, Notifications и существующие данные

Политика зафиксирована пользователем: email-validator 2.3.0, `ascii_email`, `check_deliverability=False`, `test_environment=True`, `allow_smtputf8=False`. Никаких DNS/API-запросов. `.test` разрешён для локального Mailpit. На входе убираются внешние пробелы и применяется прежний `.lower()`; после проверки возвращается lowercase ASCII email. `.casefold()` не применяется: оно могло бы превратить ß в ss. Точки и `+суффиксы` не удаляются; Unicode local-part, display names, несколько получателей и управляющие CR/LF/U+0000 отклоняются.

| Вход | Канонический адрес |
|---|---|
| `USER@faß.de` | `user@xn--fa-hia.de` |
| `user@xn--fa-hia.de` | `user@xn--fa-hia.de` |
| `user@fass.de` | `user@fass.de` — другой домен |
| `Some.One+Tag@EXAMPLE.test` | `some.one+tag@example.test` |
| `user@пример.рф` | `user@xn--e1afmkfd.xn--p1ai` |

Причина дефекта: Core проверял email-validator, но игнорировал возвращаемый ASCII-адрес; Notifications использовал Python `.encode('idna')` с IDNA2003. Теперь оба сервиса используют одинаковую небольшую функцию в собственном модуле email_addresses.py. Общего runtime-пакета/зависимости от другого сервиса нет; согласованность проверяет кросс-сервисный тест. [Документация email-validator](https://github.com/JoshData/python-email-validator#normalization) описывает нормализацию/ASCII-представление и запрет SMTPUTF8.

## Новые регистрации и уведомления

Core нормализует **до поиска существующей регистрации** и до бизнес-транзакции, ORM использует ту же функцию для вставки/изменения email. READ COMMITTED + event FOR UPDATE + UNIQUE(event_id,email) сохранены. Unicode/Punycode одного домена — одна идентичность, в том числе для двух отдельных API-процессов. Другой event по-прежнему допускает тот же адрес. Повтор email не выдаёт секрет, не создаёт новое участие, билет или outbox.

Новые Registration.email и Core payload.recipient содержат ASCII. Notifications сохраняет принятый JSON как прежде: не канонизирует/не переписывает DTO при HTTP-приёме, иначе retry ранее принятого v1 мог бы конфликтовать. MIME renderer и проверка SMTP envelope используют каноническое представление через email-validator. Новый To и фактический RCPT TO содержат один ASCII-адрес; SMTPUTF8 не включается.

## Уже сохранённые payload и MIME

Миграция меняет только Registration.email. Ни Core email_outbox payload/prepared_at, ни Notifications payload/MIME/status не переписываются. Прежние бизнес-операции могут актуализировать ещё не замороженный Core контекст как раньше; фиксация prepared payload по-прежнему делает его неизменным.

При **каждой** попытке sender загружает сохранённые MIME-байты и сравнивает канонического SMTP-получателя из To с каноническим адресом из payload. Старый payload с `user@faß.de` допустим и не меняется: при отсутствии MIME renderer создаст правильный To; уже сохранённый правильный ASCII MIME повторяется без изменения From/To/Date/Message-ID/тела. Регистронезависимые ASCII-варианты допустимы; оригинальные заголовки/байты, включая регистр Message-ID, сохраняются.

MIME `To: user@fass.de` при payload `user@faß.de` **небезопасен**: `fass.de != xn--fa-hia.de`. Sender переводит pending job в failed с постоянным безопасным last_error, не вызывает SMTP, не меняет payload/MIME/attempts/срок и переходит к следующему заданию. Автоматического исправления получателя или нового Message-ID нет. Подготовленные не-ASCII From/To также отклоняются, чтобы не ремонтировать frozen envelope и не требовать SMTPUTF8. Ручной retry такого повреждённого job отклоняется проверкой load_prepared; повтор HTTP не оживляет failed. Уже sent-письмо не отзывается и не отправляется повторно; ранее совершённую неверную внешнюю доставку исправление отменить не может.

Обе прежние границы неизменности и риск SMTP дубля после accept сохранены: [SMTP_DELIVERY.md](SMTP_DELIVERY.md).

## Read-only preflight и миграция 0004

Первичная проверка существующей установки выполнена отдельной READ ONLY транзакцией под ролью Core: на момент проверки **0 регистраций, 0 коллизий**. Email/токены не выводились. Основная БД не мигрировалась.

Для повторяемой проверки предоставлен CLI (новый образ, прежняя БД; без запуска миграции/API):

```sh
docker compose build api notifications
docker compose run --rm --no-deps api python -m app.email_audit
```

Он выполняет READ ONLY SELECT и выводит только total/changed, invalid_ids и collision_groups с UUID, без адресов. Exit 1 означает необходимость ручного решения. Это снимок, а не гарантия отсутствия последующих записей; миграция повторяет проверку под блокировкой.

Новая `0004_canonical_email`:

1. Блокирует events, затем registrations в ACCESS EXCLUSIVE до конца транзакции. Порядок соответствует бизнес-операциям, конкурентные writers не меняют проверяемый набор.
2. Вычисляет канонический адрес для всех регистраций, включая cancelled, и ищет коллизии `(event_id, canonical_email)`/невалидные старые адреса **до первого UPDATE**. Политика в revision зафиксирована отдельно от будущих app helpers, зависимости закреплены lock-файлом.
3. При проблеме останавливает весь upgrade: предыдущая revision/строки/ограничения сохраняются. В диагностике только UUID. Не объединяет/не удаляет записи, не выбирает «победителя». Нужно решить проблему явно вне миграции; не запускать автоматический merge/delete.
4. При успешной проверке обновляет только email, сохраняя ID/FIFO/статусы/билеты/токены/версии и outbox. Усиливает прежний CHECK требованием ASCII (`octet_length = char_length` в UTF8); UNIQUE остаётся прежним. Число таблиц/колонок Core остаётся 3/24. CHECK не заменяет email-validator и сам не умеет преобразовывать IDNA.
5. Downgrade до 0003 только снимает ASCII-часть CHECK. Он сохраняет канонические строки и не восстанавливает Unicode-написание: без дополнительной истории этого нельзя сделать. Для точного восстановления прежних адресных строк требуется резервная копия, а не угадывание по Punycode.

Старые revision-файлы не редактируются. Alembic env получил hide_parameters=True, чтобы даже неожиданная SQL-ошибка не показывала адреса в bind-параметрах. Рекомендуемый порядок обновления после резервной копии: собрать образы; выполнить read-only audit; остановить старые api/worker, чтобы они не записали Unicode после upgrade; выполнить миграцию; запустить новые сервисы. Пример после успешного audit:

```sh
docker compose stop api worker
docker compose run --rm migrate
docker compose up --no-build -d --wait api worker notifications notifications-sender frontend
```

При конфликте миграция останавливается; не удалять volume и не объединять участников для обхода ошибки. Основная установка в ходе этой задачи не обновлялась; эти команды — инструкция оператору.

## Проверки

- ASCII/Unicode/Punycode/ß, запрет SMTPUTF8, сохранение точек/суффиксов, повтор и две конкурирующие API-регистрации.
- PostgreSQL: корректное обновление legacy, сохранность остальных колонок/outbox, read-only audit, отказ целиком при коллизии (включая cancelled)/невалидном адресе, upgrade/downgrade/upgrade/check и 24 колонки.
- MIME: безопасный legacy JSON без изменения, корректный frozen Punycode, старый ошибочный fass → failed/нет SMTP/следующий sent; регистр ASCII и все frozen bytes сохраняются.
- Реальный SMTP: перехват RCPT TO показывает Punycode без SMTPUTF8; полный Core → HTTP inbox → MIME → SMTP → test-mailpit и отдельный smoke запущенных сервисов.
