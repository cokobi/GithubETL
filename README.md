# GitHub Repository ETL Pipeline

## Overview

This project is an ETL (Extract, Transform, Load) pipeline designed to gather, clean, and store data about newly created repositories from the GitHub REST API.

The "business problem" is that simply searching GitHub yields millions of results, many of which are low-quality, test, or abandoned projects. 
This pipeline aims to solve this by creating a clean, filtered, and structured dataset of *high-quality* repositories, making it possible to perform meaningful 
analysis on new trends, languages, and project activities.

## Project Scope

The scope of this project is to:

	- Extract repository data from the GitHub API based on a set of quality filters.
	- Implement a robust extraction strategy to handle API rate limits and pagination constraints (specifically the 1,000-result cap).
	- Transform the raw JSON data into a clean, flat, relational format using Pandas.
	- Load the transformed data into a PostgreSQL database for storage and analysis.
	- Provide a foundation for a BI (Business Intelligence) tool, such as Metabase, to connect and visualize the data.

## Project Architecture

The pipeline follows a standard ETL flow, orchestrating data from the API to a final database.

## Technology Stack

	- **Python 3.10+**
	- **Requests**: For making HTTP API calls.
	- **Pandas**: For data transformation and cleaning.
	- **SQLAlchemy**: For connecting to the database.
	- **psycopg2**: PostgreSQL driver for Python.
	- **PostgreSQL**: As the relational data warehouse.
	- **Docker**: For running PostgreSQL and Metabase in isolated containers.
	- **python-dotenv**: For managing environment variables.

## Project Structure

```
github_etl_project/
├── .env                  # Stores environment variables (NOT committed to Git)
├── .gitignore            # Specifies files for Git to ignore (e.g., .env, .venv)
├── docker-compose.yml    # Defines the `postgres-db` and `metabase-app` services.
├── main.py               # Main entry point, orchestrates the ETL flow
├── requirements.txt      # List of Python dependencies
├── README.md             # This file.
├── src/
│   ├── __init__.py
│   ├── config.py         # Handles .env loading and connection strings
│   ├── extractor.py      # Handles all GitHub API extraction logic
│   ├── transformer.py    # Handles all data cleaning and transformation
│   └── loader.py         # Handles loading data into the database
├── sql/
│   ├── create_metrics.sql   # (Run once) Creates the Materialized Views.
│   └── refresh_metrics.sql  # (Run after ETL) Refreshes the Views.
└── logs/
    └── etl.log            # ETL process log
```

## The Data

### GitHub API Endpoint

