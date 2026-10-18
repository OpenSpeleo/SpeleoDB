import type {
    Cylinder, CylinderFleetWithPerm, CylinderInstall, CylinderInstallCreateRequestRequest, CylinderInstallFeatureProperties,
    CylinderPressureCheck, CylinderPressureCheckRequest, Sensor, SensorFleetWithPerm,
    SensorInstall, V2CylinderInstallsListParams,
} from '@speleodb/api';

export type SensorFleetRecord = SensorFleetWithPerm;
export type CylinderFleetRecord = CylinderFleetWithPerm;
export type FleetRecord = SensorFleetRecord | CylinderFleetRecord;
export type SensorRecord = Sensor;
export type SensorInstallRecord = SensorInstall;
export type CylinderRecord = Cylinder;
export type CylinderInstallWrite = CylinderInstallCreateRequestRequest;
export type CylinderInstallRecord = CylinderInstallFeatureProperties;
export type CylinderInstallDetails = CylinderInstall;
export type PressureCheckWrite = CylinderPressureCheckRequest;
export type PressureCheckRecord = CylinderPressureCheck;
export type CylinderInstallQuery = V2CylinderInstallsListParams;
