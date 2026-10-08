import type { Mock } from 'vitest';
import type { RendererLayer, RendererImage, RendererMarkerOptions, RendererValue } from '../../../../../../ts-types/domain/renderer.ts';
import type { MeasurementCollection, MeasurementImageOptions, MeasurementRendererMap, MeasurementSourceDefinition } from '../../../../../../ts-types/domain/measurement-renderer.ts';

interface TestSource extends MeasurementSourceDefinition { setData: Mock<(this: TestSource, data: MeasurementCollection) => void> }
interface TestMarker { options: RendererMarkerOptions; coordinate?: readonly number[]; setLngLat: Mock<(coordinate: readonly number[]) => TestMarker>; addTo: Mock<(map: { getContainer(): HTMLElement }) => TestMarker>; remove: Mock<() => TestMarker> }
import { DEFAULTS } from '../config.ts';
import { createMeasurement } from './geometry.ts';
import { MeasurementRenderer, MEASUREMENT_LAYER_PREFIX } from './renderer.ts';

function makeMap() {
    const sources = new Map<string, TestSource>();
    const layers = new Map<string, RendererLayer>();
    const images = new Map<string, { image: RendererImage; options: MeasurementImageOptions }>();
    const listeners = new Map<string, () => void>();
    const container = document.createElement('div');
    return {
        sources, layers, images, listeners,
        getContainer: () => container,
        getStyle: vi.fn<() => { layers: RendererLayer[] } | undefined>(() => ({ layers: [...layers.values()] })),
        getSource: (id: string) => sources.get(id), getLayer: (id: string) => layers.get(id), hasImage: (id: string) => images.has(id),
        addSource: vi.fn((id: string, definition: MeasurementSourceDefinition) => sources.set(id, { ...definition, setData: vi.fn(function(this: TestSource, data: MeasurementCollection) { this.data = data; }) })),
        addLayer: vi.fn((layer: RendererLayer) => layers.set(layer.id, layer)), addImage: vi.fn((id: string, image: RendererImage, options: MeasurementImageOptions) => images.set(id, { image, options })),
        removeSource: vi.fn((id: string) => sources.delete(id)), removeLayer: vi.fn((id: string) => layers.delete(id)), removeImage: vi.fn((id: string) => images.delete(id)),
        on: vi.fn((event: string, callback: () => void) => listeners.set(event, callback)), off: vi.fn((event: string, callback: () => void) => { if (listeners.get(event) === callback) listeners.delete(event); }),
    };
}

function widthAtZoom(expression: RendererValue | undefined, zoom: number): number {
    expect((expression as RendererValue[]).slice(0, 3)).toEqual(['interpolate', ['linear'], ['zoom']]);
    const stops = (expression as RendererValue[]).slice(3) as number[];
    if (zoom <= stops[0]!) return stops[1]!;
    for (let index = 2; index < stops.length; index += 2) {
        if (zoom <= stops[index]!) {
            const fraction = (zoom - stops[index - 2]!) / (stops[index]! - stops[index - 2]!);
            return stops[index - 1]! + fraction * (stops[index + 1]! - stops[index - 1]!);
        }
    }
    return stops.at(-1)!;
}

