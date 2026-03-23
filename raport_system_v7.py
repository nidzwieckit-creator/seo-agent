import datetime
from collections import defaultdict
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Metric, Dimension
from google.oauth2 import service_account
from googleapiclient.discovery import build

import matplotlib.pyplot as plt
import os
import smtplib
from email.message import EmailMessage
import ssl
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

ACCENT_COLOR = "#1f3c88"

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak
from openai import OpenAI

from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

print("=== START RAPORT V7 ===")

# ===== KONFIG =====
PROPERTY_ID = "520666308"
GSC_SITE = "https://www.bskomfort.pl/"

# ===== DATY =====

today = datetime.date.today()

# ostatnia niedziela
last_sunday = today - datetime.timedelta(days=today.weekday() + 1)

# aktualny tydzień (poniedziałek -> niedziela)
start_current = last_sunday - datetime.timedelta(days=6)
end_current = last_sunday

# poprzedni tydzień
end_previous = start_current - datetime.timedelta(days=1)
start_previous = end_previous - datetime.timedelta(days=6)

start_90 = end_current - datetime.timedelta(days=89)
start_12m = end_current - datetime.timedelta(days=365)

# ===== 30 DNI =====
start_30 = end_current - datetime.timedelta(days=29)
end_30 = end_current

start_prev_30 = start_30 - datetime.timedelta(days=30)
end_prev_30 = start_30 - datetime.timedelta(days=1)

print("Zakresy:")
print("7 dni:", start_current, "-", end_current)
print("Poprzedni tydzień:", start_previous, "-", end_previous)
print("90 dni:", start_90, "-", end_current)
print("12 miesięcy:", start_12m, "-", end_current)

# ===== AUTORYZACJA =====

import json

google_credentials_json = os.environ["GOOGLE_CREDENTIALS"]
google_credentials_dict = json.loads(google_credentials_json)

credentials = service_account.Credentials.from_service_account_info(
    google_credentials_dict
)

ga_client = BetaAnalyticsDataClient(credentials=credentials)
gsc_service = build("searchconsole", "v1", credentials=credentials)
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

# ===== GSC =====
def get_gsc_sum(start, end):
    request = {
        "startDate": str(start),
        "endDate": str(end),
        "dimensions": ["date"]
    }

    response = gsc_service.searchanalytics().query(
        siteUrl=GSC_SITE,
        body=request
    ).execute()

    clicks = 0
    impressions = 0
    ctr_sum = 0
    pos_sum = 0
    rows = 0

    if "rows" in response:
        for row in response["rows"]:
            clicks += row.get("clicks", 0)
            impressions += row.get("impressions", 0)
            ctr_sum += row.get("ctr", 0)
            pos_sum += row.get("position", 0)
            rows += 1

    ctr = ctr_sum / rows if rows else 0
    position = pos_sum / rows if rows else 0

    return clicks, impressions, ctr, position

def get_gsc_monthly(start, end):
    from collections import defaultdict

    request = {
        "startDate": str(start),
        "endDate": str(end),
        "dimensions": ["date"],
        "rowLimit": 5000
    }

    response = gsc_service.searchanalytics().query(
        siteUrl=GSC_SITE,
        body=request
    ).execute()

    monthly = defaultdict(lambda: {
        "clicks": 0,
        "impressions": 0,
        "position_sum": 0,
        "rows": 0
    })

    if "rows" in response:
        for row in response["rows"]:
            date_str = row["keys"][0]
            month = date_str[:7]

            monthly[month]["clicks"] += row.get("clicks", 0)
            monthly[month]["impressions"] += row.get("impressions", 0)
            monthly[month]["position_sum"] += row.get("position", 0)
            monthly[month]["rows"] += 1

    result = {}

    for month, data in monthly.items():
        avg_position = data["position_sum"] / data["rows"] if data["rows"] else 0
        result[month] = {
            "clicks": data["clicks"],
            "impressions": data["impressions"],
            "position": avg_position
        }

    return result

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
            query_name = row["keys"][0]

            data[query_name] = {
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": row.get("ctr", 0),
                "position": row.get("position", 0)
            }

    return data

