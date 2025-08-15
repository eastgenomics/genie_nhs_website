from main.models import Variant
from main.utils import get_worst_csq_display_term


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
        db_variants = Variant.objects.select_related()\
            .filter(gene_symbol=search_value).order_by('pos')
    elif search_key == 'region':
        # Region format: {chrom}:{start_pos}-{end_pos}
        # Position format: {chrom}:{pos}
        try:
            chrom, poses = search_value.split(':')
            if '-' in poses:
                start_pos, end_pos = poses.split('-')
            else:
                start_pos = end_pos = poses
            db_variants = Variant.objects.select_related()\
                .filter(chrom=chrom, pos__gte=int(start_pos), 
                        pos__lte=int(end_pos)).order_by('pos')
        except (ValueError, TypeError) as e:
            # Return empty list for malformed input
            return variants
    else:
        return variants

    # Group bootstrap-table detailed view sub-tables (key-value) fields 
    # into dicts in which keys are "Variant" attribute names and values 
    # are the displayed field names (verbose name without a prefix). 
    # HaemOnc cancer patient count fields have "PC_HaemOnc:" prefix.
    haemonc_pc_names = {}
    for f in Variant._meta.get_fields():
        if f.verbose_name.startswith('PC_HaemOnc:'):
            haemonc_pc_names[f.attname] = \
                f.verbose_name.replace('PC_HaemOnc:', '')
    

    for db_variant in db_variants:
        # Create bootstrap-table detailed view sub-tables data dicts.
        # In case of HaemOnc cancer patient counts, keys are 
        # cancer type names and values are patient counts.
        haemonc_pcs = {}
        for attr, name in haemonc_pc_names.items():
            var_patient_count = getattr(db_variant, attr)
            if var_patient_count:
                haemonc_pcs[name] = var_patient_count

        # Construct variant dict which keys matches variant table 
        # "data-field" properties in "variants.html" template.
        variant = {
            'chrom': db_variant.chrom,
            'pos': db_variant.pos,
            'consequence': get_worst_csq_display_term(db_variant.consequence),
            'hgvs_c': db_variant.hgvs_c,
            'hgvs_p': db_variant.hgvs_p,
            'gene': db_variant.gene_symbol,
            'refseq_transcript': db_variant.refseq_transcript,
            'haemonc_cancers_count': db_variant.haemonc_cancers_count,
            'all_cancers_count': db_variant.all_cancers_count,
            'haemonc_pcs': haemonc_pcs,
        }
        variants.append(variant)
    return variants