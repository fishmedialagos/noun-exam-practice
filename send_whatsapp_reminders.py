"""Send opted-in students their daily WhatsApp learning reminder.

Configure this as a Render Cron Job using the same repository and environment variables
as the web service. Suggested schedule: */15 * * * * (every 15 minutes).
"""
from app import app, send_due_whatsapp_learning_reminders

if __name__ == '__main__':
    with app.app_context():
        summary = send_due_whatsapp_learning_reminders()
        print('WhatsApp learning reminder run:', summary)
