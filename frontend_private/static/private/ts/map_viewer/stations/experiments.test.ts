import type { ExperimentValues } from '../../../../../../ts-types/domain/experiment-records.ts';
import type { ViewerExperiment } from '../../../../../../ts-types/domain/station-experiments.ts';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { StationExperiments } from './experiments.ts';

const API = vi.hoisted(() => ({
        getExperiments: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        getExperimentData: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        createExperimentRecord: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        updateExperimentRecord: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
        deleteExperimentRecord: vi.fn<(...args: unknown[]) => Promise<unknown>>(),
    }));
vi.mock('../api.ts', () => ({ API }));

const Utils = vi.hoisted(() => {
    const escapeHtml = (text: string | number | boolean | null | undefined) => {
        if (text === null || text === undefined) {
            return '';
        }

        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    };

    return {
            escapeHtml: vi.fn(escapeHtml),
            showNotification: vi.fn(),
            showLoadingOverlay: vi.fn(() => document.createElement('div')),
            hideLoadingOverlay: vi.fn(),
    };
});
vi.mock('../utils.ts', () => ({ Utils }));

const xssName = '<script>alert(1)</script>';
const xssDescription = '<img src=x onerror=alert(1)>';
const measurementFieldUuid = '00000000-0000-0000-0000-000000000001';
const submitterFieldUuid = '00000000-0000-0000-0000-000000000002';
const noteFieldUuid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';

function createDeferred() {
    let resolve!: (value: unknown) => void;
    let reject!: (reason?: unknown) => void;
    const promise = new Promise((res, rej) => {
        resolve = res;
        reject = rej;
    });
    return { promise, resolve, reject };
}

function baseExperiment(overrides: Partial<ViewerExperiment> = {}) {
    return {
        id: 'exp-1',
        name: xssName,
        code: 'CODE',
        description: xssDescription,
        is_active: true,
        // Permission flags are server-computed (see ExperimentSerializer
        // can_write / can_delete). Tests override these to exercise gating.
        can_write: true,
        can_delete: true,
        experiment_fields: [
            {
                id: measurementFieldUuid,
                name: 'Measurement Date',
                type: 'date',
                order: 0,
                required: true,
            },
            {
                id: submitterFieldUuid,
                name: 'Submitter Email',
                type: 'text',
                order: 1,
                required: true,
            },
            {
                id: noteFieldUuid,
                name: 'Notes',
                type: 'text',
                order: 2,
                required: false,
            },
        ],
        ...overrides,
    };
}

