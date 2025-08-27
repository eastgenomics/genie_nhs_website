import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nhs_genie_project.settings')
import sys
import django
django.setup()

import gzip
import csv
import sqlite3
import pandas as pd

from django.conf import settings
from django.db.models import NOT_PROVIDED

from main.models import CancerType, Variant
from main.utils import get_worst_csq_display_term

# VCF cancer patient count INFO field prefixes and their respective 
# VariantCancerTypePatientCount model field names
CANCER_PC_PREFIXES = {
    'SameNucleotideChange': 'same_nucleotide_change_pc',
    'SameAminoAcidChange': 'same_amino_acid_change_pc',
    'SameOrDownstreamTruncatingVariantsPerCDS': \
        'same_or_downstream_truncating_variants_per_cds_pc',
    'NestedInframeDeletionsPerCDS': 'nested_inframe_deletions_per_cds_pc',
}
# A dict template for VariantCancerTypePatientCount row data without
# variant and cancer foreign keys. Ensures that the order of column
# names and values in SQL queries are in the same order.
CANCER_PC_DICT = dict.fromkeys(CANCER_PC_PREFIXES.values(), 0)


def get_db() -> sqlite3.Connection:
    """
    Get SQLite DB connection or exit with error.
    
    Returns
    -------
    sqlite3.Connection        
    """
    try:
        return sqlite3.connect(settings.DATABASES['default']['NAME'])
    except sqlite3.Error as e:
        sys.exit(f'Failed to connect to database: {e}')


def truncate_table(db, table_name):
    """
    Delete all records in a table and reset the primary key counter.

    Parameters
    ----------
    table_name: str
        Name of the database table that has to be cleared.
    
    Returns
    -------
    None
    """
    cur = db.cursor()
    # Truncate table (DELETE without WHERE = TRUNCATE in SQLite).
    cur.execute(f"DELETE FROM {table_name}")
    # Reset table primary key.
    cur.execute(f"DELETE FROM sqlite_sequence WHERE name='{table_name}'")
    db.commit()


def import_cancer_types(db) -> None:
    """
    Populate cancer types table from cancer_types csv.

    Parameters
    ----------
    db: 
        sqlite3.Connection

    Returns
    -------
    None
    """
    truncate_table(db, 'main_cancer_type')
    
    cancer_types_csv = settings.BASE_DIR / 'data/cancer_types.csv'
    df = pd.read_csv(cancer_types_csv)

    cancer_types = []
    for _index, row in df.iterrows():
        cancer_type = CancerType(
            cancer_type=row['display_name'],
            cancer_type_vcf=row['vcf_name'],
            is_haemonc=bool(int(row['is_haemonc'])),
            total_patient_count=int(row['total_patient_count'])
        )
        cancer_types.append(cancer_type)
    CancerType.objects.bulk_create(cancer_types)


