import type { MapActionRegistry } from '../../../../../ts-types/domain/map-actions.ts';
import type { Mock, MockInstance } from 'vitest';
import { initMapActionDispatcher as initializeDispatcher } from './action_dispatcher.ts';

describe('map action dispatcher', () => {
    it('delegates inert action data without executable HTML attributes', () => {
        const action = vi.fn();
        initMapActionDispatcher({ example: { run: action } });
        document.body.innerHTML = `
            <button data-map-action="example.run" data-map-args="[&quot;station-1&quot;,2]">
                <span>Run</span>
            </button>
        `;

        document.querySelector('span')!.click();

        expect(action).toHaveBeenCalledWith('station-1', 2);
        expect(document.querySelectorAll('[onclick], [onchange]')).toHaveLength(0);
    });
});

describe('dispatcher ownership, repetition and failures', () => {
    let add: MockInstance<typeof document.addEventListener>;
    let handlers: Map<string, (event: { target: Node }) => void>;
    let initialize: (registry: unknown) => void;
    beforeEach(async () => {
        vi.resetModules(); handlers = new Map();
        add = vi.spyOn(document, 'addEventListener').mockImplementation((name, handler) => { handlers.set(name, handler as unknown as (event: { target: Node }) => void); });
        initialize = (await import('./action_dispatcher.ts')).initMapActionDispatcher as (registry: unknown) => void;
    });
    afterEach(() => { vi.restoreAllMocks(); document.body.innerHTML = ''; });
    function invoke(action: string, args?: string, event = 'click') {
        const button = document.createElement('button'); button.dataset.mapAction = action;
        if (args !== undefined) button.dataset.mapArgs = args;
        if (event === 'change') button.dataset.mapEvent = 'change';
        handlers.get(event)!({ target: button });
    }
    it('shallow-copies the registry, retains owner identity and ignores returned pending promises', () => {
        const run = vi.fn(() => new Promise(() => {}));
        const owner: { run: Mock<(...args: unknown[]) => unknown> } = { run }; const registry = { example: owner };
        initialize(registry); registry.example = { run: vi.fn() };
        expect(invoke('example.run', '[1,"two"]')).toBeUndefined();
        expect(run.mock.contexts[0]).toBe(owner); expect(run).toHaveBeenCalledWith(1, 'two');
        owner.run = vi.fn(); invoke('example.run'); expect(owner.run).toHaveBeenCalledExactlyOnceWith();
    });
    it('replaces the active registry while installing only one click and change listener', () => {
        const first = vi.fn(); const second = vi.fn();
        initialize({ example: { run: first } }); initialize({ example: { run: second } });
        expect(add).toHaveBeenCalledTimes(2);
        invoke('example.run', '[]', 'change'); expect(first).not.toHaveBeenCalled(); expect(second).toHaveBeenCalledTimes(1);
    });
    it('ignores absent namespace separators but throws the original unknown-action and JSON errors', () => {
        initialize({ example: { run: vi.fn() } });
        invoke(''); invoke('.run'); invoke('example');
        expect(() => invoke('missing.run')).toThrow('Unknown map action: missing.run');
        expect(() => invoke('example.run', '{')).toThrow(SyntaxError);
    });
    it('preserves thrown value identity and the unguarded non-element event target failure', () => {
        const failure = { message: 'Thrown object' }; initialize({ example: { run() { throw failure as unknown; } } });
        try { invoke('example.run'); expect.unreachable(); } catch (error) { expect(error).toBe(failure); }
        expect(() => handlers.get('click')!({ target: document.createTextNode('text') })).toThrow(TypeError);
    });
});

function initMapActionDispatcher(registry: unknown) { initializeDispatcher(registry as MapActionRegistry); }
