const formatter = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'long' })

// Accepts a Date or an ISO string; a string without a timezone is read as UTC, because the
// server stores UTC and may serialize it without the "Z".
export function formatDate(value: Date | string): string {
  if (typeof value === 'string' && !/(Z|[+-]\d{2}:?\d{2})$/.test(value)) {
    return formatter.format(new Date(`${value}Z`))
  }
  return formatter.format(new Date(value))
}
