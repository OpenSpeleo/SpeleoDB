import type { Mock } from 'vitest';
import type { LandmarkDetailsContext } from '../../ts-types/controllers/landmark-details.ts';
import { init as initialize } from './landmark-details.ts';
import { initLandmarkCollectionDetails as importedinitLandmarkCollectionDetails } from '../../frontend_private/static/private/ts/landmark_collection/details_main.ts';

vi.mock('../../frontend_private/static/private/ts/landmark_collection/details_main.ts', () => ({
    initLandmarkCollectionDetails: vi.fn(),
}));

beforeEach(() => {
    initLandmarkCollectionDetails.mockReset();
});

afterEach(() => {
    vi.restoreAllMocks();
    delete window.LANDMARK_DETAILS_CONTEXT;
});

it('publishes original context synchronously before invoking the lazy initializer without arguments', async () => {
    vi.spyOn(document, 'readyState', 'get').mockReturnValue('loading');
    const context = { canWrite: false, collectionId: 'collection' };
    initLandmarkCollectionDetails.mockImplementation(() => {
        expect(window.LANDMARK_DETAILS_CONTEXT).toBe(context);
    });
    const pending = init(context);
    expect(window.LANDMARK_DETAILS_CONTEXT).toBe(context);
    expect(initLandmarkCollectionDetails).not.toHaveBeenCalled();
    await expect(pending).resolves.toBeUndefined();
    expect(initLandmarkCollectionDetails).toHaveBeenCalledExactlyOnceWith();
});

it('overwrites context and repeats initialization without validating missing context', async () => {
    await init({ canWrite: true });
    await init();
    expect(window.LANDMARK_DETAILS_CONTEXT).toBeUndefined();
    expect(initLandmarkCollectionDetails).toHaveBeenCalledTimes(2);
});

it('does not await the helper result', async () => {
    initLandmarkCollectionDetails.mockReturnValue(new Promise(() => {}));
    await expect(init({})).resolves.toBeUndefined();
});

it('propagates synchronous initializer failure while retaining the published context', async () => {
    const error = new Error('Collection failed');
    const context = { canWrite: false };
    initLandmarkCollectionDetails.mockImplementation(() => { throw error; });
    await expect(init(context)).rejects.toBe(error);
    expect(window.LANDMARK_DETAILS_CONTEXT).toBe(context);
});

const initLandmarkCollectionDetails = importedinitLandmarkCollectionDetails as unknown as Mock<() => unknown>;

function init(context?: unknown) { return initialize(context as LandmarkDetailsContext); }
