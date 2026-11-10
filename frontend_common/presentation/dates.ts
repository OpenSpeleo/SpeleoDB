const dateFormatter = new Intl.DateTimeFormat(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
});
const calendarDateFormatter = new Intl.DateTimeFormat(undefined, {
    year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC',
});
const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: 'numeric', minute: '2-digit',
});
const monthFormatter = new Intl.DateTimeFormat(undefined, {
    year: 'numeric', month: 'short',
});
const calendarMonthFormatter = new Intl.DateTimeFormat(undefined, {
    year: 'numeric', month: 'short', timeZone: 'UTC',
});

/** Preserve the precision of calendar month keys and heatmap month headers. */
export function formatMonth(value: string | Date | null | undefined, fallback = 'N/A'): string {
    if (!value) return fallback;
    const date = value instanceof Date ? value : parseCalendarDate(`${value}-01`);
    const formatter = value instanceof Date ? monthFormatter : calendarMonthFormatter;
    return !date || Number.isNaN(date.getTime()) ? fallback : formatter.format(date);
}

/** A UTC-backed calendar value avoids skipped local dates; use UTC accessors. */
export function parseCalendarDate(value: string): Date | null {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (!match) return null;
    const year = Number(match[1]);
    const month = Number(match[2]) - 1;
    const day = Number(match[3]);
    const date = new Date(0);
    date.setUTCFullYear(year, month, day);
    return date.getUTCFullYear() === year && date.getUTCMonth() === month && date.getUTCDate() === day
        ? date : null;
}

export function formatDateTime(value: string | Date | null | undefined, fallback = 'N/A'): string {
    if (!value) return fallback;
    const date = value instanceof Date ? value : new Date(value);
    return Number.isNaN(date.getTime()) ? fallback : dateTimeFormatter.format(date);
}

export function formatDate(value: string | Date | null | undefined, fallback = 'N/A'): string {
    if (!value) return fallback;
    if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
        const date = parseCalendarDate(value);
        return date ? calendarDateFormatter.format(date) : fallback;
    }
    const date = value instanceof Date ? value : new Date(value);
    return Number.isNaN(date.getTime()) ? fallback : dateFormatter.format(date);
}

/** Native date inputs use YYYY-MM-DD, with today's day taken from the browser. */
export function dateInputValue(date: Date = new Date()): string {
    return `${String(date.getFullYear()).padStart(4, '0')}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

/** Hydrate inert template dates; data-local-date identifies their precision and timezone semantics. */
export function formatDateElements(root: ParentNode = document): void {
    root.querySelectorAll<HTMLTimeElement>('time[data-local-date]').forEach(element => {
        const fallback = element.textContent || 'N/A';
        element.textContent = element.dataset.localDate === 'datetime'
            ? formatDateTime(element.dateTime, fallback)
            : element.dataset.localDate === 'month'
                ? formatMonth(element.dateTime, fallback)
                : formatDate(element.dateTime, fallback);
    });
}
