import datetime
from collections import defaultdict
from google.oauth2 import service_account
from googleapiclient.discovery import build
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
import matplotlib.pyplot as plt
import os

# ================= KONFIG =================

KEY_FILE = "klucz.json"
GSC_SITE = "https://www.bskkomfort.pl/"
LOGO_FILE = "logo.jpg"

today = datetime.date.today()
end_current = today - datetime.timedelta(days=1)
start_current = end_current - datetime.timedelta(days=29)

end_previous = start_current - datetime.timedelta(days=1)
start_previous = end_previous - datetime.timedelta(days=29)

start_12m = end_current - datetime.timedelta(days=365)

# ================= AUTORYZACJA =================

credentials = service_account.Credentials.from_service_account_file(KEY_FILE)
gsc_service = build("searchconsole", "v1", credentials=credentials)

# ================= FUNKCJE =================

def get_gsc_range(start, end):
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
    request = {
        "startDate": str(start),
        "endDate": str(end),
        "dimensions": ["date"]
    }

    response = gsc_service.searchanalytics().query(
        siteUrl=GSC_SITE,
        body=request
    ).execute()

    monthly = defaultdict(lambda: {"clicks": 0, "impressions": 0})

    if "rows" in response:
        for row in response["rows"]:
            date = row["keys"][0]
            month = date[:7]
            monthly[month]["clicks"] += row["clicks"]
            monthly[month]["impressions"] += row["impressions"]

    return monthly


def percent_change(current, previous):
    if previous == 0:
        return 0
    return round(((current - previous) / previous) * 100, 1)


def arrow(value):
    if value > 0:
        return "↑"
    elif value < 0:
        return "↓"
    else:
        return "→"


# ================= DANE =================

cur_clicks, cur_impr, cur_ctr, cur_pos = get_gsc_range(start_current, end_current)
prev_clicks, prev_impr, prev_ctr, prev_pos = get_gsc_range(start_previous, end_previous)

clicks_change = percent_change(cur_clicks, prev_clicks)
impr_change = percent_change(cur_impr, prev_impr)
ctr_change = percent_change(cur_ctr, prev_ctr)

pos_diff = round(prev_pos - cur_pos, 2)

monthly = get_gsc_monthly(start_12m, end_current)
months = sorted(monthly.keys())
clicks_values = [monthly[m]["clicks"] for m in months]
impr_values = [monthly[m]["impressions"] for m in months]

# ================= WYKRESY =================

ACCENT = "#1f3c88"

plt.figure(figsize=(10, 4))
plt.plot(months, clicks_values, marker="o", color=ACCENT)
plt.xticks(rotation=45)
plt.title("Trend 12 miesięcy – Kliknięcia")
plt.tight_layout()
plt.savefig("v8_trend_clicks.png")
plt.close()

plt.figure(figsize=(10, 4))
plt.plot(months, impr_values, marker="o", color=ACCENT)
plt.xticks(rotation=45)
plt.title("Trend 12 miesięcy – Wyświetlenia")
plt.tight_layout()
plt.savefig("v8_trend_impressions.png")
plt.close()

# ================= PDF =================

pdfmetrics.registerFont(TTFont("ArialUnicode", "/Library/Fonts/Arial Unicode.ttf"))

styles = getSampleStyleSheet()
normal = ParagraphStyle(
    'normal',
    parent=styles['Normal'],
    fontName="ArialUnicode",
    fontSize=11,
    leading=15
)

headline = ParagraphStyle(
    'headline',
    parent=styles['Normal'],
    fontName="ArialUnicode",
    fontSize=16,
    leading=20
)

doc = SimpleDocTemplate("Raport_V8_BSKOMFORT.pdf", pagesize=A4)
elements = []

if os.path.exists(LOGO_FILE):
    elements.append(Image(LOGO_FILE, width=4*cm, height=2*cm))
    elements.append(Spacer(1, 20))

elements.append(Paragraph("Raport SEO – ostatnie 30 dni vs poprzednie 30 dni", headline))
elements.append(Spacer(1, 15))

dashboard = f"""
Kliknięcia: {cur_clicks} {arrow(clicks_change)} ({clicks_change}%)
<br/><br/>
Wyświetlenia: {cur_impr} {arrow(impr_change)} ({impr_change}%)
<br/><br/>
CTR: {round(cur_ctr*100,2)}% {arrow(ctr_change)}
<br/><br/>
Średnia pozycja: {round(cur_pos,2)} {"↑" if pos_diff>0 else "↓"}
"""

elements.append(Paragraph(dashboard, normal))
elements.append(Spacer(1, 25))

elements.append(Image("v8_trend_clicks.png", width=16*cm, height=7*cm))
elements.append(Spacer(1, 25))

elements.append(Image("v8_trend_impressions.png", width=16*cm, height=7*cm))

doc.build(elements)

print("Raport V8 wygenerowany poprawnie.")
