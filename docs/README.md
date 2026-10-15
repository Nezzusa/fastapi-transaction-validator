# FastAPI - Transaction Validator

> **Note:** This is a showcase / training project. Credentials in
> `docker-compose.yml` are demo values and not a production practice.

## Description

This project features a fully containerized API built on the FastAPI framework as part of my learning process exploring RESTful architecture and a Test-Driven Development (TDD) approach. Built with Python 3.14.7 

Its purpose is to provide an entry point for incoming transactions to be validated using Pydantic models and evaluated for potential fraud based on a defined set of rules, including:

- **Idempotency key validation** (preventing duplicate processing)
- **Payment intensity** (rate limiting)
- **Payment limits** (max transactions and max cumulative volume per hour)

It also includes an automated test suite built with **pytest** running against an isolated test database.

## Tech Stack
* **Language:** Python 3.14.7,
* **Framework:** FastAPI, 
* **Database:** PostgreSQL 17
* **ORM:** SQLAlchemy
* **Testing:** Pytest
* **Containerization:** Docker & Docker Compose

## Quick Start

Requires [Docker (Docker Desktop for Windows/macOS)](https://www.docker.com/products/docker-desktop/).

```bash
git clone https://github.com/Nezzusa/fastapi-transaction-validator.git
cd fastapi-transaction-validator
docker compose up --build
```
Then open the interactive docs: http://localhost:8000/docs
!Important: Use localhost, not 0.0.0.0.

The database and tables are created automatically on first start.
To reset all data: `docker compose down -v`.

> **Troubleshooting:** if you previously ran a version of this project with
> different database credentials, the old volume is reused and login fails.
> Run `docker compose down -v` to remove it, or find it with
> `docker volume ls` and delete it with `docker volume rm <name>` manually.

## Rules:
![Fraud rules](/docs/fraud_rules.jpg)

## Usage

`POST /api/payment`

Request:

    {
      "idempotency_key": "order-123",
      "amount": 10.50,
      "currency": "USD",
      "sender": "user1"
    }

Response:

    {
      "status": "success",
      "received_amount": 10.5
    }

Repeating the same request returns the original result with
`"idempotent_retry": true` instead of creating a second transaction.


## Testing

With the stack running, in a second terminal:

    docker compose exec app python -m pytest tests/test_app.py

Tests run against a separate `paymentprocessing_test` database that is
created automatically, so your demo data is never touched.

## Project Structure

    .
    ├── src/
    │   ├── app.py        # FastAPI app, endpoint, fraud rules
    │   ├── db.py         # SQLAlchemy models
    │   └── tables.sql    # Idempotent schema, run on startup
    ├── docs/             # README.md, license and images
    ├── tests/
    │   ├── conftest.py   # Test DB setup and fixtures
    │   └── test_app.py
    ├── .gitignore
    ├── .dockerignore
    ├── Dockerfile
    ├── pytest.ini
    ├── requirements.txt
    └── compose.yml

## Design Decisions

- **Schema created on startup** from an idempotent SQL file (`IF NOT EXISTS`),
  so cloning the repo is enough to get a working database.
- **Healthcheck + `depends_on`** so the API only starts once Postgres is ready.
- **Isolated test database** so test runs can truncate tables safely.
- **Decimal for money** to avoid floating-point errors in calculations.

    
