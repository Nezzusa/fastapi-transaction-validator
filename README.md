# FastAPI - Transaction Validator

> **Note:** This is a showcase project.

## Description

This project features a fully containerized API built on the FastAPI framework as part of my learning process exploring RESTful architecture and a Test-Driven Development (TDD) approach. 

Its purpose is to provide an entry point for incoming transactions to be validated using Pydantic models and evaluated for potential fraud based on a defined set of rules, including:

- **Idempotency key validation** (preventing duplicate processing)
- **Payment intensity** (rate limiting)
- **Payment amount limits** (single transaction & cumulative limits)

It also includes an automated test suite built with **pytest** running against an isolated test database.

## Tech Stack
* **Framework:** FastAPI
* **Database:** PostgreSQL
* **ORM:** SQLAlchemy
* **Testing:** Pytest
* **Containerization:** Docker

 
