from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime

SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']
SERVICE_ACCOUNT_FILE = 'klucz.json'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)

service = build('searchconsole', 'v1', credentials=credentials)

site_url = 'https://www.bskomfort.pl/'

end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(days=30)

request = {
    'startDate': start_date.strftime('%Y-%m-%d'),
    'endDate': end_date.strftime('%Y-%m-%d'),
    'dimensions': ['date']
}

response = service.searchanalytics().query(
    siteUrl=site_url, body=request).execute()

for row in response.get('rows', []):
    print(row['keys'][0], 
          "Kliknięcia:", row['clicks'], 
          "Wyświetlenia:", row['impressions'], 
          "CTR:", round(row['ctr']*100,2), "%", 
          "Pozycja:", round(row['position'],2))

