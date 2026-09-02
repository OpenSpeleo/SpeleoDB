import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { attachTaggedEntityList } from './tagged_entity_list.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const JQUERY_SRC = readFileSync(resolve(
    __dirname, '..', '..', '..', '..', '..',
    'frontend_public', 'static', 'js', 'vendors', 'jquery-3.7.1.js',
), 'utf-8');

beforeAll(() => {
    // eslint-disable-next-line no-eval
    (0, eval)(JQUERY_SRC);
});

describe('attachTaggedEntityList', () => {
    let originalAjax;

    beforeEach(() => {
        document.body.innerHTML = `
            <div id="modal_success"><span id="modal_success_txt"></span></div>
            <div id="modal_error"><span id="modal_error_txt"></span></div>
        `;
        originalAjax = globalThis.jQuery.ajax;
    });

    afterEach(() => {
        globalThis.jQuery.ajax = originalAjax;
        document.body.innerHTML = '';
    });

    it('supports list-only workflows without mutation modal configuration', () => {
        const renderList = vi.fn();
        globalThis.jQuery.ajax = vi.fn(options => {
            options.success([{ id: 'layer-1' }]);
        });

        const list = attachTaggedEntityList({
            listEndpoint: '/api/v2/gis-layers/',
            renderList,
        });

        expect(renderList).toHaveBeenCalledWith(
            [{ id: 'layer-1' }],
            expect.objectContaining({ reload: expect.any(Function) }),
        );
        expect(globalThis.jQuery.ajax).toHaveBeenCalledWith(
            expect.objectContaining({
                url: '/api/v2/gis-layers/',
                method: 'GET',
            }),
        );

        list.reload();
        expect(globalThis.jQuery.ajax).toHaveBeenCalledTimes(2);
    });

    it('still requires a detail endpoint for configured mutation controls', () => {
        expect(() => attachTaggedEntityList({
            listEndpoint: '/api/v2/items/',
            renderList: () => {},
            confirmDeleteSelector: '#confirm-delete',
        })).toThrow(/detailEndpointBuilder/);
    });
});
