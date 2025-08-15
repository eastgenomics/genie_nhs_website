# NHS Genie

A website to browse Genie data.

## Setup and Running

### Environment

The project expects an .env file in the root directory with the following variables:

```env
# Debug mode boolean (the production docker container is always built with debug turned off)
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
# CSRF trusted origins (Optional, derived from ALLOWED_HOSTS unless explicitly provided)
CSRF_TRUSTED_ORIGINS
```

## Running for development
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

## Running for production
1. Build and run the docker container:
    ```bash
    docker compose up --build
    ```