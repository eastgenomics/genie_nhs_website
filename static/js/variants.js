document.addEventListener('DOMContentLoaded', function () {
    // Load context variables from the variant.html embedded js.
    const context = JSON.parse(document.getElementById('page-context').textContent);


    // Get variant extended row subtable ID.
    function getVariantCancerTypesSubtableID(variantID) {
        return `table-variant-cancer-types-${variantID}`
    }


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
                            const aggCancerTypes = ['All Cancers', 'Haemonc Cancers', 'Solid Cancers'];
                            if (aggCancerTypes.includes(row.cancer_type)) {
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
                        <th class="align-middle" data-field="nested_inframe_deletions_per_cds_pc" data-align="right" data-halign="center" data-sortable="true" data-width="50">Nested inframe deletions<br>per CDS patient count</th>
                        <th class="align-middle" data-field="cancer_n" data-halign="center" data-align="right" data-sortable="true" data-width="50">Total cancer<br>patient count</th>
                    </tr>
                </thead>
            </table>
        `
        return html
    }
});