def compare_queries(current, previous):
    comparison = []

    for query, data in current.items():
        prev_data = previous.get(query, {
            "clicks": 0,
            "impressions": 0,
            "ctr": 0,
            "position": 0
        })

        diff_clicks = data["clicks"] - prev_data["clicks"]
        diff_impressions = data["impressions"] - prev_data["impressions"]
        diff_position = data["position"] - prev_data["position"]

        comparison.append({
            "query": query,
            "clicks": data["clicks"],
            "impressions": data["impressions"],
            "ctr": data["ctr"],
            "position": data["position"],
            "diff_clicks": diff_clicks,
            "diff_impressions": diff_impressions,
            "diff_position": diff_position
        })

    return comparison

def percent_change(current, previous):
    if previous == 0:
        return 0
    return round(((current - previous) / previous) * 100, 1)

# ===== OBLICZENIA =====

# GA operacyjnie
ga_current = get_ga_sum(start_current, end_current)
ga_previous = get_ga_sum(start_previous, end_previous)
ga_90_total = get_ga_sum(start_90, end_current)
ga_90_avg_week = round(ga_90_total / 13, 2)

# Porównanie do średniej 90 dni
ga_vs_90_change = percent_change(ga_current, ga_90_avg_week)

# GSC operacyjnie

gsc_current_clicks, gsc_current_impr, gsc_current_ctr, gsc_current_pos = get_gsc_sum(start_current, end_current)
gsc_previous_clicks, gsc_previous_impr, gsc_previous_ctr, gsc_previous_pos = get_gsc_sum(start_previous, end_previous)

# ===== ZMIANY TYDZIEŃ DO TYGODNIA =====
ga_week_change = percent_change(ga_current, ga_previous)
gsc_clicks_week_change = percent_change(gsc_current_clicks, gsc_previous_clicks)
gsc_impr_week_change = percent_change(gsc_current_impr, gsc_previous_impr)

# GSC zapytania (frazy)
gsc_queries_current = get_gsc_queries(start_current, end_current)
gsc_queries_previous = get_gsc_queries(start_previous, end_previous)

queries_comparison = compare_queries(gsc_queries_current, gsc_queries_previous)

# ===== ANALIZA FRAZ =====

# TOP 10 po kliknięciach
top_queries = sorted(
    queries_comparison,
    key=lambda x: x["clicks"],
    reverse=True
)[:3]

# Frazy z potencjałem (pozycja 8–20 i rosną wyświetlenia)
potential_queries = [
    q for q in queries_comparison
    if 8 <= q["position"] <= 20 and q["impressions"] > 20
]

# Frazy spadkowe (spadek kliknięć > 20% i min. 20 wyświetleń)
declining_queries = [
    q for q in queries_comparison
    if q["diff_clicks"] < 0 and abs(q["diff_clicks"]) > (0.2 * q["clicks"])
]

# Skrócone dane do AI (ograniczamy ilość)
top_summary = top_queries[:5]
potential_summary = potential_queries[:5]
declining_summary = declining_queries[:5]

# ===== GSC 30 DNI =====
def arrow(value):
    if value > 0:
        return "↑"
    elif value < 0:
        return "↓"
    else:
        return "→"


gsc_30_clicks, gsc_30_impr, gsc_30_ctr, gsc_30_pos = get_gsc_sum(start_30, end_30)
gsc_prev_30_clicks, gsc_prev_30_impr, gsc_prev_30_ctr, gsc_prev_30_pos = get_gsc_sum(start_prev_30, end_prev_30)

clicks_30_change = percent_change(gsc_30_clicks, gsc_prev_30_clicks)
impr_30_change = percent_change(gsc_30_impr, gsc_prev_30_impr)
pos_change = percent_change(gsc_prev_30_pos, gsc_30_pos)

# GSC 12M trend
gsc_monthly = get_gsc_monthly(start_12m, end_current)

# ===== PROGNOZA SEO (dynamiczna – ostatnie 3 mies.) =====

# sortujemy miesiące rosnąco
months_sorted = sorted(gsc_monthly.keys())

# usuwamy bieżący miesiąc jeśli jest niepełny
current_month = end_current.strftime("%Y-%m")

