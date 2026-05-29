document.addEventListener('DOMContentLoaded', function () {
    // Load context variables from the variant.html embedded js.
    const context = JSON.parse(document.getElementById('page-context').textContent);

    // List of checkboxes used to filter variants based on their
    // 1. Consequence (e.g. PTV LoF, Silent)
    // Exclude static checkboxes from the info modal (var_classification_filters.html)
    const $csqFilters = $('.variant-consequence-filter:not(.static-control)');
    // 2. Allele type (e.g. SNVs, Indels)
    const $alleleFilters = $('.allele-filter');
    // All checkbox filters. 
    const $checkboxFilters = $([...$csqFilters, ...$alleleFilters])

    // Get variant extended row subtable ID.
    function getVariantCancerTypesSubtableID(variantID) {
        return `table-variant-cancer-types-${variantID}`
    }

    // Aggregated cancer types
    const AGG_CANCER_TYPES = new Set(['All Cancers', 'Haemonc Cancers', 'Solid Cancers']);

    // Initialise variant table.
    const $table = $('#table-variants');
    $table.bootstrapTable({
        ajax: ajaxRequest,
        detailView: true,
        detailFormatter: detailFormatter,
        method: 'get',
        // Populates extended row subtable on demand. Official bootstrap-table doc:
        // https://bootstrap-table.com/docs/api/events/#onexpandrow
        onExpandRow: function (index, row) {
            // Get variant subtable ID and data url by variant db id.
            let $subtable = $('#' + getVariantCancerTypesSubtableID(row.variant_id));
            let url = `${context.variant_cancer_patient_counts_url}?variant_id=${row.variant_id}`;
            
            // Load variant cancer type patient counts subtable data using async request.
            $.get(url)
                .done(function (res) {
                    $subtable.bootstrapTable({
                        data: res.rows,
                        rowStyle: function (row, index) {
                            if (AGG_CANCER_TYPES.has(row.cancer_type)) {
                                return {
                                    classes: 'fw-bold'  // Make aggregated cancer types bold
                                };
                            }
                            return {};
                        }
                    })
                    
                    // Get all rows as array of objects.
                    const data = $subtable.bootstrapTable('getData');
                    // Get all visible columns.
                    const columns = $subtable.bootstrapTable('getVisibleColumns');
                    // Columns with no patients (zeroes) in all cancer types.
                    const zeroColumns = [];
                    // Columns to skip in zero-checks.
                    const skipFields = ['cancer_type', 'category'];
                    
                    columns.forEach(column => {
                        // Ignore non-numeric columns.
                        if (skipFields.includes(column.field)) return;

                        // Check if all values for this column are zero.
                        const allZero = data.every(row => {
                            const val = row[column.field];
                            // Treat null/undefined as zero.
                            return val === 0 || val === '0' || val === null || val === undefined;
                        });
                        // Add column to the list of columns that are going to be hidden.
                        if (allZero) zeroColumns.push(column.field);
                    });

                    // Hide the zero columns.
                    zeroColumns.forEach(field => {
                        $subtable.bootstrapTable('hideColumn', field);                
                    })
                    // Show the subtable once it is fully ready.
                    $subtable.removeAttr('hidden');
                })
            .fail(function (xhr, status, err) {
                console.error('Failed to load cancer-type counts:', status || err);
            });
        }
    })


    // Clear all table filter controls.
    function clearFilters() {
        // Clear filters.
        $table.bootstrapTable('clearFilterControl');
        // Reset all filter checkboxes.
        $checkboxFilters.each(function() {
            // Use default checked values if specified, otherwise assume that default is checked.
            const defaultChecked = $(this).attr('default-checked')
            this.checked = (defaultChecked !== undefined) ? defaultChecked === "true" : true;
        });
        // Reload table data.
        filterTable()
        // Update the displayed variant count.
        updateVariantCount();
    };

    // Clear filters when user clicks on the button.
    $('#clear-filters-btn').on('click', clearFilters);


    // Update table variants (rows) count on the UI.
    function updateVariantCount() {
        const currentCount = $table.bootstrapTable('getData').length;
        $('#var-count-text').text(currentCount.toLocaleString());
    }


    // Update table variants (rows) count after each table search.
    $table.on('search.bs.table', function (e, text) {
        updateVariantCount();
    });


    /**
     * Populates variant table with data. Official bootstrap-table doc:
     * https://bootstrap-table.com/docs/api/table-options/#ajax
     *  
     * @param {Object} - An object with additional bootstrap-table ajax 
     *                   request params (e.g. sort order).
     * @returns {void}
     */
    function ajaxRequest(params) {
        // Ajax url and search value are obtained from the backend.
        let url = context.variants_data_url;
        let search_value = context.search_value;

        // Add any additional bootstrap-table parameters to the ajax
        // request and load variant table data.
        const sep = url.includes('?') ? '&' : '?';
        $.get(url + sep + $.param(params.data))
            .done(function (res) {
                params.success(res);
                // If no variants were found for the provided search params,
                // update the "Looking for variant data..." message.
                if (res.total === 0) {
                    $('#div-table-variants-no-data-message').text(`No variants were found for "${search_value}"`);
                    if (res.error !== '') {
                        console.log(`Failed to process the variant query: "${res.error}"`)
                    }
                } else {
                    // Otherwise, hide the message, show the table, 
                    // and update the displayed variants count.
                    document.getElementById('div-table-variants').removeAttribute("hidden");
                    document.getElementById('div-table-variants-no-data-message').setAttribute("hidden", "hidden");
                    updateVariantCount();
                }
            })
            .fail(function (xhr, status, err) {
                console.error('Failed to load cancer-type counts:', xhr.status, status || err);
            });
    }


    /**
     * Generates variant table row's detail view content - a sub-table with 
     * various cancer types patient counts. Official bootstrap-table doc:
     * https://bootstrap-table.com/docs/api/table-options/#detailformatter
     * 
     * @param {number} - Row index
     * @param {Object} - Row data
     * @returns {string} - Row's detail view html
     */
    function detailFormatter(index, row) {
        let var_cancer_types_table_id = getVariantCancerTypesSubtableID(row['variant_id'])
        let html = `
            <table id="${var_cancer_types_table_id}" 
                class="table table-sm table-sm-font w-auto"
                data-filter-control="true"
                data-sort-name="cancer_type"
                hidden
            >
                <thead>
                    <tr class="secondary">
                        <th class="align-middle" data-field="cancer_type" data-sort-name="cancer_type_order" data-filter-control="input" data-halign="center" data-sortable="true" data-width="200">Cancer type</th>
                        <th class="align-middle" data-field="category" data-align="center" data-halign="center" data-sortable="true" data-width="50">Cancer<br>Category</th>
                        <th class="align-middle" data-field="same_nucleotide_change_pc" data-align="right" data-halign="center" data-sortable="true" data-width="50">Same nucleotide<br>change patient count</th>
                        <th class="align-middle" data-field="same_amino_acid_change_pc" data-align="right" data-halign="center" data-sortable="true" data-width="50">Same amino acid change<br>patient count</th>
                        <th class="align-middle" data-field="same_or_downstream_truncating_variants_per_aa_pc" data-align="right" data-halign="center" data-sortable="true" data-width="50">Same or downstream truncating<br>variants per AA patient count</th>
                        <th class="align-middle" data-field="nested_inframe_deletions_per_aa_pc" data-align="right" data-halign="center" data-sortable="true" data-width="50">Nested inframe deletions<br>per AA patient count</th>
                        <th class="align-middle" data-field="cancer_n" data-halign="center" data-align="right" data-sortable="true" data-width="50">Total cancer<br>patient count</th>
                    </tr>
                </thead>
            </table>
        `
        return html
    }


    /**
     * A custom filter for the HGVS columns. The default bootstrap table
     * filter control process '>' as a comparison command for numeric values
     * and does not work with HGVS nomenclature (e.g. ENST00000358273.4:c.1A>G)
     * Official bootstrap-table doc:
     * https://bootstrap-table.com/docs/api/table-options/#detailformatter
     * 
     * @param {text} - The search text.
     * @param {value} - The value of the column to compare.
     * @param {field} - The column field name.
     * @param {data} - The table data.
     * @returns {Boolean} - Return false to filter out the current column/row.
     *                      Return true to not filter out the current column/row.
     */
    window.filterCustomTextSearch = function (text, value, field, data) {
        if (!text) return true;
        return String(value).toLowerCase().indexOf(String(text).toLowerCase()) !== -1;
    }


    /**
     * Parses a position value into a { start, end } object.
     * Accepts integers ("45"), ranges ("45-120"), or partial ranges where
     * either bound is unknown ("45-?" or "?-4"). Unknown bounds collapse to
     * the known bound, giving a point range (e.g. "45-?" → { start: 45, end: 45 },
     * "?-4" → { start: 4, end: 4 }). Returns null for fully unknown/missing values.
     *
     * @param {*} val - Raw position value from the table cell.
     * @returns {{ start: number, end: number } | null}
     */
    function parsePosition(val) {
        if (val == null) return null;

        const str = String(val).trim();

        // Empty, unknown ("?"), bare dash, or null string → missing value
        if (!str || str === '?' || str === '-' || str === 'null') return null;

        if (str.includes('-')) {
            const [rawStart, rawEnd] = str.split('-');

            const startUnknown = rawStart === '?' || rawStart === '';
            const endUnknown   = rawEnd   === '?' || rawEnd   === '';

            const startNum = startUnknown ? null : Number(rawStart);
            const endNum   = endUnknown   ? null : Number(rawEnd);

            // Both bounds unknown → missing value
            if (startUnknown && endUnknown) return null;

            // Unparseable numeric bound → invalid, treat as missing
            if (!startUnknown && Number.isNaN(startNum)) return null;
            if (!endUnknown   && Number.isNaN(endNum))   return null;

            // Collapse unknown bound to the known one (point range)
            const start = startUnknown ? endNum   : startNum;
            const end   = endUnknown   ? startNum : endNum;

            return { start, end };
        }

        const num = Number(str);
        if (Number.isNaN(num)) return null;
        return { start: num, end: num };
    }


    /**
     * A custom filter for numeric position columns. Supports four query formats:
     *   ">N"      → values strictly greater than N
     *   "<N"      → values strictly less than N
     *   "A-B"     → range overlap (does the position span overlap [A, B]?)
     *   "N"       → exact point-in-range (does the position span include N?)
     *   other     → plain text fallback (string contains query?)
     * Unknown/missing positions never match numeric queries.
     * Used for both the Position (pos) and Protein position (protein_pos) columns.
     *
     * @param {string} text  - The search text entered by the user.
     * @param {*}      value - The raw cell value to test.
     * @returns {boolean} - true to show the row, false to hide it.
     */

    window.filterCustomRangeFieldSearch = function (text, value) {
        if (!text) return true; // No active filter → always show

        const pos = parsePosition(value);
        const query = String(text).trim();

        // >N: strictly greater than N (pos must extend past N)
        if (query.startsWith('>')) {
            const n = Number(query.slice(1).trim());
            return !Number.isNaN(n) && !!pos && pos.end > n;
        }

        // <N: strictly less than N (pos must start before N)
        if (query.startsWith('<')) {
            const n = Number(query.slice(1).trim());
            return !Number.isNaN(n) && !!pos && pos.start < n;
        }

        // Range query: check if [pos.start, pos.end] overlaps [start, end]
        if (query.includes('-')) {
            const queryPos = parsePosition(query);
            if (queryPos) {
                return !!pos && pos.start <= queryPos.end && pos.end >= queryPos.start;
            }
            // Non-numeric dashed query: use text fallback
            return String(value ?? '').toLowerCase().includes(query.toLowerCase());
        }

        // Exact position: check if the number falls within the position's span
        const exact = Number(query);
        if (!Number.isNaN(exact)) {
            return !!pos && pos.start <= exact && pos.end >= exact;
        }

        // Non-numeric query: plain string match against the raw value
        return String(value ?? '').toLowerCase().includes(query.toLowerCase());
    };


    // Filter table based on selected variant categories and allele types.
    function filterTable() {
        // Consequence and Allele type checkbox values are the same as 
        // values in consequence_category and allele_type columns.
        const selectedCsqFilters = $csqFilters.filter(':checked').map(function() {
            return $(this).val();
        }).get();
        const selectedAlleleFilters = $alleleFilters.filter(':checked').map(function() {
            return $(this).val();
        }).get();
        $table.bootstrapTable('filterBy', {
            consequence_category: selectedCsqFilters,
            allele_type: selectedAlleleFilters,
        });
    }


    // Recalculate table and variant counts when checkbox filters change.
    $checkboxFilters.on('change', function() {
        filterTable();
        updateVariantCount();
    });


    /**
     * Bootstrap Table triggers multiple "post-header.bs.table" events during
     * the initial load, both before and after "load-success.bs.table".
     *
     * The "Consequence" select lists all unfiltered options
     * when filters are applied, so they may show options with
     * no matching results.
     *
     * To improve usability, each option displays the count of matching variants
     * based on active filters (e.g., "Missense variant (1234)"). Counts are
     * recalculated only after the table fully loads and when filters change.
     */

    // Tracks whether the table has completed its first successful load
    let tableInitialized = false
    // Lists of all possible "Consequence" values (from unfiltered data)
    let allVarCsqs = []
    // Stores the last known filter set to detect when filters change
    let currentFilters = null;

    
    /**
     * Updates a <select> control with option labels that include counts of
     * matching items (e.g., "Missense (1234)").
     * @param {HTMLSelectElement} selectElement - Target <select> element
     * @param {Array} allValues - All possible values for this field
     * @param {Array} filteredData - Table data currently visible under active filters
     * @param {String} property - Table property to count (e.g. "consequence")
     * @returns {void}
     */
    function updateSelectWithCounts(selectElement, allValues, filteredData, property) {
        // Count how many rows match each property value
        const counts = filteredData.reduce((acc, row) => {
            const key = row[property];
            acc[key] = (acc[key] || 0) + 1;
            return acc;
        }, {});

        // Compute total number of matching rows
        const all_count = Object.values(counts).reduce((sum, val) => sum + val, 0);

        // Remember currently selected value (to restore it later)
        const current = selectElement.value;

        // Clear and rebuild <select> options
        selectElement.innerHTML = '';
        selectElement.add(new Option(`All (${all_count})`, ''));

        // Add each option with its respective count
        allValues.forEach(v => {
            const count = counts[v] || 0;
            selectElement.add(new Option(`${v} (${count})`, v));
        });

        // Restore previous selection 
        if (allValues.includes(current)) {
            selectElement.value = current;
        }
    }

    
    /**
     * Combines full and partial Bootstrap Table filters into one object.
     * Partial filters override full filters when both exist.
     */
    function getCombinedFilters() {
        const instance = $table.data('bootstrap.table');
        if (!instance) return {};

        const filters = instance.filterColumns || {};
        const partialFilters = instance.filterColumnsPartial || {};

        return { ...filters, ...partialFilters };
    }

    
    // Compares two filter objects for equality by key and value.
    function filtersEqual(a, b) {
        const aKeys = Object.keys(a);
        const bKeys = Object.keys(b);
        if (aKeys.length !== bKeys.length) return false;
        return aKeys.every(k => JSON.stringify(a[k]) === JSON.stringify(b[k]));
    }


    /**
     * Refreshes the "Consequence" select controls
     * to reflect the number of matching variants for each option.
     * Runs with a small delay to ensure filters and data are fully updated.
     */    
    function updateTableSelectControls() {
        setTimeout(function() {
            let newFilters = getCombinedFilters();

            // Skip update if filters haven't changed
            if (currentFilters !== null && filtersEqual(newFilters, currentFilters)) {
                return;
            }
            currentFilters = newFilters

            // Get filtered table data
            const data = $table.bootstrapTable('getData', { useCurrentPage: false });

            // Update both select controls with new counts
            var csqSelect = $('select.bootstrap-table-filter-control-consequence')[0];
            updateSelectWithCounts(csqSelect, allVarCsqs, data, 'consequence')
        }, 50);
    }


    /**
     * After table data loads successfully for the first time:
     * - Mark table as initialized
     * - Extract all unique "consequence" values
     * - Initialize the select controls with counts
     */
    $table.on('load-success.bs.table', function () {
        // Get consequences and classes based on the table unfiltered data.
        const data = $table.bootstrapTable('getData', { useCurrentPage: false });
        allVarCsqs = [...new Set(data.map(row => row.consequence))].sort();

        // Apply default table filters.
        clearFilters()

        setTimeout(function() {
            tableInitialized = true;
            updateTableSelectControls();
        }, 1000); // Delay to ensure table is fully rendered
    });


    /**
     * When table headers are re-rendered (e.g., due to sort/filter changes),
     * update select controls if the table has already finished initializing.
     */
    $table.on('post-header.bs.table', function () {
        if (!tableInitialized) return;
        updateTableSelectControls();
    });


    // When an "only" button is clicked
    $('.only-btn').on('click', function() {
        // Get target checkbox ID and checkbox group CSS class.
        const targetId = $(this).data('target');
        const groupClass = $(this).data('group');

        // Uncheck all checkboxes in a group except the target one.
        $('.' + groupClass + ':not(.static-control)').prop('checked', false);
        $('#' + targetId).prop('checked', true);

        // Filter table.
        filterTable();
        updateVariantCount();
    });
});