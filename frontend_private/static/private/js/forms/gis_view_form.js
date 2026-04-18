/**
 * Shared GIS-view project-picker form used by both the "Create GIS view"
 * and "Edit GIS view" pages.
 *
 * Both templates render an identical dynamic grid of project rows. Each
 * row has:
 *   - a project `<select>` (new rows) OR a hidden `.project-id` input
 *     (pre-existing rows rendered by Django)
 *   - two radio buttons (latest / specific commit)
 *   - a lazy-loaded commit SHA `<select>` that only populates when
 *     "specific" is chosen
 *   - a remove button
 *
 * Usage:
 *   attachGisViewForm({
 *       endpoint: "{% url 'api:v2:gis-views' %}",   // or gis-view-detail for edit
 *       method: 'POST',                             // or 'PUT'
 *       projectsEndpoint: "{% url 'api:v2:projects' %}",
 *       commitsEndpointBuilder: function (projectId) {
 *           return Urls['api:v2:project-geojson-commits'](projectId);
 *       },
 *       // fired on success; receives the server's raw JSON response.
 *       onSuccess: function (data) {
 *           window.location.href = Urls['private:gis_view_details'](data.id);
 *       },
 *       // For the edit page we pre-seed usedProjectIds from rendered
 *       // `.project-item` rows and kick off commit-loading for rows
 *       // whose mode is already "specific".
 *       seedFromExistingRows: true,                 // default false
 *       // Initial projectCounter value (edit page sets this to the
 *       // number of pre-rendered rows so new ids don't collide).
 *       initialProjectCounter: 0,
 *       // New rows use a numeric id by default, or `new_${n}` when this
 *       // prefix is set - matches the convention of each template.
 *       newRowIdPrefix: '',
 *       successMessage: 'The GIS view has been saved.',
 *   });
 *
 * Requires: jQuery, FormModals, showAjaxErrorModal, Utils.safeHtml
 * (for escaping project names into `<option>` text).
 */

/* global FormModals, showAjaxErrorModal, Utils */
/* exported attachGisViewForm */

function _gvfGetCSRFToken() {
    var cookieMatch = document.cookie
        .split('; ')
        .filter(function (row) { return row.indexOf('csrftoken=') === 0; })[0];
    if (cookieMatch) { return cookieMatch.split('=')[1]; }
    var $input = $('input[name^=csrfmiddlewaretoken]').first();
    return $input.length ? $input.val() : '';
}

function _gvfEscape(value) {
    if (typeof Utils !== 'undefined' && Utils && typeof Utils.escapeHtml === 'function') {
        return Utils.escapeHtml(value);
    }
    var div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
}

