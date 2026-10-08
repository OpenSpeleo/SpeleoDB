export interface ToolFileUploadOptions {
    dropZoneSelector: string;
    fileInputSelector: string;
    fileNameSelector: string;
    fileErrorSelector: string;
    actionButtonSelector?: string;
    statusSelector?: string;
    allowedExtensions?: unknown[];
    readyMessage?: string;
    invalidMessage?: string;
    onFileSelected?: (file: File) => void;
}
export interface SurveyTableOptions {
    tableBodySelector?: string;
    statusSelector?: string;
    addRowBtnSelector?: string;
    clearBtnSelector?: string;
    pasteBtnSelector?: string;
    COLUMNS?: string[];
    validateCell?: (value: string, column: string, isLastRow: boolean) => boolean;
    parseClipboardText?: (text: string) => unknown[][];
    lastRowAllowedColumns?: string[];
    lastRowErrorMessage?: (fields: string[]) => string;
    dataTableSelector?: string;
}
