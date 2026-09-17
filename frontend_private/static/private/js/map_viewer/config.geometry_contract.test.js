import geometryContract from '../../../../../speleodb/gis/geometry_contract.json';
import { DEFAULTS } from './config.js';

// The Python contract test asserts its exported constants against this same
// document. Together they prevent either runtime from overriding shared policy.
it('uses exactly the same geometry constants as the Python contract', () => {
    const browserContract = Object.fromEntries(Object.keys(geometryContract)
        .map(key => [key, DEFAULTS.GIS_GEOMETRY[key.toUpperCase()]]));

    expect(browserContract).toEqual(geometryContract);
    expect(browserContract.types).toEqual(['LineString', 'Polygon']);
    expect(browserContract.max_area_m2).toBe(30_000_000);
});