if months_sorted and months_sorted[-1] == current_month:
    months_sorted = months_sorted[:-1]

# bierzemy ostatnie 3 miesiące (jeśli są)
last_3 = months_sorted[-3:]

monthly_impr = [gsc_monthly[m]["impressions"] for m in last_3]
monthly_clicks = [gsc_monthly[m]["clicks"] for m in last_3]

# zabezpieczenie jeśli za mało danych
if len(monthly_impr) >= 2:
    growth_rates = []
    for i in range(1, len(monthly_impr)):
        prev = monthly_impr[i-1]
        curr = monthly_impr[i]
        if prev > 0:
            growth_rates.append((curr - prev) / prev)

    avg_monthly_growth = sum(growth_rates) / len(growth_rates) if growth_rates else 0
else:
    avg_monthly_growth = 0

current_impr = monthly_impr[-1] if monthly_impr else 0
current_ctr = gsc_30_ctr

# projekcja 3 miesiące w przód
forecast_impr_3m = int(current_impr * ((1 + avg_monthly_growth) ** 3))
forecast_clicks_3m = int(forecast_impr_3m * current_ctr)

# scenariusz TOP10 (zakładamy CTR = 3%)
top10_ctr = 0.03
forecast_clicks_top10 = int(current_impr * top10_ctr)

# model konwersji (2%)
lead_rate = 0.02
forecast_leads_3m = round(forecast_clicks_3m * lead_rate, 1)

# ===== SCENARIUSZE AI =====

# Scenariusz A – utrzymanie trendu
scenario_growth = round(avg_monthly_growth * 100, 1)

# Scenariusz B – wejście do TOP10 (CTR 4%)
top10_ctr_realistic = 0.04
forecast_clicks_top10_real = int(current_impr * top10_ctr_realistic)

# Scenariusz C – spadek dynamiki o połowę
reduced_growth = avg_monthly_growth / 2
forecast_impr_slow = int(current_impr * ((1 + reduced_growth) ** 3))
forecast_clicks_slow = int(forecast_impr_slow * current_ctr)

# Indeks pogody SEO (0–10)
seo_index = round(min(10, max(1, (scenario_growth / 5) + 5)), 1)

# ===== INTERPRETACJA SEO INDEX =====

if seo_index <= 4:
    seo_status = "Niska dynamika – widoczność w fazie budowy."
elif seo_index <= 7:
    seo_status = "Umiarkowany wzrost – SEO rozwija się stabilnie."
elif seo_index <= 9:
    seo_status = "Silny trend wzrostowy – strategia działa skutecznie."
else:
    seo_status = "Bardzo wysoka dynamika – możliwy efekt skali i przełamanie widoczności."

print("\n=== PODSUMOWANIE V7 ===")
print("GA 7 dni:", ga_current)
print("GA poprzedni:", ga_previous)
print("GA średnia 90 dni:", ga_90_avg_week)

print("GSC 7 dni:", gsc_current_clicks, gsc_current_impr)
print("GSC poprzedni:", gsc_previous_clicks, gsc_previous_impr)

print("Trend 12M (GSC):", gsc_monthly)

STYLE_BASE = """
Pisz raport dla dwóch właścicieli firmy, którzy nie znają SEO.
Tłumacz wszystko bardzo prosto.
Jeśli coś spada – wyjaśnij dlaczego i czy to normalne.
Jeśli coś rośnie – wyjaśnij z czego to wynika.
Nie używaj marketingowego języka.
Nie pisz, że coś „wygląda zdrowo”.
Nie używaj branżowych skrótów.
Nie używaj angielskich słów.
Nie rób list ani wypunktowań.
Pisz konkretnie i normalnie, jak rozmowa między wspólnikami.
"""

# ===== ANALIZA AI =====

ai_client = OpenAI(api_key=OPENAI_API_KEY)

