import type { MapActionRegistry } from '../../../../../ts-types/domain/map-actions.ts';
import { initMapActionDispatcher } from './action_dispatcher.ts';

const failures: unknown[] = [];
function recordFailure(event: ErrorEvent) {
    event.preventDefault();
    failures.push(event.error);
}
beforeEach(() => {
    window.addEventListener('error', recordFailure);
});
afterEach(() => {
    window.removeEventListener('error', recordFailure);
    document.body.innerHTML = '';
    expect(failures.splice(0)).toEqual([]);
});

function initialize(registry: unknown) {
    initMapActionDispatcher(registry as MapActionRegistry);
}
function invoke(action: string, args?: string, event = 'click') {
    const button = document.createElement('button');
    button.dataset.mapAction = action;
    if (args !== undefined) button.dataset.mapArgs = args;
    if (event === 'change') button.dataset.mapEvent = 'change';
    document.body.append(button);
    button.dispatchEvent(new Event(event, { bubbles: true }));
}

it('delegates inert action data through the real DOM without executable attributes', () => {
    const calls: unknown[][] = [];
    initialize({ example: { run(...args: unknown[]) { calls.push(args); } } });
    document.body.innerHTML = `
        <button data-map-action="example.run" data-map-args="[&quot;station-1&quot;,2]">
            <span>Run</span>
        </button>
    `;
    document.querySelector('span')!.click();
    expect(calls).toEqual([['station-1', 2]]);
    expect(document.querySelectorAll('[onclick], [onchange]')).toHaveLength(0);
});

it('retains the original registry owner while accepting a replacement callback', () => {
    const calls: Array<{ owner: unknown; args: unknown[] }> = [];
    const owner = {
        run(...args: unknown[]) {
            calls.push({ owner: this, args });
            return new Promise(() => {});
        },
    };
    const registry: { example: unknown } = { example: owner };
    initialize(registry);
    registry.example = { run() { throw new Error('Replaced registry owner'); } };
    expect(invoke('example.run', '[1,"two"]')).toBeUndefined();
    expect(calls).toEqual([{ owner, args: [1, 'two'] }]);
    const replacementCalls: unknown[][] = [];
    Object.assign(owner, { run(...args: unknown[]) { replacementCalls.push(args); } });
    invoke('example.run');
    expect(replacementCalls).toEqual([[]]);
});

it('replaces the active registry without delivering duplicate click or change actions', () => {
    let originalCalls = 0;
    let currentCalls = 0;
    initialize({ example: { run() { originalCalls += 1; } } });
    initialize({ example: { run() { currentCalls += 1; } } });
    invoke('example.run');
    invoke('example.run', '[]', 'change');
    expect(originalCalls).toBe(0);
    expect(currentCalls).toBe(2);
});

it('ignores absent namespace separators and preserves unknown-action and JSON errors', () => {
    initialize({ example: { run() {} } });
    invoke('');
    invoke('.run');
    invoke('example');
    expect(failures).toEqual([]);
    invoke('missing.run');
    expect(failures.shift()).toEqual(new Error('Unknown map action: missing.run'));
    invoke('example.run', '{');
    expect(failures.shift()).toBeInstanceOf(SyntaxError);
});

it('preserves a thrown callback value through native event dispatch', () => {
    const failure = { message: 'Thrown object' };
    initialize({ example: { run() { throw failure as unknown; } } });
    invoke('example.run');
    expect(failures.shift()).toBe(failure);
});
