import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nhs_genie_project.settings')
import sys
import django
django.setup()

import gzip
import csv
import sqlite3

from django.conf import settings
from django.db.models import NOT_PROVIDED

from main.models import Variant
from main.utils import get_worst_csq_display_term

def import_vcf_variants() -> None:
    """
    Import data from the Genie VCF to the variant table.
    
    Returns
    -------
    None    
    """
    if not settings.GENIE_VCF.is_file():
        sys.exit('DB reset was canceled, Genie VCF file was not found:\n' + \
            str(settings.GENIE_VCF))

    # Connect to the SQLite database.
    try:
        db = sqlite3.connect(settings.DATABASES['default']['NAME'])
        cur = db.cursor()
    except sqlite3.Error as e:
        sys.exit(f'Failed to connect to database: {e}')

    # Delete all previous variant records.
    sql_query = 'DELETE FROM main_variant'
    cur.execute(sql_query)
    db.commit()

    # The first 5 variant model fields are ("id", "chrom", "pos", 
    # "ref", and "alt") are populated from non-INFO VCF fields.
    info_fields = Variant._meta.get_fields()[5:]

    # Create an SQL query with variant table column names to ensure
    # that the data is inserted into the right columns.
    sql_column_names = ', '.join(['id', 'chrom', 'pos', 'ref', 'alt']
        + [f.attname for f in info_fields])
    sql_column_values = ', '.join(['?'] * (5 + len(info_fields)))
    sql_query = (f'INSERT INTO main_variant ({sql_column_names}) '
                 f'VALUES ({sql_column_values})')

    def _insert_batch(batch_data: list):
        """
        Insert a batch of variant records to the database.

        Parameters
        ----------
        batch_data : list
            A list of variant table rows (lists).

        Returns
        -------
        None
        """
        try:
            cur.executemany(sql_query, batch_data)
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
            sys.exit('Failed to indentify the most severe consequence from '
                f'"{csqs}". Ensure consequences are delimited by "&" (or ",") '
                'and that all terms are present in VEP_CSQ_TERMS.')        

    # Counter to store the total number of processed variants.
    count = 0
    # A list to store variant rows for insertion to the database.
    batch_data = []
    with gzip.open(settings.GENIE_VCF, mode='rt') as f:
        reader = csv.reader(f, delimiter='\t')

        # Loop through the VCF file rows.
        for row in reader:
            # Skip header rows.
            if row[0][0] == '#':
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
            batch_data.append(db_row)

            # Insert a batch of variant rows to the database.
            if len(batch_data) > 9999:
                _insert_batch(batch_data)
                count += len(batch_data)
                print(f'Processed {count} variants')
                batch_data = []

    # Insert any remaining variant records (i.e. < 10,000).
    if batch_data:
        _insert_batch(batch_data)
        count += len(batch_data)
        print(f'Processed {count} variants')
    print('Successfully re-populated "variant" table.')


if __name__ == '__main__':
    # Re-populate variant table.
    import_vcf_variants()