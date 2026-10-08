import { isCurrentStationNew, setCurrentStationIsNew } from './session.ts';

afterEach(() => { setCurrentStationIsNew(false); });

it('starts false and preserves ordinary setter/getter return values', () => {
    expect(isCurrentStationNew()).toBe(false);
    expect(setCurrentStationIsNew(true)).toBeUndefined();
    expect(isCurrentStationNew()).toBe(true);
});

it.each([null, undefined, false, 0, '', NaN])('coerces falsey input %s', value => {
    setCurrentStationIsNew(true);
    setCurrentStationIsNew(value);
    expect(isCurrentStationNew()).toBe(false);
});

it.each([{}, [], 'false', 1])('coerces truthy input %s', value => {
    setCurrentStationIsNew(value);
    expect(isCurrentStationNew()).toBe(true);
});
