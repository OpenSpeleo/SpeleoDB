/**
 * Shared editable-survey-table scaffold for `tools/xls2dmp.html` and
 * `tools/xls2compass.html`.
 *
 * Both tools render the same contenteditable `<table>`:
 *   - toolbar with "Paste from Excel", "Add Row", "Clear" buttons
 *   - an index column + N data columns + a trash-button column
 *   - Enter moves focus to the cell below (Excel-like)
 *   - validation highlights invalid cells and writes a status line
 *
 * What varies between the two tools:
 *   - `COLUMNS` list (xls2dmp has 7 columns; xls2compass has 9 including
 *     a leading `station` and trailing `flags`/`comment`).
 *   - The per-cell validator (`validateCell`).
 *   - The clipboard parser (`parseClipboardText`) - xls2compass uses a
 *     simpler parse; xls2dmp strips an optional leading "Station #"
 *     column.
 *   - The human message for "the last row should only have X".
 *
 * These are all passed in as options. The AJAX submit + field-level
 * form validation (cave name, survey name, etc.) stays inline per
 * template because each tool has a different payload and endpoint.
 *
 * Usage:
 *   const surveyTable = attachSurveyTableTool({
 *       tableBodySelector: '#dataTable tbody',
 *       statusSelector:    '#status',
 *       addRowBtnSelector: '#addRowBtn',
 *       clearBtnSelector:  '#clearBtn',
 *       pasteBtnSelector:  '#pasteExcelBtn',
 *       COLUMNS: ['depth','length','azimuth','left','right','up','down'],
 *       validateCell: function (value, column, isLastRow) { ... },
 *       parseClipboardText: function (text) { ... },
 *       lastRowAllowedColumns: ['depth'],       // last row must be empty in any other data column
 *       lastRowErrorMessage: function (remove) {
 *           return 'Error: The last row should only have Station Depth. Remove: '
 *                  + remove.join(', ') + '.';
 *       },
 *   });
 *
 *   // Later:
 *   const ok = surveyTable.validateTable();
 *   const rows = surveyTable.collectRowObjects();
 *
 * Returns an object with:
 *   - renderRows(rows)
 *   - addRow(values?, idx?)
 *   - validateTable()
 *   - tableToCsv()
 *   - collectRowObjects() - array of {col: value, ...} for each row with data
 *
 * Requires: jQuery, Utils.escapeHtml (or a global `escapeHtml`).
 */

/* exported attachSurveyTableTool */

function _stEscape(value) {
    if (typeof window !== 'undefined' && typeof window.escapeHtml === 'function') {
        return window.escapeHtml(value);
    }
    var div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
}

