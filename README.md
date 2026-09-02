# Disconnection Monitoring App

Real-time web app for monitoring disconnection statuses.

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Open: http://localhost:5000

## Default Credentials

| Role  | Username | Password  |
|-------|----------|-----------|
| Admin | admin    | admin123  |

Agency accounts are auto-created on Excel import.
Default agency password: `agency123`
Username = agency name lowercased, spaces replaced with underscores.

## How to Import Data
1. Login as admin
2. Use the "Upload & Import" button
3. Select your FINAL_LIST_SEP_2026.xlsx
4. All records and agency accounts are created automatically
