/**
 * Dashboard pure-logic helpers.
 *
 * Loaded as a regular <script> in pages/dashboard.html.  Tests import
 * the real file (via readFileSync) so production and test code stay
 * in sync — no reimplementation.
 */

/* exported formatNumber, getHeatmapLevel, getInitials, getAvatarColor,
            avatarColors, groupTimestampsByLocalDate, computeHeatmapStats,
            buildCommitsChartConfig, buildProjectsChartConfig */

function formatNumber(n) {
    if (n == null) return '-';
    return n.toLocaleString();
}

function getHeatmapLevel(count) {
    if (count >= 10) return 4;
    if (count >= 6) return 3;
    if (count >= 3) return 2;
    if (count >= 1) return 1;
    return 0;
}

function getInitials(name) {
    var parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    return name.slice(0, 2).toUpperCase();
}

var avatarColors = ['#6366f1','#8b5cf6','#06b6d4','#10b981','#f59e0b','#ef4444','#ec4899','#14b8a6'];

function getAvatarColor(name) {
    var hash = 0;
    for (var i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return avatarColors[Math.abs(hash) % avatarColors.length];
}

function groupTimestampsByLocalDate(timestamps) {
    var calendar = {};
    if (Array.isArray(timestamps)) {
        for (var t = 0; t < timestamps.length; t++) {
            var dt = new Date(timestamps[t]);
            var key = dt.getFullYear() + '-' +
                String(dt.getMonth() + 1).padStart(2, '0') + '-' +
                String(dt.getDate()).padStart(2, '0');
            calendar[key] = (calendar[key] || 0) + 1;
        }
    }
    return calendar;
}

function computeHeatmapStats(calendar) {
    var today = new Date();
    today.setHours(0, 0, 0, 0);

    var total = 0;
    var weekCount = 0;
    var monthCount = 0;
    var busiestDay = '';
    var busiestDayCount = 0;

    var todayDow = today.getDay();
    var weekCutoff = new Date(today);
    weekCutoff.setDate(weekCutoff.getDate() - ((todayDow + 6) % 7));
    weekCutoff.setHours(0, 0, 0, 0);

    for (var key in calendar) {
        if (!Object.prototype.hasOwnProperty.call(calendar, key)) continue;
        var count = calendar[key];
        var d = new Date(key + 'T00:00:00');
        total += count;
        if (d >= weekCutoff) weekCount += count;
        if (d.getFullYear() === today.getFullYear() && d.getMonth() === today.getMonth()) monthCount += count;
        if (count > busiestDayCount) { busiestDayCount = count; busiestDay = key; }
    }

    var streak = 0;
    for (var s = 0; s <= 400; s++) {
        var sd = new Date(today);
        sd.setDate(sd.getDate() - s);
        var sk = sd.getFullYear() + '-' +
            String(sd.getMonth() + 1).padStart(2, '0') + '-' +
            String(sd.getDate()).padStart(2, '0');
        if (calendar[sk] && calendar[sk] > 0) { streak++; }
        else if (s === 0) { continue; }
        else { break; }
    }

    return { total: total, weekCount: weekCount, monthCount: monthCount,
             busiestDay: busiestDay, busiestDayCount: busiestDayCount, streak: streak };
}

function buildCommitsChartConfig(commitsOverTime) {
    var labels = commitsOverTime.map(function(d) { return d.month; });
    var totalData = commitsOverTime.map(function(d) { return d.total; });
    var userData = commitsOverTime.map(function(d) { return d.user; });
    return {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                { label: 'All Contributions', data: totalData, borderColor: '#818cf8' },
                { label: 'Your Contributions', data: userData, borderColor: '#34d399' }
            ]
        }
    };
}

function buildProjectsChartConfig(projectsByType) {
    var colorMap = {
        ariane:     '#6366f1',
        compass:    '#22d3ee',
        therion:    '#f59e0b',
        stickmaps:  '#10b981',
        walls:      '#f43f5e',
        other:      '#64748b'
    };
    var labels = [];
    var values = [];
    var colors = [];
    for (var key in projectsByType) {
        if (!Object.prototype.hasOwnProperty.call(projectsByType, key)) continue;
        if (projectsByType[key] > 0) {
            labels.push(key.charAt(0).toUpperCase() + key.slice(1));
            values.push(projectsByType[key]);
            colors.push(colorMap[key] || '#64748b');
        }
    }
    return {
        type: 'doughnut',
        data: { labels: labels, datasets: [{ data: values, backgroundColor: colors }] },
        isEmpty: values.length === 0,
        colors: colors
    };
}
