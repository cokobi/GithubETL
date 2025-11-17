import logging
import os
import pandas as pd
import config
from src import extractor, transformer, loader
import time
from sqlalchemy.engine import Engine

def setup_logging():
    """Initiate Logging"""
    os.makedirs(config.LOG_DIR, exist_ok=True)
    
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format=config.LOG_FORMAT,
        handlers=[
            logging.FileHandler(config.LOG_FILE),
            logging.StreamHandler()
        ]
    )
    logging.info("Logs initiated Successfully.")

def full_etl(fetch_dates: list, engine: Engine):
    """
    Runs the full ETL process for a given list of dates.
    """
    
    if not fetch_dates:
        logging.warning("Date list is empty. No data to fetch.")
        return None
    
    start_time = time.time()
    all_transformed_dataframes = []
    
    for d in fetch_dates:
        logging.info(f"--- Processing Date: {d} ---")
        daily_batch = extractor.fetch_one_date(d)           #Extract
        
        if not daily_batch:
            logging.warning(f"No items found for date {d}. Skipping.")
            continue
        
        daily_df = transformer.transform(daily_batch)       #Transform

        # Only append if the transformed DF is not empty
        if not daily_df.empty:
            all_transformed_dataframes.append(daily_df)
        else:
            logging.warning(f"No valid records found for {d} after transformation.")

    if not all_transformed_dataframes:
        logging.warning("No data collected in the entire date range. Exiting.")
        return
           
    logging.info(f"Successfully processed {len(all_transformed_dataframes)} daily batches.")
    
    final_df = pd.concat(all_transformed_dataframes, ignore_index=True)
    
    if final_df.empty:
        logging.warning("Final concatenated DataFrame is empty. No data to load.")
        return

    logging.info(f"Total_records_in_df: {final_df.shape[0]}.")

    loader.load_data_to_db(final_df, engine)         #Load

    end_time = time.time()

    logging.info(f"--- ETL Pipeline Finished Successfully ---")
    logging.info(f"Total time: {end_time - start_time:.2f} seconds.")

if __name__=="__main__":
    
    setup_logging()

    try:
        db_engine = config.get_db_engine()
        
        #calculate date range to fetch
        dates_to_fetch = list(pd.date_range(start ='2025-1-1', end ='2025-12-31', freq ='D').strftime('%Y-%m-%d'))

        full_etl(dates_to_fetch, db_engine)
    
    except Exception as e:
        logging.critical(f"ETL Pipeline FAILED critically: {e}", exc_info=True)