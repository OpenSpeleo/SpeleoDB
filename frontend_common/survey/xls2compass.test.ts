import { parseClipboardText, validateCell } from './xls2compass.ts';

it('splits commas literally without CSV quote normalization', () => {
    expect(parseClipboardText('"A,B","10"')).toEqual([['"A', 'B"', '"10"']]);
    expect(parseClipboardText('"A,10')).toEqual([['"A', '10']]);
});

it('retains station values but drops any first row whose first cell contains station', () => {
    expect(parseClipboardText('Station #,Depth\nA,10')).toEqual([['A', '10']]);
    expect(parseClipboardText('my station,10\nB,20')).toEqual([['B', '20']]);
    expect(parseClipboardText('Depth,Station #\n10,A')).toEqual([['Depth', 'Station #'], ['10', 'A']]);
});

it('strips BOMs and blank lines while retaining delimiter-only rows', () => {
    expect(parseClipboardText('\uFEFFA\t10\r\n,,\rB\t')).toEqual([['A', '10'], ['', '', ''], ['B', '']]);
});

it.each([
    ['12suffix', 'depth', false, false], ['0x10', 'depth', false, true],
    ['Infinity', 'depth', false, false], ['A', 'station', true, true],
    ['', 'left', false, true], ['', 'length', true, true],
    ['1', 'length', true, false], ['360', 'azimuth', false, false],
    ['flag', 'flags', true, false], [null, 'depth', false, false],
    [undefined, 'unknown', false, true],
] as const)('preserves Compass value policy for %s/%s', (value, column, last, expected) => {
    expect(validateCell(value, column, last)).toBe(expected);
});
