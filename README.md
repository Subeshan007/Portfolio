# CareVoice – AI Voice Appointment Booking (Flask + MongoDB)

CareVoice is a voice-first healthcare appointment booking app with two roles: patient and doctor. It uses:

- Flask (Python) for the backend
- MongoDB for data storage
- Free, browser-native Web Speech API for speech-to-text and text-to-speech (no keys required)
- Modern, responsive UI with HTML/CSS/JS

## Features
- Patient voice assistant that collects: name, age, contact, reason, preferred date/time, preferred doctor
- Patient portal to review created appointments
- Doctor dashboard to view and update appointment statuses
- Role-based authentication (doctor, patient)
- No paid AI APIs; speech runs in the browser

## Quickstart

1. Create and fill a `.env` from `.env.example`.
2. Ensure MongoDB is accessible (local or Atlas). Default is `mongodb://localhost:27017/healthcare_voice_agent`.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the server:

```bash
python app.py
```

5. Open the app at `http://localhost:5000`.

## Docker (optional)
A simple `docker-compose.yml` is provided. Start services:

```bash
docker compose up --build
```

Visit `http://localhost:5000`.

## Notes on Voice
- The Web Speech API is supported in Chromium-based browsers. If unsupported, a text fallback is provided.
- Dates should be spoken as `YYYY-MM-DD`; times as `HH:MM` (24-hour) for reliability without third-party NLP.

## Security
- This sample uses session cookies; set a strong `FLASK_SECRET_KEY` in production.
- Add HTTPS, CSRF, and stricter validation for production usage.