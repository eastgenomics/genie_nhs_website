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
ALLOWED_HOSTS=10.165.247.76
# Path to a folder with Genie VCF file
DATA_FOLDER
# Genie VCF file name
GENIE_VCF
```

## Running for development
1. Go to the project directory
2. Create python virual environment:
    ```
    python -m venv venv
    ```
3. Activate virtual environment:
    ```
    source venv/bin/activate
    ```
4. Install prerequisites:
    ```
    pip install -r requirements.txt
    ```
5. Create the local SQLite database:
    ```
    python manage.py migrate
    ```
6. Import Genie VCF data to the database:
    ```
    python db_importer.py
    ```
7. Run the website in development mode:
    ```
    python manage.py runserver 8080
    ```

## Running for production
1. Build and run the docker container:
    ```
    docker compose up --build
    ```