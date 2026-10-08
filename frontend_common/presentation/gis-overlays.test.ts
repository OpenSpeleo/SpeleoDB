import { buildGISOverlayListMarkup, buildGISLayerListMarkup, buildGISGeometryListMarkup } from './gis-overlays.ts';
import * as layerController from '../controllers/gis-layers.ts';
import * as geometryController from '../controllers/gis-geometries.ts';

afterEach(() => {
    vi.doUnmock('../features/gis-layers.ts');
    vi.resetModules();
});

it('retains controller renderer exports as the same shared display functions', () => {
    expect(layerController.buildGISOverlayListMarkup).toBe(buildGISOverlayListMarkup);
    expect(layerController.buildGISLayerListMarkup).toBe(buildGISLayerListMarkup);
    expect(geometryController.buildGISGeometryListMarkup).toBe(buildGISGeometryListMarkup);
});

it('loads the geometry controller without importing the GIS layer upload feature', async () => {
    vi.resetModules();
    vi.doMock('../features/gis-layers.ts', () => { throw new Error('Layer upload must not load on the geometry route'); });
    const controller = await import('../controllers/gis-geometries.ts');
    expect(controller.init).toBeTypeOf('function');
    expect(controller.buildGISGeometryListMarkup([]).cardsHtml).toContain('Create a line or polygon');
});
