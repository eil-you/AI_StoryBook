# AI-StoryWeaver Project Guide

## 🛠 Build & Setup Commands
- Create virtual environment: `python -m venv venv`
- Activate venv: `source venv/bin/activate` (Mac/Linux) or `.\venv\Scripts\activate` (Windows)
- Install dependencies: `pip install -r requirements.txt`
- Run dev server: `uvicorn app.main:app --reload`

## 🧪 Testing Commands
- Run all tests: `pytest`
- Run specific test file: `pytest tests/test_filename.py`
- Run with coverage: `pytest --cov=app tests/`

## 🏗 Architecture & Code Style
- **Framework**: FastAPI (Asynchronous)
- **Language**: Python 3.12+ with strict Type Hinting.
- **Project Structure**:
    - `app/api/`: Route handlers (Controllers)
    - `app/models/`: SQLAlchemy database models
    - `app/schemas/`: Pydantic data validation (DTOs)
    - `app/services/`: Business logic & External API integration (OpenAI, Sweetbook)
    - `app/core/`: Configuration, Security, Global Constants
- **Database**: SQLite (Development) / PostgreSQL (Production) using SQLAlchemy ORM.
- **Naming Convention**: 
    - Variables/Functions: `snake_case`
    - Classes: `PascalCase`
- **Validation**: Use Pydantic v2 for all request/response models to ensure data integrity.

## 🔑 Key Principles
- **Data Integrity**: Ensure 100% data consistency for book orders and payment status (reflecting SI experience).
- **Error Handling**: Use structured exception handling for external API calls (Sweetbook/OpenAI).
- **Documentation**: All API endpoints must have clear docstrings for Swagger UI.
- **Async First**: Always prefer `async def` for API endpoints and service methods to leverage FastAPI's performance.
- **Dependency Injection**: Use FastAPI's `Depends` for database sessions and service class instantiation.
- **Logging**: Implement structured logging with trace IDs to track requests flowing from AI generation to Sweetbook API.