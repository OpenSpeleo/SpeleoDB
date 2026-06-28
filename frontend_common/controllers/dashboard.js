import {
    buildCommitsChartConfig,
    buildProjectsChartConfig,
    computeHeatmapStats,
    formatNumber,
    getAvatarColor,
    getHeatmapLevel,
    getInitials,
    groupTimestampsByLocalDate,
} from '../../frontend_private/static/private/js/dashboard-helpers.js';
import { escapeHtml } from '../../frontend_private/static/private/js/xss-helpers.js';

export function init() {
    var commitsChart = null;
        var projectsChart = null;

        function populateStatCards(summary) {
            $('#stat-projects').text(formatNumber(summary.total_projects));
            $('#stat-teams').text(formatNumber(summary.total_teams));
            $('#stat-commits').text(formatNumber(summary.user_commits));
            $('#stat-stations').text(formatNumber(summary.total_stations_created));
            $('#stat-landmarks').text(formatNumber(summary.total_landmarks));
            $('#stat-gps-tracks').text(formatNumber(summary.total_gps_tracks));
        }

        function showStatCardErrors() {
            $('#stat-cards .stat-value').text('-');
        }

        function initCommitsChart(commitsOverTime) {
            var ctx = document.getElementById('commits-chart');
            if (!ctx) return;

            var config = buildCommitsChartConfig(commitsOverTime);
            config.data.datasets[0].backgroundColor = 'rgba(129,140,248,0.1)';
            config.data.datasets[0].fill = true;
            config.data.datasets[0].tension = 0.3;
            config.data.datasets[0].pointRadius = 3;
            config.data.datasets[0].pointHoverRadius = 5;
            config.data.datasets[1].backgroundColor = 'rgba(52,211,153,0.1)';
            config.data.datasets[1].fill = true;
            config.data.datasets[1].tension = 0.3;
            config.data.datasets[1].pointRadius = 3;
            config.data.datasets[1].pointHoverRadius = 5;

            config.options = {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: {
                        labels: { color: '#94a3b8', usePointStyle: true, pointStyle: 'circle' }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#64748b' },
                        grid: { color: 'rgba(51,65,85,0.4)' }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { color: '#64748b', precision: 0 },
                        grid: { color: 'rgba(51,65,85,0.4)' }
                    }
                }
            };

            commitsChart = new window.Chart(ctx, config);
        }

        function initProjectsChart(projectsByType) {
            var ctx = document.getElementById('projects-chart');
            if (!ctx) return;

            var config = buildProjectsChartConfig(projectsByType);

            if (config.isEmpty) {
                $(ctx).hide();
                $('#projects-chart-empty').removeClass('hidden');
                return;
            }

            config.data.datasets[0].borderColor = '#1e293b';
            config.data.datasets[0].borderWidth = 2;
            config.options = {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#94a3b8', usePointStyle: true, pointStyle: 'circle', padding: 16 }
                    }
                }
            };

            projectsChart = new window.Chart(ctx, config);
        }

        function renderHeatmap(calendarTimestamps) {
            var table = document.getElementById('contribution-heatmap');
            if (!table) return;

            var calendar = groupTimestampsByLocalDate(
                Array.isArray(calendarTimestamps) ? calendarTimestamps : []
            );
            if (!Array.isArray(calendarTimestamps) && calendarTimestamps && typeof calendarTimestamps === 'object') {
                calendar = calendarTimestamps;
            }

            var today = new Date();
            today.setHours(0, 0, 0, 0);

            function toMonday(d) { return (d.getDay() + 6) % 7; }

            var totalWeeks = 53;
            var endDate = new Date(today);
            endDate.setDate(endDate.getDate() + (6 - toMonday(endDate)));
            var startDate = new Date(endDate);
            startDate.setDate(startDate.getDate() - (totalWeeks * 7) + 1);

            var weeks = [];
            var cursor = new Date(startDate);

            for (var w = 0; w < totalWeeks; w++) {
                var week = [];
                for (var d = 0; d < 7; d++) {
                    var key = cursor.getFullYear() + '-' +
                        String(cursor.getMonth() + 1).padStart(2, '0') + '-' +
                        String(cursor.getDate()).padStart(2, '0');
                    var isFuture = cursor > today;
                    var count = isFuture ? 0 : (calendar[key] || 0);
                    week.push({ date: new Date(cursor), key: key, count: count, future: isFuture });
                    cursor.setDate(cursor.getDate() + 1);
                }
                weeks.push(week);
            }

            var stats = computeHeatmapStats(calendar);

            var monthHeaders = [];
            var prevMKey = '';
            for (var w = 0; w < totalWeeks; w++) {
                var firstDay = weeks[w][0];
                var mKey = firstDay.date.getFullYear() + '-' + firstDay.date.getMonth();
                if (mKey !== prevMKey) {
                    var yr = String(firstDay.date.getFullYear()).slice(-2);
                    monthHeaders.push({
                        label: firstDay.date.toLocaleString('en', { month: 'short' }) + ' ' + yr,
                        startCol: w
                    });
                    prevMKey = mKey;
                }
            }
            for (var i = 0; i < monthHeaders.length; i++) {
                var nextStart = (i + 1 < monthHeaders.length) ? monthHeaders[i + 1].startCol : totalWeeks;
                monthHeaders[i].colspan = nextStart - monthHeaders[i].startCol;
            }

            var dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

            function ordinal(n) {
                var s = ['th','st','nd','rd'];
                var v = n % 100;
                return n + (s[(v - 20) % 10] || s[v] || s[0]);
            }
            var tipMonths = ['January','February','March','April','May','June',
                             'July','August','September','October','November','December'];

            var html = '<colgroup><col class="hm-label-col">';
            for (var c = 0; c < totalWeeks; c++) html += '<col>';
            html += '</colgroup>';

            html += '<thead><tr><td></td>';
            for (var i = 0; i < monthHeaders.length; i++) {
                html += '<td colspan="' + monthHeaders[i].colspan + '">' + monthHeaders[i].label + '</td>';
            }
            html += '</tr></thead><tbody>';

            for (var row = 0; row < 7; row++) {
                html += '<tr>';
                html += '<td class="hm-day-label">' + dayLabels[row] + '</td>';
                for (var col = 0; col < totalWeeks; col++) {
                    var cell = weeks[col][row];
                    if (cell.future) {
                        html += '<td></td>';
                    } else {
                        var lvl = getHeatmapLevel(cell.count);
                        var cd = cell.date;
                        var tip = cell.count + ' contribution' + (cell.count !== 1 ? 's' : '') +
                            ' on ' + tipMonths[cd.getMonth()] + ' ' + ordinal(cd.getDate()) + '.';
                        html += '<td><div class="hm-cell hm-level-' + lvl + '" data-tip="' + tip + '" title="' + tip + '" aria-label="' + tip + '"></div></td>';
                    }
                }
                html += '</tr>';
            }
            html += '</tbody>';
            table.innerHTML = html;

            var el;
            el = document.getElementById('heatmap-total-count');
            if (el) el.textContent = stats.total.toLocaleString();

            el = document.getElementById('heatmap-week-count');
            if (el) el.textContent = stats.weekCount.toLocaleString();

            el = document.getElementById('heatmap-month-count');
            if (el) el.textContent = stats.monthCount.toLocaleString();

            var busiestEl = document.getElementById('heatmap-busiest-day');
            var busiestCountEl = document.getElementById('heatmap-busiest-count');
            if (busiestEl) {
                if (stats.busiestDayCount > 0) {
                    var bd = new Date(stats.busiestDay + 'T00:00:00');
                    busiestEl.textContent = bd.toLocaleDateString('en', { month: 'short', day: 'numeric', year: 'numeric' });
                    if (busiestCountEl) busiestCountEl.textContent = stats.busiestDayCount + ' contribution' + (stats.busiestDayCount !== 1 ? 's' : '');
                } else {
                    busiestEl.textContent = '--';
                    if (busiestCountEl) busiestCountEl.textContent = '';
                }
            }

            el = document.getElementById('heatmap-streak-count');
            if (el) el.textContent = stats.streak;
        }

        function renderActivityFeed(activity) {
            var container = document.getElementById('recent-activity');
            if (!container) return;

            // Filter out automated system commits
            var filtered = [];
            if (activity) {
                for (var i = 0; i < activity.length; i++) {
                    if (activity[i].author_name === 'SpeleoDB' && activity[i].message.indexOf('[Automated]') === 0) continue;
                    filtered.push(activity[i]);
                }
            }

            if (filtered.length === 0) {
                container.innerHTML =
                    '<div class="flex flex-col items-center justify-center py-10 text-center">' +
                        '<svg class="w-12 h-12 text-slate-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">' +
                            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>' +
                        '</svg>' +
                        '<div class="text-sm text-slate-400">No recent activity</div>' +
                        '<div class="text-xs text-slate-600 mt-1">Contributions will appear here as you work</div>' +
                    '</div>';
                return;
            }

            var html = '';
            var lastDateLabel = '';

            for (var i = 0; i < filtered.length; i++) {
                var item = filtered[i];
                var projectName = escapeHtml(item.project_name);
                var authorName = escapeHtml(item.author_name);
                var message = escapeHtml(item.message);
                var projectUrl = Urls['private:project_details'](item.project_id);
                var initials = getInitials(item.author_name);
                var color = getAvatarColor(item.author_name);

                var itemDate = new Date(item.authored_date);
                var localDateTime = itemDate.toLocaleDateString('en', {
                    month: 'short', day: 'numeric', year: 'numeric'
                }) + ' at ' + itemDate.toLocaleTimeString('en', {
                    hour: 'numeric', minute: '2-digit', hour12: true
                });
                var localDateOnly = itemDate.toLocaleDateString('en', {
                    month: 'short', day: 'numeric'
                });

                // Date group headers
                var todayDate = new Date();
                var dateLabel;
                if (itemDate.toDateString() === todayDate.toDateString()) {
                    dateLabel = 'Today';
                } else {
                    var yesterday = new Date(todayDate);
                    yesterday.setDate(yesterday.getDate() - 1);
                    if (itemDate.toDateString() === yesterday.toDateString()) {
                        dateLabel = 'Yesterday';
                    } else {
                        dateLabel = itemDate.toLocaleDateString('en', { month: 'short', day: 'numeric' });
                    }
                }

                if (dateLabel !== lastDateLabel) {
                    html += '<div class="text-xs font-semibold text-slate-500 uppercase tracking-wide px-2 ' +
                        (i > 0 ? 'mt-3 ' : '') + 'mb-1">' + dateLabel + '</div>';
                    lastDateLabel = dateLabel;
                }

                var gitUrl = Urls['private:project_revision_explorer'](item.project_id, item.commit_id);
                var shortSha = item.commit_id ? item.commit_id.slice(0, 7) : '';

                html += '<div class="activity-row">' +
                    '<div class="activity-avatar" style="background-color:' + color + '">' + initials + '</div>' +
                    '<span class="text-sm font-medium text-slate-200 shrink-0">' + authorName + '</span>' +
                    '<a href="' + projectUrl + '" class="activity-badge activity-badge-project">' + projectName + '</a>' +
                    '<a href="' + gitUrl + '" class="activity-badge activity-badge-sha" title="Browse commit">' + shortSha + '</a>' +
                    '<span class="activity-msg">' + message + '</span>' +
                    '<span class="activity-meta"><span class="activity-time-full">' + localDateTime + '</span><span class="activity-time-short">' + localDateOnly + '</span></span>' +
                '</div>';
            }
            container.innerHTML = html;
        }

        $.ajax({
            url: Urls['api:v2:user-dashboard-stats'](),
            type: 'GET',
            dataType: 'json',
            success: function(response) {
                populateStatCards(response.summary);
                initCommitsChart(response.commits_over_time);
                initProjectsChart(response.projects_by_type);
                renderHeatmap(response.contribution_calendar);
                renderActivityFeed(response.recent_activity);
            },
            error: function() {
                showStatCardErrors();
                $('#recent-activity').html('<div class="text-sm text-slate-500 py-4 text-center">Failed to load activity</div>');
            }
        });
}
