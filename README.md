# ⚡ FlowForge — Distributed Workflow Engine

> 🌐 **Live Web Application**: **[https://flowforge-web.onrender.com/](https://flowforge-web.onrender.com/)**

FlowForge is a production-grade, distributed workflow orchestration engine designed to model, schedule, and execute complex pipelines of dependent tasks. Highly inspired by **Apache Airflow**, FlowForge uses a **Directed Acyclic Graph (DAG)** model to manage dependencies, executes workloads asynchronously using distributed **Celery** workers, and streams execution states in real-time to a **WebSocket-powered dashboard**.

It features a robust **AI-driven pipeline architect** powered by **Google Gemini (2.5 & 1.5 Flash)** and **OpenAI (GPT-4o-mini)** to dynamically provision complex task networks from plain English, supported by a rule-based mock generator fallback.

---

## 📖 About the Project

FlowForge was engineered to solve the operational complexities of running large-scale, automated workflow orchestrations (like Apache Airflow) on resource-constrained environments. While tools like Airflow are robust, they are notoriously heavy to host, manage, and configure for small-to-medium teams.

FlowForge bridges this gap by providing an **ultra-lightweight, self-hostable ASGI-driven orchestration engine** that runs smoothly on standard low-memory platforms (such as Render's 512MB free tier). By consolidating task scheduling (Celery Beat), worker dispatch (Celery), and real-time streaming sockets (Daphne/Django Channels) into a unified codebase, it enables developers to prototype, manage, and monitor high-frequency pipeline steps without complex multi-instance provisioning or massive cloud bills.

---

## 🏗️ System Architecture

FlowForge is built with a highly decoupled, multi-container architecture orchestrated via **Docker Compose**:

```
                 ┌────────────────────────┐
                 │  Browser Dashboard UI  │
                 └──────────┬──▲──────────┘
                HTTP/JWT API│  │WebSocket Updates
                            ▼  │
                 ┌────────────────────────┐
                 │ Daphne ASGI Web Server ◄────────► Google Gemini & OpenAI API
                 └────┬──────────────┬────┘
                      │              │
             Write/Read│              │Publish/Subscribe
                      ▼              ▼
               ┌──────────────┐    ┌───────────┐
               │ PostgreSQL   │    │   Redis   │
               │  Database    │    │  Broker   │
               └──────▲───────┘    └─────┬─────┘
                      │                  │
                      │Write Status &    │Fetch Task
                      │Console Logs      ▼
                      │            ┌───────────┐
                      └────────────┤  Celery   │
                                   │  Worker   │
                                   └───────────┘
```

* **Daphne (Django)**: ASGI server handling secure authentication, CRUD, and WebSockets.
* **PostgreSQL**: Hard-drive persistent storage for pipelines, schedules, and history.
* **Redis**: In-memory message broker (for Celery queues) and channel layers (for live WebSockets).
* **Celery Worker**: Isolated background worker running tasks (Dummy simulations, Python scripts, or HTTP requests) in parallel, handling retries and skip-propagations.

---

## ✨ Features

- **🔐 Secure JWT Authentication**: Robust registration and login routes with automatic token refreshing.
- **📊 Real-time Monitoring Graph**: Visual task dependency network drawn using **vis.js** that updates nodes dynamically (⚪ gray -> 🔵 blue -> 🟢 green -> 🔴 red) as they progress in the background.
- **🗣️ Live Streaming Console**: Live execution logs streamed from distributed workers to the browser via WebSockets with under 5ms latency.
- **🤖 NLP AI Generator**: Type your pipeline in plain English (e.g. *"fetch metrics from API, clean with python, compile report"*) and let **Google Gemini (2.5/1.5 Flash)** or **OpenAI GPT-4o-mini** build your tasks and links instantly. Powered by a defensive dual-payload fallback loop.
- **🔄 Advanced Retry Failovers**: Automatic retries with exponential backoffs and automatic downstream skip propagation when parent tasks fail.
- **🔀 Topological Sorting**: Powered by **Kahn's Algorithm** to detect cycle deadlocks and structure correct execution steps.

---

## 🛠️ Tech Stack

* **Backend**: Django 5, Django REST Framework (DRF), Django Channels (ASGI WebSockets)
* **Task Queues**: Celery, Redis Broker
* **Databases**: PostgreSQL (Relational)
* **Frontend**: HTML5, CSS3 Main Design System, Vanilla JS, vis.js Network Graph
* **AI Engine**: Google Gemini REST Integration (2.5 & 1.5 Flash), OpenAI SDK (GPT-4o-mini)
* **Deployment**: Docker, Docker Compose, Render Cloud Infrastructure

---

## 🚀 Local Installation & Quick Start

### Prerequisites
* [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed on Windows/Mac/Linux.

### Setup Steps
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/flowforge.git
   cd flowforge
   ```
2. **Configure Environment Variables**:
   Create a `.env` file in the root directory:
   ```env
   DEBUG=True
   SECRET_KEY=your-secret-key-here
   ALLOWED_HOSTS=localhost,127.0.0.1
   
   # PostgreSQL
   POSTGRES_DB=flowforge
   POSTGRES_USER=flowforge
   POSTGRES_PASSWORD=your-postgres-password-here
   POSTGRES_HOST=db
   POSTGRES_PORT=5432
   
   # Redis & Broker
   REDIS_URL=redis://redis:6379/0
   CELERY_BROKER_URL=redis://redis:6379/0
   CELERY_RESULT_BACKEND=redis://redis:6379/0
   
   # AI Engine Credentials (At least one required for AI generation)
   GEMINI_API_KEY=your-gemini-api-key-here
   OPENAI_API_KEY=your-openai-api-key-here
   ```
3. **Boot Up Services**:
   Start the 6 orchestrator containers in detached mode:
   ```bash
   docker compose up -d
   ```
4. **Create Database Migrations**:
   Generate and apply tables for the Postgres container:
   ```bash
   docker compose exec web python manage.py makemigrations accounts dags runs
   docker compose exec web python manage.py migrate
   ```
5. **Explore the Engine**:
   * Open your browser and go to: **[http://localhost:8000/](http://localhost:8000/)**
   * Register an account, log in, and trigger your first pipeline!
   * Access background worker metrics at: **[http://localhost:5555/](http://localhost:5555/)** (Flower Console)
   * View interactive OpenAPI Swagger docs at: **[http://localhost:8000/api/docs/](http://localhost:8000/api/docs/)**

---

## ☁️ Cloud Deployment (Render Blueprint)

FlowForge is fully prepared and optimized for zero-cost, serverless deployment on **Render's Free Tier** using the bundled Blueprint configuration:

* **Managed Isolation**: Runs separate isolated Postgres databases (`flowforge-db`) and Redis Cache servers (`flowforge-redis`) securely out-of-the-box.
* **Consolidated Web & Background Architecture**: To bypass Free-tier background worker constraints, Daphne (ASGI Web Server), Celery (background worker), and Celery Beat (periodic scheduler) run concurrently in a **single consolidated container footprint** using clean supervisor thread management inside `render.yaml`!
* **Automated CI/CD**: Pushing changes to GitHub automatically triggers a clean static assembly (via native Django `ASGIStaticFilesHandler`) and database migration runtime loop, bringing modifications live instantly.
* **Keys setup**: Add `GEMINI_API_KEY` (100% free tier available at Google AI Studio) in the Render Environment Variables tab to enable free AI-driven layout generations instantly on the live domain!

---

## 🧮 How to Showcase (The Demo Guide)

1. **AI Graph Provisioning**: Create a pipeline using **🤖 AI Generate**, showing how NLP queries translate instantly to database task graphs.
2. **Cycle Deadlock Blocks**: Try creating a circular dependency between tasks, showing how the Kahn's algorithm cycle detection raises immediate warnings.
3. **Live Failover Retries**: Add a task that raises a Python error, set retries to `3`, and watch the node turn **red 🔴**, increment its attempts `#1` -> `#2` -> `#3` in real-time, and recursively transition downstream tasks to **skipped ⬜** on final failure.
