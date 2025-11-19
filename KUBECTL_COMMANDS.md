# AegisAI Kubernetes Commands Reference

This is a comprehensive reference of kubectl commands for managing the AegisAI platform on Kubernetes.

---

## 📋 TABLE OF CONTENTS
1. [Quick Access Commands](#quick-access-commands)
2. [Build & Push Docker Images](#build--push-docker-images)
3. [Deploy to Kubernetes](#deploy-to-kubernetes)
4. [View Status & Information](#view-status--information)
5. [View Logs](#view-logs)
6. [Restart & Update Pods](#restart--update-pods)
7. [Delete Resources](#delete-resources)
8. [Port Forwarding](#port-forwarding)
9. [Scale & Manage Resources](#scale--manage-resources)
10. [Debugging & Troubleshooting](#debugging--troubleshooting)
11. [Complete Rebuild Workflows](#complete-rebuild-workflows)
12. [Common Troubleshooting Scenarios](#common-troubleshooting-scenarios)

---

## 🚀 QUICK ACCESS COMMANDS

### Port Forward Services
```powershell
# API Gateway (primary access point)
kubectl port-forward -n aegisai service/api-gateway 8000:8000

# Workflow Orchestrator
kubectl port-forward -n aegisai service/workflow-orchestrator 9000:9000

# AI Service
kubectl port-forward -n aegisai service/ai-service 9004:9004

# Validation Service
kubectl port-forward -n aegisai service/validation-service 9001:9001

# Extract Metadata Service
kubectl port-forward -n aegisai service/extract-metadata-service 9002:9002

# Extract Content Service
kubectl port-forward -n aegisai service/extract-content-service 9003:9003

# PostgreSQL (for direct DB access)
kubectl port-forward -n aegisai service/postgres 5432:5432

# Redis (for direct cache access)
kubectl port-forward -n aegisai service/redis 6379:6379
```

### Check Status
```powershell
# Check pod status
kubectl get pods -n aegisai

# Check deployments
kubectl get deployments -n aegisai

# Check services
kubectl get services -n aegisai

# Check everything at once
kubectl get all -n aegisai
```

### Access API Gateway
```powershell
# After port-forwarding to localhost:8000
curl http://localhost:8000/docs

# Or use browser to view Swagger UI
start http://localhost:8000/docs
```

---

## 🏗️ BUILD & PUSH DOCKER IMAGES

### Using PowerShell Scripts (Recommended)

```powershell
# Build all images (no push)
cd D:\Study\Projects\Github\AegisAI\k8s
.\build-images.ps1 -Registry "sunzheini1407" -Tag "latest"

# Build and push all images
.\build-images.ps1 -Registry "sunzheini1407" -Tag "latest" -Push

# Build with specific tag (e.g., v1.0.0)
.\build-images.ps1 -Registry "sunzheini1407" -Tag "v1.0.0" -Push

# Build without cache (fresh build)
.\build-images.ps1 -Registry "sunzheini1407" -BuildCache:$false -Push
```

### Using Docker Commands Manually

```powershell
# Set your registry
$REGISTRY = "sunzheini1407"
$TAG = "latest"

# Build individual services
cd D:\Study\Projects\Github\AegisAI

# API Gateway
docker build -f services/api-gateway-service/Dockerfile -t ${REGISTRY}/aegisai-api-gateway:${TAG} .
docker push ${REGISTRY}/aegisai-api-gateway:${TAG}

# Workflow Orchestrator
docker build -f services/workflow-orchestrator-service/Dockerfile -t ${REGISTRY}/aegisai-workflow-orchestrator:${TAG} .
docker push ${REGISTRY}/aegisai-workflow-orchestrator:${TAG}

# Validation Service
docker build -f services/validation-service/Dockerfile -t ${REGISTRY}/aegisai-validation-service:${TAG} .
docker push ${REGISTRY}/aegisai-validation-service:${TAG}

# Extract Metadata Service
docker build -f services/extract-metadata-service/Dockerfile -t ${REGISTRY}/aegisai-extract-metadata-service:${TAG} .
docker push ${REGISTRY}/aegisai-extract-metadata-service:${TAG}

# Extract Content Service
docker build -f services/extract-content-service/Dockerfile -t ${REGISTRY}/aegisai-extract-content-service:${TAG} .
docker push ${REGISTRY}/aegisai-extract-content-service:${TAG}

# AI Service
docker build -f services/ai-service/Dockerfile -t ${REGISTRY}/aegisai-ai-service:${TAG} .
docker push ${REGISTRY}/aegisai-ai-service:${TAG}
```

### Using Docker Compose (for local builds)

```powershell
cd D:\Study\Projects\Github\AegisAI

# Build all services
docker-compose build

# Build specific service
docker-compose build api-gateway
docker-compose build workflow-orchestrator
```

---

## 🚢 DEPLOY TO KUBERNETES

### Full Deployment (Using Script)

```powershell
# Deploy everything
cd D:\Study\Projects\Github\AegisAI\k8s
.\deploy-k8s.ps1 -Registry "sunzheini1407" -Namespace "aegisai"
```

### Manual Deployment (Step by Step)

```powershell
cd D:\Study\Projects\Github\AegisAI\k8s

# 1. Create namespace
kubectl apply -f namespace.yaml

# 2. Create persistent volumes
kubectl apply -f volumes/persistent-volume.yaml

# 3. Create ConfigMaps and Secrets
kubectl apply -f configmaps/app-config.yaml
kubectl apply -f secrets/app-secrets.yaml

# 4. Deploy infrastructure (PostgreSQL & Redis)
kubectl apply -f services/postgres.yaml
kubectl apply -f services/redis.yaml

# Wait for infrastructure to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n aegisai --timeout=120s
kubectl wait --for=condition=ready pod -l app=redis -n aegisai --timeout=120s

# 5. Deploy application services
kubectl apply -f deployments/workflow-orchestrator.yaml
kubectl apply -f deployments/api-gateway.yaml
kubectl apply -f deployments/validation-service.yaml
kubectl apply -f deployments/extract-metadata-service.yaml
kubectl apply -f deployments/extract-content-service.yaml
kubectl apply -f deployments/ai-service.yaml
```

### Deploy Individual Services

```powershell
# Deploy specific service
kubectl apply -f D:\Study\Projects\Github\AegisAI\k8s\deployments\api-gateway.yaml
kubectl apply -f D:\Study\Projects\Github\AegisAI\k8s\deployments\workflow-orchestrator.yaml
kubectl apply -f D:\Study\Projects\Github\AegisAI\k8s\deployments\validation-service.yaml
kubectl apply -f D:\Study\Projects\Github\AegisAI\k8s\deployments\extract-metadata-service.yaml
kubectl apply -f D:\Study\Projects\Github\AegisAI\k8s\deployments\extract-content-service.yaml
kubectl apply -f D:\Study\Projects\Github\AegisAI\k8s\deployments\ai-service.yaml
```

### Update Secrets

```powershell
# Update secrets file, then apply
kubectl apply -f D:\Study\Projects\Github\AegisAI\k8s\secrets\app-secrets.yaml

# Restart pods to pick up new secrets (see Restart section)
```

---

## 👀 VIEW STATUS & INFORMATION

### Pods

```powershell
# List all pods
kubectl get pods -n aegisai

# List pods with more details
kubectl get pods -n aegisai -o wide

# Watch pods in real-time
kubectl get pods -n aegisai --watch

# Get specific pod details
kubectl describe pod <pod-name> -n aegisai

# List pods by label
kubectl get pods -n aegisai -l app=api-gateway
kubectl get pods -n aegisai -l app=workflow-orchestrator
kubectl get pods -n aegisai -l tier=gateway
```

### Deployments

```powershell
# List all deployments
kubectl get deployments -n aegisai

# Get deployment details
kubectl describe deployment api-gateway -n aegisai

# Get deployment status
kubectl rollout status deployment/api-gateway -n aegisai

# Get deployment history
kubectl rollout history deployment/api-gateway -n aegisai
```

### Services

```powershell
# List all services
kubectl get services -n aegisai
kubectl get svc -n aegisai

# Get service details
kubectl describe service api-gateway -n aegisai

# Get service endpoints
kubectl get endpoints -n aegisai
```

### Everything

```powershell
# View all resources in namespace
kubectl get all -n aegisai

# View all resources with labels
kubectl get all -n aegisai --show-labels

# View resources across all namespaces
kubectl get all --all-namespaces
```

### ConfigMaps & Secrets

```powershell
# List ConfigMaps
kubectl get configmaps -n aegisai
kubectl get cm -n aegisai

# View ConfigMap content
kubectl describe configmap app-config -n aegisai
kubectl get configmap app-config -n aegisai -o yaml

# List Secrets
kubectl get secrets -n aegisai

# View Secret details (data is base64 encoded)
kubectl describe secret app-secrets -n aegisai
kubectl get secret app-secrets -n aegisai -o yaml
```

### Storage

```powershell
# View Persistent Volumes
kubectl get pv

# View Persistent Volume Claims
kubectl get pvc -n aegisai

# Describe PVC
kubectl describe pvc shared-storage-pvc -n aegisai
```

---

## 📝 VIEW LOGS

### Service Logs

```powershell
# View logs for a specific service (all pods with that label)
kubectl logs -n aegisai -l app=api-gateway --tail=50
kubectl logs -n aegisai -l app=workflow-orchestrator --tail=50
kubectl logs -n aegisai -l app=validation-service --tail=50
kubectl logs -n aegisai -l app=extract-metadata-service --tail=50
kubectl logs -n aegisai -l app=extract-content-service --tail=50
kubectl logs -n aegisai -l app=ai-service --tail=50

# Follow logs in real-time
kubectl logs -n aegisai -l app=api-gateway -f
kubectl logs -n aegisai -l app=workflow-orchestrator -f

# View last 100 lines
kubectl logs -n aegisai -l app=api-gateway --tail=100

# View logs since specific time
kubectl logs -n aegisai -l app=api-gateway --since=1h
kubectl logs -n aegisai -l app=api-gateway --since=30m
```

### Pod Logs

```powershell
# Get specific pod logs
kubectl logs <pod-name> -n aegisai

# Follow specific pod logs
kubectl logs <pod-name> -n aegisai -f

# View logs from previous container instance (after crash)
kubectl logs <pod-name> -n aegisai --previous

# View logs from specific container in multi-container pod
kubectl logs <pod-name> -c <container-name> -n aegisai
```

### Infrastructure Logs

```powershell
# PostgreSQL logs
kubectl logs -n aegisai -l app=postgres --tail=50

# Redis logs
kubectl logs -n aegisai -l app=redis --tail=50
```

---

## 🔄 RESTART & UPDATE PODS

### Restart Deployments

```powershell
# Restart a deployment (rolling restart)
kubectl rollout restart deployment/api-gateway -n aegisai
kubectl rollout restart deployment/workflow-orchestrator -n aegisai
kubectl rollout restart deployment/validation-service -n aegisai
kubectl rollout restart deployment/extract-metadata-service -n aegisai
kubectl rollout restart deployment/extract-content-service -n aegisai
kubectl rollout restart deployment/ai-service -n aegisai

# Restart all deployments
kubectl rollout restart deployment -n aegisai
```

### Delete and Recreate Pods (Force Restart)

```powershell
# Delete pods by label (they will be automatically recreated)
kubectl delete pods -n aegisai -l app=api-gateway
kubectl delete pods -n aegisai -l app=workflow-orchestrator
kubectl delete pods -n aegisai -l app=validation-service
kubectl delete pods -n aegisai -l app=extract-metadata-service
kubectl delete pods -n aegisai -l app=extract-content-service
kubectl delete pods -n aegisai -l app=ai-service

# Delete all application pods at once (multi-line for clarity)
kubectl delete pods -n aegisai -l app=validation-service; `
kubectl delete pods -n aegisai -l app=extract-metadata-service; `
kubectl delete pods -n aegisai -l app=extract-content-service; `
kubectl delete pods -n aegisai -l app=ai-service; `
kubectl delete pods -n aegisai -l app=api-gateway; `
kubectl delete pods -n aegisai -l app=workflow-orchestrator

# Delete specific pod
kubectl delete pod <pod-name> -n aegisai
```

### Update Image (Rolling Update)

```powershell
# Update deployment image
kubectl set image deployment/api-gateway api-gateway=sunzheini1407/aegisai-api-gateway:v1.0.0 -n aegisai

# Update and record the change
kubectl set image deployment/api-gateway api-gateway=sunzheini1407/aegisai-api-gateway:latest -n aegisai --record

# Check rollout status
kubectl rollout status deployment/api-gateway -n aegisai
```

### Rollback

```powershell
# Rollback to previous version
kubectl rollout undo deployment/api-gateway -n aegisai

# Rollback to specific revision
kubectl rollout undo deployment/api-gateway -n aegisai --to-revision=2

# View rollout history
kubectl rollout history deployment/api-gateway -n aegisai
```

---

## 🗑️ DELETE RESOURCES

### Delete Pods

```powershell
# Delete specific pod
kubectl delete pod <pod-name> -n aegisai

# Delete pods by label
kubectl delete pods -n aegisai -l app=api-gateway

# Delete all pods (not recommended - use with caution)
kubectl delete pods --all -n aegisai
```

### Delete Deployments

```powershell
# Delete specific deployment
kubectl delete deployment api-gateway -n aegisai
kubectl delete deployment workflow-orchestrator -n aegisai

# Delete all deployments
kubectl delete deployments --all -n aegisai
```

### Delete Services

```powershell
# Delete specific service
kubectl delete service api-gateway -n aegisai

# Delete all services
kubectl delete services --all -n aegisai
```

### Delete by File

```powershell
# Delete resources defined in a file
kubectl delete -f D:\Study\Projects\Github\AegisAI\k8s\deployments\api-gateway.yaml
kubectl delete -f D:\Study\Projects\Github\AegisAI\k8s\services\postgres.yaml

# Delete all resources in a directory
kubectl delete -f D:\Study\Projects\Github\AegisAI\k8s\deployments\
```

### Delete Everything in Namespace

```powershell
# Delete all resources in namespace (DANGEROUS!)
kubectl delete all --all -n aegisai

# Delete namespace (this deletes EVERYTHING including the namespace)
kubectl delete namespace aegisai
```

### Clean Slate (Complete Teardown)

```powershell
# Delete all application resources
kubectl delete -f D:\Study\Projects\Github\AegisAI\k8s\deployments\
kubectl delete -f D:\Study\Projects\Github\AegisAI\k8s\services\
kubectl delete -f D:\Study\Projects\Github\AegisAI\k8s\volumes\
kubectl delete -f D:\Study\Projects\Github\AegisAI\k8s\configmaps\
kubectl delete -f D:\Study\Projects\Github\AegisAI\k8s\secrets\
kubectl delete -f D:\Study\Projects\Github\AegisAI\k8s\namespace.yaml
```

---

## 🔌 PORT FORWARDING

### Forward All Services

```powershell
# API Gateway (8000)
kubectl port-forward -n aegisai service/api-gateway 8000:8000

# Workflow Orchestrator (9000)
kubectl port-forward -n aegisai service/workflow-orchestrator 9000:9000

# Validation Service (9001)
kubectl port-forward -n aegisai service/validation-service 9001:9001

# Extract Metadata Service (9002)
kubectl port-forward -n aegisai service/extract-metadata-service 9002:9002

# Extract Content Service (9003)
kubectl port-forward -n aegisai service/extract-content-service 9003:9003

# AI Service (9004)
kubectl port-forward -n aegisai service/ai-service 9004:9004

# PostgreSQL (5432)
kubectl port-forward -n aegisai service/postgres 5432:5432

# Redis (6379)
kubectl port-forward -n aegisai service/redis 6379:6379
```

### Port Forward to Different Local Port

```powershell
# Forward remote port 8000 to local port 8080
kubectl port-forward -n aegisai service/api-gateway 8080:8000

# Forward to different local port
kubectl port-forward -n aegisai service/postgres 15432:5432
```

### Port Forward Pods

```powershell
# Forward to specific pod instead of service
kubectl port-forward -n aegisai <pod-name> 8000:8000
```

---

## ⚙️ SCALE & MANAGE RESOURCES

### Scale Deployments

```powershell
# Scale deployment to specific replica count
kubectl scale deployment/api-gateway -n aegisai --replicas=3
kubectl scale deployment/workflow-orchestrator -n aegisai --replicas=2

# Scale multiple deployments
kubectl scale deployment/validation-service -n aegisai --replicas=3
kubectl scale deployment/extract-metadata-service -n aegisai --replicas=3
kubectl scale deployment/extract-content-service -n aegisai --replicas=3

# Scale down to 0 (stop without deleting)
kubectl scale deployment/api-gateway -n aegisai --replicas=0

# Scale back up
kubectl scale deployment/api-gateway -n aegisai --replicas=2
```

### Autoscaling (HPA - Horizontal Pod Autoscaler)

```powershell
# Apply all HPAs from file (RECOMMENDED)
kubectl apply -f D:\Study\Projects\Github\AegisAI\k8s\hpa.yaml

# View all autoscalers
kubectl get hpa -n aegisai

# Watch HPAs in real-time
kubectl get hpa -n aegisai --watch

# Describe specific HPA
kubectl describe hpa api-gateway-hpa -n aegisai

# Delete all HPAs
kubectl delete -f D:\Study\Projects\Github\AegisAI\k8s\hpa.yaml

# Delete specific HPA
kubectl delete hpa api-gateway-hpa -n aegisai

# Create HPA manually (if needed)
kubectl autoscale deployment api-gateway -n aegisai --min=2 --max=10 --cpu-percent=70
```

### High Availability (PDB - Pod Disruption Budget)

```powershell
# Apply all PDBs from file (ensures at least 1 pod always available)
kubectl apply -f D:\Study\Projects\Github\AegisAI\k8s\pdb.yaml

# View Pod Disruption Budgets
kubectl get pdb -n aegisai

# Describe specific PDB
kubectl describe pdb api-gateway-pdb -n aegisai

# Delete all PDBs
kubectl delete -f D:\Study\Projects\Github\AegisAI\k8s\pdb.yaml
```

### Resource Management

```powershell
# View resource usage
kubectl top nodes
kubectl top pods -n aegisai

# View pod resource requests/limits
kubectl describe pod <pod-name> -n aegisai | grep -A 5 "Limits:"
```

---

## 🐛 DEBUGGING & TROUBLESHOOTING

### Execute Commands in Pod

```powershell
# Get shell access to pod
kubectl exec -it <pod-name> -n aegisai -- /bin/bash
kubectl exec -it <pod-name> -n aegisai -- /bin/sh

# Run single command in pod
kubectl exec <pod-name> -n aegisai -- ls -la
kubectl exec <pod-name> -n aegisai -- env
kubectl exec <pod-name> -n aegisai -- cat /etc/hosts

# Execute in specific container
kubectl exec -it <pod-name> -c <container-name> -n aegisai -- /bin/bash
```

### Check Pod Events

```powershell
# View events for specific pod
kubectl describe pod <pod-name> -n aegisai

# View all events in namespace
kubectl get events -n aegisai

# View events sorted by timestamp
kubectl get events -n aegisai --sort-by=.metadata.creationTimestamp

# Watch events in real-time
kubectl get events -n aegisai --watch
```

### Check Container Status

```powershell
# Check if containers are ready
kubectl get pods -n aegisai -o wide

# Get detailed pod status
kubectl describe pod <pod-name> -n aegisai

# Check restart count
kubectl get pods -n aegisai -o custom-columns=NAME:.metadata.name,RESTARTS:.status.containerStatuses[0].restartCount
```

### Network Debugging

```powershell
# Test service connectivity from within a pod
kubectl exec -it <pod-name> -n aegisai -- curl http://api-gateway:8000/docs
kubectl exec -it <pod-name> -n aegisai -- ping api-gateway
kubectl exec -it <pod-name> -n aegisai -- nslookup api-gateway

# Check service endpoints
kubectl get endpoints -n aegisai
```

### Debug Connection Issues

```powershell
# Create a debug pod
kubectl run debug -n aegisai --image=curlimages/curl:latest -it --rm -- /bin/sh

# Inside the debug pod, test connectivity
curl http://api-gateway:8000/docs
curl http://workflow-orchestrator:9000/health
```

---

## 🔧 COMPLETE REBUILD WORKFLOWS

### Workflow 0: Recover from Deleted Images (Image Recovery)

```powershell
# IF YOU DELETE YOUR LOCAL DOCKER IMAGES, HERE'S WHAT TO DO:

# Option A: Pull from Docker Hub (if images exist there)
# --------------------------------------------------------
$REGISTRY = "sunzheini1407"
$services = @("api-gateway", "workflow-orchestrator", "validation-service", "extract-metadata-service", "extract-content-service", "ai-service")

foreach ($service in $services) {
    docker pull ${REGISTRY}/aegisai-${service}:latest
}

# Then your Kubernetes cluster can pull them as normal


# Option B: Rebuild All Images from Source (MOST COMMON)
# --------------------------------------------------------
# If images were deleted from Docker Hub OR you need fresh builds:

# 1. Navigate to k8s directory
cd D:\Study\Projects\Github\AegisAI\k8s

# 2. Rebuild all images from source and push to Docker Hub
.\build-images.ps1 -Registry "sunzheini1407" -Tag "latest" -Push

# 3. Kubernetes pods will automatically pull the new images on next restart
# OR force them to pull now:
kubectl rollout restart deployment -n aegisai

# 4. Verify everything is working
kubectl get pods -n aegisai
kubectl logs -n aegisai -l app=api-gateway --tail=50


# Option C: Complete Fresh Build (Nuclear Option)
# ------------------------------------------------
# If Option B fails or you want to ensure everything is clean:

# 1. Delete all local images (if they're corrupted)
docker images | grep aegisai | awk '{print $3}' | ForEach-Object { docker rmi -f $_ }

# 2. Build from scratch without cache
cd D:\Study\Projects\Github\AegisAI\k8s
.\build-images.ps1 -Registry "sunzheini1407" -Tag "latest" -BuildCache:$false -Push

# 3. Delete all pods to force fresh image pull
kubectl delete pods --all -n aegisai

# 4. Wait and verify
kubectl get pods -n aegisai --watch
```

**What happens in Kubernetes when images are deleted:**
- ✅ **Existing pods keep running** - They use cached images on the node
- ⚠️ **New pods fail to start** - If image isn't available to pull
- 🔄 **Solution**: Rebuild and push images, then restart pods

**Prevention tip**: Always keep images in Docker Hub registry!

---

### Workflow 1: Quick Rebuild (Update Existing Images)

```powershell
# 1. Build and push new images
cd D:\Study\Projects\Github\AegisAI\k8s
.\build-images.ps1 -Registry "sunzheini1407" -Tag "latest" -Push

# 2. Restart deployments to pull new images
kubectl rollout restart deployment -n aegisai

# 3. Check rollout status
kubectl rollout status deployment/api-gateway -n aegisai
kubectl rollout status deployment/workflow-orchestrator -n aegisai

# 4. Verify pods are running
kubectl get pods -n aegisai
```

### Workflow 2: Force Rebuild (Delete and Recreate Pods)

```powershell
# 1. Build and push new images
cd D:\Study\Projects\Github\AegisAI\k8s
.\build-images.ps1 -Registry "sunzheini1407" -Tag "latest" -Push

# 2. Delete all application pods
kubectl delete pods -n aegisai -l app=api-gateway; `
kubectl delete pods -n aegisai -l app=workflow-orchestrator; `
kubectl delete pods -n aegisai -l app=validation-service; `
kubectl delete pods -n aegisai -l app=extract-metadata-service; `
kubectl delete pods -n aegisai -l app=extract-content-service; `
kubectl delete pods -n aegisai -l app=ai-service

# 3. Wait for new pods to start
kubectl get pods -n aegisai --watch
```

### Workflow 3: Complete Fresh Deployment

```powershell
# 1. Delete everything
kubectl delete all --all -n aegisai
kubectl delete pvc --all -n aegisai
kubectl delete configmap --all -n aegisai
kubectl delete secret --all -n aegisai

# 2. Build and push images
cd D:\Study\Projects\Github\AegisAI\k8s
.\build-images.ps1 -Registry "sunzheini1407" -Tag "latest" -Push

# 3. Redeploy everything
.\deploy-k8s.ps1 -Registry "sunzheini1407" -Namespace "aegisai"

# 4. Check status
kubectl get all -n aegisai
```

### Workflow 4: Nuclear Option (Complete Teardown and Rebuild)

```powershell
# 1. Delete namespace (deletes everything inside)
kubectl delete namespace aegisai

# 2. Build images from scratch
cd D:\Study\Projects\Github\AegisAI\k8s
.\build-images.ps1 -Registry "sunzheini1407" -Tag "latest" -BuildCache:$false -Push

# 3. Deploy everything
.\deploy-k8s.ps1 -Registry "sunzheini1407" -Namespace "aegisai"

# 4. Verify deployment
kubectl get all -n aegisai
kubectl get pods -n aegisai --watch
```

### Workflow 5: Update Single Service

```powershell
# 1. Build and push single service
cd D:\Study\Projects\Github\AegisAI
docker build -f services/api-gateway-service/Dockerfile -t sunzheini1407/aegisai-api-gateway:latest .
docker push sunzheini1407/aegisai-api-gateway:latest

# 2. Update the deployment
kubectl rollout restart deployment/api-gateway -n aegisai

# 3. Check rollout status
kubectl rollout status deployment/api-gateway -n aegisai

# 4. Verify
kubectl get pods -n aegisai -l app=api-gateway
kubectl logs -n aegisai -l app=api-gateway --tail=50
```

### Workflow 6: Update Secrets and Restart Services

```powershell
# 1. Update secrets file
# Edit: D:\Study\Projects\Github\AegisAI\k8s\secrets\app-secrets.yaml

# 2. Apply updated secrets
kubectl apply -f D:\Study\Projects\Github\AegisAI\k8s\secrets\app-secrets.yaml

# 3. Restart all pods to pick up new secrets
kubectl delete pods -n aegisai -l app=validation-service; `
kubectl delete pods -n aegisai -l app=extract-metadata-service; `
kubectl delete pods -n aegisai -l app=extract-content-service; `
kubectl delete pods -n aegisai -l app=ai-service; `
kubectl delete pods -n aegisai -l app=api-gateway; `
kubectl delete pods -n aegisai -l app=workflow-orchestrator

# 4. Verify pods restarted
kubectl get pods -n aegisai
```

---

## 📊 MONITORING & HEALTH CHECKS

### Metrics Server (Required for HPA)

```powershell
# Check if Metrics Server is installed
kubectl get deployment metrics-server -n kube-system

# View metrics server pods
kubectl get pods -n kube-system | grep metrics-server

# Install Metrics Server (if needed)
# For Minikube:
minikube addons enable metrics-server

# For other clusters:
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

### Resource Usage

```powershell
# Check if all pods are ready
kubectl get pods -n aegisai -o wide

# Check deployment health
kubectl get deployments -n aegisai

# View cluster info
kubectl cluster-info

# View node status
kubectl get nodes

# Check resource usage (requires metrics-server)
kubectl top nodes
kubectl top pods -n aegisai

# Check pod health/readiness
kubectl get pods -n aegisai -o custom-columns=NAME:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].status

# View all events sorted by time
kubectl get events -n aegisai --sort-by=.metadata.creationTimestamp
```

---

## 🎯 USEFUL ONE-LINERS

```powershell
# Kill and restart all application pods
kubectl delete pods --all -n aegisai

# Get all pod names
kubectl get pods -n aegisai -o name

# Get pod IPs
kubectl get pods -n aegisai -o custom-columns=NAME:.metadata.name,IP:.status.podIP

# Check which pods are not ready
kubectl get pods -n aegisai --field-selector=status.phase!=Running

# Get logs from all pods with specific label
kubectl logs -n aegisai -l tier=gateway --tail=20

# Copy file from pod
kubectl cp aegisai/<pod-name>:/path/to/file ./local-file

# Copy file to pod
kubectl cp ./local-file aegisai/<pod-name>:/path/to/file

# Get YAML of running deployment
kubectl get deployment api-gateway -n aegisai -o yaml

# Edit deployment on the fly
kubectl edit deployment api-gateway -n aegisai
```

---

## 🔍 CONTEXT & NAMESPACE MANAGEMENT

```powershell
# View current context
kubectl config current-context

# View all contexts
kubectl config get-contexts

# Switch context
kubectl config use-context <context-name>

# Set default namespace for context
kubectl config set-context --current --namespace=aegisai

# View current namespace
kubectl config view --minify --output 'jsonpath={..namespace}'
```

---

## 📚 ADDITIONAL RESOURCES

- **Kubernetes Documentation**: https://kubernetes.io/docs/
- **kubectl Cheat Sheet**: https://kubernetes.io/docs/reference/kubectl/cheatsheet/
- **Docker Hub**: https://hub.docker.com/u/sunzheini1407

---

## 🚨 COMMON TROUBLESHOOTING SCENARIOS

### Issue 1: "ImagePullBackOff" or "ErrImagePull"

**Problem**: Pods show `ImagePullBackOff` status
```powershell
kubectl get pods -n aegisai
# NAME                            READY   STATUS             RESTARTS   AGE
# api-gateway-xxx                 0/1     ImagePullBackOff   0          2m
```

**Solution**:
```powershell
# 1. Check the exact error
kubectl describe pod <pod-name> -n aegisai

# 2. Rebuild and push the image
cd D:\Study\Projects\Github\AegisAI\k8s
.\build-images.ps1 -Registry "sunzheini1407" -Tag "latest" -Push

# 3. Delete the failing pod (it will recreate)
kubectl delete pod <pod-name> -n aegisai
```

### Issue 2: Deleted All Docker Images Locally

**Problem**: You ran `docker rmi` or cleaned Docker and lost all images

**Solution**:
```powershell
# Quick recovery - rebuild all from source
cd D:\Study\Projects\Github\AegisAI\k8s
.\build-images.ps1 -Registry "sunzheini1407" -Tag "latest" -Push

# Kubernetes will automatically pull when needed
# Or force immediate pull:
kubectl rollout restart deployment -n aegisai
```

### Issue 3: Images Deleted from Docker Hub

**Problem**: Someone deleted images from sunzheini1407 registry

**Solution**:
```powershell
# 1. Rebuild everything from source
cd D:\Study\Projects\Github\AegisAI\k8s
.\build-images.ps1 -Registry "sunzheini1407" -Tag "latest" -Push

# 2. Verify images are in Docker Hub
# Visit: https://hub.docker.com/u/sunzheini1407

# 3. Restart all deployments
kubectl rollout restart deployment -n aegisai
```

### Issue 4: Pod Stuck in "Pending" State

**Problem**: Pods won't start, stuck in Pending

**Solution**:
```powershell
# Check events to see why
kubectl describe pod <pod-name> -n aegisai

# Common reasons:
# - Insufficient resources: Check with `kubectl top nodes`
# - PVC not bound: Check with `kubectl get pvc -n aegisai`
# - Node selector issues: Check deployment YAML
```

### Issue 5: Want to Use Different Tag (Not "latest")

**Problem**: Need versioned releases (v1.0.0, v2.0.0, etc.)

**Solution**:
```powershell
# 1. Build with specific tag
cd D:\Study\Projects\Github\AegisAI\k8s
.\build-images.ps1 -Registry "sunzheini1407" -Tag "v1.0.0" -Push

# 2. Update deployment to use new tag
kubectl set image deployment/api-gateway api-gateway=sunzheini1407/aegisai-api-gateway:v1.0.0 -n aegisai

# 3. Or edit deployment file and reapply
# Edit: k8s/deployments/api-gateway.yaml
# Change: image: sunzheini1407/aegisai-api-gateway:v1.0.0
kubectl apply -f D:\Study\Projects\Github\AegisAI\k8s\deployments\api-gateway.yaml
```

### Issue 6: Service Not Responding After Deployment

**Problem**: Pods are running but service doesn't respond

**Solution**:
```powershell
# 1. Check if pods are actually ready
kubectl get pods -n aegisai

# 2. Check logs for errors
kubectl logs -n aegisai -l app=api-gateway --tail=50

# 3. Test service connectivity from debug pod
kubectl run debug -n aegisai --image=curlimages/curl:latest -it --rm -- curl http://api-gateway:8000/docs

# 4. Check service endpoints
kubectl get endpoints -n aegisai

# 5. Port-forward to test directly
kubectl port-forward -n aegisai service/api-gateway 8000:8000
# Then visit: http://localhost:8000/docs
```

### Issue 7: Out of Disk Space When Building

**Problem**: Docker build fails with "no space left on device"

**Solution**:
```powershell
# Clean up Docker to free space
docker system prune -a --volumes

# WARNING: This removes:
# - All stopped containers
# - All networks not used by at least one container
# - All images without at least one container associated
# - All build cache
# - All volumes not used by at least one container

# Then rebuild
cd D:\Study\Projects\Github\AegisAI\k8s
.\build-images.ps1 -Registry "sunzheini1407" -Tag "latest" -Push
```

### Issue 8: Need to Verify What Images Are in Registry

**Problem**: Unsure which images exist in Docker Hub

**Solution**:
```powershell
# Check Docker Hub via browser
start https://hub.docker.com/u/sunzheini1407/repositories

# Or list local images
docker images | grep aegisai

# Or check what Kubernetes is using
kubectl get pods -n aegisai -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].image}{"\n"}{end}'
```

---

## ⚠️ IMPORTANT NOTES

1. **Always verify** you're in the correct namespace before executing destructive commands
2. **Backup data** before deleting PVCs or namespaces
3. **Test changes** in development before applying to production
4. **Monitor logs** after deployments to catch issues early
5. **Use labels** to manage groups of pods efficiently
6. **Set resource limits** to prevent resource exhaustion
7. **Version your images** using tags instead of relying on `:latest`

---

**Last Updated**: November 19, 2025
**Namespace**: aegisai
**Registry**: sunzheini1407

