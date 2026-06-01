import argparse
from datetime import datetime
from email.message import EmailMessage
from config_loader import cfg, Utils

def generate_eml_path(to_address, subject, body_content):
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_to = "".join(c for c in to_address if c.isalnum())[:10]
    clean_subject = "".join(c for c in subject if c.isalnum())[:15]
    filename = f"/tmp/{date_str}_{clean_to}_{clean_subject}.eml"
    
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['To'] = to_address
    msg['From'] = "sender@example.com"
    msg.set_content(body_content)

    with open(filename, 'wb') as f:
        f.write(msg.as_bytes())
    return filename

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an EML file.")
    parser.add_argument("to", help="Recipient email address")
    parser.add_argument("subject", help="Email subject")
    parser.add_argument("body", help="Email body content")
    
    args = parser.parse_args()
    path = generate_eml_path(args.to, args.subject, args.body)
    
    Utils.send_discord_notification(message, channel='draft_mail', files=[path]):
    send_discord_notification()
    print(path)