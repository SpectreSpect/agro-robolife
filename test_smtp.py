import smtplib, ssl, certifi, socket, traceback

SMTP_SERVER = "smtp.mail.ru"
USER = "spectrespect@inbox.ru"
PWD = "I3D7L7qkhBOD84yfle5v"

def try_ssl(port, timeout=10):
    ctx = ssl.create_default_context(cafile=certifi.where())
    try:
        print(f"\nTrying SMTP_SSL on port {port}...")
        server = smtplib.SMTP_SSL(SMTP_SERVER, port, context=ctx, timeout=timeout)
        server.set_debuglevel(1)
        server.login(USER, PWD)
        print("OK: Logged in via SMTP_SSL", port)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed SMTP_SSL {port}: {type(e)} {e}")
        traceback.print_exc()
        return False

def try_starttls(port=587, timeout=10):
    ctx = ssl.create_default_context(cafile=certifi.where())
    try:
        print(f"\nTrying STARTTLS on port {port}...")
        server = smtplib.SMTP(SMTP_SERVER, port, timeout=timeout)
        server.set_debuglevel(1)
        server.ehlo()
        server.starttls(context=ctx)
        server.ehlo()
        server.login(USER, PWD)
        print("OK: Logged in via STARTTLS", port)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed STARTTLS {port}: {type(e)} {e}")
        traceback.print_exc()
        return False

# Run tests
print("DNS:", socket.getaddrinfo(SMTP_SERVER, None))
try_ssl(465)
try_starttls(587)
