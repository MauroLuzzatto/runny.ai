**Effective date:** March 2026

---

Runny.AI analyses your Garmin activity data using AI. No data is stored at any point. All analysis is session-only — when you close the app, nothing is retained.

---

## 1. What Data We Access

**User profile (optional)**

If you choose to load your profile: max/resting heart rate, body weight, HR zones, VO2 max, training load, training status, training readiness, lactate threshold HR, and race time predictions. Loading your profile is not required to use the app.

**Activity data (optional)**

If you choose to load your activities: activity type, distance, duration, speed, elevation, heart rate and HR zones, calories, training effect, running power, running dynamics, swimming metrics, fastest splits, intensity minutes, body battery delta, lap count, and personal record flag.

Before any data is transmitted, the following are stripped: GPS coordinates, location names, activity names, activity and device IDs, and timestamps.

---

## 2. How Data Is Processed

Data is sent via **OpenRouter** to **Anthropic's AI models** to generate your analysis, then discarded. Neither OpenRouter nor Anthropic use API data for model training. All transmission is encrypted over HTTPS.

- OpenRouter privacy: [openrouter.ai/privacy](https://openrouter.ai/privacy)
- Anthropic privacy: [anthropic.com/privacy](https://www.anthropic.com/privacy)

Profile data (weight, heart rate metrics) constitutes health data under GDPR Article 9 and is handled with the same zero-storage approach as all other data.

---

## 3. Third Parties

| Service | Role | Retains data? |
|---|---|---|
| Garmin Connect API | Source of activity and profile data | No |
| OpenRouter | API routing to Anthropic | No |
| Anthropic | AI analysis | No |

---

## 4. Your Rights

Runny.AI stores nothing, so there is no data to delete or export. To revoke access, go to **Garmin Connect → Settings → Connected Apps** and remove Runny.AI.

---

## 5. Contact

**Mauro Luzzatto** — [mauroluzzatto@hotmail.com](mailto:mauroluzzatto@hotmail.com)
