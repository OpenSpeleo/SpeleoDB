import { escapeHtml as escapeHtmlValue } from '../../../../frontend_common/security/html.ts';
import { isValidCssColor as isValidColorValue } from '../../../../frontend_common/security/color.ts';
import { sanitizeUrl as sanitizeUrlValue } from '../../../../frontend_common/security/url.ts';

/**
 * Shared XSS helper functions.
 *
 * Exported as ES-module functions for shared forms and route controllers.
 * These functions and the map Utils facade share the same security primitives;
 * each facade retains its existing fallback and receiver policies.
 */

/* exported escapeHtml, isValidCssColor, safeCssColor, sanitizeUrl */

export function escapeHtml(text: unknown): string {
    return escapeHtmlValue(text);
}

export function isValidCssColor(color: unknown): boolean {
    return isValidColorValue(color);
}

export function safeCssColor(color: unknown, fallback?: string | null): string {
    return isValidCssColor(color) ? color as string : (fallback || '#94a3b8');
}

export function sanitizeUrl(url: unknown): string {
    return sanitizeUrlValue(url);
}
