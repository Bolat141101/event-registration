import { test, expect } from '@playwright/test';
import type { APIRequestContext, BrowserContext, Page } from '@playwright/test';
import { randomUUID } from 'node:crypto';
import { mkdir } from 'node:fs/promises';
import { dateInput } from '../src/dates';

const base = process.env.E2E_BASE_URL;
const mailpit = process.env.E2E_MAILPIT_URL;
const key = process.env.E2E_ORGANIZER_KEY;
if (
  !base ||
  !mailpit ||
  !key ||
  !process.env.E2E_ISOLATED_PROJECT?.startsWith('event-registration-relay-check-ui-')
)
  throw new Error('E2E requires explicit isolated UI Compose project, URLs and test organizer key');
const auth = { Authorization: `Bearer ${key}` };
const contexts: BrowserContext[] = [];
test.afterEach(async () => {
  await Promise.all(contexts.splice(0).map((context) => context.close()));
});
const screenshots = process.env.E2E_SCREENSHOT_DIR ?? '/tmp/maddevs-ui-visual';
async function login(page: Page, path = '/organizer') {
  await page.goto(path);
  await page.getByLabel('Ключ организатора').fill(key!);
  await page.getByRole('button', { name: 'Открыть рабочее пространство' }).click();
  await expect(page.getByRole('button', { name: 'Выйти', exact: true })).toBeVisible();
}
async function create(request: APIRequestContext, description: string, capacity = 1) {
  const response = await request.post(base + '/api/events', {
    headers: auth,
    data: { description, capacity, starts_at: new Date(Date.now() + 2 * 86400000).toISOString() },
  });
  expect(response.status()).toBe(201);
  return (await response.json()).id as string;
}
async function register(page: Page, id: string, email: string) {
  await page.goto(`/events/${id}`);
  await page.getByLabel('Email', { exact: true }).fill(email);
  await page.getByRole('button', { name: /Отправить заявку|Встать в лист ожидания/ }).click();
  await expect(page.getByText('Запрос принят.', { exact: false })).toBeVisible();
}
interface Mail {
  Text: string;
  Subject: string;
  To: { Address: string }[];
}
async function letters(
  request: APIRequestContext,
  description: string,
  address: string,
  subject?: string
): Promise<Mail[]> {
  const listing = (await (await request.get(mailpit + '/api/v1/messages')).json()) as {
    messages: { ID: string; To: { Address: string }[] }[];
  };
  const found: Mail[] = [];
  for (const item of listing.messages.filter((item) =>
    item.To.some((to) => to.Address === address)
  )) {
    const mail = (await (await request.get(mailpit + '/api/v1/message/' + item.ID)).json()) as Mail;
    if (mail.Text.includes(description) && (!subject || mail.Subject.includes(subject)))
      found.push(mail);
  }
  return found;
}
async function privateLink(request: APIRequestContext, description: string, address: string) {
  let token = '';
  await expect
    .poll(async () => {
      const href = (await letters(request, description, address))
        .map((mail) => /https?:\/\/[^\s]+\/registration#token=[\w-]+/.exec(mail.Text)?.[0])
        .find(Boolean);
      if (href) {
        const link = new URL(href);
        // Check the REAL emailed origin, not just a token transplanted to our test URL.
        expect(link.origin).toBe(base);
        token = new URLSearchParams(link.hash.slice(1)).get('token') ?? '';
      }
      return Boolean(token);
    })
    .toBe(true);
  return token;
}
async function openPrivate(page: Page, token: string) {
  // No trace/video is recorded. Avoid reporting a secret-bearing navigation URL on failure.
  try {
    await page.goto('/registration#token=' + encodeURIComponent(token));
  } catch {
    throw new Error('Private page navigation failed');
  }
  await expect
    .poll(() => page.evaluate(() => location.pathname === '/registration' && location.hash === ''))
    .toBe(true);
  expect(await page.evaluate(() => [localStorage.length, sessionStorage.length])).toEqual([0, 0]);
}
async function picture(page: Page, name: string, width: number) {
  await page.setViewportSize({ width, height: 900 });
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    .toBe(true);
  await mkdir(screenshots, { recursive: true });
  await expect(page.locator('header')).toHaveCount(1);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: `${screenshots}/${name}.png`,
    fullPage: true,
    animations: 'disabled',
  });
}

