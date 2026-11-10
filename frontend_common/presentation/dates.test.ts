import { execFileSync } from 'node:child_process';
import { dateInputValue, formatDate, formatDateElements, formatDateTime } from './dates.ts';

it.each(['2026-11-01T05:30:00Z', '2026-11-01T06:30:00Z', '2026-01-01T00:15:00Z'])(
    'uses the browser timezone for an instant, including DST and year boundaries: %s', value => {
        const date = new Date(value);
        expect(formatDateTime(value)).toBe(new Intl.DateTimeFormat(undefined, {
            year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
        }).format(date));
        expect(formatDateTime(value)).not.toMatch(/GMT|UTC/);
    },
);

it.each(['2026-01-01', '2024-02-29', '2026-03-08', '2026-11-01'])(
    'preserves the selected calendar day without UTC conversion: %s', value => {
        const [year, month, day] = value.split('-').map(Number) as [number, number, number];
        expect(formatDate(value)).toBe(new Intl.DateTimeFormat(undefined, {
            year: 'numeric', month: 'short', day: 'numeric',
        }).format(new Date(year, month - 1, day)));
    },
);

it('keeps missing and invalid dates safe without replacing the rest of a page', () => {
    expect(formatDate('2026-02-29', '-')).toBe('-');
    expect(formatDateTime('invalid')).toBe('N/A');
    expect(formatDateTime(null, '')).toBe('');
    const root = document.createElement('div');
    root.innerHTML = '<time data-local-date="datetime" datetime="invalid">Unknown</time><time data-local-date="date" datetime="2026-01-01">2026-01-01</time>';
    formatDateElements(root);
    expect(root.children[0]!.textContent).toBe('Unknown');
    expect(root.children[1]!.textContent).toBe(formatDate('2026-01-01'));
});

it('preserves a saved calendar day even when the browser timezone skipped that day', () => {
    // Samoa skipped this local day when moving across the date line. A stored
    // measurement date still names the same Gregorian day for every reader.
    // Start the real runtime in that timezone so this regression also fails
    // under a UTC CI host, without replacing Date or cached Intl formatters.
    const displayed = execFileSync('bun', ['-e',
        'import { formatDate } from "./frontend_common/presentation/dates.ts"; console.log(formatDate("2011-12-30"));',
    ], { encoding: 'utf8', env: { ...process.env, TZ: 'Pacific/Apia' } }).trim();
    expect(displayed).toBe(new Intl.DateTimeFormat(undefined, {
        year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC',
    }).format(new Date('2011-12-30T00:00:00Z')));
});

it.each([new Date(2026, 0, 1, 0, 15), new Date(2026, 11, 31, 23, 45)])(
    'uses the local calendar date for native inputs near midnight: %s', date => {
        expect(dateInputValue(date)).toBe(date.getMonth() === 0 ? '2026-01-01' : '2026-12-31');
    },
);
