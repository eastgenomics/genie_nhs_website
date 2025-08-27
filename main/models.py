import pandas as pd
from django.conf import settings
from django.db import models

def get_cancer_total_patient_counts() -> dict:
    """
    Get total patient count for each cancer type.
    
    Returns
    -------
    cancer_pcs: dict
        A dictionary in which keys are VCF cancer type names and values
        are total patient counts
    """
    cancer_pcs = {}
    cancer_types_csv = settings.BASE_DIR / 'data/cancer_types.csv'
    df = pd.read_csv(cancer_types_csv)
    for index, row in df.iterrows():
        cancer_pcs[row['vcf_name']] = row['total_patient_count']
    return cancer_pcs

CANCER_TOTAL_PATIENT_COUNTS = get_cancer_total_patient_counts()

class CancerType(models.Model):
    cancer_type = models.CharField(max_length=255)
    cancer_type_vcf = models.CharField(max_length=255)
    is_haemonc = models.BooleanField()
    total_patient_count = models.PositiveIntegerField()

    class Meta:
        db_table = 'main_cancer_type'

    def __str__(self):
        return self.cancer_type


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

    # The following two fields store the same values as the 
    # same_nucleotide_change_pc fields in VariantCancerTypePatientCount
    # model but only for the aggregated cancer types ("All" and 
    # "HaemOnc"). This is necessary to get main variant table data
    # without perfromance expensive joins with the other model.
    # N numbers for the VCF field names are obtained from the 
    # cancer_types.csv to keep it the only source for this data.
    all_cancers_count = models.PositiveIntegerField(default=0, 
        help_text=('SameNucleotideChange_All_Cancers_Count_N_' 
            + str(CANCER_TOTAL_PATIENT_COUNTS['All_Cancers'])))
    haemonc_cancers_count = models.PositiveIntegerField(default=0, 
        help_text=('SameNucleotideChange_Haemonc_Cancers_Count_N_' 
            + str(CANCER_TOTAL_PATIENT_COUNTS['Haemonc_Cancers'])))

    class Meta:
        indexes = [
            models.Index(fields=['gene_symbol']),
            models.Index(fields=['chrom', 'pos']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['chrom', 'pos', 'ref', 'alt'],
                name='uniq_variant_locus_allele',
            ),
        ]

    def __str__(self):
        return f"{self.chrom}-{self.pos}-{self.ref}-{self.alt}"
    

class VariantCancerTypePatientCount(models.Model):
    variant = models.ForeignKey(Variant, on_delete=models.CASCADE)
    cancer_type = models.ForeignKey(CancerType, on_delete=models.CASCADE)

    same_nucleotide_change_pc = models.PositiveIntegerField()
    same_amino_acid_change_pc = models.PositiveIntegerField()
    same_or_downstream_truncating_variants_per_cds_pc = \
        models.PositiveIntegerField()
    nested_inframe_deletions_per_cds_pc = models.PositiveIntegerField()

    class Meta:
        db_table = 'main_variant_cancer_type_patient_count'
