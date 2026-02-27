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
end_current = today - datetime.timedelta(days=1)
start_current = end_current - datetime.timedelta(days=6)

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
            data[row["keys"][0]] = {
                "clicks": row["clicks"],
                "impressions": row["impressions"]
            }

    return data

# ===== OBLICZENIA =====

# GA operacyjnie
ga_current = get_ga_sum(start_current, end_current)
ga_previous = get_ga_sum(start_previous, end_previous)
ga_90_total = get_ga_sum(start_90, end_current)
ga_90_avg_week = round(ga_90_total / 13, 2)

# GSC operacyjnie

gsc_current_clicks, gsc_current_impr, gsc_current_ctr, gsc_current_pos = get_gsc_sum(start_current, end_current)
gsc_previous_clicks, gsc_previous_impr, gsc_previous_ctr, gsc_previous_pos = get_gsc_sum(start_previous, end_previous)

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

def percent_change(current, previous):
    if previous == 0:
        return 0
    return round(((current - previous) / previous) * 100, 1)

clicks_30_change = percent_change(gsc_30_clicks, gsc_prev_30_clicks)
impr_30_change = percent_change(gsc_30_impr, gsc_prev_30_impr)
pos_change = percent_change(gsc_prev_30_pos, gsc_30_pos)

# GSC 12M trend
gsc_monthly = get_gsc_monthly(start_12m, end_current)

# ===== PROGNOZA SEO (dynamiczna – ostatnie 3 mies.) =====

# sortujemy miesiące rosnąco
months_sorted = sorted(gsc_monthly.keys())

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

# Zapytania
queries_current = get_gsc_queries(start_current, end_current)
queries_previous = get_gsc_queries(start_previous, end_previous)

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

print("\n=== PODSUMOWANIE V7 ===")
print("GA 7 dni:", ga_current)
print("GA poprzedni:", ga_previous)
print("GA średnia 90 dni:", ga_90_avg_week)

print("GSC 7 dni:", gsc_current_clicks, gsc_current_impr)
print("GSC poprzedni:", gsc_previous_clicks, gsc_previous_impr)

print("Nowe zapytania:", new_queries[:5])
print("Największe wzrosty:", growing_queries)
print("Największe spadki:", declining_queries)

print("Trend 12M (GSC):", gsc_monthly)

# ===== ANALIZA AI =====

ai_client = OpenAI(api_key=OPENAI_API_KEY)

dashboard_data = {
    "ga_current": ga_current,
    "ga_previous": ga_previous,
    "ga_avg_90": ga_90_avg_week,
    "gsc_current_clicks": gsc_current_clicks,
    "gsc_previous_clicks": gsc_previous_clicks,
    "gsc_current_impressions": gsc_current_impr,
    "gsc_previous_impressions": gsc_previous_impr,
    "new_queries": new_queries[:5],
    "growing_queries": growing_queries,
    "declining_queries": declining_queries,
    "trend_12m": gsc_monthly,
    "forecast_impr_3m": forecast_impr_3m,
    "forecast_clicks_3m": forecast_clicks_3m,
    "forecast_clicks_top10": forecast_clicks_top10,
    "forecast_leads_3m": forecast_leads_3m,
    "avg_monthly_growth": round(avg_monthly_growth * 100, 1),
}

# ---- GŁÓWNA ANALIZA ----

main_prompt = f"""
Jesteś analitykiem SEO dla właścicieli firmy.

Ton:
- rzeczowy
- luźny
- bez marketingowego bełkotu
- dla dwóch właścicieli sprawdzających czy SEO zaczyna działać

Zrób:
1. Krótką diagnozę sytuacji
2. Co się dzieje w krótkim terminie
3. Czy trend 12M jest zdrowy
4. Co mówią zapytania
5. 5 konkretnych działań na najbliższy tydzień

Dane:
{dashboard_data}
"""

main_response = ai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": main_prompt}],
    temperature=0.6
)

analysis_text = main_response.choices[0].message.content.strip()

# ===== PROGNOZA AI =====

