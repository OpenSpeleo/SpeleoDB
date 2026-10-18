import { createMapNavigation } from '@speleodb/map-viewer/navigation';

/** Both web composition roots use the viewer's single camera-intent owner. */
const navigation = createMapNavigation();
export const beginMapNavigation = navigation.begin;
export const cancelMapNavigation = navigation.cancel;
export const resetMapNavigation = navigation.reset;
