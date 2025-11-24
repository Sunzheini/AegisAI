# AegisAI
A cloud-native platform that processes media (images, videos, documents) and uses AI 
to generate intelligent insights, summaries, and content-aware transformations. You
can chat with the AI about your media assets.


## Structure
AegisAI/
├── services/                           # Microservices (core of your project)
│   ├── api-gateway-service/
│   ├── workflow-orchestrator-service/
│   ├── validation-service/
│   ├── extract-content-service/
│   ├── extract-metadata-service/
│   └── ai-service/                     # or CustomLLM project (which is a separate project)
├── common/nicegui_frontend
├── shared-lib/                         # Shared library across services
├── shared-storage/                     # Shared storage for media files
└── .gitignore


## Docs
Open Swagger UI: http://127.0.0.1:9000/docs


## Installation & Setup
### AegisAI 
1. Clone the repository
2. Have poetry installed in your default python environment
3. Put  `"shared-lib @ file:///C:/Workspace/Python/AegisAI/shared-lib",` in all tomls
4. You must have a .env in the root of all services
5. Change to your dir, e.g.`
STORAGE_ROOT=C:/Workspace/Python/AegisAI/shared-storage
RAW_DIR=C:/Workspace/Python/AegisAI/shared-storage/raw
PROCESSED_DIR=C:/Workspace/Python/AegisAI/shared-storage/processed
TRANSCODED_DIR=C:/Workspace/Python/AegisAI/shared-storage/transcoded
` in all .envs
6. Delete venvs if i have pushed the by mistake :)
7. Open in terminal each service and the frontend and `poetry lock`, `poetry install --no-root`
8. Open each service and the frontend
9. As an interpreter select .venv/Scripts/python.exe (which was created in 7.)
10. Create configurations for all microservices and the frontend
   create a configuration in pycharm:
       script: D:/Study/Projects/PycharmProjects/workflow-orchestrator-service/.venv/Scripts/uvicorn.exe
       parameters: main:app --reload --host 127.0.0.1 --port 9000 (or workers.my_worker:app if in a folder)
       working directory: D:/Study/Projects/PycharmProjects/workflow-orchestrator-service
11. Fix the working directories in all configs to your: `C:\Workspace\Python\AegisAI\services\api-gateway-service`
12. If it still gives an error that async_timeout is not installed, install in api_gateway_service `poetry add async_timeout`

### CustomLLM
1. Clone the repository
2. Have poetry installed in your default python environment
3. Put  `"shared-lib @ file:///C:/Workspace/Python/AegisAI/shared-lib",` in the requirements.txt of CustomLLM
4. You need an .env file in the root of CustomLLM
5. Change to your dir, e.g.`
STORAGE_ROOT=C:/Workspace/Python/AegisAI/shared-storage
RAW_DIR=C:/Workspace/Python/AegisAI/shared-storage/raw
PROCESSED_DIR=C:/Workspace/Python/AegisAI/shared-storage/processed
TRANSCODED_DIR=C:/Workspace/Python/AegisAI/shared-storage/transcoded
` in the .env
6. Delete venvs if i have pushed the by mistake..
7. Edit requirements.txt, replace:
`
opentelemetry-api==1.36.0
opentelemetry-exporter-otlp-proto-common==1.36.0
opentelemetry-exporter-otlp-proto-grpc==1.36.0
opentelemetry-instrumentation==0.53b1
opentelemetry-instrumentation-asgi==0.53b1
opentelemetry-instrumentation-fastapi==0.53b1
opentelemetry-proto==1.36.0
opentelemetry-sdk==1.36.0
opentelemetry-semantic-conventions==0.57b0
opentelemetry-util-http==0.53b1
`
with:
`
opentelemetry-api==1.38.0
opentelemetry-exporter-otlp-proto-common==1.38.0
opentelemetry-exporter-otlp-proto-grpc==1.38.0
opentelemetry-instrumentation==0.59b0
opentelemetry-instrumentation-asgi==0.59b0
opentelemetry-instrumentation-fastapi==0.59b0
opentelemetry-proto==1.38.0
opentelemetry-sdk==1.38.0
opentelemetry-semantic-conventions==0.59b0
opentelemetry-util-http==0.59b0
`
8. You must have Build Tools for Visual Studio 2022:
Open the Visual Studio Installer → find Build Tools for Visual Studio 2022 → click Modify → ensure these boxes are checked:
    Desktop development with C++
    Under “Installation details” on the right:
	    MSVC v143 - VS 2022 C++ x64/x86 build tools
	    Windows 10 or 11 SDK
	    C++ CMake tools for Windows
Install and Restart
Press Start → type “Developer Command Prompt for VS 2022”.
Right-click → Run as administrator (optional, but helps avoid permission issues).
In that window, type: cl
You should now see something like: Microsoft (R) C/C++ Optimizing Compiler Version 19.3x for x64
9. Open a terminal inside the project and run:
`python -m venv .venv`, `.venv\Scripts\activate`, `pip install -r requirements.txt`
10. Open the project
11. As interpreter select .venv/Scripts/python.exe


## Running
Start each service (by its configuration):
1. api-gateway-service (port 9000)
2. workflow-orchestrator-service (port 9001)
3. validation-service (port 9002)
4. extract-metadata-service (port 9003)
5. extract-content-service (port 9004)
6. CustomLLM
7. nicegui_frontend


## Docker
1. Use the created docker-compose.yml, Makefile and Dockerfiles in each service, api-gateway has docker-entrypoint.sh.
Note: in the current state docker-compose.yml is removed from git, since it contains secret key. You can use the
docker-compose-example.yml as a base and create your own docker-compose.yml with your secrets.
2. The only code change is: in the pyproject.toml of each service:
`
"shared-lib @ file:///app/shared-lib"                                      # use this
# "shared-lib @ file:///D:/Study/Projects/Github/AegisAI/shared-lib"       # comment this
`
3. Open terminal in the root of AegisAI and run:
`make build`    # builds the docker images
`make up`       # creates docker containers and runs them
`make down`     # stops and removes all containers
`make logs`     # shows the logs of all containers (e.g. to see if they started correctly)


## Kubernetes
see KUBERNETES_SETUP.md


### CI/CD
1. Create `\AegisAI\.github\workflows\pylint.yaml` with the code suggested from GitHub actions
2. `git add .github/workflows/pylint.yaml`, since it is ignored in .gitignore
3. Commit and push, the workflow will run
example file:

`
name: Pylint

on: [push]

jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.8", "3.9", "3.10"]
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v3
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pylint
        pip install pylint pytest
    - name: Analysing the code with pylint
      run: |
        pylint $(git ls-files '*.py') --disable=R0801 --fail-under=6.0
`













