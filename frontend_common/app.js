const CONTROLLER_SELECTOR = '[data-speleodb-controller]';
const controllerModules = import.meta.glob('./controllers/*.js');
const initializedElements = new WeakSet();

function applyCriticalRouteState() {
    if (!document.querySelector('[data-speleodb-controller="projects"]')) return;
    try {
        const stored = window.localStorage.getItem('speleo_projects_collapsed_countries');
        const countryCodes = stored ? JSON.parse(stored) : [];
        if (!Array.isArray(countryCodes)) return;
        countryCodes.forEach(countryCode => {
            const escapedCode = window.CSS.escape(String(countryCode));
            document.querySelectorAll(`.country-group[data-country-code="${escapedCode}"]`)
                .forEach(group => group.classList.add('collapsed'));
        });
    } catch {
        // Storage may be unavailable or corrupt; expanded groups are the safe default.
    }
}

export function captureInitialControllerState(root = document) {
    root.querySelectorAll('canvas[data-particle-animation]').forEach(canvas => {
        const container = canvas.parentElement;
        if (!container) return;
        canvas.dataset.initialParticleWidth = String(container.offsetWidth);
        canvas.dataset.initialParticleHeight = String(container.offsetHeight);
    });
}

function controllerModulePath(name) {
    return `./controllers/${name}.js`;
}

export function readControllerContext(element) {
    const rawContext = element.textContent?.trim() || element.dataset.speleodbContext;
    if (!rawContext) return {};

    try {
        return JSON.parse(rawContext);
    } catch (error) {
        throw new Error(
            `Invalid JSON context for controller "${element.dataset.speleodbController}"`,
            { cause: error },
        );
    }
}

export async function initializeController(element) {
    if (initializedElements.has(element)) return;

    const name = element.dataset.speleodbController;
    const loadController = controllerModules[controllerModulePath(name)];
    if (!loadController) {
        throw new Error(`Unknown SpeleoDB controller: "${name}"`);
    }

    const controller = await loadController();
    if (typeof controller.init !== 'function') {
        throw new Error(`SpeleoDB controller "${name}" does not export init()`);
    }

    await controller.init(readControllerContext(element), element);
    initializedElements.add(element);
    element.dispatchEvent(new CustomEvent('speleodb:controller-ready', {
        bubbles: true,
        detail: { name },
    }));
}

export async function initializeControllers(root = document) {
    const elements = Array.from(root.querySelectorAll(CONTROLLER_SELECTOR));
    for (const element of elements) {
        try {
            await initializeController(element);
        } catch (error) {
            console.error(error);
            element.dispatchEvent(new CustomEvent('speleodb:controller-error', {
                bubbles: true,
                detail: {
                    name: element.dataset.speleodbController,
                    error,
                },
            }));
        }
    }
}

if (typeof document !== 'undefined') {
    applyCriticalRouteState();
    captureInitialControllerState();
    // Every template places this module after its controller declarations at the
    // end of <body>. Initialize there, matching the readiness semantics of the
    // classic tail scripts and inline handlers that these controllers replace.
    // Waiting for DOMContentLoaded subtly changes measurements made by code such
    // as the public particle canvas and is therefore not behaviorally equivalent.
    initializeControllers();
}
