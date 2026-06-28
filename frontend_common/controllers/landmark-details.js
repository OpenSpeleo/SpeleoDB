export async function init(context) {
    window.LANDMARK_DETAILS_CONTEXT = context;
    const { initLandmarkCollectionDetails } = await import(
        '../../frontend_private/static/private/js/landmark_collection/details_main.js'
    );
    initLandmarkCollectionDetails();
}
