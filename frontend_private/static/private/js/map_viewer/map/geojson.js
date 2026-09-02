export function computeGeoJSONBounds(geojsonData) {
    const bounds = new mapboxgl.LngLatBounds();
    if (
        Array.isArray(geojsonData?.bbox)
        && geojsonData.bbox.length >= 4
        && geojsonData.bbox.length % 2 === 0
        && geojsonData.bbox.every(Number.isFinite)
    ) {
        const dimensions = geojsonData.bbox.length / 2;
        const west = geojsonData.bbox[0];
        const south = geojsonData.bbox[1];
        let east = geojsonData.bbox[dimensions];
        const north = geojsonData.bbox[dimensions + 1];
        if (east < west) east += 360;
        bounds.extend([west, south]);
        bounds.extend([east, north]);
        return bounds;
    }

    const longitudes = [];
    let minimumLatitude = Number.POSITIVE_INFINITY;
    let maximumLatitude = Number.NEGATIVE_INFINITY;
    const extendCoordinates = coordinates => {
        if (!Array.isArray(coordinates) || coordinates.length === 0) return;
        if (typeof coordinates[0] === 'number') {
            const [longitude, latitude] = coordinates;
            if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) return;
            longitudes.push(((longitude % 360) + 360) % 360);
            minimumLatitude = Math.min(minimumLatitude, latitude);
            maximumLatitude = Math.max(maximumLatitude, latitude);
            return;
        }
        coordinates.forEach(extendCoordinates);
    };

    const extendGeometry = geometry => {
        if (!geometry) return;
        if (geometry.type === 'GeometryCollection') {
            geometry.geometries?.forEach(extendGeometry);
            return;
        }
        extendCoordinates(geometry.coordinates);
    };

    if (geojsonData?.type === 'FeatureCollection') {
        geojsonData.features?.forEach(feature => extendGeometry(feature.geometry));
    } else if (geojsonData?.type === 'Feature') {
        extendGeometry(geojsonData.geometry);
    } else {
        extendGeometry(geojsonData);
    }

    if (longitudes.length === 0) return bounds;
    longitudes.sort((left, right) => left - right);

    let largestGap = Number.NEGATIVE_INFINITY;
    let gapIndex = 0;
    for (let index = 0; index < longitudes.length; index += 1) {
        const next = index === longitudes.length - 1
            ? longitudes[0] + 360
            : longitudes[index + 1];
        const gap = next - longitudes[index];
        if (gap > largestGap) {
            largestGap = gap;
            gapIndex = index;
        }
    }

    let west = longitudes[(gapIndex + 1) % longitudes.length];
    let east = longitudes[gapIndex];
    if (east < west) east += 360;
    if (west > 180) {
        west -= 360;
        east -= 360;
    }
    bounds.extend([west, minimumLatitude]);
    bounds.extend([east, maximumLatitude]);
    return bounds;
}
