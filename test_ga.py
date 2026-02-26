from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
from google.oauth2 import service_account

PROPERTY_ID = "520666308"

credentials = service_account.Credentials.from_service_account_file(
    "klucz.json"
)

client = BetaAnalyticsDataClient(credentials=credentials)

request = RunReportRequest(
    property=f"properties/{PROPERTY_ID}",
    dimensions=[Dimension(name="date")],
    metrics=[Metric(name="sessions")],
    date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
)

response = client.run_report(request)

for row in response.rows:
    print(row.dimension_values[0].value, row.metric_values[0].value)

