import { Config } from '../config.ts';
import { State } from '../state.ts';
import { Layers } from './layers.ts';

describe('Layers visibility selectors', () => {
    beforeEach(() => {
        State.resetLayerState();
        Config._projects = [{ id: '7' }, { id: 'other' }];
    });

    afterEach(() => vi.restoreAllMocks());

    it('normalizes IDs and keeps unknown individual preferences visible', () => {
        expect(Layers.isProjectVisible(7)).toBe(true);
        State.projectLayerStates.set('7', false);
        expect(Layers.isProjectVisible(7)).toBe(false);
        State.projectLayerStates.set('7', true);
        expect(Layers.isProjectVisible(7)).toBe(true);
    });

    it('retains the individual preference fallback when state access throws', () => {
        vi.spyOn(State.projectLayerStates, 'get').mockImplementation(() => {
            throw new Error('Unavailable preference');
        });
        expect(Layers.isProjectVisible(7)).toBe(true);
    });

    it('uses effective state before invoking the receiver’s individual selector', () => {
        const receiver = Object.create(Layers) as typeof Layers;
        const individualPreference = vi.fn(() => false);
        receiver.isProjectVisible = individualPreference;
        expect(receiver.isProjectEffectivelyVisible(7)).toBe(false);
        expect(individualPreference).toHaveBeenCalledExactlyOnceWith('7');
        State.effectiveProjectVisibility.set('7', true);
        expect(receiver.isProjectEffectivelyVisible(7)).toBe(true);
        expect(individualPreference).toHaveBeenCalledTimes(1);
    });

    it('keeps visible project enumeration bound to its receiver', () => {
        const receiver = Object.create(Layers) as typeof Layers;
        const effectiveVisibility = vi.fn((id: string | number) => id === '7');
        receiver.isProjectEffectivelyVisible = effectiveVisibility;
        expect(receiver.getVisibleProjectIds()).toEqual(['7']);
        expect(effectiveVisibility).toHaveBeenNthCalledWith(1, '7');
        expect(effectiveVisibility).toHaveBeenNthCalledWith(2, 'other');
    });

    it('reads replacement state containers after a layer reset', () => {
        State.projectLayerStates.set('7', false);
        State.effectiveProjectVisibility.set('7', false);
        expect(Layers.isProjectEffectivelyVisible(7)).toBe(false);
        State.resetLayerState();
        expect(Layers.isProjectEffectivelyVisible(7)).toBe(true);
    });
});
