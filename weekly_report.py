import os
import datetime
import smtplib
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
from config import EMAIL_NADAWCA, EMAIL_HASLO_APLIKACJI, EMAIL_ODBIORCY

# ===== KONFIG =====
PROPERTY_ID = "520666308"
KEY_FILE = "klucz.json"
GSC_SITE = "https://www.bskomfort.pl/"
FONT_PATH = "fonts/Arial.ttf"

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
            queries.append((row["keys"][0], row["clicks"]))
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

# ===== ANALIZA =====
analiza = ""

if ga_change > 10:
    analiza += "Widoczny wzrost ruchu użytkowników. "
elif ga_change < -10:
    analiza += "Spadek ruchu użytkowników – warto sprawdzić źródła wejść. "
else:
    analiza += "Ruch użytkowników stabilny. "

if gsc_clicks_change > 10:
    analiza += "Kliknięcia z Google rosną. "
elif gsc_clicks_change < -10:
    analiza += "Spadek kliknięć z Google – możliwy spadek widoczności. "
else:
    analiza += "Kliknięcia utrzymują się na podobnym poziomie. "

if gsc_ctr_current < 2:
    analiza += "CTR niski – warto poprawić tytuły i opisy stron. "

# ===== PDF =====
pdfmetrics.registerFont(TTFont('ArialPL', FONT_PATH))
doc = SimpleDocTemplate("Raport_Tygodniowy_BSKOMFORT.pdf", pagesize=A4)
elements = []
styles = getSampleStyleSheet()

normal = ParagraphStyle('Normal', parent=styles['Normal'], fontName='ArialPL', fontSize=11, leading=14)
title = ParagraphStyle('Title', parent=styles['Heading1'], fontName='ArialPL', fontSize=18)

# STRONA 1
elements.append(Paragraph("Raport tygodniowy – BSKOMFORT", title))
elements.append(Spacer(1, 12))
elements.append(Paragraph(f"Zakres: {start_current} – {end_current}", normal))
elements.append(Spacer(1, 20))
elements.append(Paragraph("Podsumowanie zarządcze:", normal))
elements.append(Spacer(1, 10))
elements.append(Paragraph(analiza, normal))
elements.append(PageBreak())

# STRONA 2 – GA
elements.append(Paragraph("Google Analytics", title))
elements.append(Spacer(1, 10))
elements.append(Paragraph(f"Użytkownicy: {ga_current} ({ga_change}%)", normal))
elements.append(Spacer(1, 10))
elements.append(Image("ga.png", width=14*cm, height=6*cm))
elements.append(PageBreak())

# STRONA 3 – GSC
elements.append(Paragraph("Google Search Console", title))
elements.append(Spacer(1, 10))
elements.append(Paragraph(f"Kliknięcia: {gsc_clicks_current} ({gsc_clicks_change}%)", normal))
elements.append(Paragraph(f"Wyświetlenia: {gsc_impr_current} ({gsc_impr_change}%)", normal))
elements.append(Paragraph(f"Średni CTR: {gsc_ctr_current}%", normal))
elements.append(Paragraph(f"Średnia pozycja: {gsc_pos_current}", normal))
elements.append(Spacer(1, 10))
elements.append(Image("gsc_clicks.png", width=14*cm, height=5*cm))
elements.append(Spacer(1, 10))
elements.append(Image("gsc_impr.png", width=14*cm, height=5*cm))
elements.append(PageBreak())

# STRONA 4 – TOP ZAPYTANIA
elements.append(Paragraph("Top 5 zapytań tygodnia", title))
elements.append(Spacer(1, 15))
for query, clicks in top_queries:
    elements.append(Paragraph(f"{query} – {clicks} kliknięć", normal))
elements.append(PageBreak())

# STRONA 5 – WNIOSKI
elements.append(Paragraph("Wnioski i rekomendacje", title))
elements.append(Spacer(1, 10))
elements.append(Paragraph("1. Monitorować CTR i poprawić tytuły podstron.", normal))
elements.append(Paragraph("2. Wzmocnić treści dla zapytań z potencjałem.", normal))
elements.append(Paragraph("3. Kontynuować działania zwiększające widoczność.", normal))

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

print("Raport 3.0 wygenerowany i wysłany.")

