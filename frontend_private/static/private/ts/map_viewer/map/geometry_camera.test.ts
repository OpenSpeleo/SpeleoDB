import { geometryCameraPadding, fitGISGeometry } from './geometry_camera.ts';
import type { CameraBounds, CameraPadding, FlatBounds, GeometryCameraMap } from '../../../../../../ts-types/domain/map-geometry.ts';

const rectangle = (left: number, top: number, right: number, bottom: number) => ({ left, top, right, bottom, width: right - left, height: bottom - top });

it('fits the full bounds beside the desktop editor and below the project panel', () => {
    const map = rectangle(0, 0, 1200, 800);
    const padding = geometryCameraPadding(map, map, [
        rectangle(784, 16, 1144, 760), rectangle(16, 16, 266, 96),
    ]) as CameraPadding;
    expect(padding).toEqual({ left: 50, right: 466, top: 146, bottom: 50 });
});

it('accounts for the offscreen map tail and mobile bottom sheet', () => {
    const map = rectangle(33, 220, 357, 983);
    const padding = geometryCameraPadding(map, rectangle(0, 0, 390, 844), [
        rectangle(43, 450, 347, 834), rectangle(49, 236, 299, 306),
    ]) as CameraPadding;
    expect(map.top + padding.top).toBeGreaterThan(306);
    expect(map.bottom - padding.bottom).toBeLessThan(450);
    expect(map.left + padding.left).toBeGreaterThan(33);
    expect(map.right - padding.right).toBeLessThan(357);
});

it('keeps padding valid on small viewports and after fullscreen expansion', () => {
    for (const size of [120, 390, 1440]) {
        const map = rectangle(0, 0, size, size);
        const padding = geometryCameraPadding(map, map) as CameraPadding;
        expect(padding.left + padding.right).toBeLessThan(size);
        expect(padding.top + padding.bottom).toBeLessThan(size);
    }
});

it('uses transient fit padding and clears tilt so no bounding-box corner is clipped', () => {
    document.body.innerHTML = '<div id="map"></div>';
    const container = document.getElementById('map')!;
    vi.spyOn(container, 'getBoundingClientRect').mockReturnValue(rectangle(0, 0, 600, 400) as DOMRect);
    const map = { getContainer: () => container, fitBounds: vi.fn<GeometryCameraMap['fitBounds']>() };
    const bounds: CameraBounds = [[-87.5, 20.5], [-87.49, 20.51]];
    fitGISGeometry(map, bounds);
    expect(map.fitBounds).toHaveBeenCalledWith(bounds, expect.objectContaining({
        maxZoom: 16, bearing: 0, pitch: 0, retainPadding: false,
    }));
    vi.restoreAllMocks();
});

it('fits the short antimeridian span without changing the imported RFC 7946 bounds', () => {
    const map = { fitBounds: vi.fn<GeometryCameraMap['fitBounds']>() };
    const bounds = Object.freeze([179.5, 10, -179.5, 11] as const);

    fitGISGeometry(map, bounds);

    const [cameraBounds] = map.fitBounds.mock.calls[0]!;
    expect(cameraBounds).toEqual([179.5, 10, 180.5, 11]);
    expect((cameraBounds as FlatBounds)[2] - (cameraBounds as FlatBounds)[0]).toBe(1);
    expect(bounds).toEqual([179.5, 10, -179.5, 11]);
});

it.each([
    [-87.5, 20.5, -87.49, 20.51],
    [-180, -85, 180, 85],
    [179.5, 10, 180.5, 11],
] as const)('preserves ordinary and already-unwrapped bounds %#', (...coordinates) => {
    const map = { fitBounds: vi.fn<GeometryCameraMap['fitBounds']>() };
    const bounds = Object.freeze(coordinates);

    fitGISGeometry(map, bounds);

    expect(map.fitBounds.mock.calls[0]![0]).toBe(bounds);
});
