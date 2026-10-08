import { parseClipboardText, validateCell } from './xls2dmp.ts';

it('handles quoted commas and doubled quotes but retains unmatched-quote acceptance', () => {
    expect(parseClipboardText('"12,5","a""b",90')).toEqual([['12,5', 'a"b', '90']]);
    expect(parseClipboardText('"12,5,90')).toEqual([['12,5,90']]);
});

it('strips an exact station column only after a station-prefixed header', () => {
    expect(parseClipboardText('Station #,Depth,Length\n1,10,2')).toEqual([['10', '2']]);
    expect(parseClipboardText('Stationary,Depth\nA,10')).toEqual([['A', '10']]);
    expect(parseClipboardText('Depth,Station #\n10,1')).toEqual([['Depth', 'Station #'], ['10', '1']]);
});

it('retains empty cells, strips BOMs and quotes, and removes entirely empty records', () => {
    expect(parseClipboardText('\uFEFF"10"\t""\t90\r\n,,\r12\t\t')).toEqual([['10', '', '90'], ['12', '', '']]);
});

it.each([
    ['12suffix', 'depth', false, true], ['0x10', 'depth', false, true],
    ['Infinity', 'depth', false, false], ['-1', 'left', false, false],
    ['', 'left', false, true], ['', 'length', true, true],
    ['1', 'length', true, false], ['360', 'azimuth', false, false],
    [null, 'depth', false, false], [undefined, 'unknown', false, true],
] as const)('preserves DMP value policy for %s/%s', (value, column, last, expected) => {
    expect(validateCell(value, column, last)).toBe(expected);
});