def import_vcf_variants(db) -> None:
    """
    Import data from the Genie VCF to the variant and variant cancer
    type patient count tables.

    Parameters
    ----------
    db: 
        sqlite3.Connection

    Returns
    -------
    None    
    """

    if not settings.GENIE_VCF.is_file():
        sys.exit('DB reset was cancelled; Genie VCF file was not found:\n' + \
            str(settings.GENIE_VCF))

    # Get database cursor
    cur = db.cursor()
    # Enable foreign key checks
    cur.execute("PRAGMA foreign_keys = ON;")
    db.commit()
    
    # Delete all previous variant and variant cancer type patient count records.
    truncate_table(db, 'main_variant_cancer_type_patient_count')
    truncate_table(db, 'main_variant')

    # "id", "chrom", "pos", "ref", and "alt" variant model fields
    #  are populated from non-INFO VCF fields.
    info_fields = [
        f for f in Variant._meta.concrete_fields
        if f.attname not in ('id', 'chrom', 'pos', 'ref', 'alt')
    ]

    # Create an SQL queries with variant table column names and
    # CANCER_PC_PREFIXES keys/values to ensure that the data is inserted
    # into the right columns.
    var_sql_column_names = ', '.join(
        ['id', 'chrom', 'pos', 'ref', 'alt'] + [f.attname for f in info_fields]
    )
    var_sql_column_values = ', '.join(['?'] * (5 + len(info_fields)))
    var_sql_query = (f'INSERT INTO main_variant ({var_sql_column_names}) '
                 f'VALUES ({var_sql_column_values})')

    var_cancer_pc_sql_column_names = ', '.join(
        ['id', 'variant_id', 'cancer_type_id']
        + list(CANCER_PC_PREFIXES.values())
    )
    var_cancer_pc_sql_column_values = \
        ', '.join(['?'] * (3 + len(CANCER_PC_PREFIXES)))
    var_cancer_pc_sql_query = (
        'INSERT INTO main_variant_cancer_type_patient_count '
        f'({var_cancer_pc_sql_column_names}) '
                 f'VALUES ({var_cancer_pc_sql_column_values})')

    def _insert_batch(var_batch_data: list, cancer_pc_batch_data: list):
        """
        Insert batches of variant and variant cancer type patient count
        records to the database.

        Parameters
        ----------
        var_batch_data : list
            List of main_variant rows (lists).
        cancer_pc_batch_data : list
            List of main_variant_cancer_type_patient_count rows (lists).

        Returns
        -------
        None
        """
        try:
            cur.execute('BEGIN')
            cur.executemany(var_sql_query, var_batch_data)
            cur.executemany(var_cancer_pc_sql_query, cancer_pc_batch_data)
            db.commit()
        except Exception as e:
            print(f'Failed to insert a batch of variant records: "{e}"')
            db.rollback()
            sys.exit('Please fix the problem and re-run the script.')

    def _verify_csqs(csqs: str) -> None:
        """
        Verify that there are no unexpected VEP consequences.

        Parameters
        ----------
        csqs : str
            VEP consequences delimited by '&' e.g.
            "non_coding_transcript_exon_variant&non_coding_transcript_variant"
        
        Returns
        -------
        None
        """
        most_severe_csq = get_worst_csq_display_term(csqs)
        if not most_severe_csq:
            sys.exit('Failed to identify the most severe consequence from '
                f'"{csqs}". Ensure consequences are delimited by "&" (or ",") '
                'and that all terms are present in VEP_CSQ_TERMS.')        

    # Counter to store the total number of processed variants.
    count = 0
    # A list to store variant rows for insertion to the database.
    var_batch_data = []
    cancer_pc_batch_data = []

    # Get cancer type db ids.
    cancer_type_ids = {}
    cancers = CancerType.objects.all()
    for cancer in cancers:
        cancer_type_ids[cancer.cancer_type_vcf] = cancer.id

    # A counter used as database variant IDs for foreign key insertion.
    # Although it is generally not a good idea to process foreign keys
    # independently from the source table, it is safe to do so in this
    # case. This function truncates variant table and resets its
    # primary key, so variant counter will correspond to variant id. 
    var_id = 1
    with gzip.open(settings.GENIE_VCF, mode='rt', encoding='utf-8', 
            newline='') as f:
        reader = csv.reader(f, delimiter='\t')

        # Loop through the VCF file rows.
        for row in reader:
            # Skip header rows.
            if row[0].startswith('#'):
                continue
            
            # Get non-INFO variant model fields data.
            chrom = row[0]
            pos = int(row[1])
            ref = row[3]
            alt = row[4]

            # Parse VCF INFO column and store results in a dict.
            # Note: the current Genie VCF has no flag INFO fields.
            info_dict = {}
            for info_item in row[7].split(';'):
                if '=' in info_item:
                    key, val = info_item.split('=', 1)
                    info_dict[key] = val

                    if key == 'Consequence':
                        # Ensure that there are no unexpected VEP csqs.
                        _verify_csqs(val)

            # Construct a variant row with values from the VCF in the
            # same order as the model attribute names in the SQL query.
            # The first item is "None" for the auto-generated ID.
            db_row = [None, chrom, pos, ref, alt]
            for f in info_fields:
                # Get VCF INFO fields name from the variant model help text.
                val = info_dict.get(f.help_text, None)
                # If INFO key is missing and model field has default - use it.
                if val is None and f.default is not NOT_PROVIDED:
                    val = f.get_default()
                db_row.append(val)
            var_batch_data.append(db_row)

            # Process variant cancer type patient counts.
            var_cancer_pcs = {}
            for key, val in info_dict.items():
                # Skip VCF fields with 0 patient counts. CANCER_PC_DICT
                # has default 0 values for each patient count type, so
                # a record is inserted if at least one of the counts is
                # not 0.
                if val == '0':
                    continue
                # Variant cancer type patient counts names have the
                # following format:
                # {COUNT_TYPE}_{CANCER_TYPE}_Count_N_{TOTAL_PATIENT_COUNT}
                if key.startswith(tuple(CANCER_PC_PREFIXES.keys())):
                    pc_type_vcf, cancer_type_vcf = \
                        key.split('_Count_')[0].split('_', 1)
                    if cancer_type_vcf not in var_cancer_pcs:
                        var_cancer_pcs[cancer_type_vcf] = dict(CANCER_PC_DICT)
                    pc_type = CANCER_PC_PREFIXES[pc_type_vcf]
                    var_cancer_pcs[cancer_type_vcf][pc_type] = int(val)
            
            # Construct a variant cancer type row with values from the 
            # VCF in the same order as the model attribute names in the 
            # SQL query. The first item is "None" for the auto-generated ID.
            for cancer, pcs in var_cancer_pcs.items():
                if cancer not in cancer_type_ids:
                    sys.exit(f'Unknown cancer type in VCF: "{cancer}". '
                             'Ensure it exists in data/cancer_types.csv')
                db_row = [None, var_id, cancer_type_ids[cancer]] + \
                    list(pcs.values())
                cancer_pc_batch_data.append(db_row)

            # Insert a batch of variant rows to the database.
            if len(var_batch_data) > 9999:
                _insert_batch(var_batch_data, cancer_pc_batch_data)
                count += len(var_batch_data)
                print(f'Processed {count} variants')
                var_batch_data = []
                cancer_pc_batch_data = []

            # Increase variant primary key
            var_id += 1

    # Insert any remaining variant records (i.e. < 10,000).
    if var_batch_data:
        _insert_batch(var_batch_data, cancer_pc_batch_data)
        count += len(var_batch_data)
        print(f'Processed {count} variants')


def reset_db():
    """
    Repopulate NHS Genie database.
    
    Returns
    -------
    None
    """

    db = get_db()
    import_cancer_types(db)
    import_vcf_variants(db)
    print('Successfully re-populated the database.')
    db.close()

if __name__ == '__main__':
    reset_db()