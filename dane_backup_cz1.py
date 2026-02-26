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

def pobierz_dane_gsc():

    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
    )

    service = build("searchconsole", "v1", credentials=credentials)

    dzis = datetime.date.today()
    tydzien_temu = dzis - datetime.timedelta(days=7)

    request = {
        "startDate": str(tydzien_temu),
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
        "data_od": str(tydzien_temu),
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
