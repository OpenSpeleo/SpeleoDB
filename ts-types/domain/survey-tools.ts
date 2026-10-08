export interface SurveyToolErrorBody { error?: string; detail?: string; message?: string }
export interface SurveyToolAjaxFailure { responseJSON?: SurveyToolErrorBody; responseText?: string }
export interface SurveyLocation { display_name: string; lat: string; lon: string }
/** Column names are supplied by the owning survey format. */
export type SurveyShot = Record<string, string>;
export interface CompassSurveyPayload {
    shots: SurveyShot[];
    survey_date: string;
    unit: string;
    cave_name: string;
    survey_name: string;
    survey_team: string[];
    comment: string;
    latitude?: number;
    longitude?: number;
}
