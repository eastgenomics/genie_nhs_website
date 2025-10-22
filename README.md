# NHS Genie

## Overview

**NHS Genie** is a web application designed for exploring 
**GENIE oncology  variant data**. It includes custom variant–patient count 
datasets generated to assist with variant interpretation according to the
[UK Somatic Variant Interpretation Guidelines (S-VIG)](https://www.acgs.uk.com/media/12831/svig-uk_guidelines_v10_-_post-acgs_ratification_final_submit01.pdf). 

The project is built with **Django 5.2** and **SQLite**, supports deployment 
both via **Docker** with **Nginx** web server and without (via **WhineNoise**),
and is distributed under the **MIT License**.


## Acknowledgement

The authors would like to acknowledge the American Association for Cancer Research 
and its financial and material support in the development of the AACR Project GENIE 
registry, as well as members of the consortium for their commitment to data sharing. 
Interpretations are the responsibility of the study authors.

**Publication**: AACR Project GENIE Consortium. AACR Project GENIE: 
Powering Precision Medicine Through an International Consortium, 
Cancer Discov. 2017 Aug;7(8):818-831.


![AACR Project GENIE LOGO](static/images/AACR_Project_GENIE.png)

## Environment and source data files

### Environment

The project expects an environment (`.env`) file in the root directory with the following variables:

```env
# Debug mode (boolean)
DEBUG
# Enable WhiteNoise to run the website in Docker without an Nginx server (boolean)
USE_WHITENOISE
# Secret key for production
SECRET_KEY
# Web server port
PORT
# Web server address(es). Multiple addresses can be provided, 
# separated by commas (e.g., `1.1.1.1`,`nhs-genie.uk`)
ALLOWED_HOSTS
# Path to the folder containing the GENIE VCF file, cancer types CSV, and database
# (optional, default is /genie_nhs_website/data)
DATA_FOLDER
# Database name (optional, default is db.sqlite3), stored in the data folder
DB_NAME
# GENIE data version (e.g., v17), displayed in multiple places on the website
GENIE_VERSION
# GENIE VCF file name
GENIE_VCF
# GENIE cancer types CSV – contains VCF and display cancer type names, 
# groups (e.g., HaemOnc), and total patient counts
GENIE_CANCER_TYPES_CSV
# CSRF trusted origins (optional, derived from ALLOWED_HOSTS 
# unless explicitly provided)
CSRF_TRUSTED_ORIGINS
```

### Genie source data

The project expects two source data files to be present in the project's data 
folder:
* A VCF file with variant cancer patient counts (`GENIE_VCF` in the `.env` file)
* A CSV file with cancer types metadata (`GENIE_CANCER_TYPES_CSV` in the `.env` file)

The CSV file must include the following columns:

* `vcf_name` (String) — The cancer type name as referenced in the VCF file's patient count attributes (e.g., `BLymphoblasticLeukemiaLymphoma`).
* `display_name` (String) — The cancer type name as it should appear on the website (e.g., `B-Lymphoblastic Leukemia/Lymphoma`).
* `is_haemonc` (Integer) — A `0` or `1` flag indicating whether the cancer type belongs to the HaemOnc group.
* `is_solid` (Integer) — A `0` or `1` flag indicating whether the cancer type belongs to the Solid Tumor group.
* `total_patient_count` (Integer) — The total number of GENIE patients associated with this cancer type.

**IMPORTANT**: These files are not included in the project's Git repository. 
They must be downloaded separately and placed in the project's data folder
(by default: `/genie_nhs_website/data`).

## Database setup

The project creates a database in the data folder from the GENIE VCF and cancer 
types CSV files, which must be located in the same folder and defined in the 
environment file (Set `GENIE_VCF` and `GENIE_CANCER_TYPES_CSV` in `.env` file). 
Note that the database is shared by all Docker containers, but its name can be 
changed in the environment file before building the container. This makes it 
possible to have multiple working instances if needed.

To set up the database:

1. Go to the project directory
2. Create a Python virtual environment:
    ```bash
    python -m venv venv
    ```
3. Activate the virtual environment:
    ```bash
    source venv/bin/activate
    ```
4. Install the required packages:
    ```bash
    pip install -r requirements.txt
    ```
5. Create the local SQLite database:
    ```bash
    python manage.py migrate
    ```
6. Import the GENIE VCF data into the database:
    ```bash
    python db_importer.py
    ```

## Running the website locally (Django development server)

1. Activate the virtual environment (created during database setup):
    ```bash
    source venv/bin/activate
    ```
2. Set `DEBUG=1` in the `.env` file
3. Run the website in development mode on port `8080`:
    ```bash
    python manage.py runserver 8080
    ```

## Running the website in Docker without a dedicated web server
1. Follow the official Docker installation instructions if not already installed:
https://docs.docker.com/engine/install/

1. Open the .env file and:
    * Set `USE_WHITENOISE=1` to serve static files
    * Set `PORT=X`, where `X` is the server port to access the website
    * Set `ALLOWED_HOSTS` to the server IP or website domain(s)
2. Build and run the Docker container:
    * Add `-d` to detach from the container (optional)
    * Add `-p` your_project_name to use a custom project name (optional), for example,
    to run multiple Docker containers:
    ```bash
    docker compose up --build -d -p nhs_genie
    ```