/** Validation policy is supplied by the owner; form transports may use different rules. */
export interface CSRFTokenPolicy { SECRET_LENGTH: number; TOKEN_LENGTH: number }

function isValidCSRFToken(token: string, policy: CSRFTokenPolicy) {
    const pattern = new RegExp(
        `^[A-Za-z0-9]{${policy.SECRET_LENGTH}}$|^[A-Za-z0-9]{${policy.TOKEN_LENGTH}}$`
    );
    return pattern.test(token);
}

export function normalizeCSRFToken(token: unknown, policy: CSRFTokenPolicy) {
    if (typeof token !== 'string') return '';
    const trimmed = token.trim();
    return isValidCSRFToken(trimmed, policy) ? trimmed : '';
}

export function getCSRFTokenFromInput(policy: CSRFTokenPolicy) {
    const input = document.querySelector<HTMLInputElement>('input[name="csrfmiddlewaretoken"]');
    return normalizeCSRFToken(input?.value, policy);
}

export function getCSRFTokenFromCookie(policy: CSRFTokenPolicy) {
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.slice('csrftoken='.length);
    if (!cookieValue) return '';
    try {
        return normalizeCSRFToken(decodeURIComponent(cookieValue), policy);
    } catch {
        return normalizeCSRFToken(cookieValue, policy);
    }
}
