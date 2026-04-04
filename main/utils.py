CHROMOSOMES = tuple(str(x) for x in range(1, 23)) + ('X', 'Y', 'MT')

# A dictionary with Ensembl VEP consequences SO and display terms
# ordered from the most to least severe. This order is essential for
# the code to work properly. The code responsible for selecting the 
# most severe consequence terms is a modified version of the ExAC
# browser util functions: 
# https://github.com/konradjk/exac_browser/blob/master/utils.py
VEP_CSQ_TERMS = {
    'transcript_ablation': 'Transcript ablation',
    'splice_acceptor_variant': 'Splice acceptor variant',
    'splice_donor_variant': 'Splice donor variant',
    'stop_gained': 'Stop gained',
    'frameshift_variant': 'Frameshift variant',
    'stop_lost': 'Stop lost',
    'start_lost': 'Start lost',
    'transcript_amplification': 'Transcript amplification',
    'feature_elongation': 'Feature elongation',
    'feature_truncation': 'Feature truncation',
    'inframe_insertion': 'Inframe insertion',
    'inframe_deletion': 'Inframe deletion',
    'missense_variant': 'Missense variant',
    'protein_altering_variant': 'Protein altering variant',
    'splice_donor_5th_base_variant': 'Splice donor 5th base variant',
    'splice_region_variant': 'Splice region variant',
    'splice_donor_region_variant': 'Splice donor region variant',
    'splice_polypyrimidine_tract_variant': 'Splice polypyrimidine tract variant',
    'incomplete_terminal_codon_variant': 'Incomplete terminal codon variant',
    'start_retained_variant': 'Start retained variant',
    'stop_retained_variant': 'Stop retained variant',
    'synonymous_variant': 'Synonymous variant',
    'coding_sequence_variant': 'Coding sequence variant',
    'mature_miRNA_variant': 'Mature miRNA variant',
    '5_prime_UTR_variant': '5 prime UTR variant',
    '3_prime_UTR_variant': '3 prime UTR variant',
    'non_coding_transcript_exon_variant': 'Non coding transcript exon variant',
    'intron_variant': 'Intron variant',
    'NMD_transcript_variant': 'Transcript variant',
    'non_coding_transcript_variant': 'Non coding transcript variant',
    'coding_transcript_variant': 'Coding transcript variant',
    'upstream_gene_variant': 'Upstream gene variant',
    'downstream_gene_variant': 'Downstream gene variant',
    'TFBS_ablation': 'TFBS ablation',
    'TFBS_amplification': 'TFBS amplification',
    'TF_binding_site_variant': 'TF binding site variant',
    'regulatory_region_ablation': 'Regulatory region ablation',
    'regulatory_region_amplification': 'Regulatory region amplification',
    'regulatory_region_variant': 'Regulatory region variant',
    'intergenic_variant': 'Intergenic variant',
    'sequence_variant': 'Sequence variant',
}

# Create VEP consequence term to severity rank dict, i.e.
# { 'transcript_ablation': 0, 'splice_acceptor_variant': 1, ... }
VEP_CSQ_TERM_TO_SEVERITY_RANK_DICT = {
    csq: i for i, csq in enumerate(VEP_CSQ_TERMS)
}
# Create VEP severity to consequence term rank dict, i.e.
# { 0: 'transcript_ablation', 1: 'splice_acceptor_variant', ... }
VEP_CSQ_SEVERITY_RANK_TO_TERM_DICT = dict(enumerate(VEP_CSQ_TERMS))


def get_worst_csq_display_term(csqs: str) -> str:
    """
    Return the most severe consequence (human-readable display term) from an
    Ensembl VEP consequences string.

    Parameters
    ----------
    csqs : str
        VEP consequences delimited by '&' (standard) or ',' (tolerated), e.g.
        "non_coding_transcript_exon_variant&non_coding_transcript_variant"

    Returns
    -------
    str
        Display term for the most severe consequence, e.g.
        "Non coding transcript exon variant".
    """
    csqs_list = csqs.replace(',', '&').split('&')
    if not csqs_list:
        return ''
    # Fail-fast sentinel on unknown terms to align with importer validation.
    if any(csq not in VEP_CSQ_TERM_TO_SEVERITY_RANK_DICT for csq in csqs_list):
        return ''
    worst_csq_index = min(VEP_CSQ_TERM_TO_SEVERITY_RANK_DICT[csq] 
                          for csq in csqs_list)
    worst_csq = VEP_CSQ_SEVERITY_RANK_TO_TERM_DICT[worst_csq_index]
    return VEP_CSQ_TERMS[worst_csq]

