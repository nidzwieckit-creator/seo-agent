import os
import datetime
import smtplib
import json
import matplotlib.pyplot as plt
from email.message import EmailMessage
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.units import cm
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

# ===== GA =====
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

# ===== GSC =====
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

# ===== TOP 5 =====
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

# ===== WYKRESY =====
plt.figure()
plt.plot(ga_current_list)
plt.title("Użytkownicy GA4")
plt.savefig("ga.png")
plt.close()

plt.figure()
plt.plot(gsc_clicks_current_list)
plt.title("Kliknięcia GSC")
plt.savefig("gsc_clicks.png")
plt.close()

plt.figure()
plt.plot(gsc_impr_current_list)
plt.title("Wyświetlenia GSC")
plt.savefig("gsc_impr.png")
plt.close()

# ===== PROMPT =====
payload = {
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

prompt = f"""
Napisz szczegółowy raport tygodniowy (minimum 4 pełne strony tekstu).

Struktura:
1. Podsumowanie zarządcze
2. Analiza GA (porównanie tydzień do tygodnia)
3. Analiza GSC
4. Interpretacja top 5 zapytań
5. Wnioski i konkretne rekomendacje

Styl:
Półformalny, merytoryczny, lekko bezpośredni (szwagier vibe), ale profesjonalny.

Dane:
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""

response = ai_client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.6
)

analysis_text = response.choices[0].message.content

# ===== PDF =====
pdfmetrics.registerFont(TTFont('ArialPL', FONT_PATH))
doc = SimpleDocTemplate("Raport_Tygodniowy_BSKOMFORT.pdf", pagesize=A4)
elements = []
styles = getSampleStyleSheet()

normal = ParagraphStyle(
    'Normal',
    parent=styles['Normal'],
    fontName='ArialPL',
    fontSize=11,
    leading=14
)

title = ParagraphStyle(
    'Title',
    parent=styles['Heading1'],
    fontName='ArialPL',
    fontSize=18
)

elements.append(Image(LOGO_PATH, width=4*cm, height=2*cm))
elements.append(Spacer(1, 10))
elements.append(Paragraph("Raport tygodniowy – BSKOMFORT", title))
elements.append(Spacer(1, 10))
elements.append(Paragraph(f"Zakres: {start_current} – {end_current}", normal))
elements.append(PageBreak())

for paragraph in analysis_text.split("\n"):
    elements.append(Paragraph(paragraph, normal))
    elements.append(Spacer(1, 6))

elements.append(PageBreak())
elements.append(Image("ga.png", width=14*cm, height=6*cm))
elements.append(Spacer(1, 10))
elements.append(Image("gsc_clicks.png", width=14*cm, height=5*cm))
elements.append(Spacer(1, 10))
elements.append(Image("gsc_impr.png", width=14*cm, height=5*cm))

doc.build(elements)

# ===== MAIL =====
msg = EmailMessage()
msg["Subject"] = "Raport tygodniowy – BSKOMFORT"
msg["From"] = EMAIL_NADAWCA
msg["To"] = ", ".join(EMAIL_ODBIORCY)
msg.set_content("W załączniku raport tygodniowy.")

with open("Raport_Tygodniowy_BSKOMFORT.pdf", "rb") as f:
    msg.add_attachment(f.read(), maintype="application", subtype="pdf", filename="Raport_Tygodniowy_BSKOMFORT.pdf")

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
    smtp.login(EMAIL_NADAWCA, EMAIL_HASLO_APLIKACJI)
    smtp.send_message(msg)

print("Raport 4.0 wygenerowany i wysłany.")

