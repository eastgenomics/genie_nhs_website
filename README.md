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
# Path to a folder with Genie VCF file
DATA_FOLDER
# Genie VCF file name
GENIE_VCF
# Genie cancer types csv - contains VCF & display cancer type names, groups (e.g. HaemOnc), and total patient counts
GENIE_CANCER_TYPES_CSV
# CSRF trusted origins (Optional, derived from ALLOWED_HOSTS unless explicitly provided)
CSRF_TRUSTED_ORIGINS
```

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
    docker compose --profile reset up --build
    ```