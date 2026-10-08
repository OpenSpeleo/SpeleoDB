import { GIS_GEOMETRY_CONTRACT } from '@speleodb/map-core/geometry';
import geometryCases from '@speleodb/map-core/geometry-cases.json';
import backendCases from '../../../../../speleodb/gis/tests/fixtures/gis_geometry_cases.json';
import geometryContract from '../../../../../speleodb/gis/geometry_contract.json';
import { DEFAULTS } from './config.ts';

// The Python contract test asserts its exported constants against this same
// document. Together they prevent either runtime from overriding shared policy.
it('uses exactly the same geometry constants as the Python contract', () => {
    const browserContract = Object.fromEntries(Object.keys(geometryContract)
        .map(key => [key, DEFAULTS.GIS_GEOMETRY[key.toUpperCase() as keyof typeof DEFAULTS.GIS_GEOMETRY]]));

    expect(browserContract).toEqual(geometryContract);
    expect(GIS_GEOMETRY_CONTRACT).toEqual(geometryContract);
    expect(geometryCases).toEqual(backendCases);
    expect(browserContract.types).toEqual(['LineString', 'Polygon']);
    expect(browserContract.max_area_m2).toBe(30_000_000);
});
