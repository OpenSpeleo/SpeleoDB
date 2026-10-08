import type { LandmarkDetailsContext } from '../../ts-types/controllers/landmark-details.ts';
export async function init(context: LandmarkDetailsContext) {
    window.LANDMARK_DETAILS_CONTEXT = context;
    const { initLandmarkCollectionDetails } = await import(
        '../../frontend_private/static/private/ts/landmark_collection/details_main.ts'
    );
    initLandmarkCollectionDetails();
}
