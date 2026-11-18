from getpass import getpass
from werkzeug.security import generate_password_hash
import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST") or os.getenv("MYSQLHOST", "localhost"),
    port=int(os.getenv("DB_PORT") or os.getenv("MYSQLPORT", "3306")),
    user=os.getenv("DB_USER") or os.getenv("MYSQLUSER", "root"),
    password=os.getenv("DB_PASSWORD") or os.getenv("MYSQLPASSWORD", ""),
    database=os.getenv("DB_NAME") or os.getenv("MYSQLDATABASE", "attendance_db"),
)
cur = conn.cursor()
username = input("Admin username: ").strip()
password = getpass("Admin password (minimum 8 characters): ")
if not username or len(password) < 8:
    raise SystemExit("Username zaroori hai aur password kam se kam 8 characters ka hona chahiye.")
cur.execute("""INSERT INTO users(username,password_hash) VALUES(%s,%s)
            ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash)""",
            (username, generate_password_hash(password)))
conn.commit()
cur.close()
conn.close()
print("Admin account ready (or updated). Login with the username and password you just entered.")
