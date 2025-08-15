from django.db import models


class Variant(models.Model):
    """The main (and only) database table, populated with data
    from the transformed GENIE VCF file. To keep field-name-related
    info in one place (here), the following conventions are established
    and MUST be maintained.

    1. The first four model attributes must be chrom, pos, ref, and alt
    in that order. This can be changed, but it will require an update 
    in db_importer.py.

    2. All fields populated from the VCF INFO column must have 
    "help_text" whose values match the respective VCF INFO keys 
    (used in db_importer.py).

    3. Fields displayed in the variant-table extended-row subtables must have
    "verbose_name" in the format "{subtable_prefix}:{displayed name}" (used in
    lookups.py:get_variants). So far the "PC_HaemOnc" prefix is used for
    HaemOnc cancer patient counts.
    """
    chrom = models.CharField(max_length=100)
    pos = models.IntegerField()
    ref = models.TextField()
    alt = models.TextField()

    gene_symbol = models.CharField(max_length=100, help_text='Hugo_Symbol')
    refseq_transcript = models.CharField(max_length=100, help_text='RefSeq', 
        null=True)
    consequence = models.CharField(max_length=600, help_text='Consequence')
    classification = models.CharField(max_length=600, 
        help_text='Variant_Classification')
    hgvs_c = models.TextField(help_text='HGVSc', null=True)
    hgvs_p = models.TextField(help_text='HGVSp', null=True)

    original_description = models.TextField(help_text='Genie_description')
    original_contig = models.CharField(max_length=100, 
        help_text='OriginalContig', null=True)
    original_start = models.IntegerField(help_text='OriginalStart', null=True)

    angiomatoid_fibrous_histiocytoma_count = models.IntegerField(
        help_text='Angiomatoid_Fibrous_Histiocytoma_count',
        verbose_name='PC_HaemOnc:Angiomatoid Fibrous Histiocytoma')
    b_lymphoblastic_leukemia_lymphoma_count = models.IntegerField(
        help_text='B_Lymphoblastic_Leukemia_Lymphoma_count',
        verbose_name='PC_HaemOnc:B Lymphoblastic Leukemia Lymphoma')
    blastic_plasmacytoid_dendritic_cell_neoplasm_count = models.IntegerField(
        help_text='Blastic_Plasmacytoid_Dendritic_Cell_Neoplasm_count',
        verbose_name='PC_HaemOnc:Blastic Plasmacytoid Dendritic Cell Neoplasm')
    blood_cancer_nos_count = models.IntegerField(
        help_text='Blood_Cancer_NOS_count',
        verbose_name='PC_HaemOnc:Blood Cancer NOS')
    blood_cancer_count = models.IntegerField(
        help_text='Blood_Cancer_count',
        verbose_name='PC_HaemOnc:Blood Cancer')
    histiocytosis_count = models.IntegerField(
        help_text='Histiocytosis_count',
        verbose_name='PC_HaemOnc:Histiocytosis')
    hodgkin_lymphoma_count = models.IntegerField(
        help_text='Hodgkin_Lymphoma_count', 
        verbose_name='PC_HaemOnc:Hodgkin Lymphoma')
    leukemia_count = models.IntegerField(
        help_text='Leukemia_count',
        verbose_name='PC_HaemOnc:Leukemia')
    lymphatic_cancer_nos_count = models.IntegerField(
        help_text='Lymphatic_Cancer_NOS_count',
        verbose_name='PC_HaemOnc:Lymphatic Cancer NOS')
    lymphatic_cancer_count = models.IntegerField(
        help_text='Lymphatic_Cancer_count',
        verbose_name='PC_HaemOnc:Lymphatic Cancer count')
    mastocytosis_count = models.IntegerField(
        help_text='Mastocytosis_count',
        verbose_name='PC_HaemOnc:Mastocytosis')
    mature_b_cell_neoplasms_count = models.IntegerField(
        help_text='Mature_B_Cell_Neoplasms_count',
        verbose_name='PC_HaemOnc:Mature B Cell Neoplasms')
    mature_t_and_nk_neoplasms_count = models.IntegerField(
        help_text='Mature_T_and_NK_Neoplasms_count',
        verbose_name='PC_HaemOnc:Mature T and NK Neoplasms')
    myelodysplastic_myeloproliferative_neoplasms_count = models.IntegerField(
        help_text='Myelodysplastic_Myeloproliferative_Neoplasms_count',
        verbose_name='PC_HaemOnc:Myelodysplastic Myeloproliferative Neoplasms')
    myelodysplastic_syndromes_count = models.IntegerField(
        help_text='Myelodysplastic_Syndromes_count',
        verbose_name='PC_HaemOnc:Myelodysplastic Syndromes')
    myeloid_neoplasms_with_germ_line_predisposition_count = \
        models.IntegerField(
        help_text='Myeloid_Neoplasms_with_Germ_Line_Predisposition_count',
        verbose_name='PC_HaemOnc:Myeloid Neoplasms with Germ Line Predisposition')
    myeloproliferative_neoplasms_count = models.IntegerField(
        help_text='Myeloproliferative_Neoplasms_count',
        verbose_name='PC_HaemOnc:Myeloproliferative Neoplasms')
    non_hodgkin_lymphoma_count = models.IntegerField(
        help_text='Non_Hodgkin_Lymphoma_count',
        verbose_name='PC_HaemOnc:Non Hodgkin Lymphoma')
    posttransplant_lymphoproliferative_disorders_count = models.IntegerField(
        help_text='Posttransplant_Lymphoproliferative_Disorders_count',
        verbose_name='PC_HaemOnc:Posttransplant Lymphoproliferative Disorders')
    t_lymphoblastic_leukemia_lymphoma_count = models.IntegerField(
        help_text='T_Lymphoblastic_Leukemia_Lymphoma_count',
        verbose_name='PC_HaemOnc:T Lymphoblastic Leukemia Lymphoma')
    all_cancers_count = models.IntegerField(help_text='all_cancers_count')
    haemonc_cancers_count = models.IntegerField(
        help_text='haemonc_cancers_count')

    class Meta:
        indexes = [
            models.Index(fields=['gene_symbol']),
            models.Index(fields=['chrom', 'pos']),
        ]

    def __str__(self):
        return f"{self.chrom}-{self.pos}-{self.ref}-{self.alt}"