import type { ModuleMock } from '../../../../../../ts-types/testing/vitest/mocks.ts';
import type { ViewerExplorationLead } from '../../../../../../ts-types/domain/map-state.ts';
import { ExplorationLeadUI } from './ui.ts';
import { configureRuntimeContext } from '../runtime_context.ts';

vi.mock('./manager.ts', () => ({
    ExplorationLeadManager: {
        createLead: vi.fn(),
        updateLead: vi.fn(),
        deleteLead: vi.fn(),
    },
}));

vi.mock('../state.ts', () => ({
    State: {
        explorationLeads: new Map(),
    },
}));

vi.mock('../config.ts', () => ({
    Config: {
        getScopedAccess: vi.fn(() => ({ write: false, delete: false })),
    },
}));

vi.mock('../map/layers.ts', () => ({
    Layers: {
        refreshExplorationLeadsLayer: vi.fn(),
        reorderLayers: vi.fn(),
    },
}));

vi.mock('../utils.ts', () => {
    const escapeHtml = (text: string | number | null | undefined) => {
        if (text === null || text === undefined) return '';
        const str = String(text);
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    };
    const RAW = Symbol('RAW_HTML');
    return {
        Utils: {
            showNotification: vi.fn(),
            escapeHtml,
            raw: (html: unknown) => ({ [RAW]: true, value: String(html) }),
            safeHtml: (strings: TemplateStringsArray, ...values: unknown[]) => strings.reduce((r, s, i) => {
                if (i < values.length) {
                    const v = values[i];
                    if (v && typeof v === 'object' && RAW in v) return r + s + (v as unknown as { value: string }).value;
                    return r + s + escapeHtml(v as string);
                }
                return r + s;
            }, ''),
        },
    };
});

vi.mock('../components/modal.ts', () => ({
    Modal: {
        base: vi.fn((id: string, title: string, content: string, footer: string) => `<div id="${id}">${content}${footer}</div>`),
        open: vi.fn((id: string, html: string, cb?: () => void) => {
            document.body.insertAdjacentHTML('beforeend', html);
            if (cb) cb();
        }),
        close: vi.fn(),
    },
}));

import { State } from '../state.ts';

describe('ExplorationLeadUI coordinate formatting', () => {
    beforeEach(() => {
        document.body.innerHTML = '';
        configureRuntimeContext({ icons: { explorationLead: 'https://example.test/lead.png' } });
        vi.clearAllMocks();
    });

    afterEach(() => {
        document.body.innerHTML = '';
        configureRuntimeContext({});
    });

    describe('showCreateModal', () => {
        it('renders formatted coordinates from numeric inputs', () => {
            ExplorationLeadUI.showCreateModal([6.123456789, 46.987654321], 'Line A', 'p1');

            const html = document.body.innerHTML;
            expect(html).toContain('46.9876543');
            expect(html).toContain('6.1234568');
        });

        it('handles string coordinates without throwing', () => {
            expect(() => {
                ExplorationLeadUI.showCreateModal(['6.123456789', '46.987654321'], 'Line A', 'p1');
            }).not.toThrow();

            const html = document.body.innerHTML;
            expect(html).toContain('46.9876543');
            expect(html).toContain('6.1234568');
        });
    });

    describe('showDetailsModal', () => {
        it('renders formatted coordinates from numeric state values', () => {
            State.explorationLeads.set('lead-1', {
                id: 'lead-1',
                coordinates: [6.123456789, 46.987654321],
                description: 'Test lead',
                projectId: 'p1',
                lineName: 'Line A',
            } as unknown as ViewerExplorationLead);

            ExplorationLeadUI.showDetailsModal('lead-1');

            const html = document.body.innerHTML;
            expect(html).toContain('46.9876543');
            expect(html).toContain('6.1234568');
        });

        it('handles string coordinates in state without throwing', () => {
            State.explorationLeads.set('lead-2', {
                id: 'lead-2',
                coordinates: ['6.5', '46.5'],
                description: 'Test lead',
                projectId: 'p1',
                lineName: 'Line B',
            } as unknown as ViewerExplorationLead);

            expect(() => {
                ExplorationLeadUI.showDetailsModal('lead-2');
            }).not.toThrow();

            const html = document.body.innerHTML;
            expect(html).toContain('46.5000000');
            expect(html).toContain('6.5000000');
        });
    });
});

import { Config as originalConfig } from '../config.ts';
import { Utils as originalUtils } from '../utils.ts';
import { Layers as originalLayers } from '../map/layers.ts';
import { Modal as originalModal } from '../components/modal.ts';
import { ExplorationLeadManager as originalExplorationLeadManager } from './manager.ts';