describe('measurement native renderer', () => {
    let map: ReturnType<typeof makeMap> & { isStyleLoaded?: Mock<() => boolean> };
    let renderer: MeasurementRenderer;
    let frames: Map<number, FrameRequestCallback>;
    let markers: TestMarker[];
    beforeEach(() => {
        map = makeMap();
        frames = new Map();
        markers = [];
        let sequence = 0;
        vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { frames.set(++sequence, callback); return sequence; });
        vi.stubGlobal('cancelAnimationFrame', (id: number) => frames.delete(id));
        vi.stubGlobal('__mapRenderer', { Marker: class implements TestMarker {
            declare options: RendererMarkerOptions;
            declare coordinate?: readonly number[];
            declare setLngLat: TestMarker['setLngLat'];
            declare addTo: TestMarker['addTo'];
            declare remove: TestMarker['remove'];
            constructor(options: RendererMarkerOptions) {
                this.options = options;
                this.setLngLat = vi.fn((coordinate: readonly number[]) => { this.coordinate = coordinate; return this; });
                this.addTo = vi.fn((map: { getContainer(): HTMLElement }) => { map.getContainer().append(options.element); return this; });
                this.remove = vi.fn(() => { options.element.remove(); return this; });
                markers.push(this);
            }
        } });
        renderer = new MeasurementRenderer(map);
    });
    afterEach(() => { renderer.destroy(); vi.unstubAllGlobals(); });
    const flush = (frames: Map<number, FrameRequestCallback>) => { const callbacks = [...frames.values()]; frames.clear(); callbacks.forEach(callback => callback(0)); };

    it('creates no map resources before use and adds native overlays in declared order', () => {
        expect(map.addLayer).not.toHaveBeenCalled();
        renderer.setMeasurements([createMeasurement([0, 0], [1, 0], 'one')]);
        expect([...map.layers.keys()]).toEqual(DEFAULTS.MEASUREMENT.LAYER_ROLES.map(role => `${MEASUREMENT_LAYER_PREFIX}${role}`));
        const label = map.layers.get(`${MEASUREMENT_LAYER_PREFIX}completed-label`)!;
        expect(label.layout).toMatchObject({ 'icon-text-fit': 'both', 'icon-optional': false, 'text-optional': false, 'text-allow-overlap': false });
        const image = map.images.get(`${MEASUREMENT_LAYER_PREFIX}capsule`)!;
        expect((image.image as { data: Uint8Array }).data).toHaveLength(image.image.width * image.image.height * 4);
        expect(image.options.stretchX[0]![0]).toBeLessThan(image.options.stretchX[0]![1]);
        expect(image.options.content).toEqual([0, 0, image.image.width, image.image.height]);
        expect(image.options.stretchX).toEqual([[DEFAULTS.MEASUREMENT.LABEL_IMAGE_RADIUS,
            image.image.width - DEFAULTS.MEASUREMENT.LABEL_IMAGE_RADIUS]]);
        expect(label.layout!['icon-text-fit-padding']).toEqual(DEFAULTS.MEASUREMENT.LABEL_PADDING);
    });

    it('retains contrasting casing around completed and draft lines through overview zooms', () => {
        renderer.setMeasurements([createMeasurement([0, 0], [1, 0], 'one')]);
        for (const kind of ['completed', 'draft']) {
            const foreground = map.layers.get(`${MEASUREMENT_LAYER_PREFIX}${kind}-line`)!.paint!['line-width'];
            const casing = map.layers.get(`${MEASUREMENT_LAYER_PREFIX}${kind}-casing`)!.paint!['line-width'];
            for (const zoom of [0, 5, 8, 10.5, 12, 13.5, 14]) {
                expect(widthAtZoom(casing, zoom) - widthAtZoom(foreground, zoom)).toBeCloseTo(1);
            }
            expect(widthAtZoom(casing, 15) - widthAtZoom(foreground, 15)).toBeCloseTo(2);
            for (const zoom of [16, 17.5, 18, 22]) {
                expect(widthAtZoom(foreground, zoom)).toBe(2);
                expect(widthAtZoom(casing, zoom)).toBe(5);
            }
        }
    });

    it('prioritizes newer measurements and preserves older complete geometry on pointer movement', () => {
        const records = [createMeasurement([0, 0], [1, 0], 'one'), createMeasurement([2, 0], [3, 0], 'two')];
        renderer.setMeasurements(records);
        const source = map.sources.get(`${MEASUREMENT_LAYER_PREFIX}completed`)!;
        const data = source.data;
        expect(data.features.filter(feature => feature.properties.role === 'label').map(feature => feature.properties.priority)).toEqual([0, -1]);
        source.setData.mockClear();
        map.getStyle.mockClear();
        for (let index = 0; index < 100; index++) renderer.setDraft({ start: [0, 0], end: [index / 100, 1] });
        expect(frames.size).toBe(1);
        flush(frames);
        expect(source.setData).not.toHaveBeenCalled();
        expect(map.getStyle).not.toHaveBeenCalled();
        expect(source.data).toBe(data);
        const draft = map.sources.get(`${MEASUREMENT_LAYER_PREFIX}draft`)!;
        expect(draft.setData).toHaveBeenCalledTimes(1);
        expect(draft.data.features.filter(feature => feature.properties.role === 'endpoint').at(-1)!.geometry.coordinates).toEqual([0.99, 1]);
    });

    it('clears only a draft while preserving complete results', () => {
        renderer.setMeasurements([createMeasurement([0, 0], [1, 0], 'one')]);
        renderer.setDraft({ start: [1, 1], end: null });
        flush(frames);
        expect(map.sources.get(`${MEASUREMENT_LAYER_PREFIX}draft`)!.data.features).toHaveLength(1);
        renderer.setDraft(null);
        flush(frames);
        expect(map.sources.get(`${MEASUREMENT_LAYER_PREFIX}draft`)!.data.features).toEqual([]);
        expect(map.sources.get(`${MEASUREMENT_LAYER_PREFIX}completed`)!.data.features).toHaveLength(4);
    });

    it('updates one live capsule immediately without native symbol fade or completed DOM markers', () => {
        renderer.setMeasurements([createMeasurement([0, 0], [1, 0], 'one')]);
        expect(markers).toHaveLength(0);
        renderer.setDraft({ start: [0, 0], end: [1, 0] });
        flush(frames);
        expect(markers).toHaveLength(1);
        const marker = markers[0]!;
        const element = marker.options.element;
        expect(marker.options).toMatchObject({ anchor: 'center', opacityWhenCovered: 0 });
        expect(element.className).toBe('measurement-live-label');
        expect(element.getAttribute('aria-hidden')).toBe('true');
        expect(element.style.getPropertyValue('--measurement-label-padding'))
            .toBe(DEFAULTS.MEASUREMENT.LABEL_PADDING.map(value => `${value}px`).join(' '));
        expect(element.style.getPropertyValue('--measurement-label-font-size')).toBe(`${DEFAULTS.MEASUREMENT.LABEL_TEXT_SIZE}px`);
        expect(element.style.getPropertyValue('--measurement-label-color')).toBe(DEFAULTS.MEASUREMENT.LABEL_TEXT_COLOR);
        expect(element.textContent).toBe('111.19 km · 69.09 mi');
        expect(map.layers.has(`${MEASUREMENT_LAYER_PREFIX}draft-label`)).toBe(false);
        renderer.setDraft({ start: [0, 0], end: [2, 0] });
        flush(frames);
        expect(markers).toHaveLength(1);
        expect(element.textContent).toBe('222.39 km · 138.19 mi');
        expect(marker.setLngLat).toHaveBeenCalledTimes(2);
        expect(map.getContainer().children).toHaveLength(1);
        renderer.setDraft({ start: [0, 0], end: null });
        expect(marker.remove).toHaveBeenCalledOnce();
        expect(map.getContainer().children).toHaveLength(0);
    });

    it('retains the single live Marker across style changes and removes it on clear', () => {
        renderer.setDraft({ start: [0, 0], end: [1, 0] });
        flush(frames);
        map.sources.clear(); map.layers.clear(); map.images.clear();
        map.listeners.get('style.load')!();
        expect(markers).toHaveLength(1);
        expect(map.getContainer().children).toHaveLength(1);
        renderer.clear();
        expect(markers[0]!.remove).toHaveBeenCalledOnce();
        expect(map.getContainer().children).toHaveLength(0);
    });

    it('retains cached complete geometry when another measurement is appended', () => {
        const first = createMeasurement([0, 0], [1, 0], 'one');
        renderer.setMeasurements([first]);
        const source = map.sources.get(`${MEASUREMENT_LAYER_PREFIX}completed`)!;
        const originalLine = source.data.features.find(feature => feature.properties.role === 'line');
        renderer.setMeasurements([first, createMeasurement([0, 1], [1, 1], 'two')]);
        expect(source.data.features.find(feature => feature.properties.role === 'line')).toBe(originalLine);
    });

    it('defers source creation until a replacement style finishes loading', () => {
        map.getStyle.mockImplementation(() => { throw new Error('Style is not done loading'); });
        renderer.setMeasurements([createMeasurement([0, 0], [1, 0], 'one')]);
        renderer.setDraft({ start: [1, 1], end: [2, 2] });
        flush(frames);
        expect(map.addSource).not.toHaveBeenCalled();
        expect(map.addImage).not.toHaveBeenCalled();
        map.getStyle.mockReturnValue({ layers: [] });
        map.listeners.get('style.load')!();
        expect(map.sources.get(`${MEASUREMENT_LAYER_PREFIX}completed`)!.data.features).toHaveLength(4);
        expect(map.sources.get(`${MEASUREMENT_LAYER_PREFIX}draft`)!.data.features).toHaveLength(4);
    });

    it('renders immediately while basemap tiles are still loading', () => {
        map.isStyleLoaded = vi.fn(() => false);
        renderer.setMeasurements([createMeasurement([0, 0], [1, 0], 'one')]);
        expect(map.sources.get(`${MEASUREMENT_LAYER_PREFIX}completed`)!.data.features).toHaveLength(4);
        expect(map.isStyleLoaded).not.toHaveBeenCalled();
    });

    it('clears safely after the map style has already been removed', () => {
        renderer.setMeasurements([createMeasurement([0, 0], [1, 0], 'one')]);
        map.getStyle.mockReturnValue(undefined);
        map.getLayer = () => { throw new Error('Removed map has no style'); };
        expect(() => renderer.destroy()).not.toThrow();
        expect(map.listeners.size).toBe(0);
    });

    it('restores a style idempotently without rebuilding or losing complete results', () => {
        renderer.setMeasurements([createMeasurement([0, 0], [1, 0], 'one')]);
        const original = map.sources.get(`${MEASUREMENT_LAYER_PREFIX}completed`)!.data;
        map.sources.clear(); map.layers.clear(); map.images.clear();
        map.listeners.get('style.load')!();
        expect(map.sources.get(`${MEASUREMENT_LAYER_PREFIX}completed`)!.data).toBe(original);
        for (const kind of ['completed', 'draft']) {
            expect(map.sources.get(`${MEASUREMENT_LAYER_PREFIX}${kind}`)!.tolerance).toBe(0);
            expect(map.layers.get(`${MEASUREMENT_LAYER_PREFIX}${kind}-line`)!.paint!['line-width'])
                .toEqual(['interpolate', ['linear'], ['zoom'], 0, 1, 8, 1, 12, 1.5, 14, 2, 16, 2, 18, 2]);
            expect(map.layers.get(`${MEASUREMENT_LAYER_PREFIX}${kind}-casing`)!.paint!['line-width'])
                .toEqual(['interpolate', ['linear'], ['zoom'], 0, 2, 8, 2, 12, 2.5, 14, 3, 16, 5, 18, 5]);
        }
        expect(map.layers.get(`${MEASUREMENT_LAYER_PREFIX}draft-line`)!.paint!['line-dasharray'])
            .toEqual(DEFAULTS.MEASUREMENT.DRAFT_DASH_ARRAY);
        const count = map.addLayer.mock.calls.length;
        renderer.restore();
        expect(map.addLayer).toHaveBeenCalledTimes(count);
    });

    it('removes all owned resources and prevents late frames or style events recreating them', () => {
        renderer.setMeasurements([createMeasurement([0, 0], [1, 0], 'one')]);
        renderer.setDraft({ start: [1, 1], end: [2, 2] });
        const lateFrame = [...frames.values()][0];
        renderer.clear();
        lateFrame!(0);
        map.listeners.get('style.load')!();
        expect(map.layers.size).toBe(0);
        expect(map.sources.size).toBe(0);
        expect(map.images.size).toBe(0);
        expect(frames.size).toBe(0);
        renderer.setMeasurements([]);
        expect(map.layers.size).toBe(DEFAULTS.MEASUREMENT.LAYER_ROLES.length);
        renderer.destroy();
        expect(map.listeners.size).toBe(0);
        renderer.setDraft({ start: [0, 0], end: [1, 0] });
        renderer.setMeasurements([]);
        expect(map.layers.size).toBe(0);
    });
});

it('preserves the original non-Error style failure instead of swallowing it', () => {
    const failure = { message: 'unrelated style failure' };
    const map = makeMap();
    map.getStyle.mockImplementation(() => { // The legacy style boundary can throw plain objects.
        throw failure as unknown as Error; });
    const renderer = new MeasurementRenderer(map);
    expect(() => renderer.setMeasurements([])).toThrow(failure);
    map.getStyle.mockReturnValue({ layers: [] });
    renderer.destroy();
});

it('does not emit class fields beyond the constructor-owned runtime properties', () => {
    const renderer = new MeasurementRenderer(makeMap());
    expect(Object.keys(renderer)).toEqual([
        'map', 'active', 'destroyed', 'draft', 'draftFrame', 'liveMarker', 'liveLabel',
        'completedData', 'draftData', 'completedFeatures', 'restoreHandler',
    ]);
    renderer.destroy();
});
