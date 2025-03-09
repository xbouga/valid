import dns.resolver
import smtplib
import re
from socket import timeout
from concurrent.futures import ThreadPoolExecutor, as_completed

def is_email_deliverable(email, timeout_seconds=10):
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return False, "Invalid email format"
    
    domain = email.split('@')[1]
    
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        mx_servers = [str(record.exchange).rstrip('.') for record in mx_records]
        mx_servers.sort()
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        return False, "Invalid domain"
    except Exception as e:
        return False, f"DNS error: {e}"
    
    for mx_server in mx_servers:
        try:
            with smtplib.SMTP(mx_server, port=25, timeout=timeout_seconds) as server:
                server.ehlo_or_helo_if_needed()
                server.mail('news@google.com')
                code, _ = server.rcpt(email)
                if code == 250:
                    return True, "Valid"
                else:
                    return False, f"Rejected (Code {code})"
        except (timeout, smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected):
            continue
        except Exception as e:
            return False, f"SMTP error: {e}"
    
    return False, "All MX failed"

def process_email(email):
    deliverable, message = is_email_deliverable(email)
    return email, deliverable, message

def process_emails(input_file, output_file, max_workers=100, batch_size=50):
    try:
        with open(input_file, 'r') as f:
            emails = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: {input_file} not found!")
        return

    # Clear output file at start
    open(output_file, 'w').close()

    valid_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]
            future_to_email = {executor.submit(process_email, email): email for email in batch}
            
            with open(output_file, 'a') as f_out:
                for future in as_completed(future_to_email):
                    email = future_to_email[future]
                    try:
                        email, deliverable, message = future.result()
                        print(f"{email} - {message}")
                        if deliverable:
                            f_out.write(email + '\n')
                            f_out.flush()
                            valid_count += 1
                    except Exception as e:
                        print(f"Error processing {email}: {e}")

    print(f"\nValidation complete. Found {valid_count} deliverable emails.")

# Run the processor
process_emails('mails.txt', 'deliverable_emails.txt')
