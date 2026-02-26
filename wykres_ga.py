from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
from google.oauth2 import service_account
import pandas as pd
import matplotlib.pyplot as plt

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

dates = []
sessions = []

for row in response.rows:
    dates.append(row.dimension_values[0].value)
    sessions.append(int(row.metric_values[0].value))

df = pd.DataFrame({
    "date": pd.to_datetime(dates),
    "sessions": sessions
})

df = df.sort_values("date")
df["rolling_avg"] = df["sessions"].rolling(window=7).mean()

plt.figure(figsize=(10,5))
plt.plot(df["date"], df["sessions"], label="Sesje dzienne")
plt.plot(df["date"], df["rolling_avg"], label="Średnia 7 dni")
plt.title("Ruch – ostatnie 30 dni")
plt.xlabel("Data")
plt.ylabel("Sesje")
plt.legend()
plt.tight_layout()

plt.savefig("wykres.png")
plt.show()

