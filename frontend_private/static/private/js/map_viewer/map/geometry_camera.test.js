import { geometryCameraPadding, fitGISGeometry } from './geometry_camera.js';

const rectangle = (left, top, right, bottom) => ({ left, top, right, bottom, width: right - left, height: bottom - top });

it('fits the full bounds beside the desktop editor and below the project panel', () => {
    const map = rectangle(0, 0, 1200, 800);
    const padding = geometryCameraPadding(map, map, [
        rectangle(784, 16, 1144, 760), rectangle(16, 16, 266, 96),
    ]);
    expect(padding).toEqual({ left: 50, right: 466, top: 146, bottom: 50 });
});

it('accounts for the offscreen map tail and mobile bottom sheet', () => {
    const map = rectangle(33, 220, 357, 983);
    const padding = geometryCameraPadding(map, rectangle(0, 0, 390, 844), [
        rectangle(43, 450, 347, 834), rectangle(49, 236, 299, 306),
    ]);
    expect(map.top + padding.top).toBeGreaterThan(306);
    expect(map.bottom - padding.bottom).toBeLessThan(450);
    expect(map.left + padding.left).toBeGreaterThan(33);
    expect(map.right - padding.right).toBeLessThan(357);
});

it('keeps padding valid on small viewports and after fullscreen expansion', () => {
    for (const size of [120, 390, 1440]) {
        const map = rectangle(0, 0, size, size);
        const padding = geometryCameraPadding(map, map);
        expect(padding.left + padding.right).toBeLessThan(size);
        expect(padding.top + padding.bottom).toBeLessThan(size);
    }
});

it('uses transient fit padding and clears tilt so no bounding-box corner is clipped', () => {
    document.body.innerHTML = '<div id="map"></div>';
    const container = document.getElementById('map');
    vi.spyOn(container, 'getBoundingClientRect').mockReturnValue(rectangle(0, 0, 600, 400));
    const map = { getContainer: () => container, fitBounds: vi.fn() };
    const bounds = [[-87.5, 20.5], [-87.49, 20.51]];
    fitGISGeometry(map, bounds);
    expect(map.fitBounds).toHaveBeenCalledWith(bounds, expect.objectContaining({
        maxZoom: 16, bearing: 0, pitch: 0, retainPadding: false,
    }));
    vi.restoreAllMocks();
});
