import { test, expect } from '@playwright/test';
import type { APIRequestContext, BrowserContext, Locator, Page } from '@playwright/test';
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
  await page.getByLabel('Organizer key').fill(key!);
  await page.getByRole('button', { name: 'Open workspace' }).click();
  await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible();
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
  await page.getByRole('button', { name: /Submit registration|Join waitlist/ }).click();
  await expect(page.getByText('Request accepted.', { exact: false })).toBeVisible();
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
async function picture(page: Page, name: string, width: number, ready: Locator) {
  await ready.waitFor({ state: 'visible' });
  await page.setViewportSize({ width, height: 900 });
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
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
  const label = 'A discussion about reliable services · ' + randomUUID().slice(0, 8);
  await page.getByLabel('Description', { exact: true }).fill(label);
  await page
    .getByLabel('Date and time · Almaty (UTC+5)', { exact: true })
    .fill(dateInput(new Date(Date.now() + 2 * 86400000).toISOString()));
  await page.getByLabel('Capacity').fill('1');
  await page.getByRole('button', { name: 'Create event' }).click();
  await expect(page.getByRole('link', { name: 'Open check-in' })).toBeVisible();
  const id = /\/organizer\/events\/([^/]+)/.exec(page.url())![1];
  const a = await browser.newContext({
    locale: 'en-GB',
    baseURL: base,
    viewport: { width: 1440, height: 900 },
  });
  const b = await browser.newContext({
    locale: 'en-GB',
    baseURL: base,
    viewport: { width: 390, height: 844 },
  });
  contexts.push(a, b);
  const first = await a.newPage();
  const second = await b.newPage();
  await first.goto('/');
  await picture(first, 'events-desktop', 1440, first.locator('.event-row').first());
  await second.goto('/');
  await picture(second, 'events-mobile', 390, second.locator('.event-row').first());
  const tag = randomUUID().slice(0, 8);
  const emails = [`first+${tag}@example.test`, `second+${tag}@example.test`];
  await Promise.all([first.goto(`/events/${id}`), second.goto(`/events/${id}`)]);
  await picture(
    second,
    'event-mobile',
    390,
    second.getByRole('heading', { name: label, exact: true })
  );
  await first.getByLabel('Email', { exact: true }).fill(emails[0]);
  await second.getByLabel('Email', { exact: true }).fill(emails[1]);
  await Promise.all([
    first.getByRole('button', { name: /Submit registration|Join waitlist/ }).click(),
    second.getByRole('button', { name: /Submit registration|Join waitlist/ }).click(),
  ]);
  for (const participant of [first, second])
    await expect(participant.getByText('Request accepted.', { exact: false })).toBeVisible();
  const tokens = await Promise.all(emails.map((email) => privateLink(request, label, email)));
  await Promise.all([openPrivate(first, tokens[0]), openPrivate(second, tokens[1])]);
  await expect
    .poll(async () =>
      [await first.locator('h1').textContent(), await second.locator('h1').textContent()].sort()
    )
    .toEqual(['You are on the waitlist', 'Participation confirmed'].sort());
  const winnerIndex = (await first
    .getByRole('heading', { name: 'Participation confirmed', exact: true })
    .count())
    ? 0
    : 1;
  const winner = winnerIndex === 0 ? first : second;
  const waiting = winnerIndex === 0 ? second : first;
  await expect(waiting.getByTestId('ticket-code')).toHaveCount(0);
  await winner.getByRole('button', { name: 'Cancel participation' }).click();
  await expect(
    winner.getByRole('heading', { name: 'Participation cancelled', exact: true })
  ).toBeVisible();
  await expect(
    waiting.getByRole('heading', { name: 'Participation confirmed', exact: true })
  ).toBeVisible();
  await expect
    .poll(
      async () => (await letters(request, label, emails[1 - winnerIndex], 'Event ticket')).length
    )
    .toBe(1);
  const ticket = await waiting.getByTestId('ticket-code').innerText();
  await winner.getByRole('button', { name: 'Rejoin event' }).click();
  await expect(
    winner.getByRole('heading', { name: 'You are on the waitlist', exact: true })
  ).toBeVisible();
  const repeated = await a.newPage();
  await register(repeated, id, emails[winnerIndex]);
  await repeated.close();
  await expect(page.getByTestId('stat-confirmed')).toHaveText('1');
  await expect(page.getByTestId('stat-waitlisted')).toHaveText('1');
  await picture(page, 'organizer-desktop', 1280, page.getByTestId('stat-waitlisted'));
  const soon = new Date(Date.now() + 20000);
  await page.getByLabel('New date and time · Almaty (UTC+5)').fill(dateInput(soon.toISOString()));
  await page.getByRole('button', { name: 'Save date' }).click();
  await expect(page.getByText('Date saved.', { exact: false })).toBeVisible();
  for (const email of emails)
    await expect
      .poll(async () => (await letters(request, label, email, 'Rescheduled')).length)
      .toBe(1);
  await page.getByRole('link', { name: 'Open check-in' }).click();
  await expect(page.getByRole('button', { name: 'Check in participant' })).toBeEnabled({
    timeout: 30000,
  });
  const other = await browser.newContext({ locale: 'en-GB', baseURL: base });
  contexts.push(other);
  const gate = await other.newPage();
  await login(gate, `/organizer/events/${id}/check-in`);
  for (const staff of [page, gate])
    await staff.getByLabel('Ticket code', { exact: true }).fill(ticket);
  await Promise.all([
    page.getByRole('button', { name: 'Check in participant' }).click(),
    gate.getByRole('button', { name: 'Check in participant' }).click(),
  ]);
  await expect
    .poll(
      async () =>
        [
          await page.locator('#checkin-result').innerText(),
          await gate.locator('#checkin-result').innerText(),
        ].filter((text) => text.includes('Participant checked in.')).length
    )
    .toBe(1);
  await expect
    .poll(
      async () =>
        [
          await page.locator('#checkin-result').innerText(),
          await gate.locator('#checkin-result').innerText(),
        ].filter((text) => text.includes('This ticket has already been checked in.')).length
    )
    .toBe(1);
  for (const staff of [page, gate])
    await expect(staff.getByTestId('stat-checked_in')).toHaveText('1');
  await expect(waiting.getByRole('heading', { name: 'You are checked in' })).toBeVisible();
  await picture(page, 'checkin-desktop', 1280, page.getByTestId('stat-checked_in'));
  await picture(waiting, 'ticket-mobile', 390, waiting.getByTestId('ticket-code'));
});

