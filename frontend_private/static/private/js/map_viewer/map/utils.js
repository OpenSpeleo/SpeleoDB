
// Process GeoJSON to ensure altitude is zero
function processGeoJSON(geojsonData) {
    if (!geojsonData || !geojsonData.features) return geojsonData;
    
    const processed = JSON.parse(JSON.stringify(geojsonData)); // Deep copy
    
    function forceAltitudeZero(coords) {
        if (typeof coords[0] === 'number') {
            if (coords.length >= 3) return [coords[0], coords[1], 0];
            return coords;
        } else if (Array.isArray(coords[0])) {
            return coords.map(c => forceAltitudeZero(c));
        }
        return coords;
    }

    processed.features.forEach(feature => {
        if (feature.geometry && feature.geometry.coordinates) {
            feature.geometry.coordinates = forceAltitudeZero(feature.geometry.coordinates);
        }
    });
    
    return processed;
}




