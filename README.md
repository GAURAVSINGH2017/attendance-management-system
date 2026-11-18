# AttendEase — Attendance Management System

Mini project built with HTML, CSS, JavaScript, Python Flask and MySQL.

## Features

- Admin login with hashed passwords
- Student directory with search, edit and archive
- Class-wise subject setup with optional teacher name
- Attendance by date, class and subject (Present, Absent, Late)
- Attendance reports by date range, class, subject and student
- Below-75% attendance alerts and filtered CSV download
- Optional guardian email alerts when a student's status changes to Absent or Late
- Separate teacher and student sign-ins, with students limited to their own attendance
- Email notification delivery log and configuration status
- JSON API used by the browser to load subjects dynamically
- Responsive mobile and tablet layout
- Deployment configuration for free Render hosting with a MySQL-compatible TiDB database

## Run locally on Windows

1. Start the MySQL service and create/select the `attendance_db` database.
2. Copy `.env.example` to `.env` and set `DB_PASSWORD` to your MySQL root password.
3. Install packages in the project virtual environment:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

4. Upgrade the database once for subject-wise attendance:

   ```powershell
   .\.venv\Scripts\python.exe setup_db.py
   ```

5. Create or reset an admin account:

   ```powershell
   .\.venv\Scripts\python.exe create_admin.py
   ```

6. Start the site and open `http://127.0.0.1:5000`:

   ```powershell
   .\.venv\Scripts\python.exe app.py
   ```

## JSON API

API routes require an authenticated browser session.

- `GET /api/classes` — active classes
- `GET /api/classes/<class_name>/subjects` — active subjects and teacher names for one class
- `GET /api/students?class_name=8` — active students, optionally filtered by class
- `GET /api/attendance/summary?start=2026-11-01&end=2026-11-30&class_name=8&subject_id=1` — attendance totals as JSON

The attendance page uses JavaScript `fetch()` to get the selected class's subjects from the API.

For free public hosting, follow [DEPLOYMENT.md](DEPLOYMENT.md). The free web service may sleep while idle, but your own computer does not need to stay on.

Email alerts are optional. Add guardian email addresses to student profiles and configure either the Google Apps Script relay (`GOOGLE_APPS_SCRIPT_URL`, `GOOGLE_APPS_SCRIPT_TOKEN`) or Resend (`RESEND_API_KEY`, `RESEND_FROM`) as private hosting environment variables. The Gmail relay is subject to Google's daily quota; Resend requires a verified sending domain for guardian addresses. The app does not send SMS alerts.

The existing admin account is treated as a teacher account. Add a student's date of birth and the app automatically creates a username from the student's name plus DOB in `DDMMYY` format; the initial password is the normalized student name plus `@123`. The student must choose a new password on first login. Teachers can reset it from the student's edit page. Students sign in separately and can view only their own attendance and report; they cannot edit attendance or other records. There is no public student registration.
