from main.models import Variant, VariantCancerTypePatientCount
from main.utils import get_worst_csq_display_term


def get_variant_cancer_type_pcs(variant_id) -> list:
    """
    Search the database variant cancer type patient count table by
    variant id and return a list variant cancer types patient count
    data rows for the extended row subtable.

    Parameters
    ----------
    variant_id : int
        A database id of a variant.
    
    Returns
    -------
    data: list
        A list of dictionaries which stores variant cancer types patient 
        counts subtable rows data.
    """

    var_pc_cancers = (VariantCancerTypePatientCount.objects
        .select_related('cancer_type').filter(variant_id=variant_id)
    )

    data = []
    for var_pc_cancer in var_pc_cancers:
        if var_pc_cancer.cancer_type.is_haemonc:
            is_haemonc = '&#9989;' # Tick
        else:
            is_haemonc = '&#10060;' # Cross
        row = {
            'cancer_type': var_pc_cancer.cancer_type.cancer_type,
            'is_haemonc': is_haemonc,
            'same_nucleotide_change_pc': \
                var_pc_cancer.same_nucleotide_change_pc,
            'same_amino_acid_change_pc': \
                var_pc_cancer.same_amino_acid_change_pc,
            'same_or_downstream_truncating_variants_per_cds_pc': \
                var_pc_cancer.same_or_downstream_truncating_variants_per_cds_pc,
            'nested_inframe_deletions_per_cds_pc': \
                var_pc_cancer.nested_inframe_deletions_per_cds_pc,
            'cancer_n': var_pc_cancer.cancer_type.total_patient_count,
        }
        data.append(row)
    return data
    

def get_variants(search_key: str, search_value: str) -> list:
    """
    Search the database variant table using provided search parameters 
    and return a list of variant data rows (dicts) for the displayed
    variant table.

    Parameters
    ----------
    search_key : str
        Search type keyword. Must be 'gene' or 'region'.
    search_value : str
        Search value - gene name (e.g. NF1), chromosomal region 
        (e.g. 17:31226000-31227000) or position (e.g. 7:140753336) location.
    
    Returns
    -------
    variants: list
        A list of variant dictionaries which stores variant table rows data.
    """

    # Search the database variant table by gene name or region/pos and
    # return an empty list if the search key is anything else.
    variants = []
    if search_key == 'gene':
        db_variants = Variant.objects.filter(
            gene_symbol=search_value).order_by('pos')
    elif search_key == 'region':
        # Region format: {chrom}:{start_pos}-{end_pos}
        # Position format: {chrom}:{pos}
        try:
            chrom, poses = search_value.split(':')
            if '-' in poses:
                start_pos, end_pos = poses.split('-')
            else:
                start_pos = end_pos = poses
            db_variants = Variant.objects.filter(
                chrom=chrom, pos__gte=int(start_pos), pos__lte=int(end_pos)
            ).order_by('pos')
        except (ValueError, TypeError):
            # Return empty list for malformed input
            return variants
    else:
        return variants

    def _format_hgvs(hgvs):
        """Split joined HGVS descriptions."""
        return hgvs.replace('&', ', ') if hgvs else hgvs

    for db_variant in db_variants:
        # Construct variant dict which keys matches variant table 
        # "data-field" properties in "variants.html" template.
        variant = {
            'variant_id': db_variant.id,
            'chrom': db_variant.chrom,
            'pos': db_variant.pos,
            'consequence': get_worst_csq_display_term(db_variant.consequence),
            'hgvs_c': _format_hgvs(db_variant.hgvs_c),
            'hgvs_p': _format_hgvs(db_variant.hgvs_p),
            'gene': db_variant.gene_symbol,
            'refseq_transcript': db_variant.refseq_transcript,
            'haemonc_cancers_count': db_variant.haemonc_cancers_count,
            'all_cancers_count': db_variant.all_cancers_count,
        }
        variants.append(variant)
    return variants