import { getCSRFTokenFromInput, getCSRFTokenFromCookie, normalizeCSRFToken } from '../../../../../frontend_common/runtime/csrf.ts';
import { DEFAULTS } from './defaults.ts';
import { getRuntimeContext } from './runtime_context.ts';

/** Map transport preserves input, decoded-cookie, then runtime-context precedence. */
export function getMapCSRFToken(): string {
    return getCSRFTokenFromInput(DEFAULTS.CSRF)
        || getCSRFTokenFromCookie(DEFAULTS.CSRF)
        || normalizeCSRFToken(getRuntimeContext().csrfToken, DEFAULTS.CSRF);
}
