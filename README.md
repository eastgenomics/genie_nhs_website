# NHS Genie

A website to browse Genie data.

## Setup and Running

### Environment

The project expects an .env file in the root directory with the following variables:

```env
# Debug mode boolean
DEBUG
# Secret production key
SECRET_KEY
# Web server port
PORT
# Web server address
ALLOWED_HOSTS
# Path to a folder with Genie VCF file and cancer types csv
DATA_FOLDER
# Genie data version (e.g. v17), is displayed in multiple places on the website
GENIE_VERSION
# Genie VCF file name
GENIE_VCF
# Genie cancer types csv - contains VCF & display cancer type names, groups (e.g. HaemOnc), and total patient counts
GENIE_CANCER_TYPES_CSV
# CSRF trusted origins (Optional, derived from ALLOWED_HOSTS unless explicitly provided)
CSRF_TRUSTED_ORIGINS
```

### Genie cancer types CSV

The project expects a CSV file  (GENIE_CANCER_TYPES_CSV in the environment file) containing metadata for cancer types to be located in the same directory as the associated VCF file.

The CSV file must include the following columns:

* `vcf_name` (String) — The cancer type name as referenced in the VCF file's patient count attributes (e.g., `BLymphoblasticLeukemiaLymphoma`).
* `display_name` (String) — The cancer type name as it should appear on the website (e.g., `B-Lymphoblastic Leukemia/Lymphoma`).
* `is_haemonc` (Integer) — A `0` or `1` flag indicating whether the cancer type belongs to the HaemOnc group.
* `is_solid` (Integer) — A `0` or `1` flag indicating whether the cancer type belongs to the Solid Tumor group.
* `total_patient_count` (Integer) — The total number of GENIE patients associated with this cancer type.

## Running locally (development)
1. Go to the project directory
2. Create Python virtual environment:
    ```bash
    python -m venv venv
    ```
3. Activate virtual environment:
    ```bash
    source venv/bin/activate
    ```
4. Install prerequisites:
    ```bash
    pip install -r requirements.txt
    ```
5. Create the local SQLite database:
    ```bash
    python manage.py migrate
    ```
6. Import Genie VCF data to the database:
    ```bash
    python db_importer.py
    ```
7. Run the website in development mode:
    ```bash
    python manage.py runserver 8080
    ```

## Running in docker (production)
* Build and run the docker container when database is ready (i.e. after db_importer.py was executed):
    ```bash
    docker compose up --build
    ```
* Build and run the docker container, and re-seed the database:
    ```bash
    docker compose --profile db-reset up --build
    ```