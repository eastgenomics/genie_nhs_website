CHROMOSOMES = ['%s' % x for x in range(1, 23)]
CHROMOSOMES.extend(['X', 'Y', 'MT'])

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
    'NMD_transcript_variant': 'transcript variant',
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
    csq:i for i,csq in enumerate(list(VEP_CSQ_TERMS))
}
# Create VEP severity to consequence term rank dict, i.e.
# { 0: 'transcript_ablation', 1: 'splice_acceptor_variant', ... }
VEP_CSQ_SEVERITY_RANK_TO_TERM_DICT = dict(enumerate(list(VEP_CSQ_TERMS)))


def get_worst_csq_display_term(csqs: str) -> str:
    """
    Get the most severe consequence from a variant Ensembl VEP
    conseqeunces string.

    Parameters
    ----------
    csqs : str
        Variant consequences string from Ensembl VEP, e.g.
        "non_coding_transcript_exon_variant,non_coding_transcript_variant"
    
    Returns
    -------
    str
        Most severe consequence from the input string, e.g.
        "non_coding_transcript_exon_variant"
    """

    worst_csq_index = min(
        [VEP_CSQ_TERM_TO_SEVERITY_RANK_DICT[csq] for csq in csqs.split('&')])
    worst_csq = VEP_CSQ_SEVERITY_RANK_TO_TERM_DICT[worst_csq_index]
    return VEP_CSQ_TERMS[worst_csq]