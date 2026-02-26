print("TO JEST V6 Z WYKRESAMI")
import datetime
from collections import defaultdict
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Metric, Dimension
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ===== KONFIG =====
PROPERTY_ID = "520666308"
KEY_FILE = "klucz.json"
GSC_SITE = "https://www.bskomfort.pl/"

# ===== DATY =====
today = datetime.date.today()
end_current = today - datetime.timedelta(days=1)
start_current = end_current - datetime.timedelta(days=6)

end_previous = start_current - datetime.timedelta(days=1)
start_previous = end_previous - datetime.timedelta(days=6)

start_90 = end_current - datetime.timedelta(days=89)
start_12m = end_current - datetime.timedelta(days=365)

print("=== ZAKRESY ===")
print("7 dni:", start_current, "-", end_current)
print("Poprzedni tydzień:", start_previous, "-", end_previous)
print("90 dni:", start_90, "-", end_current)
print("12 miesięcy:", start_12m, "-", end_current)

# ===== AUTORYZACJA =====
credentials = service_account.Credentials.from_service_account_file(KEY_FILE)
ga_client = BetaAnalyticsDataClient(credentials=credentials)
gsc_service = build("searchconsole", "v1", credentials=credentials)

# ===== GA FUNKCJE =====
def get_ga_sum(start, end):
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        metrics=[Metric(name="activeUsers")],
        date_ranges=[DateRange(start_date=str(start), end_date=str(end))]
    )
    response = ga_client.run_report(request)
    if response.rows:
        return int(response.rows[0].metric_values[0].value)
    return 0

def get_ga_monthly(start, end):
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        metrics=[Metric(name="activeUsers")],
        dimensions=[Dimension(name="yearMonth")],
        date_ranges=[DateRange(start_date=str(start), end_date=str(end))]
    )
    response = ga_client.run_report(request)

    monthly = {}
    if response.rows:
        for row in response.rows:
            month = row.dimension_values[0].value
            value = int(row.metric_values[0].value)
            monthly[month] = value
    return monthly

# ===== GSC FUNKCJE =====
def get_gsc_sum(start, end):
    request = {
        "startDate": str(start),
        "endDate": str(end)
    }
    response = gsc_service.searchanalytics().query(
        siteUrl=GSC_SITE,
        body=request
    ).execute()

    clicks = 0
    impressions = 0

    if "rows" in response:
        for row in response["rows"]:
            clicks += row["clicks"]
            impressions += row["impressions"]

    return clicks, impressions

def get_gsc_queries(start, end):
    request = {
        "startDate": str(start),
        "endDate": str(end),
        "dimensions": ["query"],
        "rowLimit": 250
    }
    response = gsc_service.searchanalytics().query(
        siteUrl=GSC_SITE,
        body=request
    ).execute()

    data = {}
    if "rows" in response:
        for row in response["rows"]:
            data[row["keys"][0]] = {
                "clicks": row["clicks"],
                "impressions": row["impressions"]
            }
    return data

# ===== OBLICZENIA =====

# GA
ga_current = get_ga_sum(start_current, end_current)
ga_previous = get_ga_sum(start_previous, end_previous)
ga_90_total = get_ga_sum(start_90, end_current)
ga_12m_monthly = get_ga_monthly(start_12m, end_current)

ga_90_avg_week = round(ga_90_total / 13, 2)  # 90 dni ≈ 13 tygodni

print("\n=== GA ===")
print("7 dni:", ga_current)
print("Poprzedni tydzień:", ga_previous)
print("Średnia tygodniowa z 90 dni:", ga_90_avg_week)
print("Trend 12M:", ga_12m_monthly)

# GSC
gsc_current = get_gsc_sum(start_current, end_current)
gsc_previous = get_gsc_sum(start_previous, end_previous)
gsc_90 = get_gsc_sum(start_90, end_current)
gsc_12m = get_gsc_sum(start_12m, end_current)

queries_current = get_gsc_queries(start_current, end_current)
queries_previous = get_gsc_queries(start_previous, end_previous)

# Analiza zapytań
new_queries = []
growing_queries = []
declining_queries = []

for q in queries_current:
    if q not in queries_previous:
        new_queries.append(q)
    else:
        diff = queries_current[q]["impressions"] - queries_previous[q]["impressions"]
        if diff > 0:
            growing_queries.append((q, diff))
        elif diff < 0:
            declining_queries.append((q, diff))

growing_queries = sorted(growing_queries, key=lambda x: x[1], reverse=True)[:5]
declining_queries = sorted(declining_queries, key=lambda x: x[1])[:5]

print("\n=== GSC ===")
print("7 dni:", gsc_current)
print("Poprzedni tydzień:", gsc_previous)
print("90 dni:", gsc_90)
print("12 miesięcy:", gsc_12m)

print("\nNowe zapytania:", new_queries[:5])
print("Największe wzrosty:", growing_queries)
print("Największe spadki:", declining_queries)

# ===== TEST WYKRES =====
import matplotlib.pyplot as plt

plt.figure()
plt.bar(["Test A", "Test B"], [10, 20])
plt.title("Test wykresu")
plt.savefig("test_wykres.png")
plt.close()

print("Wykres testowy zapisany.")
