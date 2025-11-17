import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy import text
import logging
import pandas as pd

TABLE_NAME = 'repositories'

def load_data_to_db(df: pd.DataFrame, engine: Engine, table_name = TABLE_NAME):
    if df.empty:
        logging.warning("DataFrame is empty, skipping load.")
        return
    
    logging.info(f"Starting to load {len(df)} rows into table '{table_name}'...")

    try:
        df.to_sql(
            name=table_name, 
            con=engine, 
            if_exists='replace', #if DB exists drop and replace data
            index=False, 
            method='multi'
            )
        logging.info(f"Successfully loaded data into '{table_name}'.")
    except Exception as e:
        logging.error(f"Failed to load data into database: {e}", exc_info=True) #exc_info=True captures Traceback in the log
        raise