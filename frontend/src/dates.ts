export const timezone = 'Almaty time · UTC+5';
const options = { timeZone: 'Asia/Almaty' };
export const fullDate = (value: string) =>
  new Intl.DateTimeFormat('en-GB', {
    ...options,
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date(value));
export const time = (value: string) =>
  new Intl.DateTimeFormat('en-GB', {
    ...options,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(new Date(value));
export const day = (value: string) =>
  new Intl.DateTimeFormat('en-GB', { ...options, day: '2-digit' }).format(new Date(value));
export const month = (value: string) =>
  new Intl.DateTimeFormat('en-GB', { ...options, month: 'short', year: 'numeric' }).format(
    new Date(value)
  );
export function dateInput(value: string): string {
  const parts = new Intl.DateTimeFormat('en-GB', {
    ...options,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(value));
  const get = (name: string) => parts.find((part) => part.type === name)!.value;
  const base = `${get('year')}-${get('month')}-${get('day')}T${get('hour')}:${get('minute')}`;
  return get('second') === '00' ? base : `${base}:${get('second')}`;
}
export function inputToISO(value: string): string {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(value))
    throw new Error('Enter a date and time.');
  const date = new Date(`${value}+05:00`);
  if (!Number.isFinite(date.valueOf())) throw new Error('Enter a valid date.');
  return date.toISOString();
}
export function takePrivateToken(): string {
  const fragment = new URLSearchParams(window.location.hash.slice(1));
  const token = fragment.get('token');
  if (token !== null)
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
  return window.location.pathname === '/registration' && token && token.length <= 256 ? token : '';
}
