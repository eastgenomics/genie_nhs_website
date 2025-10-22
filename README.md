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

1. Go to the project directory.
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

## Running the website in Docker with Nginx or WhiteNoise
1. Follow the official Docker installation instructions if not already installed:
https://docs.docker.com/engine/install/
2. Go to the project directory.
3. Open the .env file and:
    * Set `USE_WHITENOISE` to `1` if deploying with **WhiteNoise**
    or to `0` if deploying with **Nginx**
    * Set `PORT=X`, where `X` is the server port used to access the website.
    * Set `ALLOWED_HOSTS` to the server IP or website domain(s)
4. Create a `staticfiles` folder and set ownership and permissions so that it 
    is accessible by the app/Nginx user (change the user ID `1000` if necessary):
    ```bash
    mkdir staticfiles
    sudo chown -R 1000:1000 ./staticfiles
    sudo chmod -R a+rwx ./staticfiles
    ```
    **IMPORTANT**: If the website opens but cannot load css and javascript
    files then this folder is either missing or it's permissions are not 
    configured correctly.
5. If deploying with **Nginx**, you need to edit your Nginx server
    configuration. This README does not cover a full Nginx setup and assumes 
    that you already have a server block configured to listen on a specific 
    port. For more information about Nginx configuration, refer to the
    [official guides](https://nginx.org/en/docs/beginners_guide.html).

    Add `/` and `/static/` location blocks (optionally with security headers) 
    inside your server configuration. **IMPORTANT**: Replace {PORT} with the 
    PORT number from the .env file and {WEB_SERVER_PATH} with the project path.

    ```nginx
    server {
        server_name your-website-domain.com;
        
        # Your website ports and SSL certificates configuration
        # ...

        # Optional security headers
        add_header Strict-Transport-Security 'max-age=31536000; includeSubDomains; preload';
        add_header X-XSS-Protection "1; mode=block";
        add_header X-Frame-Options "SAMEORIGIN";
        add_header X-Content-Type-Options nosniff;
        add_header Referrer-Policy "strict-origin";
        add_header Permissions-Policy "geolocation=(),midi=(),sync-xhr=(),microphone=(),camera=(),magnetometer=(),gyroscope=(),fullscreen=(self),payment=()";


        location / {
            # Replace {PORT} with the the PORT number from the .env file 
            proxy_pass http://127.0.0.1:{PORT}; 
            proxy_redirect off;
            proxy_connect_timeout 5s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        location /static/ {
            # Replace {WEB_SERVER_PATH} with the path to the project 
            alias {WEB_SERVER_PATH}/genie_nhs_website/staticfiles/;
            # Enable long-lived caching for immutable static files to boost
            # performance and reduce origin load.
            access_log off;
            expires 7d;
            try_files $uri =404;
        }
    }
    ```

    Test your Nginx configuration and restart the service:
    ```bash
    sudo nginx -t
    sudo systemctl restart nginx
    ```    

6. Build and run the Docker container (`-d` is optional to detach from the 
    container):
    ```bash
    docker compose --build -d
    ```