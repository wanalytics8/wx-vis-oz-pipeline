import requests
from bs4 import BeautifulSoup
from urllib.request import Request, urlopen
from datetime import datetime, timedelta
import pandas as pd
import pandas_gbq
import json
import os
import tabula
import functions_framework

# Google Cloud Libraries
from google.cloud import secretmanager
from google.cloud import storage
from google.oauth2 import service_account
from typing import Tuple, Any

# --- CONFIGURATION FROM ENVIRONMENT VARIABLES ---
# GCS Bucket (Defaulting to the one provided for local testing context)
GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME', 'cloud-ai-platform-61d1d1ac-0c20-4f68-80f0-c83968051585') 
# BigQuery Table (Defaulting to the test table)
DESTINATION_TABLE = os.environ.get('BQ_DESTINATION_TABLE', '99_temp.vizoz_datatest')
# BigQuery Table 2 (Defaulting to the test table)
DESTINATION_TABLE_2 = os.environ.get('BQ_DESTINATION_TABLE_2', '99_temp.vizoz_test_results') 
# GCP Project ID/Number
PROJECT_ID = os.environ.get('GCP_PROJECT_ID', '121869423260')
# Secret ID containing the service account JSON key
SECRET_ID = os.environ.get('SECRET_ID', 'semology-dev') 


# --- HELPER FUNCTION: DOWNLOAD PDF TO GCS ---
def download_pdf_to_gcs(url: str, storage_client: storage.Client, bucket_name: str) -> str:
    """Downloads PDF from URL, finds the filename, and uploads the content to GCS."""
    
    # 1. Get the PDF link from the main page
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    webpage = urlopen(req).read()
    soup = BeautifulSoup(webpage, 'html.parser')
    pdf_links = soup.find_all('a', href=True)
    
    pdf_url = next((link.get('href') for link in pdf_links if link.get('href') and link.get('href').endswith('.pdf')), None)

    if not pdf_url:
        raise Exception("PDF link not found on the page.")

    # 2. Download the PDF content
    pdf_response = requests.get(pdf_url, stream=True, headers={'User-Agent': 'Mozilla/5.0'})
    pdf_response.raise_for_status()
    
    filename = pdf_url.split('/')[-1]
    
    # 3. Upload content to GCS
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f'input/{filename}')
    blob.upload_from_string(pdf_response.content, content_type='application/pdf')
    
    print(f"Downloaded and uploaded to GCS: gs://{bucket_name}/input/{filename}")
    return filename 

# --- MAIN ORCHESTRATION FUNCTION ---
@functions_framework.http
def extract_and_load_visualoz(request) -> Tuple[str, int]:
    """
    Main function, NOT triggered by HTTP request. 
    Handles the entire ETL process (Download -> Extract -> Clean -> Load).
    """
    
    # --- 1. SETUP & DATE CALCULATION ---
    # The storage client must be initialized inside the function scope
    storage_client = storage.Client()
    
    # Calculate the date for the URL (2 day prior)
    d4 = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
    url = f"https://virtualoz.com.au/report/total-tv-overnight-top-30-programs/?date={d4}"
    d4_xdash = d4.replace('-', '')
    
    print(f"Starting pipeline for date: {d4}")
    
    try:
        # --- 2. DOWNLOAD PDF & SAVE LOCALLY FOR TABULA ---
        pdf_temp_path = f"/tmp/daily_overnight_programs_reach_{d4_xdash}.pdf"
        
        # Download the file content from the website and store a copy in GCS
        pdf_filename = download_pdf_to_gcs(url, storage_client, GCS_BUCKET_NAME)
        
        # Download the GCS copy *locally* to the /tmp directory for tabula to read
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(f'input/{pdf_filename}')
        blob.download_to_filename(pdf_temp_path) 
        
        # --- 3. EXTRACT TABLE USING TABULA-PY ---
        page_number = 3
        area = (50, 50, 700, 800)
        
        dfs = tabula.read_pdf(pdf_temp_path, pages=page_number, multiple_tables=True, area=area, lattice=True)
        
        if not dfs:
            raise Exception("No table found or extraction failed.")
            
        df = dfs[0]
        
        # --- 4. DATA CLEANING ---
        df1 = df.drop(['Unnamed: 0'], axis=1)
        df1_cols = df1.columns
        df1.columns = ['Description','Network','Total TV National Reach','Total TV National Average Audience','BVOD National Average Audience']
        
        # Extract header data 
        df1['Description'][0] = df1_cols.str.split('\r')[0][1]
        df1['Network'][0] = df1_cols.str.split('\r')[1][1]
        
        # Final adjustments (Rank column, Date column, removing final row)
        df2 = df1.reset_index()
        df2['index'] = df2['index'] + 1 
        df2 = df2.rename({'index': 'Rank'}, axis=1)
        df2 = df2[df2['Rank'] < 30] 
        df2['Date'] = d4
        
        print(f"Data cleaning complete. Found {len(df2)} rows.")

        # --- 5. EXPORT TO BIGQUERY ---
        client = secretmanager.SecretManagerServiceClient()
        # Note: This path uses the PROJECT_ID as configured by environment variable
        name = f"projects/{PROJECT_ID}/secrets/{SECRET_ID}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(response.payload.data.decode("UTF-8"))
        )
        
        pandas_gbq.to_gbq(
            df2,
            destination_table=DESTINATION_TABLE,
            project_id=PROJECT_ID,
            credentials=credentials,
            if_exists='append'
        )
        
        print(f"Successfully loaded data to {DESTINATION_TABLE}")
        
        page_number = 9
        area = (50, 50, 700, 800)
        
        dfs = tabula.read_pdf(pdf_temp_path, pages=page_number, multiple_tables=True, area=area, lattice=True)
        
        if not dfs:
            raise Exception("No table found or extraction failed.")
            
        df = dfs[0]
        
        # --- 4. DATA CLEANING ---
        df1 = df.drop(['Unnamed: 0'], axis=1)
        df1_cols = df1.columns
        df1.columns = ['Description','Network','Total TV National Reach','Total TV National Average Audience','BVOD National Average Audience']
        
        # Extract header data 
        df1['Description'][0] = df1_cols.str.split('\r')[0][1]
        df1['Network'][0] = df1_cols.str.split('\r')[1][1]
        
        # Final adjustments (Rank column, Date column, removing final row)
        df2 = df1.reset_index()
        df2['index'] = df2['index'] + 1 
        df2 = df2.rename({'index': 'Rank'}, axis=1)
        df2 = df2[df2['Rank'] < 30] 
        df2['Date'] = d4
        
        print(f"Data cleaning complete. Found {len(df2)} rows.")

        # --- 5. EXPORT TO BIGQUERY ---
        client = secretmanager.SecretManagerServiceClient()
        # Note: This path uses the PROJECT_ID as configured by environment variable
        name = f"projects/{PROJECT_ID}/secrets/{SECRET_ID}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(response.payload.data.decode("UTF-8"))
        )
        
        pandas_gbq.to_gbq(
            df2,
            destination_table=DESTINATION_TABLE_2,
            project_id=PROJECT_ID,
            credentials=credentials,
            if_exists='append'
        )
        
        print(f"Successfully loaded data to {DESTINATION_TABLE_2}")
        
        return 'Pipeline finished successfully!', 200

    except Exception as e:
        print(f"Pipeline execution failed: {e}")
        return f'Pipeline failed: {e}', 500
