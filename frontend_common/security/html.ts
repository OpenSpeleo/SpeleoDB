/** Escape a value for HTML text or a quoted attribute without changing coercion. */
export function escapeHtml(text: unknown): string {
    if (text === null || text === undefined) return '';
    const str = String(text);
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