function attachSurveyTableTool(options) {
    var tableBodySelector = options.tableBodySelector;
    var statusSelector = options.statusSelector || '#status';
    var addRowBtnSelector = options.addRowBtnSelector;
    var clearBtnSelector = options.clearBtnSelector;
    var pasteBtnSelector = options.pasteBtnSelector;
    var COLUMNS = options.COLUMNS;
    var validateCell = options.validateCell;
    var parseClipboardText = options.parseClipboardText;
    var lastRowAllowedColumns = options.lastRowAllowedColumns || [];
    var lastRowErrorMessage = options.lastRowErrorMessage;
    var dataTableSelector = options.dataTableSelector || '#dataTable';

    if (!tableBodySelector) { throw new Error('attachSurveyTableTool: tableBodySelector required'); }
    if (!Array.isArray(COLUMNS) || COLUMNS.length === 0) {
        throw new Error('attachSurveyTableTool: COLUMNS must be a non-empty array');
    }
    if (typeof validateCell !== 'function') {
        throw new Error('attachSurveyTableTool: validateCell required');
    }
    if (typeof parseClipboardText !== 'function') {
        throw new Error('attachSurveyTableTool: parseClipboardText required');
    }

    var $tbody = $(tableBodySelector);
    if (!$tbody.length) {
        throw new Error('attachSurveyTableTool: table body not found: ' + tableBodySelector);
    }
    var $status = $(statusSelector);

    function setStatus(text, color, weight) {
        $status.text(text || '');
        if (color || weight) {
            $status.css({ color: color || '', 'font-weight': weight || '' });
        } else {
            $status.css({ color: '', 'font-weight': '' });
        }
    }

    function addRow(values, idx) {
        values = values || [];
        var index = typeof idx === 'number' ? idx : $tbody.children().length + 1;
        var html = '<td>' + index + '</td>' +
            COLUMNS.map(function (col, j) {
                return '<td contenteditable="true" data-col="' + col + '">' +
                    _stEscape(values[j] != null ? values[j] : '') +
                    '</td>';
            }).join('') +
            '<td class="actions"><button class="trash" title="Delete row">🗑️</button></td>';
        var $tr = $('<tr>').html(html);
        $tbody.append($tr);
        $tr.find('.trash').on('click', function () {
            $tr.remove();
            refreshIndexes();
            validateTable();
        });
    }

    function refreshIndexes() {
        $tbody.children('tr').each(function (i) {
            $(this).children('td').first().text(i + 1);
        });
    }

    function renderRows(rows) {
        $tbody.empty();
        rows.forEach(function (r, i) { addRow(r, i + 1); });
        refreshIndexes();
        validateTable();
    }

    function onCellInput(td) {
        var $td = $(td);
        var col = $td.data('col');
        var $row = $td.parent();
        var $allRows = $tbody.children('tr');
        var isLastRow = $allRows.last().is($row);
        var ok = validateCell($td.text(), col, isLastRow);
        $td.toggleClass('invalid', !ok);
        validateTable();
    }

    function validateTable() {
        var allValid = true;
        var lastRowErrors = [];
        var $allRows = $tbody.children('tr');
        var $lastRow = $allRows.last();

        $(dataTableSelector + ' tbody td[data-col]').each(function () {
            var $td = $(this);
            var col = $td.data('col');
            var $row = $td.parent();
            var isLastRow = $lastRow.is($row);
            var ok = validateCell($td.text(), col, isLastRow);
            $td.toggleClass('invalid', !ok);

            if (!ok) {
                allValid = false;
                if (isLastRow && $td.text().trim() !== '' && lastRowAllowedColumns.indexOf(col) === -1) {
                    var fieldName = col.charAt(0).toUpperCase() + col.slice(1);
                    if (lastRowErrors.indexOf(fieldName) === -1) {
                        lastRowErrors.push(fieldName);
                    }
                }
            }
        });

        var statusMessage = 'All cells valid.';
        if (!allValid) {
            if (lastRowErrors.length > 0 && typeof lastRowErrorMessage === 'function') {
                statusMessage = lastRowErrorMessage(lastRowErrors);
            } else {
                statusMessage = 'Some cells are invalid.';
            }
        }
        setStatus(statusMessage, allValid ? 'green' : 'red', 'bold');
        return allValid;
    }

    function tableToCsv() {
        var rows = [];
        $tbody.children('tr').each(function () {
            var row = [];
            $(this).find('td[data-col]').each(function () {
                row.push($(this).text().trim());
            });
            rows.push(row);
        });
        return rows.map(function (r) {
            return r.map(function (cell) {
                if (cell.indexOf(',') !== -1 || cell.indexOf('"') !== -1 || cell.indexOf('\n') !== -1) {
                    return '"' + cell.replace(/"/g, '""') + '"';
                }
                return cell;
            }).join(',');
        }).join('\n');
    }

    function collectRowObjects() {
        var rows = [];
        $tbody.find('tr').each(function () {
            var row = {};
            $(this).find('td[data-col]').each(function () {
                row[$(this).data('col')] = $(this).text().trim();
            });
            if (Object.keys(row).length > 0) { rows.push(row); }
        });
        return rows;
    }

    function getEditableTdFromTarget(target) {
        if (!target) { return null; }
        var node = target.nodeType === 3 ? target.parentElement : target;  // 3 = TEXT_NODE
        if (!node) { return null; }
        var $td = $(node).closest('td[data-col]');
        return $td.length ? $td[0] : null;
    }

    function placeCaretAtEnd(el) {
        var range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(false);
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
    }

    function focusCell(cell) {
        if (!cell) { return; }
        $(cell).focus();
        placeCaretAtEnd(cell);
    }

    function moveToCellBelow(currentTd) {
        var $currentTd = $(currentTd);
        var $currentRow = $currentTd.parent();
        var $currentRowCells = $currentRow.find('td[data-col]');
        var colIndex = $currentRowCells.index($currentTd);
        var $nextRow = $currentRow.next();
        if ($nextRow.length) {
            var $nextRowCells = $nextRow.find('td[data-col]');
            focusCell($nextRowCells.eq(colIndex)[0] || $nextRowCells.last()[0]);
        } else {
            $currentTd.blur();
            $(dataTableSelector).blur();
            var sel = window.getSelection();
            if (sel) { sel.removeAllRanges(); }
        }
    }

    // Event wiring
    $tbody[0].addEventListener('keydown', function (e) {
        if (e.key !== 'Enter') { return; }
        var td = getEditableTdFromTarget(e.target);
        if (!td) { return; }
        e.preventDefault();
        validateTable();
        moveToCellBelow(td);
    }, true);

    $tbody.on('input', 'td[data-col]', function (e) {
        var td = getEditableTdFromTarget(e.target);
        if (!td) { return; }
        onCellInput(td);
    });

    $tbody[0].addEventListener('beforeinput', function (e) {
        var td = getEditableTdFromTarget(e.target);
        if (!td) { return; }
        setTimeout(function () { onCellInput(td); }, 0);
    });

    $tbody.on('keyup', 'td[data-col]', function (e) {
        var td = getEditableTdFromTarget(e.target);
        if (!td) { return; }
        onCellInput(td);
    });

    $tbody[0].addEventListener('blur', function (e) {
        var td = getEditableTdFromTarget(e.target);
        if (!td) { return; }
        onCellInput(td);
    }, true);

    if (addRowBtnSelector) {
        $(addRowBtnSelector).on('click', function () {
            addRow();
            validateTable();
        });
    }

    if (clearBtnSelector) {
        $(clearBtnSelector).on('click', function () {
            $tbody.empty();
            setStatus('Cleared.');
        });
    }

    if (pasteBtnSelector) {
        $(pasteBtnSelector).on('click', async function () {
            try {
                var text = await navigator.clipboard.readText();
                var rows = parseClipboardText(text);
                renderRows(rows);
                setStatus('Imported ' + rows.length + ' rows.');
            } catch (err) {
                setStatus('Unable to read clipboard. Try Ctrl+V directly.');
            }
        });
    }

    return {
        renderRows: renderRows,
        addRow: addRow,
        validateTable: validateTable,
        tableToCsv: tableToCsv,
        collectRowObjects: collectRowObjects,
        setStatus: setStatus,
    };
}
