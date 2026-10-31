# SmartAttend AI — College Attendance Workspace

SmartAttend AI is an intelligent attendance tracking, prediction, and IoT device management workspace built for Students, Staff, and Administrators.

**Created by Simbu AI/ML from ESEC.**

---

## 🏗️ Architecture & Deployment Stack

- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Recharts → **Deployed on Vercel**
- **Backend API**: Python 3.12 Flask, SQLAlchemy, Gunicorn → **Deployed on Render**
- **Database**: PostgreSQL → **Hosted on Supabase**
- **Authentication**: Supabase Auth (Email / Password + JWT validation)
- **IoT & Machine Learning**: Pluggable Raspberry Pi client + Scikit-Learn attendance forecasting

---

## 🚀 Step-by-Step Deployment Guide

### 1. Supabase Setup (Database + Auth)

1. Create a free account at [supabase.com](https://supabase.com) and create a new project.
2. Go to **Project Settings → API**:
   - Copy **Project URL** (e.g., `https://xyzcompany.supabase.co`)
   - Copy **anon public key** (`eyJhbGciOi...`)
   - Copy **JWT Secret** (under JWT Settings)
3. Go to **Project Settings → Database**:
   - Find **Connection string → URI**
   - Copy the URI (starts with `postgresql://postgres:...@db...:5432/postgres`)
4. Go to **Authentication → Providers → Email**:
   - Make sure Email provider is enabled.
   - (Optional) Disable "Confirm email" if you want users to log in immediately without verifying email.

---

### 2. Render Setup (Backend API Deployment)

1. Sign up/Log in to [render.com](https://render.com).
2. Click **New + → Web Service**.
3. Connect your GitHub repository (`smartattend-ai`).
4. Configure the Web Service:
   - **Name**: `smartattend-api`
   - **Region**: Singapore (or nearest)
   - **Branch**: `main`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `gunicorn --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 90 backend.wsgi:app`
5. Under **Environment Variables**, add:
   - `DATABASE_URL`: *(Your Supabase PostgreSQL URI)*
   - `SUPABASE_URL`: *(Your Supabase Project URL)*
   - `SUPABASE_ANON_KEY`: *(Your Supabase Anon Key)*
   - `SUPABASE_JWT_SECRET`: *(Your Supabase JWT Secret)*
   - `SMARTATTEND_JWT_SECRET`: *(Any random 32-character string)*
   - `SMARTATTEND_BOOTSTRAP_TOKEN`: *(A secret token for provisioning the first Admin, e.g., `admin-setup-2026`)*
   - `SMARTATTEND_ALLOWED_ORIGINS`: `https://your-app.vercel.app,http://localhost:3000` *(Add your Vercel URL once deployed)*
   - `RUN_MIGRATIONS_ON_STARTUP`: `true` *(Enables auto-creation of all tables on first launch)*
   - `SMARTATTEND_COOKIE_SECURE`: `true`
   - `SMARTATTEND_REQUIRE_HTTPS`: `true`
6. Click **Create Web Service**. Wait for the build to finish.
7. Note down your backend URL: `https://smartattend-api.onrender.com`.

---

### 3. Vercel Setup (Frontend Deployment)

1. Sign up/Log in to [vercel.com](https://vercel.com).
2. Click **Add New → Project** and import your GitHub repository (`smartattend-ai`).
3. In the configure project screen:
   - **Framework Preset**: Vite
   - **Root Directory**: `./` (leave default)
   - **Build Command**: `pnpm build` (or `npm run build`)
   - **Output Directory**: `dist`
4. Under **Environment Variables**, add:
   - `VITE_SUPABASE_URL`: *(Your Supabase Project URL)*
   - `VITE_SUPABASE_ANON_KEY`: *(Your Supabase Anon Key)*
   - `VITE_API_BASE_URL`: `https://smartattend-api.onrender.com/api` *(Your Render backend URL + `/api`)*
5. Click **Deploy**.
6. Once deployed, copy your Vercel URL (e.g. `https://smartattend-ai.vercel.app`) and add it to `SMARTATTEND_ALLOWED_ORIGINS` in your Render dashboard environment variables!

---

### 4. First-Time Admin Setup

1. Open your Vercel app in the browser.
2. In Supabase Dashboard, go to **Authentication → Users → Add user** (create your admin email & password).
3. Open your Vercel app, click **Sign In**, and enter your credentials.
4. Because the account is newly created, the UI will ask for the **First-admin bootstrap token**.
5. Enter the `SMARTATTEND_BOOTSTRAP_TOKEN` you set in Render (e.g. `admin-setup-2026`).
6. Your account is now provisioned with full **Admin** permissions! You can now access all live attendance, device management, predictions, and reports dashboards.

---

## 💻 Local Development

1. Copy `.env.example` to `.env` and fill in your Supabase credentials.
2. Install frontend packages:
   ```bash
   pnpm install
   ```
3. Run Flask backend on port 5001:
   ```bash
   python -m flask --app backend.wsgi:app run --port 5001
   ```
4. Run Vite frontend:
   ```bash
   pnpm dev
   ```
5. Open `http://localhost:3000`.

---

## 📂 Project Structure

```text
smartattend/
├── src/                         # React 18 TypeScript frontend
│   ├── App.tsx                  # Main router & email/password login
│   ├── components/              # Navigation, layout, brand marks, and visual charts
│   ├── lib/                     # Supabase client, auth context, API client
│   └── pages/                   # Role dashboards, Attendance, Predictions, Reports, Devices
├── backend/
│   ├── app/                     # Flask backend application
│   │   ├── api/                 # Blueprints for auth, attendance, staff, students, devices, reports
│   │   ├── config.py            # Dynamic PostgreSQL & Supabase environment loader
│   │   ├── extensions.py        # SQLAlchemy & Flask-Migrate
│   │   ├── models.py            # Relational models (PostgreSQL compatible)
│   │   └── security.py          # Supabase JWT token verification
│   ├── migrations/              # Alembic database migration versions
│   └── wsgi.py                  # Gunicorn / WSGI entrypoint with auto-migration
├── iot/                         # Raspberry Pi attendance client & offline queue
├── smartattend_ml/              # Scikit-learn Random Forest attendance prediction models
├── render.yaml                  # Render Infrastructure-as-Code deployment config
├── vercel.json                  # Vercel SPA routing and header configuration
└── package.json                 # Node dependencies
```
