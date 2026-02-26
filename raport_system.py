import datetime
import matplotlib.pyplot as plt
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

# ===== AUTORYZACJA =====
credentials = service_account.Credentials.from_service_account_file(KEY_FILE)
ga_client = BetaAnalyticsDataClient(credentials=credentials)
gsc_service = build("searchconsole", "v1", credentials=credentials)

# ===== GA =====
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

# ===== GSC =====
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
            data[row["keys"][0]] = row["impressions"]
    return data

# ===== OBLICZENIA =====
ga_current = get_ga_sum(start_current, end_current)
ga_previous = get_ga_sum(start_previous, end_previous)
ga_90_total = get_ga_sum(start_90, end_current)
ga_12m_monthly = get_ga_monthly(start_12m, end_current)

ga_90_avg_week = round(ga_90_total / 13, 2)

gsc_current = get_gsc_sum(start_current, end_current)
gsc_previous = get_gsc_sum(start_previous, end_previous)

queries_current = get_gsc_queries(start_current, end_current)
queries_previous = get_gsc_queries(start_previous, end_previous)

# ===== ANALIZA ZAPYTAŃ =====
growing = []
declining = []

for q in queries_current:
    prev = queries_previous.get(q, 0)
    diff = queries_current[q] - prev
    if diff > 0:
        growing.append((q, diff))
    elif diff < 0:
        declining.append((q, diff))

growing = sorted(growing, key=lambda x: x[1], reverse=True)[:5]
declining = sorted(declining, key=lambda x: x[1])[:5]

# ===== WYKRES 1 – 7 dni vs tydzień =====
plt.figure()
plt.bar(["Poprzedni tydzień", "Aktualny tydzień"], [ga_previous, ga_current])
plt.title("GA – tydzień vs tydzień")
plt.savefig("v6_ga_week.png")
plt.close()

# ===== WYKRES 2 – tydzień vs średnia 90 dni =====
plt.figure()
plt.bar(["Średnia 90 dni", "Aktualny tydzień"], [ga_90_avg_week, ga_current])
plt.title("GA – tydzień vs średnia 90 dni")
plt.savefig("v6_ga_90.png")
plt.close()

# ===== WYKRES 3 – trend 12M =====
months = sorted(ga_12m_monthly.keys())
values = [ga_12m_monthly[m] for m in months]

plt.figure()
plt.plot(months, values, marker="o")
plt.title("Trend GA – 12 miesięcy")
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("v6_ga_12m.png")
plt.close()

# ===== WYKRES 4 – wzrosty zapytań =====
if growing:
    labels = [q[0][:20] for q in growing]
    vals = [q[1] for q in growing]

    plt.figure()
    plt.barh(labels, vals)
    plt.title("Największe wzrosty zapytań")
    plt.tight_layout()
    plt.savefig("v6_queries_up.png")
    plt.close()

# ===== WYKRES 5 – spadki zapytań =====
if declining:
    labels = [q[0][:20] for q in declining]
    vals = [abs(q[1]) for q in declining]

    plt.figure()
    plt.barh(labels, vals)
    plt.title("Największe spadki zapytań")
    plt.tight_layout()
    plt.savefig("v6_queries_down.png")
    plt.close()

print("Wykresy wygenerowane.")