test('Unicode/Punycode repeat, invalid private link, keyboard access and not-found page', async ({
  page,
  request,
}) => {
  const label = 'Email checks · ' + randomUUID().slice(0, 8);
  const id = await create(request, label);
  const local = 'person+' + randomUUID().slice(0, 8);
  await register(page, id, `${local}@faß.de`);
  await register(page, id, `${local}@xn--fa-hia.de`);
  const token = await privateLink(request, label, `${local}@xn--fa-hia.de`);
  await openPrivate(page, token);
  await expect(
    page.getByRole('heading', { name: 'Participation confirmed', exact: true })
  ).toBeVisible();
  const snapshot = await (await request.get(base + '/api/events/' + id)).json();
  expect(snapshot.confirmed).toBe(1);
  expect(snapshot.waitlisted).toBe(0);
  await openPrivate(page, 'fake-invalid-token');
  await expect(page.getByRole('alert')).toContainText('Invalid link');
  await page.goto('/events/' + randomUUID());
  await expect(page.getByRole('heading', { name: 'Event not found' })).toBeVisible();
  await page.goto('/organizer');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await page.getByLabel('Organizer key').fill('fake-wrong-key');
  await page.getByRole('button', { name: 'Open workspace' }).click();
  await expect(page.getByRole('alert')).toContainText('The organizer key is incorrect');
});

