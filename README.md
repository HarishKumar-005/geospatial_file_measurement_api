
## Setup and Run

### Requirements

- Python 3.14
- Git

### Activate the virtual environment on Windows PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
```

### Install the API dependencies

```powershell
python -m pip install fastapi uvicorn
```

### Start the development server

```powershell
python -m uvicorn app.main:app --reload
```

### API Documentation

- Health endpoint: <http://127.0.0.1:8000/health>
- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>