test('two independent participants: last seat, FIFO, email, resume, reschedule, checkin once and live', async ({
  browser,
  page,
  request,
}) => {
  await login(page);
  const label = 'Открытая встреча о надёжных сервисах · ' + randomUUID().slice(0, 8);
  await page.getByLabel('Описание', { exact: true }).fill(label);
  await page
    .getByLabel('Дата и время · Алматы (UTC+5)', { exact: true })
    .fill(dateInput(new Date(Date.now() + 2 * 86400000).toISOString()));
  await page.getByLabel('Лимит мест').fill('1');
  await page.getByRole('button', { name: 'Создать мероприятие' }).click();
  await expect(page.getByRole('link', { name: 'Открыть чекин' })).toBeVisible();
  const id = /\/organizer\/events\/([^/]+)/.exec(page.url())![1];
  const a = await browser.newContext({ baseURL: base, viewport: { width: 1440, height: 900 } });
  const b = await browser.newContext({ baseURL: base, viewport: { width: 390, height: 844 } });
  contexts.push(a, b);
  const first = await a.newPage();
  const second = await b.newPage();
  await first.goto('/');
  await picture(first, 'afisha-desktop', 1440);
  await second.goto('/');
  await picture(second, 'afisha-mobile', 390);
  const tag = randomUUID().slice(0, 8);
  const emails = [`first+${tag}@example.test`, `second+${tag}@example.test`];
  await Promise.all([first.goto(`/events/${id}`), second.goto(`/events/${id}`)]);
  await picture(second, 'event-mobile', 390);
  await first.getByLabel('Email', { exact: true }).fill(emails[0]);
  await second.getByLabel('Email', { exact: true }).fill(emails[1]);
  await Promise.all([
    first.getByRole('button', { name: /Отправить заявку|Встать в лист ожидания/ }).click(),
    second.getByRole('button', { name: /Отправить заявку|Встать в лист ожидания/ }).click(),
  ]);
  for (const participant of [first, second])
    await expect(participant.getByText('Запрос принят.', { exact: false })).toBeVisible();
  const tokens = await Promise.all(emails.map((email) => privateLink(request, label, email)));
  await Promise.all([openPrivate(first, tokens[0]), openPrivate(second, tokens[1])]);
  await expect
    .poll(async () =>
      [await first.locator('h1').textContent(), await second.locator('h1').textContent()].sort()
    )
    .toEqual(['Вы в листе ожидания', 'Участие подтверждено'].sort());
  const winnerIndex = (await first
    .getByRole('heading', { name: 'Участие подтверждено', exact: true })
    .count())
    ? 0
    : 1;
  const winner = winnerIndex === 0 ? first : second;
  const waiting = winnerIndex === 0 ? second : first;
  await expect(waiting.getByTestId('ticket-code')).toHaveCount(0);
  await winner.getByRole('button', { name: 'Отказаться от участия' }).click();
  await expect(
    winner.getByRole('heading', { name: 'Участие отменено', exact: true })
  ).toBeVisible();
  await expect(
    waiting.getByRole('heading', { name: 'Участие подтверждено', exact: true })
  ).toBeVisible();
  await expect
    .poll(async () => (await letters(request, label, emails[1 - winnerIndex], 'Билет')).length)
    .toBe(1);
  const ticket = await waiting.getByTestId('ticket-code').innerText();
  await winner.getByRole('button', { name: 'Восстановить участие' }).click();
  await expect(
    winner.getByRole('heading', { name: 'Вы в листе ожидания', exact: true })
  ).toBeVisible();
  const repeated = await a.newPage();
  await register(repeated, id, emails[winnerIndex]);
  await repeated.close();
  await expect(page.getByTestId('stat-confirmed')).toHaveText('1');
  await expect(page.getByTestId('stat-waitlisted')).toHaveText('1');
  await picture(page, 'organizer-desktop', 1280);
  const soon = new Date(Date.now() + 20000);
  await page.getByLabel('Новая дата и время · Алматы (UTC+5)').fill(dateInput(soon.toISOString()));
  await page.getByRole('button', { name: 'Сохранить дату' }).click();
  await expect(page.getByText('Дата сохранена.', { exact: false })).toBeVisible();
  for (const email of emails)
    await expect.poll(async () => (await letters(request, label, email, 'Перенос')).length).toBe(1);
  await page.getByRole('link', { name: 'Открыть чекин' }).click();
  await expect(page.getByRole('button', { name: 'Отметить участника' })).toBeEnabled({
    timeout: 30000,
  });
  const other = await browser.newContext({ baseURL: base });
  contexts.push(other);
  const gate = await other.newPage();
  await login(gate, `/organizer/events/${id}/check-in`);
  for (const staff of [page, gate])
    await staff.getByLabel('Код билета', { exact: true }).fill(ticket);
  await Promise.all([
    page.getByRole('button', { name: 'Отметить участника' }).click(),
    gate.getByRole('button', { name: 'Отметить участника' }).click(),
  ]);
  await expect
    .poll(
      async () =>
        [
          await page.locator('#checkin-result').innerText(),
          await gate.locator('#checkin-result').innerText(),
        ].filter((text) => text.includes('Участник отмечен.')).length
    )
    .toBe(1);
  await expect
    .poll(
      async () =>
        [
          await page.locator('#checkin-result').innerText(),
          await gate.locator('#checkin-result').innerText(),
        ].filter((text) => text.includes('Этот билет уже отмечен.')).length
    )
    .toBe(1);
  for (const staff of [page, gate])
    await expect(staff.getByTestId('stat-checked_in')).toHaveText('1');
  await expect(waiting.getByRole('heading', { name: 'Вы уже отмечены на входе' })).toBeVisible();
  await picture(page, 'checkin-desktop', 1280);
  await picture(waiting, 'ticket-mobile', 390);
});

