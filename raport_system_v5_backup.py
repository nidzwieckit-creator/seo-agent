import os
import datetime
import smtplib
import json
import matplotlib.pyplot as plt
from email.message import EmailMessage
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.platypus import Table, TableStyle
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import Frame, PageTemplate
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Metric, Dimension
from google.oauth2 import service_account
from googleapiclient.discovery import build
from openai import OpenAI
from config import EMAIL_NADAWCA, EMAIL_HASLO_APLIKACJI, EMAIL_ODBIORCY, OPENAI_API_KEY


# ===== KONFIG =====
PROPERTY_ID = "520666308"
KEY_FILE = "klucz.json"
GSC_SITE = "https://www.bskomfort.pl/"
FONT_PATH = "fonts/Arial.ttf"
LOGO_PATH = "logo.jpg"

ACCENT_COLOR = colors.HexColor("#1f3c88")  # elegancki granat


# ===== DATY =====
today = datetime.date.today()
end_current = today - datetime.timedelta(days=1)
start_current = end_current - datetime.timedelta(days=6)

end_previous = start_current - datetime.timedelta(days=1)
start_previous = end_previous - datetime.timedelta(days=6)


def percent_change(new, old):
    if old == 0:
        return 0
    return round(((new - old) / old) * 100, 2)


# ===== AUTORYZACJA =====
credentials = service_account.Credentials.from_service_account_file(KEY_FILE)
ga_client = BetaAnalyticsDataClient(credentials=credentials)
gsc_service = build("searchconsole", "v1", credentials=credentials)
ai_client = OpenAI(api_key=OPENAI_API_KEY)


# ===== STYL PDF 5.0 =====
pdfmetrics.registerFont(TTFont('ArialPL', FONT_PATH))

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    'TitleStyle',
    parent=styles['Heading1'],
    fontName='ArialPL',
    fontSize=20,
    textColor=ACCENT_COLOR,
    spaceAfter=14
)

section_style = ParagraphStyle(
    'SectionStyle',
    parent=styles['Heading2'],
    fontName='ArialPL',
    fontSize=16,
    textColor=ACCENT_COLOR,
    spaceAfter=10
)

normal_style = ParagraphStyle(
    'NormalStyle',
    parent=styles['Normal'],
    fontName='ArialPL',
    fontSize=12,
    leading=16
)

small_style = ParagraphStyle(
    'SmallStyle',
    parent=styles['Normal'],
    fontName='ArialPL',
    fontSize=9,
    textColor=colors.grey
)


# ===== NAGŁÓWEK I STOPKA NA KAŻDEJ STRONIE =====
def header_footer(canvas, doc):
    canvas.saveState()

    # Logo w prawym górnym rogu
    if os.path.exists(LOGO_PATH):
        canvas.drawImage(LOGO_PATH, A4[0] - 3.5 * cm, A4[1] - 2.5 * cm, width=2.5 * cm, height=1.2 * cm, preserveAspectRatio=True)

    # Linia pod nagłówkiem
    canvas.setStrokeColor(ACCENT_COLOR)
    canvas.setLineWidth(1)
    canvas.line(2 * cm, A4[1] - 2.8 * cm, A4[0] - 2 * cm, A4[1] - 2.8 * cm)

    # Stopka
    canvas.setFont("ArialPL", 9)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2 * cm, 1.2 * cm, f"Raport tygodniowy – BSKOMFORT | {start_current} – {end_current}")

    canvas.restoreState()
# ===== GA – DANE =====
def get_ga_data(start, end):
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        metrics=[Metric(name="activeUsers")],
        dimensions=[Dimension(name="date")],
        date_ranges=[DateRange(start_date=str(start), end_date=str(end))]
    )
    response = ga_client.run_report(request)
    values = [int(row.metric_values[0].value) for row in response.rows]
    return values, sum(values)


ga_current_list, ga_current = get_ga_data(start_current, end_current)
ga_previous_list, ga_previous = get_ga_data(start_previous, end_previous)
ga_change = percent_change(ga_current, ga_previous)


# ===== GSC – DANE =====
def get_gsc_data(start, end):
    request = {
        "startDate": str(start),
        "endDate": str(end),
        "dimensions": ["date"]
    }
    response = gsc_service.searchanalytics().query(siteUrl=GSC_SITE, body=request).execute()

    clicks = []
    impressions = []
    ctr_total = 0
    position_total = 0

    if "rows" in response:
        for row in response["rows"]:
            clicks.append(row["clicks"])
            impressions.append(row["impressions"])
            ctr_total += row["ctr"]
            position_total += row["position"]

    avg_ctr = round((ctr_total / len(clicks)) * 100, 2) if clicks else 0
    avg_position = round(position_total / len(clicks), 2) if clicks else 0

    return clicks, impressions, sum(clicks), sum(impressions), avg_ctr, avg_position


