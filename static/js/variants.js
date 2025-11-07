document.addEventListener('DOMContentLoaded', function () {
    // Load context variables from the variant.html embedded js.
    const context = JSON.parse(document.getElementById('page-context').textContent);

    // List of checkboxes used to filter variants based on their
    // 1. Classification (e.g. PTV LoF, Silent)
    const $classFilters = $('.variant-classification-filter');
    // 2. Allele type (e.g. SNVs, Indels)
    const $alleleFilters = $('.allele-filter');
    // All checkbox filters. 
    const $checkboxFilters = $([...$classFilters, ...$alleleFilters])

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
        // Reload table data.
        $table.bootstrapTable('filterBy', {});
        // Update the displayed variant count.
        updateVariantCount();
        // Reset all filter checkboxes.
        $checkboxFilters.each(function() {
            this.checked = true;
        });
    }


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
                        <th class="align-middle" data-field="same_or_downstream_truncating_variants_per_cds_pc" data-align="right" data-halign="center" data-sortable="true" data-width="50">Same or downstream truncating<br>variants per CDS patient count</th>
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
     * A custom filter for the Position column. Supports range (start-end) search.
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
    window.filterCustomIntegerSearch = function (text, value, field, data) {
        if (!text) return true;

        if (String(text).indexOf('-') !== -1) {
            let range = text.split('-');
            let start = Number(range[0]);
            let end = Number(range[1]);
            value = Number(value);
            return value >= start && value <= end;
        } else if (String(text).startsWith('>')) {
            let pos = Number(text.replace('>', '').trim())
            return value >= pos
        } else if (String(text).startsWith('<')) {
            let pos = Number(text.replace('<', '').trim())
            return value <= pos
        } else {
            return String(value).toLowerCase().indexOf(String(text).toLowerCase()) !== -1;
        }  
    }


    // Filter table based on selected variant categories and allele types.
    function filterTable() {
        // Classification and Allele type checkbox values are the same as 
        // values in classification_category and allele_type columns.
        const selectedClassFilters = $classFilters.filter(':checked').map(function() {
            return $(this).val();
        }).get();
        const selectedAlleleFilters = $alleleFilters.filter(':checked').map(function() {
            return $(this).val();
        }).get();
        $table.bootstrapTable('filterBy', {
            classification_category: selectedClassFilters,
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
     * The "Consequence" and "Classification" selects list all unfiltered options
     * and don't update when filters are applied, so they may show options with
     * no matching results.
     *
     * To improve usability, each option displays the count of matching variants
     * based on active filters (e.g., "Missense variant (1234)"). Counts are
     * recalculated only after the table fully loads and when filters change.
     */

    // Tracks whether the table has completed its first successful load
    let tableInitialized = false
    // Lists of all possible "Consequence" and "Classification" values (from unfiltered data)
    let allVarCsqs = []
    let allVarClasses = []
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
        all_count = Object.values(counts).reduce((sum, val) => sum + val, 0);

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
     * Refreshes the "Consequence" and "Classification" select controls
     * to reflect the number of matching variants for each option.
     * Runs with a small delay to ensure filters and data are fully updated.
     */    
    function updateTableSelectControls() {
        setTimeout(function() {
            let newFilters = getCombinedFilters();

            // Skip update if filters haven't changed
            if (currentFilters !== null && filtersEqual(newFilters, currentFilters)) {
                return {}
            }
            currentFilters = newFilters

            // Get filtered table data
            const data = $table.bootstrapTable('getData', { useCurrentPage: false });

            // Update both select controls with new counts
            var csqSelect = $('select.bootstrap-table-filter-control-consequence')[0];
            updateSelectWithCounts(csqSelect, allVarCsqs, data, 'consequence')

            var classSelect = $('select.bootstrap-table-filter-control-classification')[0];
            updateSelectWithCounts(classSelect, allVarClasses, data, 'classification')
        }, 50);
    }


    /**
     * After table data loads successfully for the first time:
     * - Mark table as initialized
     * - Extract all unique "consequence" and "classification" values
     * - Initialize the select controls with counts
     */
    $table.on('load-success.bs.table', function () {
        setTimeout(function() {
            tableInitialized = true;
            const data = $table.bootstrapTable('getData', { useCurrentPage: false });
            allVarCsqs = [...new Set(data.map(row => row.consequence))].sort();
            allVarClasses = [...new Set(data.map(row => row.classification))].sort();

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
        $('.' + groupClass).prop('checked', false);
        $('#' + targetId).prop('checked', true);

        // Filter table.
        filterTable();
        updateVariantCount();
    });
});