function attachGisViewForm(options) {
    var endpoint = options.endpoint;
    var method = options.method || 'POST';
    var projectsEndpoint = options.projectsEndpoint;
    var commitsEndpointBuilder = options.commitsEndpointBuilder;
    var onSuccess = options.onSuccess;
    var seedFromExistingRows = Boolean(options.seedFromExistingRows);
    var projectCounter = options.initialProjectCounter || 0;
    var newRowIdPrefix = options.newRowIdPrefix || '';
    var successMessage = options.successMessage || 'The GIS view has been saved.';
    var reloadDelayMs = typeof options.reloadDelayMs === 'number' ? options.reloadDelayMs : 2000;

    if (!endpoint) { throw new Error('attachGisViewForm: endpoint is required'); }
    if (!projectsEndpoint) { throw new Error('attachGisViewForm: projectsEndpoint is required'); }
    if (typeof commitsEndpointBuilder !== 'function') {
        throw new Error('attachGisViewForm: commitsEndpointBuilder must be function(projectId)');
    }

    var availableProjects = [];
    var usedProjectIds = new Set();

    FormModals.bindAutoDismiss();

    function toggleNoProjectsMessage() {
        var $container = $('#projects_container');
        var $message = $('#no_projects_message');
        if ($container.children().length === 0) {
            $message.removeClass('hidden').show();
        } else {
            $message.addClass('hidden').hide();
        }
    }

    function getAvailableProjectsForDropdown(currentProjectId) {
        return availableProjects.filter(function (p) {
            return !usedProjectIds.has(p.id) || p.id === currentProjectId;
        });
    }

    async function loadUserProjects() {
        try {
            var response = await fetch(projectsEndpoint, {
                headers: { 'X-CSRFToken': _gvfGetCSRFToken() },
                credentials: 'same-origin',
            });
            var data = await response.json();
            if (Array.isArray(data)) {
                availableProjects = data.slice().sort(function (a, b) {
                    return (a.name || '').localeCompare(b.name || '');
                });
            }
        } catch (error) {
            console.error('Error loading projects:', error);
        }
    }

    async function loadCommitsForProject(projectId, $select, initialSha) {
        $select.html('<option value="">Loading commits...</option>').prop('disabled', true);
        try {
            var response = await fetch(commitsEndpointBuilder(projectId), {
                headers: { 'X-CSRFToken': _gvfGetCSRFToken() },
                credentials: 'same-origin',
            });
            var data = await response.json();
            if (Array.isArray(data) && data.length > 0) {
                $select.html('<option value="">Select a commit...</option>');
                data.forEach(function (commit) {
                    var date = (commit.commit_date || '').split('T')[0];
                    var commitSha = commit.commit_sha || '';
                    var shortSha = commitSha.substring(0, 8);
                    var author = commit.commit_author_name || 'Unknown';
                    var message = (commit.commit_message || 'No message').split('\n')[0];
                    var truncated = message.length > 50 ? message.substring(0, 50) + '...' : message;
                    var optionText = '[' + date + '] ' + author + ': ' + truncated + ' - ' + shortSha;
                    var $option = $('<option>', { value: commitSha, text: optionText });
                    if (initialSha && commitSha === initialSha) {
                        $option.prop('selected', true);
                    }
                    $select.append($option);
                });
                $select.prop('disabled', false);
                $select.data('loaded', true);
            } else {
                $select.html('<option value="">No GeoJSON commits available</option>').prop('disabled', true);
            }
        } catch (error) {
            console.error('Error loading commits:', error);
            $select.html('<option value="">Error loading commits</option>').prop('disabled', true);
        }
    }

    function createProjectElement(rowId) {
        var avail = getAvailableProjectsForDropdown();
        var projectOptions = avail.map(function (p) {
            return '<option value="' + _gvfEscape(p.id) + '">' + _gvfEscape(p.name) + '</option>';
        }).join('');

        return (
            '<div class="bg-slate-700 rounded-lg p-4 border border-slate-600 project-item" data-project-id="' + _gvfEscape(rowId) + '">' +
            '  <div class="flex flex-col gap-4">' +
            '    <div>' +
            '      <label class="block text-xs font-medium text-slate-400 mb-1">Project<span class="text-rose-600"> *</span></label>' +
            '      <select class="form-select w-full project-select" required>' +
            '        <option value="">Select a project...</option>' +
            projectOptions +
            '      </select>' +
            '    </div>' +
            '    <div>' +
            '      <label class="block text-xs font-medium text-slate-400 mb-2">Commit Selection</label>' +
            '      <div class="flex flex-col sm:flex-row gap-3">' +
            '        <label class="flex items-center cursor-pointer">' +
            '          <input type="radio" name="commit_mode_' + _gvfEscape(rowId) + '" value="latest" class="form-radio commit-mode-radio" checked />' +
            '          <span class="text-sm ml-2 text-slate-300">Always Latest</span>' +
            '        </label>' +
            '        <label class="flex items-center cursor-pointer">' +
            '          <input type="radio" name="commit_mode_' + _gvfEscape(rowId) + '" value="specific" class="form-radio commit-mode-radio" />' +
            '          <span class="text-sm ml-2 text-slate-300">Specific Commit</span>' +
            '        </label>' +
            '      </div>' +
            '    </div>' +
            '    <div class="commit-sha-container hidden">' +
            '      <label class="block text-xs font-medium text-slate-400 mb-1">Commit<span class="text-rose-600"> *</span></label>' +
            '      <select class="form-select w-full commit-sha-select">' +
            '        <option value="">Loading commits...</option>' +
            '      </select>' +
            '      <p class="text-xs text-slate-500 mt-1">Select a commit from the project history</p>' +
            '    </div>' +
            '    <div class="flex justify-end">' +
            '      <button type="button" class="btn-sm bg-rose-500 hover:bg-rose-600 text-white remove-project-btn" data-project-id="' + _gvfEscape(rowId) + '">' +
            '        <svg class="w-4 h-4 fill-current shrink-0 inline-block mr-1" viewBox="0 0 16 16"><path d="M5 7h6v2H5V7z" /></svg>' +
            '        Remove Project' +
            '      </button>' +
            '    </div>' +
            '  </div>' +
            '</div>'
        );
    }

    $('#add_project_btn').click(function (e) {
        e.preventDefault();
        if (getAvailableProjectsForDropdown().length === 0) {
            FormModals.showError("No more projects available to add. You've either added all your projects or you don't have access to any projects.");
            return;
        }
        projectCounter++;
        var rowId = newRowIdPrefix ? newRowIdPrefix + projectCounter : projectCounter;
        $('#projects_container').prepend(createProjectElement(rowId));
        toggleNoProjectsMessage();
    });

    $(document).on('click', '.remove-project-btn', function (e) {
        e.preventDefault();
        var rowId = $(this).data('project-id');
        var $row = $('.project-item[data-project-id="' + rowId + '"]');
        var $projectSelect = $row.find('.project-select');
        if ($projectSelect.length) {
            var selected = $projectSelect.val();
            if (selected) { usedProjectIds.delete(selected); }
        } else {
            var hiddenId = $row.find('.project-id').val();
            if (hiddenId) { usedProjectIds.delete(hiddenId); }
        }
        $row.remove();
        toggleNoProjectsMessage();
    });

    $(document).on('change', '.project-select', function () {
        var $container = $(this).closest('.project-item');
        var oldProjectId = $container.data('selected-project-id');
        var newProjectId = $(this).val();
        if (oldProjectId) { usedProjectIds.delete(oldProjectId); }
        if (newProjectId) {
            usedProjectIds.add(newProjectId);
            $container.data('selected-project-id', newProjectId);
            var isSpecific = $container.find('input[value="specific"]').is(':checked');
            if (isSpecific) {
                loadCommitsForProject(newProjectId, $container.find('.commit-sha-select'));
            }
        }
    });

    $(document).on('change', '.commit-mode-radio', function () {
        var $container = $(this).closest('.project-item');
        var $shaContainer = $container.find('.commit-sha-container');
        var $shaSelect = $container.find('.commit-sha-select');
        if ($(this).val() === 'specific') {
            $shaContainer.removeClass('hidden');
            $shaSelect.prop('required', true);
            var $projectSelect = $container.find('.project-select');
            var projectId = $projectSelect.length
                ? $projectSelect.val()
                : $container.find('.project-id').val();
            if (projectId && !$shaSelect.data('loaded')) {
                loadCommitsForProject(projectId, $shaSelect);
            }
        } else {
            $shaContainer.addClass('hidden');
            $shaSelect.prop('required', false);
        }
    });

    function collectFormData() {
        var projects = [];
        $('.project-item').each(function () {
            var projectId;
            var $projectSelect = $(this).find('.project-select');
            if ($projectSelect.length) {
                projectId = $projectSelect.val();
            } else {
                projectId = $(this).find('.project-id').val();
            }
            var useLatest = $(this).find('input[value="latest"]').is(':checked');
            var commitSha = $(this).find('.commit-sha-select').val();
            if (projectId) {
                projects.push({
                    project_id: projectId,
                    use_latest: useLatest,
                    commit_sha: useLatest ? '' : (commitSha || ''),
                });
            }
        });
        return {
            name: $('#name').val().trim(),
            description: $('#description').val().trim(),
            allow_precise_zoom: $('#allow_precise_zoom').is(':checked'),
            projects: projects,
        };
    }

    $('#btn_submit').click(function (e) {
        e.preventDefault();
        $('#error_div').hide();
        $('#success_div').hide();

        var payload = collectFormData();
        if (!payload.name) {
            FormModals.showError('Please enter a name for the GIS view.');
            return false;
        }
        if (payload.projects.length === 0) {
            FormModals.showError('Please add at least one project to the GIS view.');
            return false;
        }
        var hasInvalidCommit = false;
        $('.project-item').each(function () {
            var useLatest = $(this).find('input[value="latest"]').is(':checked');
            var commitSha = $(this).find('.commit-sha-select').val();
            if (!useLatest && !commitSha) { hasInvalidCommit = true; }
        });
        if (hasInvalidCommit) {
            FormModals.showError("Projects with 'Specific Commit' mode must have a commit selected.");
            return false;
        }

        var csrftoken = _gvfGetCSRFToken();

        $.ajax({
            url: endpoint,
            method: method,
            data: JSON.stringify(payload),
            contentType: 'application/json; charset=utf-8',
            cache: false,
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-CSRFToken', csrftoken);
                return true;
            },
            success: function (data) {
                FormModals.showSuccess(successMessage);
                window.setTimeout(function () {
                    if (typeof onSuccess === 'function') {
                        onSuccess(data);
                    } else {
                        window.location.reload();
                    }
                }, reloadDelayMs);
            },
            error: function (xhr) {
                showAjaxErrorModal(xhr);
            },
        });
        return false;
    });

    loadUserProjects();

    if (seedFromExistingRows) {
        $('.project-item').each(function () {
            var pid = $(this).find('.project-id').val();
            if (pid) { usedProjectIds.add(pid); }
            var $commitSelect = $(this).find('.commit-sha-select');
            var projectIdAttr = $commitSelect.data('project-id');
            var initialSha = $commitSelect.data('initial-sha');
            if (projectIdAttr && !$(this).find('input[value="latest"]').is(':checked')) {
                loadCommitsForProject(projectIdAttr, $commitSelect, initialSha);
            }
        });
    }

    toggleNoProjectsMessage();
}