dashboard_data = {
    # GA
    "ga_current": ga_current,
    "ga_previous": ga_previous,
    "ga_week_change": ga_week_change,
    "ga_vs_90_change": ga_vs_90_change,
    "ga_avg_90": ga_90_avg_week,

    # GSC tydzień
    "gsc_current_clicks": gsc_current_clicks,
    "gsc_previous_clicks": gsc_previous_clicks,
    "gsc_clicks_week_change": gsc_clicks_week_change,

    "gsc_current_impressions": gsc_current_impr,
    "gsc_previous_impressions": gsc_previous_impr,
    "gsc_impr_week_change": gsc_impr_week_change,

    "gsc_current_ctr": round(gsc_current_ctr * 100, 2),
    "gsc_previous_ctr": round(gsc_previous_ctr * 100, 2),

    "gsc_current_position": round(gsc_current_pos, 2),
    "gsc_previous_position": round(gsc_previous_pos, 2),

    # Frazy
    "top_queries": top_summary,
    "potential_queries": potential_summary,
    "declining_queries": declining_summary,

    "count_top_queries": len(top_summary),
    "count_potential_queries": len(potential_summary),
    "count_declining_queries": len(declining_summary),

    "total_queries_current": len(gsc_queries_current),
    "total_queries_previous": len(gsc_queries_previous),

    # Trend 12M
    "trend_12m": gsc_monthly,

    # Prognoza
    "forecast_impr_3m": forecast_impr_3m,
    "forecast_clicks_3m": forecast_clicks_3m,
    "forecast_clicks_top10": forecast_clicks_top10,
    "forecast_leads_3m": forecast_leads_3m,
    "avg_monthly_growth_percent": round(avg_monthly_growth * 100, 1),
}

# ---- GŁÓWNA ANALIZA ----

main prompt = f"""
{STYLE_BASE}

Masz poniższe dane:

{dashboard_data}

===== ZASADY ANALIZY =====

1. Najważniejsze są dane tygodniowe:
- ostatnie 7 dni vs poprzedni tydzień
- to jest główna podstawa wniosków

2. Dane 30-dniowe:
- traktuj jako szerszy kontekst
- pomagają ocenić czy coś jest chwilowe czy trwałe

3. Dane miesięczne:
- traktuj tylko jako tło (trend)
- NIE oceniaj bieżącego miesiąca jako spadku jeśli jest niepełny

4. Jeśli CTR spada przy wzroście wyświetleń:
- wyjaśnij że to normalne (większy zasięg = więcej słabszych pozycji)

5. Jeśli dane są niskie przez początek okresu:
- NIE nazywaj tego spadkiem
- wyjaśnij to normalnie

===== ZADANIE =====

Napisz krótką analizę:

- co się realnie dzieje (na podstawie tygodni)
- czy idzie to w dobrą stronę
- co jest normalne (np. wahania, CTR)
- czy coś wymaga uwagi

Pisz prostym językiem, jak do laika.
Bez lania wody i bez żargonu SEO.
Nie używaj list ani wypunktowań.
"""

main_response = ai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": main_prompt}],
    temperature=0.6
)

analysis_text = main_response.choices[0].message.content.strip()

# ===== PROGNOZA AI =====

forecast_prompt = f"""
{STYLE_BASE}

Masz dane dotyczące prognozy na 3 miesiące:

- Średnie miesięczne tempo wzrostu wyświetleń: {round(avg_monthly_growth*100,1)}%
- Prognozowane wyświetlenia za 3 miesiące: {forecast_impr_3m}
- Prognozowane kliknięcia za 3 miesiące: {forecast_clicks_3m}
- Szacowana liczba potencjalnych zapytań (2% konwersji): {forecast_leads_3m}

Wyjaśnij krótko:
- czy tempo wzrostu jest szybkie czy raczej spokojne,
- co te liczby oznaczają w praktyce.

Nie analizuj wariantów.
Nie porównuj scenariuszy.
Maksymalnie 5 zdań.
"""

forecast_response = ai_client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[{"role": "user", "content": forecast_prompt}],
    temperature=0.6
)

forecast_text = forecast_response.choices[0].message.content

# ---- ANALIZA POD WYKRESEM KLIKNIĘĆ ----

clicks_prompt = f"""
{STYLE_BASE}

Skup się tylko na trendzie kliknięć z 12 miesięcy:

{gsc_monthly}

Powiedz:
- czy trend w dłuższym czasie rośnie czy nie
- czy ostatnie miesiące są lepsze czy słabsze
- czy to wygląda jak realny rozwój czy wahanie

Nie oceniaj SEO ogólnie.
Nie używaj list.
2–4 zdania.
"""

