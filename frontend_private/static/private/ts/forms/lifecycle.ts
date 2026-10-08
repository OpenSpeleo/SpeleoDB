/** Raw jQuery field policy: callers deliberately keep their existing selector. */
export function readFormCSRFToken(selector = 'input[name^=csrfmiddlewaretoken]'): string {
    return $(selector).val() as string;
}

export function hideFormStatus(): void {
    $('#error_div').hide();
    $('#success_div').hide();
}

/** Resolve the current location only when the existing delay expires. */
export function scheduleFormReload(delay: number): void {
    window.setTimeout(function () { window.location.reload(); }, delay);
}

export function scheduleFormRedirect(target: string, delay: number): void {
    window.setTimeout(function () { window.location.href = target; }, delay);
}
