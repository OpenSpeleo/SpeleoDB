import { beginMapNavigation, cancelMapNavigation, resetMapNavigation } from './navigation_intent.ts';
import type { NavigationGesture } from '../../../../../../ts-types/domain/map-runtime.ts';

afterEach(() => resetMapNavigation());

it('shares latest camera intent across entity types', () => {
    const map = {};
    const gps = beginMapNavigation(map, 'gps:one');
    const project = beginMapNavigation(map, 'project:two');
    expect(gps.isCurrent()).toBe(false);
    expect(project.isCurrent()).toBe(true);
});

it('hiding an unrelated entity preserves navigation, but hiding its target cancels it', () => {
    const intent = beginMapNavigation({}, 'gis-layer:one');
    cancelMapNavigation('gps:other');
    expect(intent.isCurrent()).toBe(true);
    cancelMapNavigation('gis-layer:one');
    expect(intent.isCurrent()).toBe(false);
});

it('cancels on map replacement, teardown and user camera gestures', () => {
    const handlers: { movestart?: (event: NavigationGesture) => void } = {};
    const map = { on: vi.fn((event: 'movestart', handler: (event: NavigationGesture) => void) => { handlers[event] = handler; }), off: vi.fn() };
    const intent = beginMapNavigation(map, 'project:one');
    handlers.movestart!({});
    expect(intent.isCurrent()).toBe(true);
    handlers.movestart!({ originalEvent: new Event('pointerdown') });
    expect(intent.isCurrent()).toBe(false);
    const replacement = beginMapNavigation(map, 'project:one');
    resetMapNavigation({});
    expect(map.off).toHaveBeenCalledWith('movestart', expect.any(Function));
    expect(replacement.isCurrent()).toBe(false);
    const pending = beginMapNavigation({}, 'project:one');
    resetMapNavigation();
    expect(pending.isCurrent()).toBe(false);
});

it('keeps absent-map intents false and permits maps without gesture subscription methods', () => {
    expect(beginMapNavigation(null, 'missing').isCurrent()).toBe(false);
    const map = {};
    const intent = beginMapNavigation(map, 'present');
    expect(intent.isCurrent()).toBe(true);
    cancelMapNavigation();
    expect(intent.isCurrent()).toBe(false);
});
