/** Preserve the trimmed input for accepted HTTP(S) or relative URLs. */
export function sanitizeUrl(url: unknown): string {
    if (!url || typeof url !== 'string') return '';
    const trimmed = url.trim();
    if (trimmed === '') return '';
    try {
        const parsed = new URL(trimmed, window.location.origin);
        if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
            return trimmed;
        }
    } catch (_) {
        if (!/^[a-zA-Z][a-zA-Z0-9+\-.]*:/.test(trimmed)) {
            return trimmed;
        }
    }
    return '';
}