# Variant classifications grouped by categories.
# MAF-style terms (used by GENIE v17 and earlier).
LOF_CLASSIFICATIONS = {
    'Frame_Shift_Del',
    'Frame_Shift_Ins',
    'Nonsense_Mutation',
    'Splice_Site',
}

LOF_CANDIDATE_PTV_CLASSIFICATIONS = {
    'Frame_Shift_Del',
    'Frame_Shift_Ins',
    'Nonsense_Mutation',
}

MISSENSE_AND_INFRAME_INDEL_CLASSIFICATIONS = {
    'In_Frame_Ins',
    'In_Frame_Del',
    'Nonstop_Mutation',
    'Missense_Mutation',
    'Translation_Start_Site',
}

# VEP consequence SO terms (used by GENIE v19+).
VEP_LOF_CONSEQUENCES = {
    'frameshift_variant',
    'stop_gained',
    'splice_acceptor_variant',
    'splice_donor_variant',
}

VEP_LOF_CANDIDATE_PTV_CONSEQUENCES = {
    'frameshift_variant',
    'stop_gained',
}

VEP_MISSENSE_AND_INFRAME_INDEL_CONSEQUENCES = {
    'missense_variant',
    'inframe_insertion',
    'inframe_deletion',
    'protein_altering_variant',
    'stop_lost',
    'start_lost',
}

VEP_SILENT_CONSEQUENCES = {
    'synonymous_variant',
}


def _get_worst_consequence(consequence: str) -> str:
    """Return the single worst VEP consequence SO term from a
    '&'-delimited consequence string."""
    csqs = consequence.replace(',', '&').split('&')
    known = [c for c in csqs if c in VEP_CSQ_TERM_TO_SEVERITY_RANK_DICT]
    if not known:
        return ''
    return min(known, key=lambda c: VEP_CSQ_TERM_TO_SEVERITY_RANK_DICT[c])


def get_classification_category(
    classification: str | None, consequence: str | None, hgvs_p: str
) -> str:
    """
    Return variant classification category based on its MAF classification
    (v17) or VEP consequence (v19+), and HGVSp notation.

    Uses MAF classification when available; falls back to VEP consequence.

    Parameters
    ----------
    classification : str or None
        GENIE MAF variant classification (e.g. Nonsense_Mutation).
        None or empty for v19+ data.
    consequence : str or None
        VEP consequence string, possibly '&'-delimited
        (e.g. "frameshift_variant" or "missense_variant&NMD_transcript_variant").
    hgvs_p : str
        Variant HGVSp notation (e.g. p.(Ala2Val))

    Returns
    -------
    str
        Variant classification category: "PTV LoF", "non-PTV LoF",
        "Missense / Inframe indel", "Silent", "Other".
    """
    if classification:
        # MAF-based classification (v17 and earlier)
        if (classification in LOF_CANDIDATE_PTV_CLASSIFICATIONS
                and hgvs_p and 'Ter' in hgvs_p):
            return 'PTV LoF'
        elif classification in LOF_CLASSIFICATIONS:
            return 'non-PTV LoF'
        elif classification in MISSENSE_AND_INFRAME_INDEL_CLASSIFICATIONS:
            return 'Missense / Inframe indel'
        elif classification == 'Silent':
            return 'Silent'
        else:
            return 'Other'

    # VEP consequence-based classification (v19+)
    if not consequence:
        return 'Other'

    worst = _get_worst_consequence(consequence)
    if not worst:
        return 'Other'

    if (worst in VEP_LOF_CANDIDATE_PTV_CONSEQUENCES
            and hgvs_p and 'Ter' in hgvs_p):
        return 'PTV LoF'
    elif worst in VEP_LOF_CONSEQUENCES:
        return 'non-PTV LoF'
    elif worst in VEP_MISSENSE_AND_INFRAME_INDEL_CONSEQUENCES:
        return 'Missense / Inframe indel'
    elif worst in VEP_SILENT_CONSEQUENCES:
        return 'Silent'
    else:
        return 'Other'