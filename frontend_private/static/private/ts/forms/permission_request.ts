interface PermissionRequestOptions {
    endpoint: string | undefined;
    method: string;
    data: string;
    csrfToken: string;
    validate?: (this: unknown, xhr: JQuery.jqXHR<unknown>, settings: JQuery.AjaxSettings<unknown>) => boolean;
    success: NonNullable<JQuery.AjaxSettings<unknown>['success']>;
    error: NonNullable<JQuery.AjaxSettings<unknown>['error']>;
}

/** Shared user/team request mechanics; validation and modal policy stay with each owner. */
export function sendPermissionRequest(options: PermissionRequestOptions): void {
    $.ajax({
        url: options.endpoint,
        method: options.method,
        data: options.data,
        contentType: 'application/json; charset=utf-8',
        cache: false,
        beforeSend: function (xhr, settings) {
            xhr.setRequestHeader('X-CSRFToken', options.csrfToken);
            return options.validate ? options.validate.call(this, xhr, settings) : true;
        },
        success: options.success,
        error: options.error,
    });
}