test('network failure keeps a real error and retries; SSE reconnect receives current counts', async ({
  page,
  request,
}) => {
  await page.route('**/api/events?*', (route) => route.abort());
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('No connection');
  await page.unroute('**/api/events?*');
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.locator('.event-list')).toBeVisible();
  const label = 'Connection recovery · ' + randomUUID().slice(0, 8);
  const id = await create(request, label);
  await login(page, `/organizer/events/${id}`);
  await expect(page.getByText('Updates automatically', { exact: true })).toBeVisible();
  await page.context().setOffline(true);
  await expect(page.getByText('Connection lost.', { exact: false })).toBeVisible();
  const response = await request.post(base + `/api/events/${id}/registrations`, {
    data: { email: 'reconnect+' + randomUUID().slice(0, 8) + '@example.test' },
  });
  expect(response.status()).toBe(202);
  await expect(page.getByTestId('stat-confirmed')).toHaveText('0');
  await page.context().setOffline(false);
  await expect(page.getByText('Updates automatically', { exact: true })).toBeVisible();
  await expect(page.getByTestId('stat-confirmed')).toHaveText('1');
  await picture(page, 'organizer-mobile', 390, page.getByTestId('stat-confirmed'));
});

test('a stale participant action refreshes the real generation after HTTP409', async ({
  page,
  request,
}) => {
  const label = 'Participation refresh · ' + randomUUID().slice(0, 8);
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
  const clicked = page.getByRole('button', { name: 'Cancel participation' }).click();
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
  await expect(page.getByText('Participation changed.', { exact: false })).toBeVisible();
  await expect(page.getByTestId('ticket-code')).not.toHaveText(oldTicket);
  await expect(
    page.getByRole('heading', { name: 'Participation confirmed', exact: true })
  ).toBeVisible();
});

for (const shift of [-365, 365]) {
  test(`server time governs all actions despite device clock shift ${shift} days`, async ({
    browser,
    request,
  }) => {
    const label = 'Server time · ' + randomUUID().slice(0, 8);
    const id = await create(request, label);
    const context = await browser.newContext({ locale: 'en-GB', baseURL: base });
    contexts.push(context);
    const visitor = await context.newPage();
    await visitor.clock.setFixedTime(new Date(Date.now() + shift * 86400000));
    const address = 'clock+' + randomUUID().slice(0, 8) + '@example.test';
    await register(visitor, id, address);
    const token = await privateLink(request, label, address);
    await openPrivate(visitor, token);
    await visitor.getByRole('button', { name: 'Cancel participation' }).click();
    await visitor.getByRole('button', { name: 'Rejoin event' }).click();
    await expect(visitor.getByRole('button', { name: 'Cancel participation' })).toBeEnabled();
    const staff = await context.newPage();
    await staff.clock.setFixedTime(new Date(Date.now() + shift * 86400000));
    await login(staff, `/organizer/events/${id}`);
    const later = new Date(Date.now() + 3 * 86400000);
    await staff
      .getByLabel('New date and time · Almaty (UTC+5)')
      .fill(dateInput(later.toISOString()));
    await staff.getByRole('button', { name: 'Save date' }).click();
    await expect(staff.getByText('Date saved.', { exact: false })).toBeVisible();
    await staff.getByRole('link', { name: 'Open check-in' }).click();
    await expect(staff.getByRole('button', { name: 'Check in participant' })).toBeDisabled();
    await context.setOffline(true);
    await expect(visitor.getByRole('button', { name: 'Cancel participation' })).toBeDisabled();
    await expect(staff.getByRole('button', { name: 'Check in participant' })).toBeDisabled();
    const moved = await request.patch(base + `/api/events/${id}/schedule`, {
      headers: auth,
      data: { starts_at: new Date(Date.now() + 3000).toISOString(), expected_schedule_version: 2 },
    });
    expect(moved.status()).toBe(200);
    // Change the device clock in the opposite direction while SSE is unavailable.
    await visitor.clock.setFixedTime(new Date(Date.now() - shift * 86400000));
    await context.setOffline(false);
    await expect(staff.getByRole('button', { name: 'Check in participant' })).toBeEnabled({
      timeout: 15000,
    });
    await expect(
      visitor.getByText('The event has started. Participation can no longer be changed.')
    ).toBeVisible();
    await visitor.goto(`/events/${id}`);
    await expect(visitor.getByRole('heading', { name: 'Registration closed' })).toBeVisible();
    await staff.getByRole('link', { name: 'Manage event' }).click();
    await expect(staff.getByRole('button', { name: 'Save date' })).toBeDisabled();
  });
}

