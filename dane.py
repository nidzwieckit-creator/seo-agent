import datetime
import json
import os
from googleapiclient.discovery import build
from google.oauth2 import service_account

# ---------------------------------------
# KONFIGURACJA
# ---------------------------------------

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
SERVICE_ACCOUNT_FILE = "klucz.json"
SITE_URL = "https://www.bskomfort.pl/"

HISTORIA_PLIK = "historia.json"


# ---------------------------------------
# POBIERANIE DANYCH Z GSC
# ---------------------------------------

def pobierz_dane_gsc(dni):

    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
    )

    service = build("searchconsole", "v1", credentials=credentials)

    dzis = datetime.date.today()
    start = dzis - datetime.timedelta(days=dni)
    request = {
        "startDate": str(start),
        "endDate": str(dzis),
        "dimensions": ["date"],
    }

    response = service.searchanalytics().query(
        siteUrl=SITE_URL,
        body=request
    ).execute()

    wyswietlenia = 0
    klikniecia = 0
    ctr = 0
    pozycja = 0
    dni = 0

    if "rows" in response:
        for row in response["rows"]:
            wyswietlenia += row.get("impressions", 0)
            klikniecia += row.get("clicks", 0)
            ctr += row.get("ctr", 0)
            pozycja += row.get("position", 0)
            dni += 1

    if dni > 0:
        ctr = ctr / dni
        pozycja = pozycja / dni

    return {
        "data_od": str(start),
        "data_do": str(dzis),
        "wyswietlenia": wyswietlenia,
        "klikniecia": klikniecia,
        "ctr": round(ctr * 100, 2),
        "pozycja": round(pozycja, 2)
    }


# ---------------------------------------
# HISTORIA
# ---------------------------------------

def wczytaj_historie():
    if not os.path.exists(HISTORIA_PLIK):
        return []
    with open(HISTORIA_PLIK, "r") as f:
        return json.load(f)


def zapisz_historie(nowe_dane):
    historia = wczytaj_historie()
    historia.append(nowe_dane)
    with open(HISTORIA_PLIK, "w") as f:
        json.dump(historia, f, indent=4)


# ---------------------------------------
# GŁÓWNA FUNKCJA
# ---------------------------------------

def pobierz_i_zapisz():

    dane = pobierz_dane_gsc()
    zapisz_historie(dane)
    return dane


if __name__ == "__main__":
    dane = pobierz_i_zapisz()
    print("Pobrano dane:")
    print(dane)

# ========================================
# POBIERANIE DANYCH Z GA4
# ========================================

def pobierz_dane_ga4(dni):

    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest

    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE
    )

    PROPERTY_ID = "520666308"

    client = BetaAnalyticsDataClient(credentials=credentials)

    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        date_ranges=[
            DateRange(
                start_date=f"{dni}daysAgo",
                end_date="today"
            )
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="totalUsers"),
            Metric(name="engagementRate")
        ]
    )

    response = client.run_report(request)

    sessions = 0
    users = 0
    engagement = 0

    if response.rows:
        row = response.rows[0]
        sessions = int(row.metric_values[0].value)
        users = int(row.metric_values[1].value)
        engagement = float(row.metric_values[2].value) * 100

    return {
        "sessions": sessions,
        "users": users,
        "engagement": round(engagement, 2)
    }