clicks_response = ai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": clicks_prompt}],
    temperature=0.4
)

clicks_analysis_text = clicks_response.choices[0].message.content.strip()

# ---- ANALIZA POD WYKRESEM WYŚWIETLEŃ ----

impressions_prompt = f"""
{STYLE_BASE}

Skup się tylko na trendzie wyświetleń z 12 miesięcy:

{gsc_monthly}

Wyjaśnij:
- czy zasięg strony rośnie czy stoi w miejscu
- czy ostatnie miesiące pokazują przyspieszenie
- czy widać, że Google pokazuje nas częściej niż wcześniej

Nie oceniaj całego SEO.
Nie używaj list.
2–4 zdania.
"""

impressions_response = ai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": impressions_prompt}],
    temperature=0.4
)

impressions_analysis_text = impressions_response.choices[0].message.content.strip()

# ===== ANALIZA AI – CTR + POZYCJA =====

ctr_last = round(gsc_30_ctr * 100, 2)
pos_last = round(gsc_30_pos, 2)

ctr_trend = percent_change(gsc_30_ctr, gsc_prev_30_ctr)
pos_trend = percent_change(gsc_prev_30_pos, gsc_30_pos)

ctr_position_prompt = f"""
{STYLE_BASE}

Dane z ostatnich 30 dni:

- Aktualny CTR: {ctr_last}%
- Zmiana CTR względem poprzednich 30 dni: {ctr_trend}%
- Aktualna średnia pozycja: {pos_last}
- Zmiana pozycji: {pos_trend}%
- Liczba wszystkich fraz obecnie: {len(gsc_queries_current)}
- Liczba fraz poprzednio: {len(gsc_queries_previous)}

Wyjaśnij:
- co oznacza zmiana CTR w kontekście wzrostu lub spadku liczby wyświetleń,
- czy spadek CTR może wynikać z większej liczby nowych fraz,
- czy zmiana pozycji jest realnie duża czy kosmetyczna,
- czy to wygląda jak etap przejściowy czy problem.

Nie używaj list.
Nie oceniaj „zdrowo / niezdrowo”.
2–4 zdania.
"""

ctr_position_response = ai_client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[{"role": "user", "content": ctr_position_prompt}],
    temperature=0.4
)

ctr_position_analysis_text = ctr_position_response.choices[0].message.content

# ===== ANALIZA FRAZ =====

queries_prompt = f"""
{STYLE_BASE}

Masz dane o frazach:

- Liczba wszystkich fraz teraz: {len(gsc_queries_current)}
- Liczba fraz wcześniej: {len(gsc_queries_previous)}

Najmocniejsze frazy:
{top_summary}

Frazy z potencjałem (pozycja 8–20):
{potential_summary}

Frazy spadkowe:
{declining_summary}

Wyjaśnij:
- czy pojawiają się nowe, realne zapytania
- czy wygasają stare, mało wartościowe frazy
- czy to wygląda jak rozszerzanie widoczności
- czy spadki są groźne czy normalne

Pisz prosto.
Nie używaj list.
3–6 zdań.
"""

queries_response = ai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": queries_prompt}],
    temperature=0.5
)

queries_analysis_text = queries_response.choices[0].message.content.strip()

# ===== SCENARIUSZE GENEROWANE PRZEZ AI =====

scenario_prompt = f"""
{STYLE_BASE}

Masz trzy możliwe warianty rozwoju:

Wariant 1 – utrzymanie obecnego tempa:
{forecast_impr_3m} wyświetleń i {forecast_clicks_3m} kliknięć

Wariant 2 – poprawa pozycji (CTR 4%):
{forecast_clicks_top10_real} kliknięć miesięcznie

Wariant 3 – wolniejszy wzrost:
{forecast_impr_slow} wyświetleń i {forecast_clicks_slow} kliknięć

Wyjaśnij:
- czym różnią się te trzy warianty,
- który jest najbardziej realny,
- czy obecna sytuacja jest stabilna czy łatwo może się zmienić.

Nie powtarzaj opisu z prognozy.
Nie tłumacz ponownie wzrostu procentowego.
Maksymalnie 6 zdań.
"""

