import { describe, expect, it } from 'vitest';
import { dateInput, fullDate, inputToISO, time } from '../src/dates';

describe('explicit Almaty time', () => {
  it('converts local form time independently of the browser timezone', () => {
    expect(inputToISO('2026-12-01T19:30')).toBe('2026-12-01T14:30:00.000Z');
    expect(inputToISO('2026-12-01T00:15:30')).toBe('2026-11-30T19:15:30.000Z');
  });
  it('round-trips the same absolute instant across a UTC date boundary', () => {
    const value = '2026-12-31T22:10:11Z';
    expect(dateInput(value)).toBe('2027-01-01T03:10:11');
    expect(inputToISO(dateInput(value))).toBe('2026-12-31T22:10:11.000Z');
    expect(fullDate(value)).toContain('2027');
    expect(time(value)).toBe('03:10');
  });
  it.each(['', '2026-01-01', 'not-a-date', '2026-12-01T12:00Z'])(
    'rejects incomplete or ambiguous form input %s',
    (value) => {
      expect(() => inputToISO(value)).toThrow();
    }
  );
});

// Private links are consumed once before rendering, without browser storage.
import { afterEach, vi } from 'vitest';
import { takePrivateToken } from '../src/dates';
afterEach(() => vi.unstubAllGlobals());
it('removes a private token from the address without putting it into history state', () => {
  const replaceState = vi.fn();
  vi.stubGlobal('window', {
    location: { pathname: '/registration', search: '', hash: '#token=fake-private-token' },
    history: { replaceState },
  });
  expect(takePrivateToken()).toBe('fake-private-token');
  expect(replaceState).toHaveBeenCalledWith(null, '', '/registration');
});
it('rejects oversized tokens and still clears the fragment', () => {
  const replaceState = vi.fn();
  vi.stubGlobal('window', {
    location: { pathname: '/registration', search: '', hash: '#token=' + 'x'.repeat(257) },
    history: { replaceState },
  });
  expect(takePrivateToken()).toBe('');
  expect(replaceState).toHaveBeenCalledOnce();
});

it('uses the native datetime-local representation when seconds are zero', () => {
  expect(dateInput('2026-10-25T16:47:00Z')).toBe('2026-10-25T21:47');
  expect(inputToISO(dateInput('2026-10-25T16:47:00Z'))).toBe('2026-10-25T16:47:00.000Z');
});

it('renders English dates while retaining the Almaty timezone', () => {
  expect(fullDate('2026-12-31T22:10:11Z')).toBe('1 January 2027');
  expect(time('2026-12-31T22:10:11Z')).toBe('03:10');
});
