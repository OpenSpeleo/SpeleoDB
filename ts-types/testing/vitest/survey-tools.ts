import type { Mock } from 'vitest';
import type { SurveyToolAjaxFailure } from '../../domain/survey-tools.ts';
import type { SurveyTableOptions } from '../../domain/forms/tools.ts';

export interface SurveyToolAjaxCall {
    url: string;
    method: string;
    headers?: Record<string, string>;
    data?: string | FormData;
    beforeSend?: (xhr: {setRequestHeader(name: string, value: string): void}) => boolean;
    success: (response: unknown) => void;
    error: (xhr: SurveyToolAjaxFailure, status: string, error: string) => void;
}
export interface UploadToolDouble {
    getFile: Mock<() => File | null>;
    setStatus: Mock<(text?: string, color?: string, weight?: string) => void>;
    reset: Mock<() => void>;
}
export interface SurveyTableDouble {
    renderRows: Mock<(rows: unknown[][]) => void>;
    validateTable: Mock<() => boolean>;
}
export type ConfiguredSurveyOptions = SurveyTableOptions & Required<Pick<SurveyTableOptions,
    'validateCell' | 'parseClipboardText' | 'lastRowErrorMessage'>>;