gsc_clicks_current_list, gsc_impr_current_list, gsc_clicks_current, gsc_impr_current, gsc_ctr_current, gsc_pos_current = get_gsc_data(start_current, end_current)
_, _, gsc_clicks_previous, gsc_impr_previous, _, _ = get_gsc_data(start_previous, end_previous)

gsc_clicks_change = percent_change(gsc_clicks_current, gsc_clicks_previous)
gsc_impr_change = percent_change(gsc_impr_current, gsc_impr_previous)


# ===== TOP 5 ZAPYTAŃ =====
def get_top_queries(start, end):
    request = {
        "startDate": str(start),
        "endDate": str(end),
        "dimensions": ["query"],
        "rowLimit": 5
    }
    response = gsc_service.searchanalytics().query(siteUrl=GSC_SITE, body=request).execute()

    queries = []
    if "rows" in response:
        for row in response["rows"]:
            queries.append({
                "query": row["keys"][0],
                "clicks": row["clicks"],
                "impressions": row["impressions"],
                "ctr": round(row["ctr"] * 100, 2),
                "position": round(row["position"], 2)
            })

    return queries


top_queries = get_top_queries(start_current, end_current)


# ===== WYKRES 1 – PORÓWNANIE TYDZIEŃ DO TYDZIEŃ (GA) =====
plt.figure(figsize=(8, 4))
plt.bar(["Poprzedni tydzień", "Aktualny tydzień"], [ga_previous, ga_current])
plt.title("Użytkownicy – porównanie tydzień do tygodnia")
plt.tight_layout()
plt.savefig("wykres_ga_porownanie.png")
plt.close()


# ===== WYKRES 2 – TREND 4-TYGODNIOWY (GA) =====
trend_values = [ga_previous, ga_current]
plt.figure(figsize=(8, 4))
plt.plot(trend_values, marker="o")
plt.title("Trend użytkowników (2 ostatnie tygodnie)")
plt.tight_layout()
plt.savefig("wykres_ga_trend.png")
plt.close()


# ===== WYKRES 3 – KLIKNIĘCIA VS WYŚWIETLENIA =====
plt.figure(figsize=(8, 4))
plt.bar(["Kliknięcia", "Wyświetlenia"], [gsc_clicks_current, gsc_impr_current])
plt.title("Kliknięcia vs Wyświetlenia (aktualny tydzień)")
plt.tight_layout()
plt.savefig("wykres_gsc_relacja.png")
plt.close()


# ===== WYKRES 4 – CTR I POZYCJA =====
plt.figure(figsize=(8, 4))
plt.bar(["CTR (%)", "Śr. pozycja"], [gsc_ctr_current, gsc_pos_current])
plt.title("CTR vs Średnia pozycja")
plt.tight_layout()
plt.savefig("wykres_gsc_ctr_pozycja.png")
plt.close()


# ===== WYKRES 5 – TOP 5 (KLIKNIĘCIA) =====
if top_queries:
    labels = [q["query"][:20] for q in top_queries]
    clicks_vals = [q["clicks"] for q in top_queries]

    plt.figure(figsize=(8, 4))
    plt.barh(labels, clicks_vals)
    plt.title("Top 5 zapytań – kliknięcia")
    plt.tight_layout()
    plt.savefig("wykres_top5.png")
    plt.close()
# ===== DASHBOARD DANE =====
dashboard_data = {
    "ga_current": ga_current,
    "ga_previous": ga_previous,
    "ga_change_percent": ga_change,
    "gsc_clicks_current": gsc_clicks_current,
    "gsc_clicks_previous": gsc_clicks_previous,
    "gsc_clicks_change_percent": gsc_clicks_change,
    "gsc_impressions_current": gsc_impr_current,
    "gsc_impressions_previous": gsc_impr_previous,
    "gsc_impressions_change_percent": gsc_impr_change,
    "gsc_ctr_current": gsc_ctr_current,
    "gsc_position_current": gsc_pos_current,
    "top_queries": top_queries
}