describe('StationExperiments', () => {
    let container: HTMLDivElement;

    async function renderStation(stationId = 'st-1') {
        await StationExperiments.render(stationId, container);
    }

    async function selectExperiment(experimentId = 'exp-1') {
        const selector = container.querySelector<HTMLInputElement>('#experiment-selector')!;
        selector.value = experimentId;
        selector.dispatchEvent(new Event('change', { bubbles: true }));

        await vi.waitFor(() => {
            expect(API.getExperimentData).toHaveBeenCalled();
            expect(container.innerHTML).toContain('Data Records');
            expect(container.innerHTML).not.toContain('Loading Data Records');
        });
    }

    beforeEach(() => {
        container = document.createElement('div');
        document.body.appendChild(container);

        vi.clearAllMocks();

        API.getExperiments.mockResolvedValue([baseExperiment()]);
        API.getExperimentData.mockResolvedValue([]);
        API.createExperimentRecord.mockResolvedValue({});
        API.updateExperimentRecord.mockResolvedValue({});
        API.deleteExperimentRecord.mockResolvedValue({});
    });

    afterEach(() => {
        StationExperiments.closeRecordModal();
        StationExperiments.closeDeleteRowModal();
        document.body.innerHTML = '';
    });

it('preserves primitive and callable coercion in nested API error messages', async () => {
    const callable = () => 'callable error';
    API.getExperimentData.mockRejectedValue({ data: { errors: [42, true, Symbol('detail'), callable] } });
    await renderStation();
    const selector = container.querySelector<HTMLSelectElement>('#experiment-selector')!;
    selector.value = 'exp-1';
    selector.dispatchEvent(new Event('change'));
    await vi.waitFor(() => expect(Utils.showNotification).toHaveBeenCalledWith(
        'error', [String(42), String(true), String(Symbol('detail')), String(callable)].join(', ')
    ));
});

it('keeps the submit listener async through request settlement', async () => {
    await renderStation();
    const registrations = vi.spyOn(HTMLElement.prototype, 'addEventListener');
    await StationExperiments.openAddRowModal('st-1', 'exp-1');
    const submit = registrations.mock.calls.find(([name]) => name === 'submit')![1] as (event: Event) => Promise<void>;
    registrations.mockRestore();
    (document.getElementById(`field-${measurementFieldUuid}`) as HTMLInputElement).value = '2025-01-01';
    const pending = createDeferred();
    API.createExperimentRecord.mockReturnValue(pending.promise);
    const result = submit(new Event('submit', { cancelable: true }));
    expect(result).toBeInstanceOf(Promise);
    expect(API.createExperimentRecord).toHaveBeenCalledOnce();
    pending.resolve({ id: 'created', data: {} });
    await expect(result).resolves.toBeUndefined();
});

    it('escapes experiment name in select option text', async () => {
        await renderStation();

        const html = container.innerHTML;
        expect(html).not.toMatch(/<script>alert\(1\)<\/script>/i);
        expect(html).toContain('&lt;script&gt;');
        expect(Utils.escapeHtml).toHaveBeenCalledWith(xssName);
    });

    it('escapes experiment description when an experiment is selected', async () => {
        await renderStation();
        await selectExperiment();

        const html = container.innerHTML;
        expect(html).not.toMatch(/<img[^>]*onerror/i);
        expect(html).toContain('&lt;img');
        expect(Utils.escapeHtml).toHaveBeenCalledWith(xssDescription);
    });

    it('escapes text field values in table cells', async () => {
        const cellPayload = '<svg onload=alert(1)>';
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [noteFieldUuid]: cellPayload,
                },
            },
        ]);

        await renderStation();
        await selectExperiment();

        const html = container.innerHTML;
        expect(html).not.toMatch(/<svg[^>]*onload/i);
        expect(html).toContain('&lt;svg');
    });

    it('escapes double quotes in data-station-id on the Add Record button', async () => {
        const stationId = 'ab" onclick="evil" data-x=';
        API.getExperiments.mockResolvedValue([baseExperiment({ name: 'Safe', description: '' })]);

        await renderStation(stationId);
        await selectExperiment();

        await vi.waitFor(() => {
            expect(container.querySelector<HTMLInputElement>('#add-experiment-row-btn')!).toBeTruthy();
        });

        const button = container.querySelector<HTMLInputElement>('#add-experiment-row-btn')!;
        expect(button.getAttribute('data-station-id')).toBe(stationId);
        expect(container.innerHTML).not.toMatch(/data-station-id="[^"]*"\s+onclick/i);
        expect(container.innerHTML).toContain('&quot;');
    });

    it('shows edit actions when the experiment exposes can_write=true', async () => {
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [noteFieldUuid]: 'Editable row',
                },
            },
        ]);

        await renderStation();
        await selectExperiment();

        expect(container.querySelector<HTMLInputElement>('[data-experiment-action="edit-record"]')!).toBeTruthy();
    });

    it('hides edit actions when the experiment exposes can_write=false', async () => {
        API.getExperiments.mockResolvedValue([baseExperiment({ can_write: false, can_delete: false })]);
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [noteFieldUuid]: 'Read only row',
                },
            },
        ]);

        await renderStation();
        await selectExperiment();

        expect(container.querySelector<HTMLInputElement>('[data-experiment-action="edit-record"]')!).toBeNull();
    });

    it('shows edit actions when can_write=true and keeps delete admin-only', async () => {
        API.getExperiments.mockResolvedValue([baseExperiment({ can_write: true, can_delete: false })]);
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [noteFieldUuid]: 'Editable row',
                },
            },
        ]);

        await renderStation();
        await selectExperiment();

        expect(container.querySelector<HTMLInputElement>('[data-experiment-action="edit-record"]')!).toBeTruthy();
        // can_delete=false -> delete button is the disabled/admin-only variant
        expect(
            container.querySelector<HTMLInputElement>('[data-experiment-action="delete-record"]')!
        ).toBeNull();
    });

    it('hides the add button when can_write=false', async () => {
        API.getExperiments.mockResolvedValue([baseExperiment({ can_write: false, can_delete: false })]);

        await renderStation();
        await selectExperiment();

        expect(container.querySelector<HTMLInputElement>('#add-experiment-row-btn')!).toBeNull();
    });

    it('renders a read-only banner when can_write=false on the selected experiment', async () => {
        API.getExperiments.mockResolvedValue([baseExperiment({ can_write: false, can_delete: false })]);
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [noteFieldUuid]: 'Existing row',
                },
            },
        ]);

        await renderStation();
        await selectExperiment();

        const banner = container.querySelector<HTMLInputElement>('[data-experiment-readonly-notice]')!;
        expect(banner).toBeTruthy();
        expect(banner.textContent).toContain('Read-only access');
        expect(banner.textContent).toContain('experiment admin');
        // The banner replaces, not duplicates, the action UI.
        expect(container.querySelector<HTMLInputElement>('#add-experiment-row-btn')!).toBeNull();
        expect(container.querySelector<HTMLInputElement>('[data-experiment-action="edit-record"]')!).toBeNull();
    });

    it('does not render the read-only banner when can_write=true', async () => {
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [noteFieldUuid]: 'Editable row',
                },
            },
        ]);

        await renderStation();
        await selectExperiment();

        expect(container.querySelector<HTMLInputElement>('[data-experiment-readonly-notice]')!).toBeNull();
    });

    it('prefills the edit modal from the selected row', async () => {
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [noteFieldUuid]: 'Original note',
                },
            },
        ]);

        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('[data-experiment-action="edit-record"]')!.click();

        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        expect((document.getElementById(`field-${measurementFieldUuid}`) as HTMLInputElement).value).toBe('2025-01-01');
        expect((document.getElementById(`field-${noteFieldUuid}`) as HTMLInputElement).value).toBe('Original note');
        expect((document.getElementById(`field-${submitterFieldUuid}`) as HTMLInputElement)).toBeNull();
    });

    it('updates a row in place after a successful edit', async () => {
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [noteFieldUuid]: 'Original note',
                },
            },
        ]);
        API.updateExperimentRecord.mockResolvedValue({
            id: 'row-1',
            data: {
                [measurementFieldUuid]: '2025-01-01',
                [noteFieldUuid]: 'Updated note',
            },
        });

        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('[data-experiment-action="edit-record"]')!.click();
        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        const noteInput = (document.getElementById(`field-${noteFieldUuid}`) as HTMLInputElement);
        noteInput.value = 'Updated note';
        noteInput.dispatchEvent(new Event('input', { bubbles: true }));

        (document.getElementById('experiment-row-form') as HTMLInputElement).dispatchEvent(
            new Event('submit', { bubbles: true, cancelable: true })
        );

        await vi.waitFor(() => {
            expect(API.updateExperimentRecord).toHaveBeenCalledWith('row-1', {
                [measurementFieldUuid]: '2025-01-01',
                [noteFieldUuid]: 'Updated note',
            });
        });

        await vi.waitFor(() => {
            expect(container.innerHTML).toContain('Updated note');
        });
        expect(Utils.showNotification).toHaveBeenCalledWith('success', 'Data record updated successfully');
    });

    it('blocks invalid edits before calling the API', async () => {
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [noteFieldUuid]: 'Original note',
                },
            },
        ]);

        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('[data-experiment-action="edit-record"]')!.click();
        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        const measurementInput = (document.getElementById(`field-${measurementFieldUuid}`) as HTMLInputElement);
        measurementInput.value = '2999-01-01';

        (document.getElementById('experiment-row-form') as HTMLInputElement).dispatchEvent(
            new Event('submit', { bubbles: true, cancelable: true })
        );

        expect(API.updateExperimentRecord).not.toHaveBeenCalled();
        expect(Utils.showNotification).toHaveBeenCalledWith(
            'error',
            'Please fix validation errors before submitting'
        );
        expect((document.getElementById(`field-${measurementFieldUuid}-error`) as HTMLInputElement).textContent)
            .toContain('Measurement date cannot be in the future');
    });

    it('shows API validation errors when an edit fails', async () => {
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [noteFieldUuid]: 'Original note',
                },
            },
        ]);
        API.updateExperimentRecord.mockRejectedValue(
            Object.assign(new Error('API request failed'), {
                data: {
                    errors: {
                        data: ['Bad edited value'],
                    },
                },
            })
        );

        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('[data-experiment-action="edit-record"]')!.click();
        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        (document.getElementById(`field-${noteFieldUuid}`) as HTMLInputElement).value = 'Bad edited value';
        (document.getElementById('experiment-row-form') as HTMLInputElement).dispatchEvent(
            new Event('submit', { bubbles: true, cancelable: true })
        );

        await vi.waitFor(() => {
            expect(Utils.showNotification).toHaveBeenCalledWith('error', 'Bad edited value');
        });
    });

    it('closes the modal and surfaces a permission notice when the API returns 403 on submit', async () => {
        // Simulates an in-flight permission change (or a stale modal opened
        // before a deploy that tightened the gating contract).
        API.getExperiments
            .mockResolvedValueOnce([baseExperiment({ can_write: true, can_delete: true })])
            .mockResolvedValueOnce([baseExperiment({ can_write: false, can_delete: false })]);
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [noteFieldUuid]: 'Original note',
                },
            },
        ]);
        API.updateExperimentRecord.mockRejectedValue(
            Object.assign(new Error('Not authorized to perform this action.'), {
                status: 403,
                data: { detail: 'Not authorized to perform this action.' },
            })
        );

        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('[data-experiment-action="edit-record"]')!.click();
        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        (document.getElementById('experiment-row-form') as HTMLInputElement).dispatchEvent(
            new Event('submit', { bubbles: true, cancelable: true })
        );

        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeNull();
        });

        // Permission-specific notification — not the generic "Failed to update" message.
        expect(Utils.showNotification).toHaveBeenCalledWith(
            'error',
            'Your access to this experiment changed. Edit is no longer permitted.'
        );

        // Table re-renders with the read-only banner now visible.
        expect(container.querySelector<HTMLInputElement>('[data-experiment-readonly-notice]')!).toBeTruthy();
        expect(container.querySelector<HTMLInputElement>('[data-experiment-action="edit-record"]')!).toBeNull();
        expect(container.querySelector<HTMLInputElement>('#add-experiment-row-btn')!).toBeNull();
    });

    it('closes the add modal and refreshes access when create returns 403', async () => {
        API.getExperiments
            .mockResolvedValueOnce([baseExperiment({ can_write: true, can_delete: true })])
            .mockResolvedValueOnce([baseExperiment({ can_write: false, can_delete: false })]);
        API.createExperimentRecord.mockRejectedValue(
            Object.assign(new Error('Not authorized to perform this action.'), {
                status: 403,
                data: { detail: 'Not authorized to perform this action.' },
            })
        );

        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('#add-experiment-row-btn')!.click();
        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        (document.getElementById(`field-${measurementFieldUuid}`) as HTMLInputElement).value = '2025-01-03';
        (document.getElementById('experiment-row-form') as HTMLInputElement).dispatchEvent(
            new Event('submit', { bubbles: true, cancelable: true })
        );

        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeNull();
        });

        expect(Utils.showNotification).toHaveBeenCalledWith(
            'error',
            'Your access to this experiment changed. Add is no longer permitted.'
        );
        expect(container.querySelector<HTMLInputElement>('[data-experiment-readonly-notice]')!).toBeTruthy();
        expect(container.querySelector<HTMLInputElement>('#add-experiment-row-btn')!).toBeNull();
        expect(container.querySelector<HTMLInputElement>('[data-experiment-action="edit-record"]')!).toBeNull();
    });

    it('keeps the modal open and uses the generic error path for non-403 failures', async () => {
        // Regression guard: the new 403 branch must not swallow other errors.
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [noteFieldUuid]: 'Original note',
                },
            },
        ]);
        API.updateExperimentRecord.mockRejectedValue(
            Object.assign(new Error('boom'), {
                status: 500,
                data: { detail: 'boom' },
            })
        );

        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('[data-experiment-action="edit-record"]')!.click();
        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        (document.getElementById('experiment-row-form') as HTMLInputElement).dispatchEvent(
            new Event('submit', { bubbles: true, cancelable: true })
        );

        await vi.waitFor(() => {
            expect(API.updateExperimentRecord).toHaveBeenCalled();
        });

        // Modal stays open; user can fix and retry.
        expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        expect(Utils.showNotification).toHaveBeenCalledWith('error', 'boom');
        // No permission downgrade was applied — generic 5xx is not a perm signal.
        expect(container.querySelector<HTMLInputElement>('[data-experiment-readonly-notice]')!).toBeNull();
    });

    it('keeps the current rows when a stale selection request resolves late', async () => {
        const firstLoad = createDeferred();
        const secondLoad = createDeferred();

        API.getExperiments.mockResolvedValue([
            baseExperiment({ id: 'exp-1', name: 'Experiment One', description: '' }),
            baseExperiment({ id: 'exp-2', name: 'Experiment Two', description: '' }),
        ]);
        API.getExperimentData.mockImplementation((_stationId, experimentId) => {
            if (experimentId === 'exp-1') {
                return firstLoad.promise;
            }
            if (experimentId === 'exp-2') {
                return secondLoad.promise;
            }
            return Promise.resolve([]);
        });

        await renderStation();

        const selector = container.querySelector<HTMLInputElement>('#experiment-selector')!;
        selector.value = 'exp-1';
        selector.dispatchEvent(new Event('change', { bubbles: true }));
        selector.value = 'exp-2';
        selector.dispatchEvent(new Event('change', { bubbles: true }));

        secondLoad.resolve([
            {
                id: 'row-2',
                data: {
                    [measurementFieldUuid]: '2025-01-02',
                    [noteFieldUuid]: 'Second experiment row',
                },
            },
        ]);

        await vi.waitFor(() => {
            expect(container.innerHTML).toContain('Second experiment row');
        });

        firstLoad.resolve([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [noteFieldUuid]: 'First experiment row',
                },
            },
        ]);

        await vi.waitFor(() => {
            expect(container.innerHTML).toContain('Second experiment row');
            expect(container.innerHTML).not.toContain('First experiment row');
        });
    });

    it('renders a load error state instead of the empty-state add prompt', async () => {
        API.getExperimentData.mockRejectedValue(new Error('Backend exploded'));

        await renderStation();
        await selectExperiment();

        await vi.waitFor(() => {
            expect(container.innerHTML).toContain('Error Loading Records');
        });

        expect(container.innerHTML).toContain('Backend exploded');
        expect(container.innerHTML).not.toContain('No Data Records Yet');
        expect(container.innerHTML).not.toContain('Add First Record');
        expect(Utils.showNotification).toHaveBeenCalledWith('error', 'Backend exploded');
    });

    it('rejects malformed save responses instead of corrupting the in-memory rows', async () => {
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [noteFieldUuid]: 'Original note',
                },
            },
        ]);
        API.updateExperimentRecord.mockResolvedValue({
            data: {
                [measurementFieldUuid]: '2025-01-01',
                [noteFieldUuid]: 'Broken response',
            },
        });

        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('[data-experiment-action="edit-record"]')!.click();
        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        (document.getElementById(`field-${noteFieldUuid}`) as HTMLInputElement).value = 'Broken response';
        (document.getElementById('experiment-row-form') as HTMLInputElement).dispatchEvent(
            new Event('submit', { bubbles: true, cancelable: true })
        );

        await vi.waitFor(() => {
            expect(Utils.showNotification).toHaveBeenCalledWith(
                'error',
                'Server returned an experiment record without an id.'
            );
        });

        expect(container.innerHTML).toContain('Original note');
        expect(container.innerHTML).not.toContain('Broken response');
        expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
    });

    it('adds a new record through the shared modal flow', async () => {
        API.createExperimentRecord.mockResolvedValue({
            id: 'row-new',
            data: {
                [measurementFieldUuid]: '2025-01-03',
                [noteFieldUuid]: 'Added note',
            },
        });

        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('#add-experiment-row-btn')!.click();

        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        (document.getElementById(`field-${measurementFieldUuid}`) as HTMLInputElement).value = '2025-01-03';
        (document.getElementById(`field-${noteFieldUuid}`) as HTMLInputElement).value = 'Added note';

        (document.getElementById('experiment-row-form') as HTMLInputElement).dispatchEvent(
            new Event('submit', { bubbles: true, cancelable: true })
        );

        await vi.waitFor(() => {
            expect(API.createExperimentRecord).toHaveBeenCalledWith('st-1', 'exp-1', {
                [measurementFieldUuid]: '2025-01-03',
                [noteFieldUuid]: 'Added note',
            });
        });

        await vi.waitFor(() => {
            expect(container.innerHTML).toContain('Added note');
        });
        expect(Utils.showNotification).toHaveBeenCalledWith('success', 'Data record added successfully');
    });

    it('deletes a record through the confirmation modal', async () => {
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [noteFieldUuid]: 'Delete me',
                },
            },
        ]);

        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('[data-experiment-action="delete-record"]')!.click();

        await vi.waitFor(() => {
            expect((document.getElementById('delete-experiment-row-modal') as HTMLInputElement)).toBeTruthy();
        });

        document.querySelector<HTMLElement>('[data-delete-record-id="row-1"]')!.click();

        await vi.waitFor(() => {
            expect(API.deleteExperimentRecord).toHaveBeenCalledWith('row-1');
        });

        await vi.waitFor(() => {
            expect(container.innerHTML).not.toContain('Delete me');
        });
        expect(Utils.showNotification).toHaveBeenCalledWith('success', 'Record deleted successfully');
    });

    it('refreshes permissions after a delete 403 without downgrading write access', async () => {
        API.getExperiments
            .mockResolvedValueOnce([baseExperiment({ can_write: true, can_delete: true })])
            .mockResolvedValueOnce([baseExperiment({ can_write: true, can_delete: false })]);
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [noteFieldUuid]: 'Still here',
                },
            },
        ]);
        API.deleteExperimentRecord.mockRejectedValue(
            Object.assign(new Error('Not authorized to perform this action.'), {
                status: 403,
                data: { detail: 'Not authorized to perform this action.' },
            })
        );

        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('[data-experiment-action="delete-record"]')!.click();
        await vi.waitFor(() => {
            expect((document.getElementById('delete-experiment-row-modal') as HTMLInputElement)).toBeTruthy();
        });

        document.querySelector<HTMLElement>('[data-delete-record-id="row-1"]')!.click();

        await vi.waitFor(() => {
            expect(Utils.showNotification).toHaveBeenCalledWith(
                'error',
                'Your access to this experiment changed. Delete is no longer permitted.'
            );
        });

        expect(container.innerHTML).toContain('Still here');
        expect(container.querySelector<HTMLInputElement>('[data-experiment-readonly-notice]')!).toBeNull();
        expect(container.querySelector<HTMLInputElement>('#add-experiment-row-btn')!).toBeTruthy();
        expect(container.querySelector<HTMLInputElement>('[data-experiment-action="edit-record"]')!).toBeTruthy();
        expect(container.querySelector<HTMLInputElement>('[data-experiment-action="delete-record"]')!).toBeNull();
    });

    it('closes the record modal when the cancel button is clicked', async () => {
        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('#add-experiment-row-btn')!.click();

        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        document.querySelector<HTMLElement>('#experiment-record-modal [data-modal-close="record"].btn-secondary')!.click();

        expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeNull();
        expect(API.createExperimentRecord).not.toHaveBeenCalled();
    });

    it('closes the record modal when the Escape key is pressed', async () => {
        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('#add-experiment-row-btn')!.click();

        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));

        expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeNull();
    });

    it('closes the record modal when the overlay is clicked', async () => {
        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('#add-experiment-row-btn')!.click();

        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        const modal = (document.getElementById('experiment-record-modal') as HTMLInputElement);
        modal.dispatchEvent(new MouseEvent('click', { bubbles: true }));

        expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeNull();
    });

    it('blocks add submission when a required field is empty and shows inline error', async () => {
        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('#add-experiment-row-btn')!.click();

        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        // Leave the required Measurement Date input empty
        (document.getElementById('experiment-row-form') as HTMLInputElement).dispatchEvent(
            new Event('submit', { bubbles: true, cancelable: true })
        );

        expect(API.createExperimentRecord).not.toHaveBeenCalled();
        expect(Utils.showNotification).toHaveBeenCalledWith(
            'error',
            'Please fix validation errors before submitting'
        );

        const errorEl = (document.getElementById(`field-${measurementFieldUuid}-error`) as HTMLInputElement);
        expect(errorEl).toBeTruthy();
        expect(errorEl.textContent).toContain('required');
        expect(errorEl.classList.contains('hidden')).toBe(false);
    });

    it('validates non-select fields when they lose focus', async () => {
        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('#add-experiment-row-btn')!.click();

        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        const measurementInput = (document.getElementById(`field-${measurementFieldUuid}`) as HTMLInputElement);
        measurementInput.dispatchEvent(new FocusEvent('blur'));

        const errorEl = (document.getElementById(`field-${measurementFieldUuid}-error`) as HTMLInputElement);
        expect(errorEl.textContent).toContain('required');
        expect(errorEl.classList.contains('hidden')).toBe(false);
        expect(measurementInput.classList.contains('border-red-500')).toBe(true);
    });

    it('prefills boolean and select inputs from the row in edit mode', async () => {
        const boolFieldUuid = 'cccccccc-1111-2222-3333-444444444444';
        const selectFieldUuid = 'dddddddd-1111-2222-3333-444444444444';

        API.getExperiments.mockResolvedValue([
            baseExperiment({
                experiment_fields: [
                    {
                        id: measurementFieldUuid,
                        name: 'Measurement Date',
                        type: 'date',
                        order: 0,
                        required: true,
                    },
                    {
                        id: submitterFieldUuid,
                        name: 'Submitter Email',
                        type: 'text',
                        order: 1,
                        required: true,
                    },
                    {
                        id: boolFieldUuid,
                        name: 'Confirmed',
                        type: 'boolean',
                        order: 2,
                        required: false,
                    },
                    {
                        id: selectFieldUuid,
                        name: 'Quality',
                        type: 'select',
                        order: 3,
                        required: false,
                        options: ['low', 'medium', 'high'],
                    },
                ],
            }),
        ]);
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [boolFieldUuid]: true,
                    [selectFieldUuid]: 'medium',
                },
            },
        ]);

        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('[data-experiment-action="edit-record"]')!.click();

        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        const boolInput = (document.getElementById(`field-${boolFieldUuid}`) as HTMLInputElement);
        expect(boolInput.tagName).toBe('SELECT');
        expect(boolInput.value).toBe('true');

        const selectInput = (document.getElementById(`field-${selectFieldUuid}`) as HTMLSelectElement);
        expect(selectInput.tagName).toBe('SELECT');
        expect(selectInput.value).toBe('medium');
        // Make sure all the options were rendered.
        const optionValues = Array.from(selectInput.options).map(opt => opt.value);
        expect(optionValues).toEqual(expect.arrayContaining(['', 'low', 'medium', 'high']));
    });

    it('parses boolean field values when editing and submits booleans, not strings', async () => {
        const boolFieldUuid = 'cccccccc-1111-2222-3333-444444444444';

        API.getExperiments.mockResolvedValue([
            baseExperiment({
                experiment_fields: [
                    {
                        id: measurementFieldUuid,
                        name: 'Measurement Date',
                        type: 'date',
                        order: 0,
                        required: true,
                    },
                    {
                        id: submitterFieldUuid,
                        name: 'Submitter Email',
                        type: 'text',
                        order: 1,
                        required: true,
                    },
                    {
                        id: boolFieldUuid,
                        name: 'Confirmed',
                        type: 'boolean',
                        order: 2,
                        required: false,
                    },
                ],
            }),
        ]);
        API.getExperimentData.mockResolvedValue([
            {
                id: 'row-1',
                data: {
                    [measurementFieldUuid]: '2025-01-01',
                    [boolFieldUuid]: true,
                },
            },
        ]);
        API.updateExperimentRecord.mockImplementation(async (_id, data) => ({
            id: 'row-1',
            data,
        }));

        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('[data-experiment-action="edit-record"]')!.click();
        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        const boolInput = (document.getElementById(`field-${boolFieldUuid}`) as HTMLInputElement);
        boolInput.value = 'false';
        boolInput.dispatchEvent(new Event('change', { bubbles: true }));

        (document.getElementById('experiment-row-form') as HTMLInputElement).dispatchEvent(
            new Event('submit', { bubbles: true, cancelable: true })
        );

        await vi.waitFor(() => {
            expect(API.updateExperimentRecord).toHaveBeenCalled();
        });

        const sentPayload = API.updateExperimentRecord.mock.calls[0]![1] as ExperimentValues;
        expect(sentPayload[boolFieldUuid]).toBe(false);
        expect(typeof sentPayload[boolFieldUuid]).toBe('boolean');
    });

    it('restores a previously-set body overflow value when the modal closes', async () => {
        // Unrelated code set this before the experiment modal opened.
        // Closing the modal must NOT clobber it back to empty.
        document.body.style.overflow = 'scroll';

        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('#add-experiment-row-btn')!.click();
        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        // Inside the modal, scroll is locked by us.
        expect(document.body.style.overflow).toBe('hidden');

        StationExperiments.closeRecordModal();

        expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeNull();
        expect(document.body.style.overflow).toBe('scroll');
    });

    it('restores empty body overflow when nothing was set before opening the modal', async () => {
        document.body.style.overflow = '';

        await renderStation();
        await selectExperiment();

        container.querySelector<HTMLInputElement>('#add-experiment-row-btn')!.click();
        await vi.waitFor(() => {
            expect((document.getElementById('experiment-record-modal') as HTMLInputElement)).toBeTruthy();
        });

        expect(document.body.style.overflow).toBe('hidden');

        StationExperiments.closeRecordModal();

        expect(document.body.style.overflow).toBe('');
    });
});