describe('ExplorationLeadUI mutation and permission contracts', () => {
    beforeEach(() => {
        vi.clearAllMocks(); document.body.innerHTML = ''; State.explorationLeads.clear();
        Config.getScopedAccess.mockReturnValue({ read: true, write: false, delete: false });
    });
    afterEach(() => { vi.restoreAllMocks(); document.body.innerHTML = ''; });
    it('keeps the create callback async, rejects empty descriptions and updates the existing cached object on success', async () => {
        const cached: ViewerExplorationLead = { id: 'lead', coordinates: [1, 2], lineName: '', description: '', projectId: null, createdAt: undefined }; State.explorationLeads.set('lead', cached);
        ExplorationLeadManager.createLead.mockResolvedValue({ id: 'lead', project: 'project', longitude: '1', latitude: '2' });
        const coordinates: [number, number] = [1, 2];
        ExplorationLeadUI.showCreateModal(coordinates, '<Line>', 'project');
        const form = (document.getElementById('create-lead-form') as HTMLFormElement);
        expect(form.onsubmit!.constructor.name).toBe('AsyncFunction');
        await form.onsubmit!(new Event('submit') as SubmitEvent); expect(ExplorationLeadManager.createLead).not.toHaveBeenCalled();
        (document.getElementById('lead-description') as HTMLTextAreaElement).value = '  Passage  ';
        await form.onsubmit!(new Event('submit') as SubmitEvent);
        expect(ExplorationLeadManager.createLead).toHaveBeenCalledExactlyOnceWith('project', coordinates, 'Passage');
        expect(State.explorationLeads.get('lead')).toBe(cached); expect(cached.lineName).toBe('<Line>');
        expect(Layers.refreshExplorationLeadsLayer).toHaveBeenCalledTimes(1); expect(Layers.reorderLayers).toHaveBeenCalledTimes(1);
        expect(Modal.close).toHaveBeenCalledWith('create-lead-modal');
    });
    it('catches create failures and restores loading controls without closing the form', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});
        ExplorationLeadManager.createLead.mockRejectedValue({ message: 'Rejected' });
        ExplorationLeadUI.showCreateModal([1, 2], 'Line', 'project');
        (document.getElementById('lead-description') as HTMLTextAreaElement).value = 'Passage';
        await expect((document.getElementById('create-lead-form') as HTMLFormElement).onsubmit!(new Event('submit') as SubmitEvent)).resolves.toBeUndefined();
        expect(Utils.showNotification).toHaveBeenCalledWith('error', 'Rejected');
        expect((document.getElementById('create-lead-btn-loading') as HTMLElement).classList.contains('hidden')).toBe(true);
        expect(Modal.close).not.toHaveBeenCalled();
    });
    it.each([[false, false], [true, false], [true, true]])('retains scoped write=%s/delete=%s controls', (write, remove) => {
        State.explorationLeads.set('lead', { id: 'lead', coordinates: [1, 2], projectId: 'project', description: '<script>text</script>' } as unknown as ViewerExplorationLead);
        Config.getScopedAccess.mockReturnValue({ read: true, write, delete: remove });
        ExplorationLeadUI.showDetailsModal('lead');
        expect(Config.getScopedAccess).toHaveBeenCalledWith('project', 'project');
        expect((document.getElementById('lead-description-edit') as HTMLTextAreaElement).disabled).toBe(!write);
        expect(Boolean((document.getElementById('save-lead-btn') as HTMLElement))).toBe(write);
        expect(Boolean((document.getElementById('delete-lead-btn') as HTMLElement))).toBe(write && remove);
        expect(document.querySelector('script')).toBeNull();
    });
    it('reports missing leads without opening a dialog', () => {
        ExplorationLeadUI.showDetailsModal('absent');
        expect(Utils.showNotification).toHaveBeenCalledWith('error', 'Exploration lead not found'); expect(Modal.open).not.toHaveBeenCalled();
    });
    it('retains the UI receiver for delete navigation and trims updates, including empty descriptions', async () => {
        State.explorationLeads.set('lead', { id: 'lead', coordinates: [1, 2], projectId: 'project', lineName: 'Line' } as unknown as ViewerExplorationLead);
        Config.getScopedAccess.mockReturnValue({ read: true, write: true, delete: true });
        const confirm = vi.spyOn(ExplorationLeadUI, 'showDeleteConfirmModal').mockImplementation(() => {});
        ExplorationLeadUI.showDetailsModal('lead');
        (document.getElementById('delete-lead-btn') as HTMLElement).click();
        expect(confirm.mock.contexts[0]).toBe(ExplorationLeadUI);
        expect(confirm).toHaveBeenCalledWith('lead', 'Line');
        (document.getElementById('lead-description-edit') as HTMLTextAreaElement).value = '  ';
        await (document.getElementById('save-lead-btn') as HTMLElement).onclick!(new MouseEvent("click") as PointerEvent);
        expect(ExplorationLeadManager.updateLead).toHaveBeenCalledWith('lead', { description: '' });
        expect(Modal.close).toHaveBeenCalledWith('lead-details-modal');
    });
    it('awaits deletion before refreshing and contains ordinary rejected objects', async () => {
        vi.spyOn(console, 'error').mockImplementation(() => {});
        ExplorationLeadManager.deleteLead.mockRejectedValueOnce({ message: 'Denied' });
        ExplorationLeadUI.showDeleteConfirmModal('lead', '<Line>');
        await (document.getElementById('confirm-delete-lead-btn') as HTMLElement).onclick!(new MouseEvent("click") as PointerEvent);
        expect(Utils.showNotification).toHaveBeenCalledWith('error', 'Denied');
        expect(Layers.refreshExplorationLeadsLayer).not.toHaveBeenCalled();
        ExplorationLeadManager.deleteLead.mockResolvedValueOnce({} as unknown as Awaited<ReturnType<typeof originalExplorationLeadManager.deleteLead>>);
        await (document.getElementById('confirm-delete-lead-btn') as HTMLElement).onclick!(new MouseEvent("click") as PointerEvent);
        expect(Layers.refreshExplorationLeadsLayer).toHaveBeenCalledTimes(1);
        expect(Modal.close).toHaveBeenCalledWith('delete-lead-modal');
    });
});

const Config = originalConfig as unknown as ModuleMock<typeof originalConfig>;

const Utils = originalUtils as unknown as ModuleMock<typeof originalUtils>;

const Layers = originalLayers as unknown as ModuleMock<typeof originalLayers>;

const Modal = originalModal as unknown as ModuleMock<typeof originalModal>;

const ExplorationLeadManager = originalExplorationLeadManager as unknown as ModuleMock<typeof originalExplorationLeadManager>;