scenario_response = ai_client.responses.create(
    model="gpt-4.1-mini",
    input=scenario_prompt
)

scenario_text = scenario_response.output_text

# ===== WYKRES 1 – Trend 12M Kliknięcia =====
months = sorted(gsc_monthly.keys())
clicks_values = [gsc_monthly[m]["clicks"] for m in months]
impr_values = [gsc_monthly[m]["impressions"] for m in months]

plt.figure(figsize=(10, 5))
plt.plot(months, clicks_values, marker="o", color=ACCENT_COLOR)
plt.title("Trend 12 miesięcy – Kliknięcia")
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("v7_trend_clicks.png")
plt.close()

# ===== WYKRES 2 – Trend 12M Wyświetlenia =====
plt.figure(figsize=(10, 5))
plt.plot(months, impr_values, marker="o", color=ACCENT_COLOR)
plt.title("Trend 12 miesięcy – Wyświetlenia")
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("v7_trend_impressions.png")
plt.close()

# ===== WYKRES 12M – CTR + ŚREDNIA POZYCJA =====

months = sorted(gsc_monthly.keys())

ctr_values = []
pos_values = []

for m in months:
    clicks = gsc_monthly[m]["clicks"]
    impressions = gsc_monthly[m]["impressions"]
    ctr = (clicks / impressions) if impressions > 0 else 0
    ctr_values.append(round(ctr * 100, 2))
    pos_values.append(gsc_monthly[m].get("position", 0))

plt.figure(figsize=(10, 5))

plt.plot(months, ctr_values, marker="o", label="CTR (%)")
plt.plot(months, pos_values, marker="o", label="Średnia pozycja")

plt.title("Trend 12 miesięcy – CTR i Średnia pozycja")
plt.xticks(rotation=45)
plt.legend()
plt.tight_layout()

plt.savefig("v7_trend_ctr_position.png")
plt.close()

# ===== WYKRES 3 – Tydzień vs Poprzedni =====
labels = ["GA", "GSC Kliknięcia", "GSC Wyświetlenia"]
current_values = [ga_current, gsc_current_clicks, gsc_current_impr]
previous_values = [ga_previous, gsc_previous_clicks, gsc_previous_impr]

x = range(len(labels))

plt.figure(figsize=(10, 5))
plt.bar([i - 0.2 for i in x], previous_values, width=0.4, label="Poprzedni tydzień")
plt.bar([i + 0.2 for i in x], current_values, width=0.4, label="Aktualny tydzień", color=ACCENT_COLOR)

plt.xticks(x, labels)
plt.title("Porównanie tydzień do tygodnia")
plt.legend()
plt.tight_layout()
plt.savefig("v7_week_compare.png")
plt.close()

print("Wykresy wygenerowane.")

# ===== PDF =====

doc = SimpleDocTemplate("Raport_V7_BSKOMFORT.pdf", pagesize=A4)
styles = getSampleStyleSheet()

pdfmetrics.registerFont(TTFont('Arial', 'Arial.ttf'))

styles["Normal"].fontName = "Arial"
styles["Heading1"].fontName = "Arial"
styles["Heading2"].fontName = "Arial"
styles["Heading3"].fontName = "Arial"

elements = []

# ===== HEADER =====

logo = Image("logo.jpg", width=3*cm, height=3*cm, kind='proportional')

title = Paragraph(
    "Raport tygodniowy – BSKOMFORT",
    styles["Heading1"]
)

date_range_str = f"{start_current.strftime('%d.%m.%Y')} – {end_current.strftime('%d.%m.%Y')}"

date_line = Paragraph(
    date_range_str,
    styles["Heading1"]
)

header_table = Table(
    [[logo, [title, Spacer(1,6), date_line]]],
    colWidths=[5*cm, 11*cm]
)

header_table.setStyle([
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
])

elements.append(header_table)
elements.append(Spacer(1, 20))

# ===== PODSUMOWANIE POD LOGIEM =====

