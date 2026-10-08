/** Accept only the hex color forms supported by existing application facades. */
export function isValidCssColor(color: unknown): color is string {
    if (!color || typeof color !== 'string') return false;
    return /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/.test(color);
}
