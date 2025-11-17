import requests
import pandas as pd
import time
import logging
import config

BASE_URL = config.BASE_URL

DEFAULT_Q_FILTERS = {
    'is': 'public',
    'archived': 'false',
    'size': '>=500',
    'stars': '>=1',
    'forks': '>=1',
    'has': ['readme', 'license']
}
DEFAULT_API_PARAMS = {
    'sort': 'created',
    'order': 'desc',
    'per_page': 100
}
HEADERS = config.get_github_headers()


def api_query_builder(base_url = BASE_URL, query_filters = DEFAULT_Q_FILTERS, api_params = DEFAULT_API_PARAMS):      
    filter_parts = []
    for key, val in query_filters.items():
        if isinstance(val, list):
            for item in val:
                filter_parts.append(f'{key}:{item}')
        else:
            filter_parts.append(f'{key}:{val}')
    filters = '+'.join(filter_parts)
    params = '&'.join([f"{key}={value}" for key, value in api_params.items()])
    return base_url + '?q='+ filters + '&' + params


def fetch_page(url, max_retries = 3, backoff = 3, **kwargs):
    date_val = kwargs.get('date_val', 'Unknown')
    for retry in range(1,max_retries+1):
        page = kwargs.get('page', 'Unknown')
        try:
            response = requests.get(url, timeout=10, headers=HEADERS)
            response.raise_for_status()
            data = response.json()

            count = data.get('total_count','Unknown')
                        
            #validate structure
            if not isinstance(data, dict) or 'items' not in data:
                raise ValueError('Unexpected payload. \'items\' key is missing.')
            
            logging.info(f"Success. TotalRecords:{count}, RequestDate:{date_val}, RequestPage{page} .")
            return data.get('items', [])
        
        except ValueError as ve:
           logging.error(f"Data validation failed: {ve}")
           return []

        except requests.exceptions.HTTPError as http_err:
            
            #Handle 422 (page limit)
            if http_err.response.status_code == 422:
                logging.warning(f"Got HTTP 422. Assuming end of results for {date_val}, Page {page}.")
                return [] # Return an empty list to stop the 'while' loop in fetch_one_date

            logging.warning(f"attempt {retry} failed: {http_err}")
            if retry == max_retries:
                logging.error(f"Max retries exceeded. Request FAILED for RequestDate:{date_val}, RequestPage:{page}.")
                raise
            time.sleep(backoff ** retry)
        
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            return []
    return []
    
def fetch_one_date(date_value): #date_value expects string date format: '202x-MM-DD'
    items = []
    page = 1
    q_filter_override = DEFAULT_Q_FILTERS.copy()
    q_filter_override['created'] = date_value
    while True:
        q_params_override = DEFAULT_API_PARAMS.copy()
        q_params_override['page'] = page
        url_per_page = api_query_builder(BASE_URL, q_filter_override, q_params_override)
        page_items = fetch_page(url_per_page, page=page, date_val=date_value)
        if not page_items:
            break
        items.extend(page_items)
        page += 1
        time.sleep(2.1)
    return items