test('initial server time is unknown until a real SSE snapshot arrives', async ({
  page,
  request,
}) => {
  const id = await create(request, 'Waiting for server time · ' + randomUUID().slice(0, 8));
  await page.route('**/stream', (route) => route.abort());
  await page.goto(`/events/${id}`);
  await expect(page.getByRole('button', { name: 'Submit registration' })).toBeDisabled();
  await expect(page.getByText('Checking server time.', { exact: false })).toBeVisible();
  await expect(page.locator('.availability')).toHaveText('Checking status');
  await page.unroute('**/stream');
  await page.reload();
  await expect(page.getByRole('button', { name: 'Submit registration' })).toBeEnabled();
});

test('event pagination works in public and organizer views through the real API', async ({
  page,
  request,
}) => {
  for (let index = 0; index < 23; index++)
    await create(request, 'Page · ' + randomUUID().slice(0, 8));

  async function turn(direction: 'Next' | 'Previous', offset: number, organizer = false) {
    let intercepted!: () => void;
    const entered = new Promise<void>((done) => {
      intercepted = done;
    });
    let release!: () => void;
    const gate = new Promise<void>((done) => {
      release = done;
    });
    const pattern = `**/api/events?limit=20&offset=${offset}`;
    await page.route(
      pattern,
      async (route) => {
        intercepted();
        await gate;
        await route.continue();
      },
      { times: 1 }
    );
    const response = page.waitForResponse((res) => {
      const url = new URL(res.url());
      return url.pathname === '/api/events' && url.searchParams.get('offset') === String(offset);
    });
    try {
      await page.getByRole('button', { name: direction, exact: true }).click();
      await entered;
      await expect(page.getByText('Loading…', { exact: true })).toBeVisible();
    } finally {
      release();
    }
    const acknowledged = await response;
    expect(acknowledged.status()).toBe(200);
    const body = (await acknowledged.json()) as { items: { id: string }[] };
    const prefix = organizer ? '/organizer/events/' : '/events/';
    const selector = organizer ? '.organizer-list h3 a' : '.event-row h2 a';
    const expected = body.items.map((event) => prefix + event.id);
    expect(expected.length).toBeGreaterThan(0);
    await expect
      .poll(() =>
        page
          .locator(selector)
          .evaluateAll((links) => links.map((link) => link.getAttribute('href')))
      )
      .toEqual(expected);
    await expect(page.getByText(`Page ${offset / 20 + 1}`, { exact: true })).toBeVisible();
    return expected;
  }

  await page.goto('/');
  await expect(page.locator('.event-row')).toHaveCount(20);
  const firstIds = await page
    .locator('.event-row h2 a')
    .evaluateAll((links) => links.map((link) => link.getAttribute('href')));
  const secondIds = await turn('Next', 20);
  expect(secondIds.some((id) => firstIds.includes(id))).toBe(false);
  expect(await turn('Previous', 0)).toEqual(firstIds);
  await login(page);
  await expect(page.locator('.organizer-list article')).toHaveCount(20);
  await turn('Next', 20, true);
  await turn('Previous', 0, true);
});

