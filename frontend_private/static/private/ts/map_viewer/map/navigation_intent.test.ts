import { Evented, type MapEventType } from 'maplibre-gl';
import { beginMapNavigation, cancelMapNavigation, resetMapNavigation } from './navigation_intent.ts';

class CameraEvents extends Evented<Pick<MapEventType, 'movestart'>> {}

afterEach(() => resetMapNavigation());

it('shares latest camera intent between web entity controllers', async () => {
    const otherConsumer = await import('./navigation_intent.ts');
    const map = new CameraEvents();
    const gps = beginMapNavigation(map, 'gps:one');
    const project = otherConsumer.beginMapNavigation(map, 'project:two');
    expect(gps.isCurrent()).toBe(false);
    expect(project.isCurrent()).toBe(true);
    cancelMapNavigation('gps:one');
    expect(project.isCurrent()).toBe(true);
    otherConsumer.cancelMapNavigation('project:two');
    expect(project.isCurrent()).toBe(false);
});

it('binds the web owner to map gestures and releases it on composition teardown', () => {
    const map = new CameraEvents();
    resetMapNavigation(map);
    const intent = beginMapNavigation(map, 'project:one');
    map.fire('movestart', { originalEvent: new Event('pointerdown') });
    expect(intent.isCurrent()).toBe(false);
    const pending = beginMapNavigation(map, 'project:two');
    resetMapNavigation();
    expect(pending.isCurrent()).toBe(false);
    expect(map.listens('movestart')).toBe(false);
});
