interface PermissionRequestOptions {
    request: () => Promise<unknown>;
    validate?: () => boolean;
    success: () => void;
    error: (error: unknown) => void;
}

/** Shared permission form lifecycle; callers supply typed generated operations. */
export function sendPermissionRequest(options: PermissionRequestOptions): void {
    if (options.validate?.() === false) return;
    void options.request().then(options.success, options.error);
}
