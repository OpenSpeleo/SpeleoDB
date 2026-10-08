import type { GisViewFormOptions } from '../../ts-types/domain/forms/gis-view.ts';
import type { GisViewSaved } from '../../ts-types/controllers/gis-view-form.ts';
import type { ApplicationUrls } from '../../ts-types/browser/urls.d.ts';
import type { Mock } from 'vitest';
import type { GisViewFormContext } from '../../ts-types/controllers/gis-view-form.ts';
import { init as initialize } from './gis-view-form.ts';
import { attachGisViewForm } from '../../frontend_private/static/private/ts/forms/gis_view_form.ts';

vi.mock('../../frontend_private/static/private/ts/forms/gis_view_form.ts', () => ({
    attachGisViewForm: vi.fn(),
}));

// The double deliberately returns values ignored by the real controller.
const attachment = vi.mocked(attachGisViewForm) as unknown as Mock<(options: GisViewFormOptions<GisViewSaved> & {existingProjects?: unknown}) => unknown>;
function init(context?: unknown) { return initialize(context as GisViewFormContext); }

beforeEach(() => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('complete');
    attachment.mockReset();
    window.Urls = {} as ApplicationUrls;
});

afterEach(() => {
    vi.restoreAllMocks();
    delete (window as unknown as { Urls?: ApplicationUrls }).Urls;
});

it('waits for load, copies context and supplies lazy builders without changing nested identity', async () => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const context = { endpoint: '/views/', existingProjects: [{ id: 'project' }] };
    const pending = init(context);
    expect(attachment).not.toHaveBeenCalled();
    window.dispatchEvent(new Event('load'));
    await expect(pending).resolves.toBeUndefined();
    const options = attachment.mock.calls[0]![0];
    expect(options).not.toBe(context);
    expect(options.existingProjects).toBe(context.existingProjects);
    expect(options.endpoint).toBe(context.endpoint);
    expect(Object.hasOwn(options, 'onSuccess')).toBe(true);
    expect(options.onSuccess).toBeUndefined();
    expect(options.commitsEndpointBuilder).toBeTypeOf('function');
    expect(context).not.toHaveProperty('commitsEndpointBuilder');
});

it('resolves the current commit route lazily and forwards the project identifier exactly', async () => {
    await init({});
    const builder = attachment.mock.calls[0]![0].commitsEndpointBuilder!;
    expect(() => builder('project')).toThrow('Missing Django URL route: api:v2:project-geojson-commits');
    const route = vi.fn().mockReturnValue('/commits/');
    window.Urls['api:v2:project-geojson-commits'] = route;
    expect(builder('project')).toBe('/commits/');
    expect(route).toHaveBeenCalledExactlyOnceWith('project');
});

it('builds successful redirects from the response ID and reports absent redirect routes', async () => {
    await init({ redirectRoute: 'private:gis_view_details' });
    const onSuccess = attachment.mock.calls[0]![0].onSuccess!;
    expect(() => onSuccess({ id: 17 })).toThrow('Missing Django URL route: private:gis_view_details');
    const route = vi.fn().mockReturnValue('#saved-view');
    window.Urls['private:gis_view_details'] = route;
    onSuccess({ id: 17 });
    expect(route).toHaveBeenCalledExactlyOnceWith(17);
    expect(window.location.hash).toBe('#saved-view');
    window.history.replaceState(null, '', '/');
});

it('repeats attachments, ignores returned promises and propagates synchronous helper errors', async () => {
    attachment.mockReturnValue(new Promise(() => {}));
    await init({});
    await init({});
    expect(attachment).toHaveBeenCalledTimes(2);
    const error = new Error('Attachment failed');
    attachment.mockImplementation(() => { throw error; });
    await expect(init({})).rejects.toBe(error);
});

it('rejects missing context before calling the helper', async () => {
    await expect(init()).rejects.toThrow(TypeError);
    expect(attachment).not.toHaveBeenCalled();
});
