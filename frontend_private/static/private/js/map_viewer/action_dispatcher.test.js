import { initMapActionDispatcher } from './action_dispatcher.js';

describe('map action dispatcher', () => {
    it('delegates inert action data without executable HTML attributes', () => {
        const action = vi.fn();
        initMapActionDispatcher({ example: { run: action } });
        document.body.innerHTML = `
            <button data-map-action="example.run" data-map-args="[&quot;station-1&quot;,2]">
                <span>Run</span>
            </button>
        `;

        document.querySelector('span').click();

        expect(action).toHaveBeenCalledWith('station-1', 2);
        expect(document.querySelectorAll('[onclick], [onchange]')).toHaveLength(0);
    });
});
