import { v2UserReleaseAllLocksDestroy, v2ProjectsReleaseCreateWithJson, v2ProjectsList } from '@speleodb/api';
import { apiData, webApiOptions } from '../api/client.ts';
import type { ProjectsContext } from '../../ts-types/controllers/projects.ts';
import type { EntityId } from '../../ts-types/domain/identifiers.ts';
import { showApiErrorModal } from '../../frontend_private/static/private/ts/forms/api_errors.ts';

export function init(context: ProjectsContext) {
    $("body").click(function() {
            if ($("#modal_success").is(":visible")) {
                $("#modal_success").hide();
            }
            if ($("#modal_error").is(":visible")) {
                $("#modal_error").hide();
            }
            if ($("#modal_confirmation_unlock").is(":visible")) {
                $("#modal_confirmation_unlock").hide();
            }
            if ($("#modal_confirmation_mass_unlock").is(":visible")) {
                $("#modal_confirmation_mass_unlock").hide();
            }
        });

        $('#btn_release_all_locks').click(function (e) {
            $("#modal_confirmation_mass_unlock").css('display', 'flex');
            return false; // prevent default
        });

        $('#btn_confirmed_mass_unlock').click(function () {
            $("#error_div").hide();
            $("#success_div").hide();
            $("#modal_confirmation_mass_unlock").hide();

            void apiData(v2UserReleaseAllLocksDestroy(webApiOptions())).then(function () {
                    $("#modal_success_txt").html("All the projects have been unlocked.");
                    $("#modal_success").css('display', 'flex');

                    window.setTimeout(function(){
                        // Redirect to project listing
                        window.location.href = context.projectsUrl;
                    }, 2000);
            }).catch(showApiErrorModal);
            return false; // prevent default
        });

        $('.btn-unlock').click(function (e) {
            console.log("Unlocking project: " + ($(this).data('project_id') as EntityId));
            $('#btn_confirmed_unlock').data('project_id', ($(this).data('project_id') as EntityId));
            $("#modal_confirmation_unlock").css('display', 'flex');
            return false; // prevent default
        });

        $('#btn_confirmed_unlock').click(function () {
            $("#error_div").hide();
            $("#success_div").hide();
            $("#modal_confirmation_unlock").hide();

            void apiData(v2ProjectsReleaseCreateWithJson(String($(this).data('project_id')), {}, webApiOptions())).then(function () {
                    $("#modal_success_txt").html("The project has been unlocked for edition.");
                    $("#modal_success").css('display', 'flex');

                    window.setTimeout(function(){
                        // Refresh the page
                        window.location.reload();
                    }, 2000);
            }).catch(showApiErrorModal);
            return false; // prevent default
        });

        // Fetch all projects at once and update revision counts
        void apiData(v2ProjectsList(webApiOptions())).then(function(data) {
                if (Array.isArray(data)) {
                    // Create a map of project_id -> commit_count for quick lookup
                    var commitCounts: Record<string, number> = {};
                    data.forEach(function(project) {
                        commitCounts[project.id] = project.commit_count;
                    });

                    // Update all revision elements
                    $('.async_revision').each(function() {
                        var $element = $(this);
                        var target_div = $("#" + ($element.data('id') as string));
                        var project_id = $element.data('project_id') as EntityId;

                        if (commitCounts.hasOwnProperty(project_id)) {
                            target_div.html(commitCounts[project_id] as unknown as string);
                        } else {
                            target_div.html("-");
                        }
                    });
                } else {
                    console.log("ERROR: unexpected response", data);
                    // Set all elements to error state
                    $('.async_revision').each(function() {
                        $("#" + ($(this).data('id') as string)).html("-");
                    });
                }
        }).catch(function(error: unknown) {
                console.error("Failed to load project revision counts", error);
                // Set all elements to error state
                $('.async_revision').each(function() {
                    $("#" + ($(this).data('id') as string)).html("-");
                });
        });

        // Country group collapse/expand with localStorage persistence
        var STORAGE_KEY = 'speleo_projects_collapsed_countries';

        function getCollapsedCountries() {
            try {
                var stored = localStorage.getItem(STORAGE_KEY);
                return stored ? JSON.parse(stored) as string[] : [];
            } catch (e) {
                return [];
            }
        }

        function saveCollapsedCountries(collapsed: string[]) {
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(collapsed));
            } catch (e) {
                // localStorage unavailable
            }
        }

        function toggleCountryGroup(header: HTMLElement) {
            var $group = $(header).closest('.country-group');
            $group.toggleClass('collapsed');

            var code = $group.data('country-code') as string;
            var current = getCollapsedCountries();
            var idx = current.indexOf(code);
            if ($group.hasClass('collapsed')) {
                if (idx === -1) current.push(code);
            } else {
                if (idx !== -1) current.splice(idx, 1);
            }
            saveCollapsedCountries(current);
        }

        // Click handler for all country group headers
        $('.country-group-header').click(function() {
            toggleCountryGroup(this);
        });

        // Keyboard handler (Enter / Space) for accessibility
        $('.country-group-header, .country-group-header-inner').on('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleCountryGroup($(this).closest('.country-group-header')[0] || this);
            }
        });
}
