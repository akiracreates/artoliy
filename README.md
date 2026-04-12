# Artoliy

Artoliy is a Telegram bot built for artist profiles and lightweight discovery. Artists can create a portfolio-style profile, update it over time, and make themselves easier to find through tags. The project is structured as a Telegram bot connected to a FastAPI backend, with Redis handling storage and indexing.

It started as a CRUD-focused university assignment, but the implementation leans into a clearer product idea: a small artist directory instead of a generic user registry.

## What the project does

Artoliy lets an artist:

- create a profile
- view their own profile
- edit profile fields
- delete their profile
- browse available tags
- browse artists by tag

It also includes admin-only functionality:

- activate admin access with a code
- list all profiles
- export all profiles as JSON through the backend
- edit any user profile from the backend
- delete user profiles
- clear all project data from Redis

## Architecture

```text
Telegram bot ↔ FastAPI backend ↔ Redis
```

The split is intentional.

The Telegram bot handles interaction: commands, menus, prompts, and multi-step input flows.

The FastAPI backend handles the main logic: validation, permissions, profile CRUD, admin checks, tag browsing, and response shaping.

Redis stores the actual data: profile hashes, per-user tags, reverse tag indexes, a global user index, dynamic admin state, and lock keys used to reduce write conflicts.

## Tech stack

- Python
- aiogram
- FastAPI
- Redis
- Pydantic
- httpx
- python-dotenv

## Current implemented features

### User side
- profile creation
- profile viewing
- profile editing
- profile deletion
- profile existence checks
- tag list browsing
- artist browsing by tag

### Admin side
- admin activation by code
- profile listing
- JSON export endpoint
- admin profile update endpoint
- admin profile deletion
- full Redis project-data flush

### Bot behavior
- `/start`
- `/cancel`
- dynamic menu for regular users and admins
- FSM-based multi-step profile creation
- FSM-based field-by-field profile editing
- browse by `/tag <name>`

## Profile model

The current profile model uses these required fields:

- `telegram_user_id`
- `display_name`
- `artist_name`

Optional fields:

- `username`
- `short_bio`
- `portfolio_link`
- `contact_info`
- `commission_status`
- `tags`
- `price_range`

System-managed fields:

- `created_at`
- `updated_at`

At the moment, commission status supports only:

- `open`
- `closed`

## Backend routes

### User routes
- `GET /users/{telegram_user_id}/exists`
- `POST /users`
- `GET /users/{telegram_user_id}`
- `PATCH /users/{telegram_user_id}`
- `DELETE /users/{telegram_user_id}`

### Admin routes
- `POST /admin/activate`
- `GET /admin/users`
- `GET /admin/export/json`
- `PATCH /admin/users/{telegram_user_id}`
- `DELETE /admin/users/{telegram_user_id}`
- `DELETE /admin/redis/flush`

### Discovery routes
- `GET /artists/tags`
- `GET /artists/by-tag/{tag}`

## Data model in Redis

The backend currently stores data with a simple Redis structure:

- `user:{telegram_user_id}` for the main profile hash
- `user:{telegram_user_id}:tags` for the user’s tags
- `tag:{normalized_tag}` for reverse tag indexing
- `users:all` for the global user list
- `admins` for dynamically activated admins

There are also lock keys used during writes so create, update, and delete operations are less likely to step on each other.

## Project structure

```text
backend/
├── main.py
├── .env
└── app/
    ├── config.py
    ├── dependencies.py
    ├── redis_keys.py
    ├── schemas.py
    └── services.py

bot/
├── main.py
├── .env
└── app/
    ├── api.py
    ├── config.py
    ├── keyboards.py
    ├── states.py
    └── utils.py
```

## Local setup

### 1. Clone the repository
```bash
git clone https://github.com/your-username/artoliy.git
cd artoliy
```

### 2. Create and activate a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create `backend/.env`:

```env
REDIS_HOST=localhost
REDIS_PORT=6379
ADMIN_CODE=your_admin_code
ADMIN_IDS=123456789
```

Create `bot/.env`:

```env
BOT_TOKEN=your_telegram_bot_token
BACKEND_BASE_URL=http://127.0.0.1:8000
```

### 5. Start Redis
Make sure Redis is running locally.

### 6. Start the backend
```bash
cd backend
uvicorn main:app --reload
```

### 7. Start the bot
In a second terminal:

```bash
cd bot
python main.py
```

## What is already good about it

This project is more than a Telegram bot with a few commands attached.

It already demonstrates:

- separation of concerns between interface, backend logic, and storage
- REST API design around a real use case
- Redis-backed data modeling
- role-based behavior
- async communication between bot and backend
- a clearer product idea than a generic demo CRUD app

That makes it easier to explain both as coursework and as portfolio work.

## Current limitations

This is still a student project in active development, and a few rough edges are real:

- admin delete and admin flush currently have a request mismatch between the bot and backend
- the bot sends the admin activation success message twice
- FSM state is in memory, so in-progress flows are lost if the bot restarts
- the bot handlers still live in one large `main.py`
- automated tests have not been added yet

So the core system is in place, but it is not pretending to be production-ready.

## Next cleanup steps

The most obvious next improvements are:

- align the remaining admin delete and flush behavior between bot and backend
- normalize admin-side error handling
- remove the duplicate admin activation message
- split bot handlers into smaller modules
- add tests for backend CRUD flows
- improve the admin editing flow inside Telegram

## Why this project exists

Artoliy was built to satisfy the assignment requirements around Telegram, REST API design, Redis, CRUD, and admin controls, but in a format that feels more specific and presentable than a generic registry app.

The goal was to make something functional first, but also something worth showing.