test('real SSE recovers the event after an initial REST transport failure', async ({
  page,
  request,
}) => {
  const id = await create(request, 'Initial connection · ' + randomUUID().slice(0, 8));
  await page.route(`**/api/events/${id}`, (route) => route.abort());
  await page.goto(`/events/${id}`);
  await expect(page.getByRole('button', { name: 'Submit registration' })).toBeEnabled();
  await page
    .getByLabel('Email', { exact: true })
    .fill('initial+' + randomUUID().slice(0, 8) + '@example.test');
  await page.getByRole('button', { name: 'Submit registration' }).click();
  await expect(page.getByText('Request accepted.', { exact: false })).toBeVisible();
});

for (const direction of [-1, 1]) {
  test(`availability uses server time with browser clock shifted ${direction} year`, async ({
    page,
    request,
  }) => {
    const id = await create(request, 'Availability · ' + randomUUID().slice(0, 8));
    await page.clock.setFixedTime(new Date(Date.now() + direction * 365 * 86400000));
    await page.goto(`/events/${id}`);
    await expect(page.getByRole('button', { name: 'Submit registration' })).toBeEnabled();
    await expect(page.locator('.availability')).toHaveText('Available 1 of 1');
    await page.goto('/');
    // Locate the new event on its actual page, independent of previous test data.
    let offset = 0;
    while (true) {
      const listing = await request.get(base + `/api/events?limit=20&offset=${offset}`);
      expect(listing.status()).toBe(200);
      const body = (await listing.json()) as {
        items: { id: string }[];
        next_offset: number | null;
      };
      if (body.items.some((event) => event.id === id)) break;
      expect(body.next_offset).not.toBeNull();
      offset = body.next_offset!;
      const response = page.waitForResponse(
        (res) => new URL(res.url()).searchParams.get('offset') === String(offset)
      );
      await page.getByRole('button', { name: 'Next', exact: true }).click();
      await response;
      await expect(page.getByText(`Page ${offset / 20 + 1}`, { exact: true })).toBeVisible();
    }
    await expect(
      page
        .locator('.event-row')
        .filter({ has: page.locator(`h2 a[href="/events/${id}"]`) })
        .locator('.availability')
    ).toHaveText('Available 1 of 1');
    await page.goto(`/events/${id}`);
    await expect(page.getByRole('button', { name: 'Submit registration' })).toBeEnabled();
    const starts = new Date(Date.now() + 1500).toISOString();
    const moved = await request.patch(base + `/api/events/${id}/schedule`, {
      headers: auth,
      data: { starts_at: starts, expected_schedule_version: 1 },
    });
    expect(moved.status()).toBe(200);
    await expect(page.getByRole('heading', { name: 'Registration closed' })).toBeVisible();
    await expect(page.locator('.availability')).toHaveText('Already started');
    await page.context().setOffline(true);
    await expect(page.locator('.availability')).toHaveText('Checking status');
    await page.context().setOffline(false);
    await expect(page.locator('.availability')).toHaveText('Already started');
  });
}

test('capture waits for page data before layout and screenshot checks', async ({ page }) => {
  await page.setContent('<header>Events</header><main>Capture readiness test</main>');
  let loaded = false;
  const ready = {
    waitFor: async () => {
      loaded = true;
    },
  } as unknown as Locator;
  const guarded = new Proxy(page, {
    get(target, property) {
      const value = Reflect.get(target, property);
      if (property === 'evaluate')
        return (...args: unknown[]) => {
          expect(loaded, 'Layout must not be checked before page data is ready').toBe(true);
          return Reflect.apply(value, target, args);
        };
      return typeof value === 'function' ? value.bind(target) : value;
    },
  });
  await picture(guarded, 'capture-readiness-regression', 390, ready);
  expect(loaded).toBe(true);
});
