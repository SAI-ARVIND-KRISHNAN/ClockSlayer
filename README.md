# ZenChrono (Backend API) — Focus with Force

A modular productivity backend platform for time tracking, habit reinforcement, AI-driven session recommendations, and real-time reminders.  
Currently built with Node.js + MongoDB. Frontend in Next.js + Three.js coming soon.

---

## Core Concept

ClockSlayer is designed to help users fight distraction and reclaim deep work by:
- Logging screen sessions and app usage
- Blocking distractions (via integrations)
- Sending smart reminders
- Using ML-based predictions to recommend focus windows

---

## Monorepo Structure

ClockSlayer-production/  
- Analytics/       → Tracks session logs, user behavior, and analytics  
- ETC/             → Embedding + Transformer Core (ML-based prediction engine)  
- Recommender/     → Personalized productivity model trainer & inference  
- Reminder/        → Notification and reminder scheduler  
- Score/           → Calculates focus scores and productivity metrics  
- server/          → Main Express API and route controller (entry point)

Each submodule includes:
- Microservice logic
- MongoDB schema definitions
- Utility functions (hashing, encoding, logging)
- Python-based ML modules with their own requirements.txt

---

## Tech Stack

- Node.js + Express
- MongoDB (Mongoose)
- JWT Auth with bcryptjs
- Python (scikit-learn for ML modules)
- Async queues for interservice communication
- Custom Express routing logic

---

## API Features

- Analytics → logs session activity, transforms data  
- Reminder → schedules & sends productivity reminders  
- ETC → generates embeddings, returns ML-based focus predictions  
- Recommender → trains models and serves personalized focus suggestions  
- Score → calculates historical and real-time productivity metrics

---

## Getting Started

### Prerequisites

- Node.js v18+
- Python 3.10+
- MongoDB running locally or via Atlas
- virtualenv (recommended for Python submodules)

### Setup

```bash
git clone https://github.com/yourusername/ClockSlayer.git
cd ClockSlayer-production
npm install
npm run dev
```

### Running ML Modules
```bash
cd Analytics/
pip install -r requirements.txt
python main.py
```

## TO-DO
- WebSocket-based live session tracking
- GPU-accelerated ML inference
- API documentation (Swagger or Postman collection)
- Next.js frontend integration
- CI/CD with GitHub Actions and Docker

