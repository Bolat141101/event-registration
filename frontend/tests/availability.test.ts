import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { afterEach, expect, it, vi } from 'vitest';
import { Availability } from '../src/components/common';

const event = {
  id: 'fixture',
  description: 'Check',
  starts_at: '2030-01-01T12:00:00Z',
  capacity: 1,
  confirmed: 0,
  waitlisted: 0,
  checked_in: 0,
  schedule_version: 1,
};
const render = (serverNow: number | null) =>
  renderToStaticMarkup(createElement(Availability, { event, serverNow }));
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});
it.each([-1, 1])('ignores device clock shifted %s year', (direction) => {
  vi.useFakeTimers();
  vi.setSystemTime(Date.parse(event.starts_at) + direction * 365 * 86400000);
  expect(render(Date.parse(event.starts_at) - 1)).toContain('Available 1 of 1');
  expect(render(Date.parse(event.starts_at))).toContain('Already started');
});
it('shows unknown status before synchronization or after disconnect', () => {
  expect(render(null)).toContain('Checking status');
  expect(render(null)).not.toContain(' available');
});
it('never reads the device wall clock', () => {
  vi.spyOn(Date, 'now').mockImplementation(() => {
    throw new Error('Device clock must not be used');
  });
  expect(render(Date.parse(event.starts_at))).toContain('Already started');
});
