import pandas as pd
import logging

#filter columns
required_cols = ['id','name','description','created_at','updated_at','pushed_at',
'size','stargazers_count','watchers_count','language','forks',
'watchers','score', 'user','user_type','user_id']

def filter_columns(items_list, keep_columns = required_cols):
    raw_data = pd.DataFrame(items_list)
    
    logging.info(f"Starting data filtering.")

    #filter out archived, disabled & templates
    filtered_data = raw_data[
        (raw_data['archived'] == False) &
        (raw_data['disabled'] == False) &
        (raw_data['is_template'] == False)
    ].copy()

    #extract data from 'owner' - a dict field
    filtered_data['user'] =  filtered_data['owner'].str.get('login')
    filtered_data['user_type'] =  filtered_data['owner'].str.get('type')
    filtered_data['user_id'] =  filtered_data['owner'].str.get('id')
    
    #keep only requiered columns
    final_cols_in_df = [col for col in keep_columns if col in filtered_data.columns] #avoids error in case of a missing field
    filtered_data = filtered_data[final_cols_in_df]

    logging.info(f"RawRecordsCount: {raw_data.shape[0]}. PostFilteringRecords: {filtered_data.shape[0]}. FilteredRecords: {raw_data.shape[0]-filtered_data.shape[0]}")

    return filtered_data

def handle_nulls_and_dupes(df):
    logging.info(f"Starting data null and duplicates handling.")
    
    raw_count = df.shape[0]
    df.drop_duplicates(subset=['id'], inplace=True)
    count_after_dedupe = df.shape[0]
    df.dropna(subset=['id','created_at','user_id','user_type'], inplace=True)
    count_after_dropna = df.shape[0]
    
    logging.info(f"RawRecordsCount: {raw_count}, RemovedDuplicatedRecords: {raw_count - count_after_dedupe}, RemovedNullRecords: {count_after_dedupe - count_after_dropna}. FinalRecordsCount: {df.shape[0]}")

    #assign average size per user when size is null 
    df['size'] = df['size'].fillna(df.groupby(['user_id'])['size'].transform('mean'))
    #if user average size is also null - size will get the average of all users
    df['size'] = df['size'].fillna(df['size'].mean())

    df['language'] = df['language'].fillna('Unknown')
    
    logging.info(f"Successfully handled records with missing size and language values.")

    return df

def datetime_columns_formatter(df):
    if not df.empty:
        df['created_at'] = pd.to_datetime(df['created_at'])
        df['updated_at'] = pd.to_datetime(df['updated_at'])
        df['pushed_at'] = pd.to_datetime(df['pushed_at'])
    
    logging.info(f"Successfully converted datetime values.")
    return df

def transform(items_list):
    df_raw = filter_columns(items_list)

    if df_raw.empty:
        logging.warning("DataFrame is empty after filtering. Skipping further transformation.")
        return df_raw
    
    df_deduped = handle_nulls_and_dupes(df_raw)
    df_transformed = datetime_columns_formatter(df_deduped)
    return df_transformed