import type { SensorInstallRecord } from '../../../../../../ts-types/domain/fleet-records.ts';
import { StationLogs } from './logs.ts';
import { StationResources } from './resources.ts';
import { StationSensors } from './sensors.ts';
import { formatExpiracyDate, renderSensorHistoryHtml } from './sensor_presentation.ts';

const timestamp = '2026-01-01T00:18:00Z';
const timestampLabel = new Intl.DateTimeFormat(undefined, {
    year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
}).format(new Date(timestamp));
const calendarLabel = new Intl.DateTimeFormat(undefined, {
    year: 'numeric', month: 'short', day: 'numeric',
}).format(new Date(2026, 0, 1));

function textOf(html: string) {
    const element = document.createElement('div');
    element.innerHTML = html;
    return element.textContent;
}

it('shows the same browser-local timestamp in journal entries and resource cards', () => {
    const journal = StationLogs.renderEntry({ id: 'journal', creation_date: timestamp }, false, false);
    const resource = StationResources.renderResourceCard({ resource_type: 'note', creation_date: timestamp }, false, false);
    expect(textOf(journal)).toContain(timestampLabel);
    expect(textOf(resource)).toContain(timestampLabel);
    expect(textOf(journal + resource)).not.toMatch(/GMT|UTC/);
});

it('keeps sensor installation calendar dates while localizing the modification instant', () => {
    const install: SensorInstallRecord = {
        id: 'install', sensor_id: 'sensor', sensor_name: 'Sensor', sensor_fleet_id: 'fleet',
        sensor_fleet_name: 'Fleet', station_id: 'station', station_name: 'Station',
        install_date: '2026-01-01', install_user: 'diver@example.com', uninstall_date: null,
        uninstall_user: null, status: 'installed', expiracy_memory_date: null,
        expiracy_battery_date: null, created_by: 'diver@example.com',
        creation_date: timestamp, modified_date: timestamp,
    };
    const element = document.createElement('div');
    element.innerHTML = renderSensorHistoryHtml([install], 'station', 'project', 'all', false);
    const cells = element.querySelectorAll('#sensor-history-tbody td');
    expect(cells[3]?.textContent).toBe(calendarLabel);
    expect(cells[5]?.textContent).toBe('-');
    expect(cells[7]?.textContent).toBe(timestampLabel);
});

it('shows sensor expiry as a calendar date with a local calendar-day countdown', () => {
    const today = new Date();
    const tomorrow = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
    const value = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, '0')}-${String(tomorrow.getDate()).padStart(2, '0')}`;
    const label = new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric' }).format(tomorrow);
    expect(textOf(formatExpiracyDate(value))).toBe(`${label} (in 1 days)`);
});

it('defaults sensor retrieval to the browser calendar day without changing the date wire format', () => {
    const container = document.createElement('div');
    container.id = 'station-modal-content';
    document.body.append(container);
    try {
        StationSensors.showRetrieveModal('install', 'station', 'project');
        const today = new Date();
        const expected = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
        expect(container.querySelector<HTMLInputElement>('#retrieval-date')?.value).toBe(expected);
    } finally {
        container.remove();
    }
});