# ===== PROMPT 5.0 =====
prompt = f"""
Stwórz raport tygodniowy dla właścicieli firmy BSKOMFORT.

Raport ma mieć charakter:
- profesjonalny
- decyzyjny
- konkretny
- z lekkim charakterem (szwagier vibe)
- bez lania wody
- bez angielskich wstawek
- 100% po polsku

Struktura raportu:

1. DASHBOARD (krótko, mocno)
   - jednozdaniowe podsumowanie sytuacji
   - czy trend jest dobry czy nie
   - co jest największym plusem
   - co jest największym zagrożeniem

2. ANALIZA GA4
   - porównanie tydzień do tygodnia
   - interpretacja biznesowa
   - czy wzrost/spadek ma znaczenie
   - czy to stabilny trend czy przypadek

3. ANALIZA GOOGLE SEARCH CONSOLE
   - kliknięcia vs wyświetlenia
   - CTR
   - średnia pozycja
   - czy problem to widoczność czy brak klikalności
   - bez owijania

4. TOP 5 ZAPYTAŃ
   - które ma potencjał
   - które jest do poprawy
   - które wymaga osobnej podstrony

5. PLAN NA TEN TYDZIEŃ
   - konkretne działania
   - maksymalnie 5 punktów
   - priorytety
   - ton decyzyjny

Długość: pełne 4–5 stron tekstu.
Styl: dynamiczny, rzeczowy, lekko bezpośredni, ale nie przesadzony.

Dane:
{json.dumps(dashboard_data, ensure_ascii=False, indent=2)}
"""


response = ai_client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.6
)

analysis_text = response.choices[0].message.content
# ===== GENEROWANIE PDF 5.0 =====
doc = SimpleDocTemplate(
    "Raport_Tygodniowy_BSKOMFORT.pdf",
    pagesize=A4,
    rightMargin=2*cm,
    leftMargin=2*cm,
    topMargin=3.5*cm,
    bottomMargin=2*cm
)

elements = []

# ===== STRONA 1 – DASHBOARD =====
elements.append(Paragraph("Raport tygodniowy – BSKOMFORT", title_style))
elements.append(Spacer(1, 20))

dashboard_table_data = [
    ["Wskaźnik", "Poprzedni tydzień", "Aktualny tydzień", "Zmiana %"],
    ["Użytkownicy", ga_previous, ga_current, f"{ga_change}%"],
    ["Kliknięcia", gsc_clicks_previous, gsc_clicks_current, f"{gsc_clicks_change}%"],
    ["Wyświetlenia", gsc_impr_previous, gsc_impr_current, f"{gsc_impr_change}%"],
    ["CTR (%)", "-", gsc_ctr_current, "-"],
    ["Śr. pozycja", "-", gsc_pos_current, "-"],
]

dashboard_table = Table(dashboard_table_data, hAlign="LEFT")
dashboard_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), ACCENT_COLOR),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ('FONTNAME', (0, 0), (-1, -1), 'ArialPL'),
    ('FONTSIZE', (0, 0), (-1, -1), 11),
    ('ROWHEIGHT', (0, 0), (-1, -1), 18),
]))

elements.append(dashboard_table)
elements.append(Spacer(1, 20))
elements.append(PageBreak())


# ===== STRONA 2–4 – ANALIZA TEKSTOWA =====
for paragraph in analysis_text.split("\n"):
    elements.append(Paragraph(paragraph, normal_style))
    elements.append(Spacer(1, 8))

elements.append(PageBreak())


# ===== STRONA – WYKRESY =====
elements.append(Paragraph("Wizualizacja danych", section_style))
elements.append(Spacer(1, 15))

wykresy = [
    "wykres_ga_porownanie.png",
    "wykres_ga_trend.png",
    "wykres_gsc_relacja.png",
    "wykres_gsc_ctr_pozycja.png",
    "wykres_top5.png"
]

for wykres in wykresy:
    if os.path.exists(wykres):
        elements.append(Image(wykres, width=15*cm, height=7*cm))
        elements.append(Spacer(1, 15))

doc.build(elements, onFirstPage=header_footer, onLaterPages=header_footer)


# ===== WYSYŁKA MAILA =====
msg = EmailMessage()
msg["Subject"] = "Raport tygodniowy – BSKOMFORT 5.0"
msg["From"] = EMAIL_NADAWCA
msg["To"] = ", ".join(EMAIL_ODBIORCY)
msg.set_content("W załączniku raport tygodniowy 5.0.")

with open("Raport_Tygodniowy_BSKOMFORT.pdf", "rb") as f:
    msg.add_attachment(
        f.read(),
        maintype="application",
        subtype="pdf",
        filename="Raport_Tygodniowy_BSKOMFORT.pdf"
    )

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
    smtp.login(EMAIL_NADAWCA, EMAIL_HASLO_APLIKACJI)
    smtp.send_message(msg)

print("Raport 5.0 wygenerowany i wysłany.")

