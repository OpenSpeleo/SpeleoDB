import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { login } from './viewer-fixture.ts';

/** Observe the normal bootstrap without importing or initializing controllers twice. */
async function observeControllers(page: Page) {
    await page.addInitScript(() => {
        document.addEventListener('speleodb:controller-ready', event => {
            if (event.target instanceof HTMLElement) event.target.dataset.browserReady = 'true';
        });
        document.addEventListener('speleodb:controller-error', event => {
            if (event.target instanceof HTMLElement) event.target.dataset.browserError = 'true';
        });
    });
}

async function openController(page: Page, path: string, controller: string) {
    const response = await page.goto(path);
    expect(response?.status()).toBe(200);
    const declaration = page.locator(`[data-speleodb-controller="${controller}"]`);
    await expect(declaration).toHaveAttribute('data-browser-ready', 'true');
    await expect(page.locator('[data-browser-error]')).toHaveCount(0);
    return declaration;
}

async function endpoint(page: Page, controller: string) {
    const declaration = page.locator(`[data-speleodb-controller="${controller}"]`);
    const context = JSON.parse(await declaration.textContent() || '{}') as { endpoint: string };
    return new URL(context.endpoint, page.url()).href;
}

type FixtureRoute = 'project' | 'readonly_project' | 'cylinder' | 'sensor' | 'readonly_cylinder' | 'experiment' | 'landmarks';
function fixtureRoute(name: FixtureRoute) {
    const routes = JSON.parse(process.env.VIEWER_BROWSER_ROUTES || '{}') as Partial<Record<FixtureRoute, string>>;
    expect(routes[name], 'Run database-backed route cases through tests/browser/test_django_browser.py').toBeTruthy();
    return routes[name]!;
}

async function contextFor(page: Page, path: string, controller: string) {
    const response = await page.request.get(path);
    expect(response.status()).toBe(200);
    const html = await response.text();
    const content = html.match(new RegExp(`data-speleodb-controller="${controller}"[^>]*>([\\s\\S]*?)<\\/script>`));
    expect(content, `${controller} context in ${path}`).toBeTruthy();
    return JSON.parse(content![1]!) as { endpoint: string; deleteUrl: string; unlockUrl: string; dataUrl: string };
}

test.beforeEach(async ({ page }) => { await observeControllers(page); });

test('login validates locally and presents the server authentication error', async ({ page }) => {
    await openController(page, '/login/', 'auth-form');
    await page.locator('#btn_submit').click();
    await expect(page.locator('#error_div')).toContainText('The Email Address is not valid');
    const url = await endpoint(page, 'auth-form');
    await page.route(url, route => route.fulfill({ status: 401, json: { data: { flows: [{ id: 'verify_email' }] } } }));
    await page.locator('#email').fill('browser@example.test');
    await page.locator('#password').fill('invalid-password');
    const request = page.waitForRequest(url);
    await page.locator('#btn_submit').click();
    expect((await request).method()).toBe('POST');
    await expect(page.locator('#error_div')).toContainText('Your email is not verified');
});

test('public mobile menu retains Escape and outside dismissal with real Alpine', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openController(page, '/login/', 'public-shell');
    const toggle = page.locator('[data-speleodb-bind="public-templates-base-2"]');
    const menu = page.locator('[data-speleodb-bind="public-templates-base-3"]');
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await expect(menu).not.toHaveCSS('max-height', '0px');
    await page.keyboard.press('Escape');
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await toggle.click();
    await page.locator('#email').click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
});

