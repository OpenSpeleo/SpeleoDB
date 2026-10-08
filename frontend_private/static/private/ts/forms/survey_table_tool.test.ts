import { readFileSync } from 'node:fs';
import path from 'node:path';
import type { FormTestJQuery } from '../../../../../ts-types/testing/vitest/forms.ts';

const jquerySource = readFileSync(path.join(process.cwd(), 'frontend_public/static/ts/vendors/jquery-3.7.1.js'), 'utf8');
const jqueryHost = globalThis as typeof globalThis & { jQuery: FormTestJQuery };
let originalAjax: FormTestJQuery['ajax'];
beforeAll(() => { (0, eval)(jquerySource); });
beforeEach(() => {
    vi.useFakeTimers();
    originalAjax = jqueryHost.jQuery.ajax;
    document.body.innerHTML = '<div id="modal_error"><span id="modal_error_txt"></span></div><div id="modal_success"><span id="modal_success_txt"></span></div>';
});
afterEach(() => {
    jqueryHost.jQuery.ajax = originalAjax;
    jqueryHost.jQuery(document).off();
    document.body.innerHTML = '';
    vi.useRealTimers();
});

import { attachSurveyTableTool } from './survey_table_tool.ts';

function surveyControls(): void {
    document.body.insertAdjacentHTML('beforeend', '<table id="dataTable"><tbody></tbody></table><div id="status"></div><button id="add">Add</button><button id="clear">Clear</button>');
}
const surveyOptions = { tableBodySelector: '#dataTable tbody', COLUMNS: ['depth', 'length'], validateCell: () => true, parseClipboardText: (text: string) => text.split('\n').map(row => row.split('\t')), addRowBtnSelector: '#add', clearBtnSelector: '#clear' };

it('escapes editable values and preserves CSV quoting and keyed row serialization', () => {
    surveyControls();
    const tool = attachSurveyTableTool(surveyOptions);
    tool.renderRows([['<img src=x>', 'a,"b"'], [' 3 ', '']]);
    expect(document.querySelector('tbody img')).toBeNull();
    expect(tool.tableToCsv()).toBe('<img src=x>,"a,""b"""\n3,');
    expect(tool.collectRowObjects()).toEqual([{ depth: '<img src=x>', length: 'a,"b"' }, { depth: '3', length: '' }]);
    expect(tool.validateTable()).toBe(true);
});

it('keeps last-row validation messages and updates row indexes on removal', () => {
    surveyControls();
    const tool = attachSurveyTableTool({ ...surveyOptions,
        validateCell: (value: string, column: string, last: boolean) => !last || column === 'depth' || value.trim() === '',
        lastRowAllowedColumns: ['depth'], lastRowErrorMessage: (fields: string[]) => fields.join(', '),
    });
    tool.renderRows([['1', '2'], ['3', '4']]);
    expect(tool.validateTable()).toBe(false);
    expect(jqueryHost.jQuery('#status').text()).toBe('Length');
    jqueryHost.jQuery('.trash').first().trigger('click');
    expect(document.querySelector('tbody tr td')!.textContent).toBe('1');
    jqueryHost.jQuery('#clear').trigger('click');
    expect(tool.collectRowObjects()).toEqual([]);
    expect(jqueryHost.jQuery('#status').text()).toBe('Cleared.');
});