The pipeline queries a single, powerful endpoint:

	- **Endpoint**: 'https://api.github.com/search/repositories'
	- **Documentation**: [GitHub Search API Docs](https://docs.github.com/en/rest/search/search?#search-repositories)

All filtering is done using the 'q' (query) parameter. 
Our default query is built from a set of filters designed to find *high-quality* projects, defined as:

	- 'is:public'
	- 'archived:false'
	- 'size:>=500' (at least 500 KB)
	- 'stars:>=1' (at least one star)
	- 'forks:>=1' (at least one fork)
	- 'has:readme'
	- 'has:license'

### Data Snapshot (Before vs. After Transform)

The 'transformer.py' script's main job is to convert complex raw data into a clean, flat table.

**Before (Raw 'items' from API):**

| id  | owner                                                     | language |
|-----|-----------------------------------------------------------|----------|
| 123 | '{"login":"user-a", "id":456, "type":"User", ...}'        | 'null'   |
| 456 | '{"login":"org-b", "id":789, "type":"Organization", ...}' | 'Python' |

**After (Clean DataFrame loaded to SQL):**

| id  | language | user    | user_type    | user_id |
|-----|----------|---------|--------------|---------|
| 123 | 'Unknown'| 'user-a'| 'User'       | 456     |
| 456 | 'Python' | 'org-b' | 'Organization'| 789     |


## ETL Process Explained

### 1. Extract

The extraction logic is the most complex part of the project due to two major GitHub API constraints:

	1. **Rate Limiting**: The API limits authenticated users to 30 requests per minute. We handle this by adding a 'time.sleep(2.1)' after every request to stay under the limit.
	2. **The 1,000-Result Limit**: The API will *never* return more than 1,000 results (10 pages of 100) for a single query, even if the true 'total_count' is higher.

Our filters are effective, but this creates a "dense" data problem. 
For example, **January 2025 alone has over 22,000 high-quality repositories**. 
This is far more than the 1,000-result cap, making a simple monthly query impossible.

**Solution (Daily Chunking and Pagination):**

To solve this, we break the extraction into smaller, manageable chunks:

	1. **Daily Chunking**: The 'main.py' script runs a loop for every day in the desired year. 
						   For each day, it calls the 'fetch_one_date' function (from 'extractor.py'). 
						   This assumes that no single day has more than 1,000 results. 
						   This assumption should be validated against the 'total_count' logged for each day.
	2. **Pagination**: The 'fetch_one_date' function handles the 100-item-per-page limit. 
					   It runs an internal loop, requesting 'page=1', 'page=2', etc., for that single day, using the 'fetch_page' function for each request. 
					   It stops when the API returns an empty list of items.
	3. **Risk and Validation**: This process involves thousands of API calls. A single call failure (e.g., a network error) could cause data loss. 
								To mitigate this, the 'fetch_page' function logs the 'total_count' for each day and implements a robust 'try/except' block with a retry mechanism. 
								For a full validation, the final 'total_count' in the database should be compared against the sum of the logs.

### 2. Transform

The 'transformer.py' script receives the raw list of 'items' and performs several key operations using Pandas:

	- **Flattening**: The 'owner' field, a nested JSON object, is flattened into three separate columns: 'user', 'user_type', and 'user_id'.
	- **Filtering**: Rows are dropped if they are 'archived', 'disabled', or 'is_template'.
	- **Type Conversion**: Date fields ('created_at', 'updated_at', 'pushed_at') are converted from strings to proper 'datetime' objects. This is critical for time-series analysis in the database.
	- **Imputation (Null Handling)**:
	  - 'language': Null values are filled with the string 'Unknown' for clearer grouping.
	  - 'size': Null values are filled using a two-step mean imputation: first by 'user_id', and any remaining nulls (for new users) are filled by the global 'size' mean.
	- **Cleansing**: Duplicates on 'id' are dropped, and rows with nulls in critical key fields ('id', 'created_at') are dropped.

### 3. Load

The loading strategy is handled by 'loader.py' and orchestrated by 'main.py'.

	- **Initial Load**: The 'run_full_etl()' function in 'main.py' performs the full historical backfill (e.g., for all of 2025). 
						At the end of the run, it concatenates all daily DataFrames into one large DataFrame. 
						The 'loader' then uses 'if_exists='replace'' to completely rebuild the 'repositories' table. 
						This ensures a clean state for each full run.
	- **Future Continuity (Daily Load)**: A new function, 'run_daily_load()', can be added to 'main.py' to run daily. 
										  This function would only fetch data for "yesterday" and instruct the loader to use 'if_exists='append'' 
										  to add new data without deleting the historical records.

## Setup and Installation

Follow these steps to set up and run the project locally.

### 1. Prerequisites

	- Python 3.10+
	- Docker and Docker Desktop installed and running.
	- A GitHub Personal Access Token.

### 2. Clone & Install

'''bash
	# Clone the repository
	git clone [your-repository-url]
	cd github-etl-project

	# Create and activate a virtual environment
	python -m venv .venv

	# On Windows
	.\.venv\Scripts\activate

	# On MacOS/Linux
	source .venv/bin/activate

	# Install dependencies
	pip install -r requirements.txt
'''

### 3. GitHub Token (Critical for Rate Limits)

The GitHub API is heavily rate-limited.

	- Anonymous: 10 requests/minute
	- Authenticated (with Token): 30 requests/minute

Our script *requires* a token to function.

	1. [Click here to generate a new Personal Access Token (Classic)](https://github.com/settings/tokens/new).
	2. Give it a **Note** (e.g., "ETL Project").
	3. Set an **Expiration**.
	4. Select **only** the 'public_repo' scope.
	5. Generate the token and **copy it immediately**.

### 4. Environment Variables

Create a file named **.env** in the root of the project directory. It must *not* be committed to Git.

Copy the following template into your **.env** file and fill in your values.

'''env
	# .env

	# --- GitHub ---
	# Your GitHub PAT (e.g., ghp_...)
	GITHUB_TOKEN=ghp_...

	# --- PostgreSQL ---
	# These must match the 'docker run' command
	DB_USER=postgres
	DB_PASS=MySecretPassword123
	DB_HOST=localhost
	DB_PORT=5432
	DB_NAME=github_db

	# --- Logging ---
	# (Options: DEBUG, INFO, WARNING, ERROR)
	LOG_LEVEL=INFO
	LOG_DIR="logs"
'''

### 5. Database Setup (Docker)

This project uses Docker Compose to run both the PostgreSQL database and the Metabase analytics tool.

Simply run the following command in your terminal:

	docker-compose up -d

This will start both services in the background.

### 6. Running the ETL Pipeline

With your '.env' file saved and the Docker container running, you can now run the main pipeline:

	python main.py

This will start the full ETL process. You can monitor its progress in the terminal and in the 'logs/etl.log' file.

### 7. Create Analytics Tables (SQL)

After the ETL process is finished, you must create and populate the aggregated analytics tables (Materialized Views).

	1. Connect to your database (e.g., using the VS Code 	PostgreSQL extension).
	2. Run Once: Open and execute the file sql/create_metrics.sql to create the views.
	3. Run After Every ETL: Open and execute the file sql/refresh_metrics.sql to populate the views with the latest data.

### 8. Access Metabase & Visualization

Now you are ready for the final step:

	1. Open your browser and go to: http://localhost:3000
	2. Follow the setup steps to create your admin account.
	3. When Metabase asks to "Add your data", connect to your PostgreSQL database with the following settings:

		* Database type: PostgreSQL
		* Host: postgres-db (This is the service name from docker-compose.yml, not localhost)
		* Port: 5432
		* Database name: github_db
		* Username: postgres
		* Password: MySecretPassword123

	4. Metabase will sync and discover your tables.
	5. Click "New" -> "Question" and select your analytics tables (e.g., daily_repo_metrics) to build fast, interactive dashboards.