forecast_prompt = f"""
Jesteś analitykiem SEO tworzącym prognozę.

Ton:
- rzeczowy
- spokojny
- bez obiecywania wyników
- bez marketingowego języka

Na podstawie danych:

Średnie miesięczne tempo wzrostu wyświetleń: {round(avg_monthly_growth*100,1)}%
Prognozowane wyświetlenia za 3 miesiące: {forecast_impr_3m}
Prognozowane kliknięcia za 3 miesiące (przy obecnym CTR): {forecast_clicks_3m}
Prognozowane kliknięcia przy scenariuszu TOP10 (CTR 3%): {forecast_clicks_top10}
Szacowana liczba potencjalnych zapytań (2% konwersji): {forecast_leads_3m}

Zrób:
1. Krótką ocenę momentum.
2. Co się stanie przy utrzymaniu trendu.
3. Co zmienia wejście do TOP10.
4. Ostrożną ocenę potencjału zapytań.

Max 8–10 zdań.
"""

forecast_response = ai_client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[{"role": "user", "content": forecast_prompt}],
    temperature=0.6
)

forecast_text = forecast_response.choices[0].message.content

# ---- ANALIZA POD WYKRESEM KLIKNIĘĆ ----

clicks_prompt = f"""
Jesteś analitykiem SEO dla właścicieli firmy.

Ton:
- rzeczowy
- luźny
- bez marketingowego bełkotu

Skup się WYŁĄCZNIE na trendzie kliknięć z 12 miesięcy:
{gsc_monthly}

Napisz 2-3 zdania:
- czy trend jest rosnący, spadający czy niestabilny
- czy ostatnie miesiące są lepsze czy gorsze
- czy wygląda to zdrowo
"""

clicks_response = ai_client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": clicks_prompt}],
    temperature=0.4
)

clicks_analysis_text = clicks_response.choices[0].message.content.strip()

# ---- ANALIZA POD WYKRESEM WYŚWIETLEŃ ----

impressions_prompt = f"""
Jesteś analitykiem SEO dla właścicieli firmy.

Ton:
- rzeczowy
- luźny
- bez marketingowego bełkotu

Skup się WYŁĄCZNIE na trendzie wyświetleń z 12 miesięcy:
{gsc_monthly}

Napisz 2-3 zdania:
- czy trend rośnie, spada czy jest stabilny
- czy ostatnie miesiące pokazują poprawę
- czy wygląda to zdrowo
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
Krótko oceń wykres 12M dla CTR i średniej pozycji.

Dane:
- Aktualny CTR: {ctr_last}%
- Zmiana CTR: {ctr_trend}%
- Aktualna średnia pozycja: {pos_last}
- Zmiana pozycji: {pos_trend}%

Ton:
- rzeczowy
- bez marketingowego bełkotu
- krótko (2–3 zdania)
- luźny
"""

ctr_position_response = ai_client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[{"role": "user", "content": ctr_position_prompt}],
    temperature=0.4
)

ctr_position_analysis_text = ctr_position_response.choices[0].message.content

# ===== SCENARIUSZE GENEROWANE PRZEZ AI =====

scenario_prompt = f"""
Na podstawie poniższych danych opisz w prosty sposób, co może wydarzyć się z naszą widocznością w Google.

Dane:
- Średni wzrost miesięczny: {scenario_growth}%
- Prognoza 3 miesiące (utrzymanie trendu): {forecast_impr_3m} wyświetleń i {forecast_clicks_3m} kliknięć
- Scenariusz TOP10 (CTR 4%): {forecast_clicks_top10_real} kliknięć miesięcznie
- Scenariusz ostrożny: {forecast_impr_slow} wyświetleń i {forecast_clicks_slow} kliknięć
- Indeks kondycji SEO: {seo_index}/10
- Ocena systemowa: {seo_status}

Napisz to:
- bardzo prostym językiem
- tak, jakbyś tłumaczył to komuś, kto nie zna się na SEO
- bez marketingowego bełkotu
- bez branżowych skrótów
- bez angielskich słów
- bez punktów i list

Ma to brzmieć jak normalne, spokojne wyjaśnienie sytuacji między wspólnikami.
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
