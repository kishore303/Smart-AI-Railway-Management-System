# SIH26027 Frontend — Module 15

Backend integration ready at `GET /api/dashboard/overview` and `GET /api/dashboard/health`.

Professional government/railway UI: navy header (#0f265c), light background (#f8fafc), formal typography, compact tables, status badges (green SAFE/APPROVED, amber PENDING, red UNSAFE/REJECTED).

This is a backend-first integration; full Next.js + Tailwind + shadcn/ui + MapLibre + ECharts implementation can consume the overview API.

No cyberpunk/neon/glassmorphism — enterprise operational portal only.

To run frontend (when scaffolded):
```
npm install
npm run dev
```
Backend: `uvicorn app.main:app --reload --port 8000`
