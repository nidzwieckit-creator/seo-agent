import smtplib
from email.message import EmailMessage
from config import EMAIL_NADAWCA, EMAIL_HASLO_APLIKACJI, EMAIL_ODBIORCY

msg = EmailMessage()
msg["Subject"] = "Test systemu raportowego BSKOMFORT"
msg["From"] = EMAIL_NADAWCA
msg["To"] = ", ".join(EMAIL_ODBIORCY)
msg.set_content("Jeśli czytasz tę wiadomość, system raportowy działa poprawnie.")

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
    smtp.login(EMAIL_NADAWCA, EMAIL_HASLO_APLIKACJI)
    smtp.send_message(msg)

print("Mail wysłany poprawnie.")

