export interface SurveyLocation { display_name: string; lat: string; lon: string }
/** Column names are supplied by the owning survey format. */
export type SurveyShot = Record<string, string>;
