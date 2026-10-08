import type { FormTestJQuery } from '../../../../../ts-types/testing/vitest/forms.ts';
import type { TaggedListApi } from '../../../../../ts-types/domain/forms/tagged-list.ts';

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { attachTaggedEntityList } from './tagged_entity_list.ts';

const jqueryHost = globalThis as typeof globalThis & { jQuery: FormTestJQuery };

const __dirname = dirname(fileURLToPath(import.meta.url));
const JQUERY_SRC = readFileSync(resolve(
    __dirname, '..', '..', '..', '..', '..',
    'frontend_public', 'static', 'ts', 'vendors', 'jquery-3.7.1.js',
), 'utf-8');

beforeAll(() => {
    // eslint-disable-next-line no-eval
    (0, eval)(JQUERY_SRC);
});

describe('attachTaggedEntityList', () => {
    let originalAjax: FormTestJQuery['ajax'];

    beforeEach(() => {
        document.body.innerHTML = `
            <div id="modal_success"><span id="modal_success_txt"></span></div>
            <div id="modal_error"><span id="modal_error_txt"></span></div>
        `;
        originalAjax = jqueryHost.jQuery.ajax;
    });

    afterEach(() => {
        jqueryHost.jQuery.ajax = originalAjax;
        document.body.innerHTML = '';
    });

    it('supports list-only workflows without mutation modal configuration', () => {
        const renderList = vi.fn();
        jqueryHost.jQuery.ajax = vi.fn(options => {
            options.success([{ id: 'layer-1' }]);
        });

        const list = attachTaggedEntityList({
            listEndpoint: '/api/v2/gis-layers/',
            renderList,
        });

        expect(renderList).toHaveBeenCalledWith(
            [{ id: 'layer-1' }],
            expect.objectContaining({ reload: expect.any(Function) as unknown }),
        );
        expect(jqueryHost.jQuery.ajax).toHaveBeenCalledWith(
            expect.objectContaining({
                url: '/api/v2/gis-layers/',
                method: 'GET',
            }),
        );

        list.reload();
        expect(jqueryHost.jQuery.ajax).toHaveBeenCalledTimes(2);
    });

    it('still requires a detail endpoint for configured mutation controls', () => {
        expect(() => attachTaggedEntityList({
            listEndpoint: '/api/v2/items/',
            renderList: () => {},
            confirmDeleteSelector: '#confirm-delete',
        })).toThrow(/detailEndpointBuilder/);
    });
});

it('starts loading before returning the same mutable facade supplied to the renderer', () => {
    const originalAjax = jqueryHost.jQuery.ajax;
    const events: string[] = [];
    let renderedApi: TaggedListApi | undefined;
    jqueryHost.jQuery.ajax = vi.fn(options => {
        events.push('request');
        options.success([{ id: 'tag-1' }]);
    });
    try {
        const api = attachTaggedEntityList({ listEndpoint: '/tags/', renderList: (entities, facade) => {
            events.push('render');
            renderedApi = facade;
        } });
        events.push('returned');
        expect(events).toEqual(['request', 'render', 'returned']);
        expect(renderedApi).toBe(api);
        api.reload = vi.fn();
        api.reload();
        expect(api.reload).toHaveBeenCalledOnce();
    } finally {
        jqueryHost.jQuery.ajax = originalAjax;
    }
});