elements.append(Paragraph(
    f"<b>Kliknięcia (ostatnie 30 dni):</b> {gsc_30_clicks} {arrow(clicks_30_change)} ({clicks_30_change}%)",
    styles["Normal"]
))
elements.append(Spacer(1, 6))

elements.append(Paragraph(
    f"<b>Wyświetlenia (ostatnie 30 dni):</b> {gsc_30_impr} {arrow(impr_30_change)} ({impr_30_change}%)",
    styles["Normal"]
))
elements.append(Spacer(1, 6))

elements.append(Paragraph(
    f"<b>CTR:</b> {round(gsc_30_ctr*100,2)}% {arrow(percent_change(gsc_30_ctr, gsc_prev_30_ctr))} ({percent_change(gsc_30_ctr, gsc_prev_30_ctr)}%)",
    styles["Normal"]
))
elements.append(Spacer(1, 6))

elements.append(Paragraph(
    f"<b>Średnia pozycja:</b> {round(gsc_30_pos,2)} {arrow(pos_change)} ({pos_change}%)",
    styles["Normal"]
))
elements.append(Spacer(1, 40))

# ===== DASHBOARD 30 DNI =====


elements.append(Image("v7_trend_clicks.png", width=16*cm, height=8*cm))
elements.append(Spacer(1, 50))

elements.append(Spacer(1, 10))
elements.append(Paragraph(f"<i>{clicks_analysis_text}</i>", styles["Normal"]))
elements.append(Spacer(1, 20))

elements.append(Spacer(1, 20))

elements.append(Image("v7_trend_impressions.png", width=16*cm, height=8*cm))
elements.append(Spacer(1, 12))

elements.append(Paragraph(f"<i>{impressions_analysis_text}</i>", styles["Normal"]))
elements.append(Spacer(1, 25))

elements.append(Image("v7_trend_ctr_position.png", width=16*cm, height=8*cm))
elements.append(Spacer(1, 15))
elements.append(Paragraph(f"<i>{ctr_position_analysis_text}</i>", styles["Normal"]))
elements.append(Spacer(1, 25))
elements.append(Spacer(1, 20))

elements.append(Spacer(1, 25))
elements.append(Paragraph("<b>Co dzieje się z frazami</b>", styles["Heading2"]))
elements.append(Spacer(1, 15))

for line in queries_analysis_text.split("\n"):
    elements.append(Paragraph(line, styles["Normal"]))
    elements.append(Spacer(1, 8))

elements.append(Spacer(1, 30))
elements.append(Paragraph("<b>Prognoza SEO – scenariusz dynamiczny</b>", styles["Heading2"]))
elements.append(Spacer(1, 15))

for line in forecast_text.split("\n"):
    elements.append(Paragraph(line, styles["Normal"]))
    elements.append(Spacer(1, 8))

# ===== SCENARIUSZE ROZWOJU SEO =====

elements.append(Spacer(1, 35))
elements.append(Paragraph("<b>Scenariusze rozwoju SEO</b>", styles["Heading2"]))
elements.append(Spacer(1, 20))

for line in scenario_text.strip().split("\n\n"):
    elements.append(Paragraph(line.strip(), styles["Normal"]))
    elements.append(Spacer(1, 18))

doc.build(elements)

print("PDF wygenerowany.")

# ===== WYSYŁKA MAILA =====

EMAIL_ADDRESS = "nidzwieckit@gmail.com"
EMAIL_PASSWORD = "xadrclwvuazjhjln"
EMAIL_TO = [
    "nidzwieckit@gmail.com",
    "bsurzycki@bskomfort.pl"
]

msg = EmailMessage()
msg["Subject"] = "Raport SEO"
msg["From"] = EMAIL_ADDRESS
msg["To"] = EMAIL_TO
msg.set_content("W załączniku aktualny raport SEO.")

with open("Raport_V7_BSKOMFORT.pdf", "rb") as f:
    file_data = f.read()
    file_name = "Raport_V7_BSKOMFORT.pdf"

msg.add_attachment(file_data, maintype="application", subtype="pdf", filename=file_name)

context = ssl.create_default_context()

with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
    server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    server.send_message(msg)

print("Mail wysłany.")

import os