test.describe('authenticated controller composition', () => {
    test.beforeEach(async ({ page }) => { await login(page); });

    test('preferences keep independent Alpine scopes, JSON booleans and menu dismissal', async ({ page }) => {
        await openController(page, '/private/preferences/', 'entity-crud');
        const first = page.locator('#email_on_speleodb_updates');
        const second = page.locator('#email_on_projects_updates');
        const firstInitial = await first.isChecked();
        const secondInitial = await second.isChecked();
        await page.locator('label[for="email_on_speleodb_updates"]').click();
        expect(await first.isChecked()).toBe(!firstInitial);
        expect(await second.isChecked()).toBe(secondInitial);
        await expect(page.locator('[data-speleodb-bind="private-user-preferences-2"]'))
            .toHaveText(firstInitial ? 'Off' : 'On');
        const url = await endpoint(page, 'entity-crud');
        await page.route(url, route => route.fulfill({ json: {} }));
        const submitted = page.waitForRequest(url);
        await page.locator('#btn_submit').click();
        const request = await submitted;
        expect(request.method()).toBe('PATCH');
        expect(JSON.parse(request.postData()!) as unknown).toMatchObject({
            email_on_speleodb_updates: !firstInitial,
            email_on_projects_updates: secondInitial,
        });
        expect(request.headers()['x-csrftoken']).toBeTruthy();
        await expect(page.locator('#modal_success')).toBeVisible();
        await page.locator('#modal_success').click();
        const menu = page.locator('[data-speleodb-bind="private-templates-base_private-7"]');
        const panel = page.locator('[data-speleodb-bind="private-templates-base_private-8"]');
        await menu.click();
        await expect(menu).toHaveAttribute('aria-expanded', 'true');
        await expect(panel).toBeVisible();
        await page.keyboard.press('Escape');
        await expect(panel).toBeHidden();
        await expect(menu).toHaveAttribute('aria-expanded', 'false');
    });

    test('feedback retains score selection, multipart submission and reset', async ({ page }) => {
        await openController(page, '/private/feedback/', 'feedback');
        const url = await endpoint(page, 'feedback');
        await page.route(url, route => route.fulfill({ json: {} }));
        await page.locator('[data-score="5"]').click();
        await page.locator('#feedback').fill('Browser feedback');
        const submitted = page.waitForRequest(url);
        await page.locator('#btn_submit').click();
        const request = await submitted;
        expect(request.method()).toBe('POST');
        expect(request.headers()['content-type']).toContain('multipart/form-data; boundary=');
        expect(request.postData()).toContain('name="score"\r\n\r\n5');
        expect(request.postData()).toContain('Browser feedback');
        await expect(page.locator('#modal_success')).toBeVisible();
        await expect(page.locator('#feedback')).toHaveValue('');
        // Setting a hidden input's value also changes its reset default.
        await expect(page.locator('input[name="score"]')).toHaveValue('5');
    });

    test('experiment creation validates required custom fields and duplicate names', async ({ page }) => {
        await openController(page, '/private/experiment/new/', 'experiment-form');
        await page.locator('#btn_submit').click();
        await expect(page.locator('#modal_error_txt')).toContainText('at least one custom field');
        await page.locator('#modal_error').click();
        await page.locator('#add_field_btn').click();
        await page.locator('.field-name').fill('pH');
        await page.locator('.field-type').selectOption('number');
        await page.locator('#add_field_btn').click();
        await page.locator('.field-name').nth(1).fill('pH');
        await page.locator('.field-type').nth(1).selectOption('number');
        await page.locator('#btn_submit').click();
        await expect(page.locator('#modal_error_txt')).toContainText('Duplicate field names');
        await page.locator('#modal_error').click();
        await page.locator('.remove-field-btn').nth(1).click();
        await expect(page.locator('.field-item')).toHaveCount(1);
    });

    for (const kind of ['cylinder', 'sensor'] as const) {
        test(`${kind} fleet creation dialog resets values and cancels without a mutation`, async ({ page }) => {
            await openController(page, fixtureRoute(kind), 'fleet');
            await page.locator(`#add_${kind}_btn`).click();
            await expect(page.locator(`#${kind}_modal`)).toBeVisible();
            await page.locator(`#modal_${kind}_name`).fill('Unsaved browser item');
            await page.locator(`#${kind}_modal_cancel`).click();
            await expect(page.locator(`#${kind}_modal`)).toBeHidden();
            await page.locator(`#add_${kind}_btn`).click();
            await expect(page.locator(`#modal_${kind}_name`)).toHaveValue('');
        });
    }

    test('read-only fleet and project pages omit write actions and reject danger navigation', async ({ page }) => {
        await openController(page, fixtureRoute('readonly_cylinder'), 'fleet');
        await expect(page.locator('#add_cylinder_btn, #add_first_cylinder_btn')).toHaveCount(0);
        await expect(page.locator('#cylinder_modal_save')).toBeHidden();
        await page.goto(fixtureRoute('readonly_project'));
        await expect(page.locator('#btn_submit')).toBeDisabled();
        await expect(page.locator('#btn_lock_project')).toHaveCount(0);
        await page.goto(`${fixtureRoute('readonly_project')}danger_zone/`);
        await expect(page).toHaveURL(new URL(fixtureRoute('readonly_project'), process.env.VIEWER_BROWSER_BASE_URL).href);
        await expect(page.locator('#btn_delete')).toHaveCount(0);
    });

    test('project file selection keeps removal and multipart PUT error recovery', async ({ page }) => {
        await openController(page, `${fixtureRoute('project')}upload/`, 'project-upload');
        await page.locator('#artifact').setInputFiles([
            { name: 'one.dmp', mimeType: 'application/octet-stream', buffer: Buffer.from('one') },
            { name: 'two.dmp', mimeType: 'application/octet-stream', buffer: Buffer.from('two') },
        ]);
        await expect(page.locator('.remove-file')).toHaveCount(2);
        await page.locator('.remove-file').first().click();
        await expect(page.locator('#dropzone')).not.toContainText('one.dmp');
        await expect(page.locator('#dropzone')).toContainText('two.dmp');
        await page.locator('#message').fill('Browser revision');
        const url = await endpoint(page, 'project-upload');
        await page.route(url, route => route.fulfill({ status: 400, json: { detail: 'Fixture upload rejected' } }));
        const submitted = page.waitForRequest(url);
        await page.locator('#btn_submit').click();
        const request = await submitted;
        expect(request.method()).toBe('PUT');
        expect(request.postData()).toContain('filename="two.dmp"');
        expect(request.postData()).not.toContain('filename="one.dmp"');
        expect(request.headers()['x-csrftoken']).toBeTruthy();
        await expect(page.locator('#modal_error_txt')).toContainText('Fixture upload rejected');
        await expect(page.locator('#loading_spinner')).toBeHidden();
    });

    for (const [controller, suffix, button] of [
        ['permission-modal', 'permissions/user/', '#btn_open_add_user'],
        ['team-permission', 'permissions/team/', '#btn_open_add_team'],
    ] as const) {
        test(`${controller} opens a fresh modal and closes through its existing control`, async ({ page }) => {
            await openController(page, `${fixtureRoute('project')}${suffix}`, controller);
            await page.locator(button).click();
            await expect(page.locator('#permission_modal')).toBeVisible();
            await expect(page.locator('#level')).toBeEnabled();
            if (controller === 'permission-modal') await page.locator('#user').fill('unsaved@example.test');
            await page.locator('#permission_modal .btn_close').last().click();
            await expect(page.locator('#permission_modal')).toBeHidden();
            await page.locator(button).click();
            if (controller === 'permission-modal') await expect(page.locator('#user')).toHaveValue('');
            else await expect(page.locator('#team')).toBeEnabled();
        });
    }

    test('danger confirmation submits DELETE only after confirmation and presents failure', async ({ page }) => {
        const path = `${fixtureRoute('project')}danger_zone/`;
        const context = await contextFor(page, path, 'danger-zone');
        const url = new URL(context.deleteUrl, process.env.VIEWER_BROWSER_BASE_URL).href;
        let requests = 0;
        await page.route(url, route => {
            requests++;
            expect(route.request().method()).toBe('DELETE');
            return route.fulfill({ status: 403, json: { detail: 'Fixture deletion denied' } });
        });
        await openController(page, path, 'danger-zone');
        await page.locator('#btn_delete').click();
        await expect(page.locator('#modal_confirmation')).toBeVisible();
        expect(requests).toBe(0);
        await page.locator('#btn_confirmed_delete').click();
        await expect(page.locator('#modal_error_txt')).toContainText('Fixture deletion denied');
        expect(requests).toBe(1);
    });

    test('Git instructions dialog opens and closes with the compiled controller', async ({ page }) => {
        await openController(page, `${fixtureRoute('project')}git_instructions/`, 'git-instructions');
        await page.locator('#btn_show_git_instructions').click();
        await expect(page.locator('#modal_git_instructions')).toBeVisible();
        await expect(page.locator('#modal_git_instructions')).toContainText('git clone');
        await page.locator('#modal_git_instructions .btn_close').first().click();
        await expect(page.locator('#modal_git_instructions')).toBeHidden();
    });

    test('revision download clones keep independent Alpine state', async ({ page }) => {
        const path = `${fixtureRoute('project')}revisions/`;
        const context = await contextFor(page, path, 'revision-history');
        const fixture = await page.request.get(context.endpoint);
        expect(fixture.headers()['x-speleodb-browser-fixture']).toBe('revisions');
        const payload: unknown = await fixture.json();
        expect(payload).toMatchObject({ commits: [{ message: 'Browser revision 1' }, { message: 'Browser revision 2' }] });
        await openController(page, path, 'revision-history');
        const buttons = page.locator('#commit-table-container tr:not(#commit-template) [data-speleodb-bind="revision-project-revision_history-2"]');
        await expect(buttons).toHaveCount(2);
        await buttons.first().click();
        await expect(buttons.first()).toHaveAttribute('aria-expanded', 'true');
        await expect(buttons.nth(1)).toHaveAttribute('aria-expanded', 'false');
        await page.keyboard.press('Escape');
        await expect(buttons.first()).toHaveAttribute('aria-expanded', 'false');
    });

    test('Git tree folder navigation reuses the fetched revision', async ({ page }) => {
        const path = `${fixtureRoute('project')}browser/${'a'.repeat(40)}/`;
        const context = await contextFor(page, path, 'git-view');
        const fixture = await page.request.get(context.endpoint);
        expect(fixture.headers()['x-speleodb-browser-fixture']).toBe('tree');
        const before = Number(fixture.headers()['x-speleodb-fixture-reads']);
        await openController(page, path, 'git-view');
        await expect(page.locator('#commit-message')).toHaveText('Browser tree');
        await page.locator('#git-viewer-container .gitfolder-link').click();
        await expect(page.locator('#git-viewer-container .download-file-name')).toHaveText('cave.dmp');
        await page.locator('#git-viewer-container .gitfolder-link').click();
        await expect(page.locator('#git-viewer-container .gitfolder-name')).toHaveText('surveys');
        const after = await page.request.get(context.endpoint);
        // One controller read plus this measurement read, with no navigation refetch.
        expect(Number(after.headers()['x-speleodb-fixture-reads']) - before).toBe(2);
    });

    test('mutex release restores its button after a rejected POST', async ({ page }) => {
        const path = `${fixtureRoute('project')}mutexes/`;
        const context = await contextFor(page, path, 'mutex-lock');
        const url = new URL(context.unlockUrl, process.env.VIEWER_BROWSER_BASE_URL).href;
        await page.route(url, route => route.fulfill({ status: 409, json: { detail: 'Fixture lock conflict' } }));
        await openController(page, path, 'mutex-lock');
        const button = page.locator('button.btn_unlock');
        const submitted = page.waitForRequest(url);
        await button.click();
        expect((await submitted).method()).toBe('POST');
        await expect(page.locator('#modal_error_txt')).toContainText('Fixture lock conflict');
        await expect(button).toBeEnabled();
    });

    test('project country keyboard collapse persists through a fresh page load', async ({ page }) => {
        await page.setViewportSize({ width: 390, height: 844 });
        await openController(page, '/private/projects/', 'projects');
        const group = page.locator('.country-group').filter({ visible: true }).first();
        const code = await group.getAttribute('data-country-code');
        await group.locator('.country-group-header').press('Enter');
        await expect(group).toHaveClass(/collapsed/);
        const stored = await page.evaluate(() => localStorage.getItem('speleo_projects_collapsed_countries'));
        expect(JSON.parse(stored!) as unknown).toContain(code);
        await page.reload();
        await expect(page.locator(`.country-group[data-country-code="${code}"]`).first()).toHaveClass(/collapsed/);
    });

    test('station tag creation resets its name and color on cancellation', async ({ page }) => {
        await openController(page, '/private/station_tags/', 'station-tags');
        await page.locator('#btn-create-tag').click();
        await expect(page.locator('#edit-tag-modal')).toBeVisible();
        const initialColor = await page.locator('#edit-tag-color').inputValue();
        await page.locator('#edit-tag-name').fill('Unsaved tag');
        await page.locator('.tag-color-picker-option').last().click();
        await page.locator('#edit-tag-modal .btn-close-edit-modal').last().click();
        await expect(page.locator('#edit-tag-modal')).toBeHidden();
        await page.locator('#btn-create-tag').click();
        await expect(page.locator('#edit-tag-name')).toHaveValue('');
        await expect(page.locator('#edit-tag-color')).toHaveValue(initialColor);
    });

    test('export creation rejects safely and restores the request button', async ({ page }) => {
        await openController(page, '/private/exports/', 'user-exports');
        const url = await endpoint(page, 'user-exports');
        await page.route(url, route => route.request().method() === 'POST'
            ? route.fulfill({ status: 403, json: { detail: 'Fixture export denied' } })
            : route.continue());
        const submitted = page.waitForRequest(request => request.url() === url && request.method() === 'POST');
        await page.locator('#export-create').click();
        expect((await submitted).headers()['x-csrftoken']).toBeTruthy();
        await expect(page.locator('#export-message')).toContainText('Fixture export denied');
        await expect(page.locator('#export-create')).toBeEnabled();
    });

    test('read-only experiment grid retries a failed data request with the real vendor', async ({ page }) => {
        const path = fixtureRoute('experiment');
        const context = await contextFor(page, path, 'experiment-data');
        let fail = true;
        await page.route(`**${context.dataUrl}*`, route => fail
            ? route.fulfill({ status: 503, json: { detail: 'Fixture unavailable' } })
            : route.fulfill({ json: { type: 'FeatureCollection', features: [] } }));
        await openController(page, path, 'experiment-data');
        await expect(page.locator('#errorText')).toContainText('Failed to fetch data: 503');
        fail = false;
        await page.locator('#refreshDataBtn').click();
        await expect(page.locator('#dataGridContainer')).toBeVisible();
        await expect(page.locator('#recordCount')).toHaveText('0');
        await expect(page.locator('#errorMessage')).toBeHidden();
    });

    test('read-only landmark collection preserves disabled settings and absent mutation controls', async ({ page }) => {
        await openController(page, fixtureRoute('landmarks'), 'landmark-details');
        await expect(page.locator('#name')).toBeDisabled();
        await expect(page.locator('#add-first-landmark-btn, #landmarks-bulk-delete-btn, .landmark-edit-btn')).toHaveCount(0);
        await expect(page.getByText('No landmarks', { exact: false }).first()).toBeVisible();
    });

    for (const [path, controller] of [['dmp_doctor', 'dmp-doctor'], ['dmp_to_json', 'dmp2json']] as const) {
        test(`${controller} validates files and restores controls after server rejection`, async ({ page }) => {
            await openController(page, `/private/tools/${path}/`, controller);
            const file = page.locator('#fileInput');
            await expect(page.locator('#downloadBtn')).toBeDisabled();
            await file.setInputFiles({ name: 'invalid.txt', mimeType: 'text/plain', buffer: Buffer.from('invalid') });
            await expect(page.locator('#fileErrorDisplay')).toContainText('Invalid file type');
            await expect(page.locator('#downloadBtn')).toBeDisabled();
            await file.setInputFiles({ name: 'survey.DMP', mimeType: 'application/octet-stream', buffer: Buffer.from('survey') });
            await expect(page.locator('#fileNameDisplay')).toContainText('survey.DMP');
            await expect(page.locator('#downloadBtn')).toBeEnabled();
            const url = await endpoint(page, controller);
            await page.route(url, route => route.fulfill({ status: 400, json: { error: 'Fixture conversion rejected' } }));
            const submitted = page.waitForRequest(url);
            await page.locator('#downloadBtn').click();
            const request = await submitted;
            expect(request.method()).toBe('POST');
            expect(request.headers()['content-type']).toContain('multipart/form-data; boundary=');
            expect(request.headers()['x-csrftoken']).toBeTruthy();
            await expect(page.locator('#modal_error_txt')).toHaveText('Fixture conversion rejected');
            await expect(page.locator('#downloadBtn')).toBeEnabled();
        });
    }

    for (const [path, controller, columns] of [['xls_to_dmp', 'xls2dmp', 7], ['xls_to_compass', 'xls2compass', 10]] as const) {
        test(`${controller} preserves contenteditable keyboard navigation and row clearing`, async ({ page }) => {
            await openController(page, `/private/tools/${path}/`, controller);
            await page.locator('#clearBtn').click();
            await expect(page.locator('#dataTable tbody tr')).toHaveCount(0);
            await page.locator('#addRowBtn').click();
            const cells = page.locator('#dataTable tbody tr').first().locator('[contenteditable="true"]');
            await expect(cells).toHaveCount(columns);
            await cells.first().fill('12');
            await cells.first().press('Tab');
            await expect(cells.nth(1)).toBeFocused();
            await page.locator('#addRowBtn').click();
            await expect(page.locator('#dataTable tbody tr')).toHaveCount(2);
            await expect(cells.first()).toHaveText('12');
            await page.locator('#clearBtn').click();
            await expect(page.locator('#dataTable tbody tr')).toHaveCount(0);
            await expect(page.locator('#status')).toHaveText('Cleared.');
        });
    }
});