test('Unicode/Punycode repeat, invalid private link, keyboard access and not-found page', async ({
  page,
  request,
}) => {
  const label = 'Проверка адресов · ' + randomUUID().slice(0, 8);
  const id = await create(request, label);
  const local = 'person+' + randomUUID().slice(0, 8);
  await register(page, id, `${local}@faß.de`);
  await register(page, id, `${local}@xn--fa-hia.de`);
  const token = await privateLink(request, label, `${local}@xn--fa-hia.de`);
  await openPrivate(page, token);
  await expect(
    page.getByRole('heading', { name: 'Участие подтверждено', exact: true })
  ).toBeVisible();
  const snapshot = await (await request.get(base + '/api/events/' + id)).json();
  expect(snapshot.confirmed).toBe(1);
  expect(snapshot.waitlisted).toBe(0);
  await openPrivate(page, 'fake-invalid-token');
  await expect(page.getByRole('alert')).toContainText('Ссылка недействительна');
  await page.goto('/events/' + randomUUID());
  await expect(page.getByRole('heading', { name: 'Мероприятие не найдено' })).toBeVisible();
  await page.goto('/organizer');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'К содержимому' })).toBeFocused();
  await page.keyboard.press('Enter');
  await page.getByLabel('Ключ организатора').fill('fake-wrong-key');
  await page.getByRole('button', { name: 'Открыть рабочее пространство' }).click();
  await expect(page.getByRole('alert')).toContainText('Ключ организатора не подходит');
});

test('network failure keeps a real error and retries; SSE reconnect receives current counts', async ({
  page,
  request,
}) => {
  await page.route('**/api/events', (route) => route.abort());
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Нет связи');
  await page.unroute('**/api/events');
  await page.getByRole('button', { name: 'Попробовать ещё раз' }).click();
  await expect(page.locator('.event-list')).toBeVisible();
  const label = 'Восстановление связи · ' + randomUUID().slice(0, 8);
  const id = await create(request, label);
  await login(page, `/organizer/events/${id}`);
  await expect(page.getByText('Обновляется автоматически', { exact: true })).toBeVisible();
  await page.context().setOffline(true);
  await expect(page.getByText('Связь прервана.', { exact: false })).toBeVisible();
  const response = await request.post(base + `/api/events/${id}/registrations`, {
    data: { email: 'reconnect+' + randomUUID().slice(0, 8) + '@example.test' },
  });
  expect(response.status()).toBe(202);
  await expect(page.getByTestId('stat-confirmed')).toHaveText('0');
  await page.context().setOffline(false);
  await expect(page.getByText('Обновляется автоматически', { exact: true })).toBeVisible();
  await expect(page.getByTestId('stat-confirmed')).toHaveText('1');
  await picture(page, 'organizer-mobile', 390);
});

test('a stale participant action refreshes the real generation after HTTP409', async ({
  page,
  request,
}) => {
  const label = 'Обновление участия · ' + randomUUID().slice(0, 8);
  const id = await create(request, label);
  const address = 'version+' + randomUUID().slice(0, 8) + '@example.test';
  await register(page, id, address);
  const token = await privateLink(request, label, address);
  await openPrivate(page, token);
  const oldTicket = await page.getByTestId('ticket-code').innerText();
  let intercepted!: () => void;
  const pending = new Promise<void>((done) => {
    intercepted = done;
  });
  let release!: () => void;
  const gate = new Promise<void>((done) => {
    release = done;
  });
  await page.route('**/api/registration/cancel', async (route) => {
    intercepted();
    await gate;
    await route.continue();
  });
  const clicked = page.getByRole('button', { name: 'Отказаться от участия' }).click();
  await pending;
  const headers = { Authorization: `Bearer ${token}` };
  expect(
    (
      await request.post(base + '/api/registration/cancel', {
        headers,
        data: { expected_participation_no: 1 },
      })
    ).status()
  ).toBe(200);
  expect(
    (
      await request.post(base + '/api/registration/resume', {
        headers,
        data: { expected_participation_no: 1 },
      })
    ).status()
  ).toBe(200);
  release();
  await clicked;
  await expect(page.getByText('Участие изменилось.', { exact: false })).toBeVisible();
  await expect(page.getByTestId('ticket-code')).not.toHaveText(oldTicket);
  await expect(
    page.getByRole('heading', { name: 'Участие подтверждено', exact: true })
  ).toBeVisible();
});
