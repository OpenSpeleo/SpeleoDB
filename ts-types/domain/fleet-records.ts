import type { EntityId } from './identifiers.ts';
import type { RecordDates } from './station-records.ts';
export interface FleetRecord extends RecordDates {
    id: EntityId;
    name: string;
    description: string;
    is_active: boolean;
    user_permission_level?: number;
    user_permission_level_label?: string;
}
export interface SensorFleetRecord extends FleetRecord { sensor_count: number }
export interface CylinderFleetRecord extends FleetRecord { cylinder_count: number }
export interface SensorRecord extends RecordDates {
    active_installs?: SensorInstallRecord[];
    id: EntityId;
    name: string;
    notes: string;
    fleet: EntityId;
    fleet_id?: EntityId;
    fleet_name?: string;
    status: string;
}
export interface SensorInstallRecord extends RecordDates {
    id: EntityId;
    sensor: EntityId;
    station: EntityId;
    install_date: string;
    install_user: string;
    uninstall_date: string | null;
    uninstall_user: string | null;
    status: string;
    expiracy_memory_date: string | null;
    expiracy_battery_date: string | null;
    sensor_id?: EntityId;
    sensor_name?: string;
    sensor_fleet_id?: EntityId;
    sensor_fleet_name?: string;
    station_id?: EntityId;
    station_name?: string;
}
export interface CylinderRecord extends RecordDates {
    active_installs?: CylinderInstallRecord[];
    id: EntityId;
    name: string;
    serial: string;
    brand: string;
    owner: string;
    notes: string;
    type: string;
    o2_percentage?: number;
    he_percentage: number;
    pressure: number;
    unit_system: string;
    fleet: EntityId;
    use_anode: boolean;
    manufactured_date: string | null;
    last_visual_inspection_date: string | null;
    last_hydrostatic_test_date: string | null;
    status: string;
}
export interface CylinderInstallWrite {
    cylinder?: EntityId;
    latitude?: number | string;
    longitude?: number | string;
    notes?: string;
    location_name?: string;
    project?: EntityId | null;
    distance_from_entry?: number | null;
    unit_system?: string;
    install_date?: string;
    install_user?: string;
    uninstall_date?: string | null;
    uninstall_user?: string | null;
    status?: string;
}
export interface CylinderInstallRecord extends CylinderInstallWrite, RecordDates { id: EntityId }
export interface PressureCheckWrite {
    user?: string;
    notes?: string;
    pressure?: number;
    unit_system?: string;
    check_date?: string;
}
export interface PressureCheckRecord extends PressureCheckWrite, RecordDates { id: EntityId; install: EntityId }
export interface CylinderInstallQuery { cylinder_id?: EntityId; fleet_id?: EntityId; status?: string }

/** Additional fields returned by the install detail serializer. */
export interface CylinderInstallDetails extends CylinderInstallRecord {
    status: string;
    cylinder_id: EntityId;
    cylinder_name: string;
    cylinder_serial: string;
    cylinder_fleet_id: EntityId;
    cylinder_fleet_name: string;
    cylinder_unit_system: string;
    project_id: EntityId | null;
    project_name: string | null;
    pressure_check_count: number;
}
