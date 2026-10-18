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

    beforeEach(() => {
        document.body.innerHTML = `
            <div id="modal_success"><span id="modal_success_txt"></span></div>
            <div id="modal_error"><span id="modal_error_txt"></span></div>
        `;
        });

    afterEach(() => {
            document.body.innerHTML = '';
    });

    it('supports list-only workflows without mutation modal configuration', async () => {
        const renderList = vi.fn();
        const load = vi.fn(async () => [{ id: 'layer-1' }]);
        const list = attachTaggedEntityList({ list: load, renderList });
        await Promise.resolve();
        expect(renderList).toHaveBeenCalledWith(
            [{ id: 'layer-1' }],
            expect.objectContaining({ reload: expect.any(Function) as unknown }),
        );
        expect(load).toHaveBeenCalledOnce();
        list.reload();
        expect(load).toHaveBeenCalledTimes(2);
    });

    it('requires remove for configured deletion controls', () => {
        expect(() => attachTaggedEntityList({
            list: async () => [], renderList: () => {}, confirmDeleteSelector: '#confirm-delete',
        })).toThrow(/remove/);
    });
});

it('starts loading before returning the same facade supplied asynchronously to the renderer', async () => {
    const events: string[] = [];
    let renderedApi: TaggedListApi | undefined;
    const api = attachTaggedEntityList({
        list: async () => { events.push('request'); return [{ id: 'tag-1' }]; },
        renderList: (_entities, facade) => { events.push('render'); renderedApi = facade; },
    });
    events.push('returned');
    expect(events).toEqual(['request', 'returned']);
    await Promise.resolve();
    expect(events).toEqual(['request', 'returned', 'render']);
    expect(renderedApi).toBe(api);
    api.reload();
    expect(events).toEqual(['request', 'returned', 'render', 'request']);
});
