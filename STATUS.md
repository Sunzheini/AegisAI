# Status and ToDo

## Status
Working with USE_AWS=TRUE, without docker, with docker and with k8s. Not working with USE_AWS=FALSE.
TESTS working with USE_AWS=TRUE.

## ToDo:
- CI/CD
- Next thing in AWS
- integrate multipr / -tr / asyncio from playground
- Keep a ref to the files ina  db / list and delete any uploaded files / select a file for conversation
- Celery?
- user stories use jira
- pylint / black -> run on other pc -> review


## High-level plan к8:
1. Create Kubernetes manifests for each service:
Deployment YAML (defines pods, replicas, container specs)
Service YAML (exposes services internally/externally)
ConfigMap/Secret YAMLs (for .env variables)
Ingress YAML (for API gateway routing)

2. Structure: Add a k8s/ or deployments/ folder with manifests for:
- api-gateway-deployment.yaml
- workflow-orchestrator-deployment.yaml
- validation-service-deployment.yaml
- etc (other stuff if needed).

3. Helm charts (optional but recommended): Package everything for easier deployment and versioning (tbh ние ползваме но малко е тегаво докато ги нацелиш правилно, не ти е задължително)
4. Local testing: Use Minikube or Kind to test locally before AWS (Minikube лесно се слага и можеш да ги разцъкаш локално).
 

## High-level plan за CI/CD:
1. Choose a platform: GitHub Actions (easiest since you're on GitHub), GitLab CI, or AWS CodePipeline
2. Pipeline stages:
2.1. CI (Continuous Integration):
   Lint code (flake8, black)
   Run unit tests
   Build Docker images
   Push images to AWS ECR (Elastic Container Registry)

2.2. CD (Continuous Deployment):
    Deploy to AWS EKS (Elastic Kubernetes Service)
    Apply Kubernetes manifests
    Run smoke tests
3. Create .github/workflows/ with YAML files:
    ci.yml: Runs on every push/PR
    cd.yml: Runs on merge to main or tags
