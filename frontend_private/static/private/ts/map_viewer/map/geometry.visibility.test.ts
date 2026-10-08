import { Config } from '../config.ts';
import { ProjectPanel } from '../components/project_panel.ts';
import { State } from '../state.ts';
import { Geometry } from './geometry.ts';
import { Layers } from './layers.ts';

describe.each(['findMagneticSnapPoint', 'findNearestSnapPointWithinRadius'] as const)(
    '%s project visibility', method => {
        beforeEach(() => {
            State.resetLayerState();
            State.map = null;
            localStorage.clear();
            ProjectPanel._countryVisibility = {};
            Config._projects = [{ id: '1', country: 'MX' }, { id: '2', country: 'US' }];
            Geometry.cachePreparedSnapPoints('1', [
                { coordinates: [10, 20], lineName: 'MX survey', type: 'start', lineIndex: 0 },
            ]);
        });

        afterEach(() => {
            Geometry.cachePreparedSnapPoints('1', []);
            Geometry.cachePreparedSnapPoints('2', []);
            ProjectPanel.destroy();
            State.resetLayerState();
            vi.restoreAllMocks();
        });

        it('immediately excludes a project when its country closes and restores it when reopened', async () => {
            ProjectPanel.toggleProject('1', true);
            expect(Geometry[method]([10, 20]).snapped).toBe(true);
            ProjectPanel._saveCountryVisibility({ MX: false });
            ProjectPanel._syncCountryToMap('MX', [Config.projects[0]!]);
            expect(Layers.isProjectVisible('1')).toBe(true);
            expect(Geometry[method]([10, 20]).snapped).toBe(false);
            ProjectPanel._saveCountryVisibility({ MX: true });
            ProjectPanel._syncCountryToMap('MX', [Config.projects[0]!]);
            expect(Geometry[method]([10, 20]).snapped).toBe(true);
            await Layers.whenDisplayApplied();
        });

        it('keeps an individually hidden project excluded when its country opens', async () => {
            ProjectPanel._saveCountryVisibility({ MX: false });
            ProjectPanel.toggleProject('1', false);
            ProjectPanel._saveCountryVisibility({ MX: true });
            ProjectPanel._syncCountryToMap('MX', [Config.projects[0]!]);
            expect(Geometry[method]([10, 20]).snapped).toBe(false);
            expect(Layers.isProjectVisible('1')).toBe(false);
            await Layers.whenDisplayApplied();
        });

        it('chooses a visible project instead of a closer endpoint behind a country gate', async () => {
            Geometry.cachePreparedSnapPoints('2', [
                { coordinates: [10.000001, 20], lineName: 'US survey', type: 'start', lineIndex: 0 },
            ]);
            ProjectPanel._saveCountryVisibility({ MX: false });
            ProjectPanel._syncCountryToMap('MX', [Config.projects[0]!]);
            expect(Geometry[method]([10, 20])).toMatchObject({ snapped: true, projectId: '2' });
            expect(Geometry.findMagneticSnapPoint([10, 20], '1').snapped).toBe(false);
            await Layers.whenDisplayApplied();
        });

        it('invalidates snap eligibility without rescanning or discarding cached endpoints', async () => {
            const coordinates = vi.fn(() => [[10, 20], [10.001, 20]]);
            Geometry.cacheLineFeatures('1', {
                features: [{
                    type: 'Feature', properties: { section_name: 'Cached survey' },
                    geometry: { type: 'LineString', get coordinates() { return coordinates(); } },
                }],
            });
            expect(coordinates).toHaveBeenCalledOnce();
            const cachedCount = Geometry.getSnapInfo().totalSnapPoints;
            const cache = vi.spyOn(Geometry, 'cacheLineFeatures');
            const preparedCache = vi.spyOn(Geometry, 'cachePreparedSnapPoints');
            for (let index = 0; index < 10; index++) {
                const visible = index % 2 === 0;
                ProjectPanel._saveCountryVisibility({ MX: visible });
                ProjectPanel._syncCountryToMap('MX', [Config.projects[0]!]);
                expect(Geometry[method]([10, 20]).snapped).toBe(visible);
            }
            await Layers.whenDisplayApplied();
            expect(coordinates).toHaveBeenCalledOnce();
            expect(cache).not.toHaveBeenCalled();
            expect(preparedCache).not.toHaveBeenCalled();
            expect(Geometry.getSnapInfo().totalSnapPoints).toBe(cachedCount);
        });
    },
);
