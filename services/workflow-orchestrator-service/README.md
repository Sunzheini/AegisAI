# workflow-orchestrator-service notes


## Install dependencies (Poetry)
poetry add "fastapi[standard]"
poetry add "uvicorn[standard]"


## Start
```
uvicorn main:app --reload

or

run with a new configuration in PyCharm (no hot reload but stable and you can stop it)
script: D:/Study/Projects/PycharmProjects/workflow-orchestrator-service/.venv/Scripts/uvicorn.exe
parameters: main:app --reload --host 127.0.0.1 --port 9000 (8000 is for api-gateway-service)
working directory: D:/Study/Projects/PycharmProjects/workflow-orchestrator-service
add environment variables if needed
```


## If it is not stopping with Ctrl+C
```
taskkill /f /im uvicorn.exe
taskkill /f /im python.exe
```
and delete the __pycache__ folders


## Docs
Open Swagger UI: http://127.0.0.1:9000/docs


## `Depends` keyword
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

# black --check .          # See what would change
# black --diff .           # Preview changes
# black .                  # Apply changes, but exclude venv, .venv, .idea, migrations, test, __pycache__
# pylint --ignore-paths=".*venv.*|.*\.idea.*|.*migrations.*|.*test.*|.*__pycache__.*" .   
