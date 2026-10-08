import { DEFAULTS } from './defaults.ts';
import { DEFAULTS as publicDefaults } from './config.ts';
import geometryContract from '../../../../../speleodb/gis/geometry_contract.json' with { type: 'json' };

it('re-exports the same shallow-frozen defaults and geometry contract references', () => {
    expect(publicDefaults).toBe(DEFAULTS);
    expect(Object.isFrozen(DEFAULTS)).toBe(true);
    expect(Object.isFrozen(DEFAULTS.UI)).toBe(false);
    expect(DEFAULTS.GIS_GEOMETRY.TYPES).toBe(geometryContract.types);
});
