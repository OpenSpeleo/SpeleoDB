import type { CylinderInstalls } from '../../frontend_private/static/private/ts/map_viewer/stations/cylinders.ts';
import type { StationSensors } from '../../frontend_private/static/private/ts/map_viewer/stations/sensors.ts';
import type { StationTags } from '../../frontend_private/static/private/ts/map_viewer/stations/tags.ts';

/** Existing private composition supplies these owners, retaining their method receivers. */
export interface MapActionRegistry {
    cylinder: typeof CylinderInstalls;
    sensors: typeof StationSensors;
    tags: typeof StationTags;
    navigation: {
        reload: () => void;
        returnToStationManager: () => void;
    };
}
