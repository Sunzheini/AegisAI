# AegisAI
A cloud-native platform that not only processes media (images, 
videos, documents) but also uses AI to generate intelligent 
insights, summaries, and content-aware transformations.

## Structure
AegisAI/
├── services/                       # Microservices (core of your project)
│   ├── api-gateway-service/
│   └── another-service/
├── common/                         # Shared elements
├── docker-compose.yml              # Local development
├── pyproject.toml                  # Root-level for dev tools
├── poetry.lock
├── README.md
├── WORK_PLAN.md
└── .gitignore


## general notes
### Install dependencies (Poetry)
poetry add "fastapi[standard]"
poetry add "uvicorn[standard]"

### Start
create a configuration in pycharm:
    script: D:/Study/Projects/PycharmProjects/workflow-orchestrator-service/.venv/Scripts/uvicorn.exe
    parameters: main:app --reload --host 127.0.0.1 --port 9000 (or workers.my_worker:app if in a folder)
    working directory: D:/Study/Projects/PycharmProjects/workflow-orchestrator-service
    add environment variables if needed

### Docs
Open Swagger UI: http://127.0.0.1:9000/docs

### `Depends` keyword
The Depends keyword is one of the most powerful features in FastAPI. It's the dependency injection
system that makes FastAPI so clean and modular.

    ```
    from fastapi import Depends

    def my_dependency():
        return "some value"

    @app.get("/items/")
    async def read_items(value: str = Depends(my_dependency)):
        return {"value": value}
    ```
    What Happens:
        FastAPI sees Depends(my_dependency)
        It calls my_dependency() function
        It passes the return value to your route function as value
        Your route uses the value

### Checking and formatting
black --check .          # See what would change
black --diff .           # Preview changes
black .                  # Apply changes, but exclude venv, .venv, .idea, migrations, test, __pycache__
pylint --ignore-paths=".*venv.*|.*\.idea.*|.*migrations.*|.*test.*|.*__pycache__.*" .
