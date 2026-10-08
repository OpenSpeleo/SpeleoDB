/** AJAX failures may omit a parsed body or status text. Body fields are untrusted. */
export interface AjaxFailure {
    responseJSON?: unknown;
    status?: number;
    statusText?: string;
}
