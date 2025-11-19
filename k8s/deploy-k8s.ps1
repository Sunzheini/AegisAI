# AegisAI Kubernetes Deployment Script
# Usage: .\deploy.ps1 [-Registry "sunzheini1407"]

param(
    [Parameter(Mandatory=$false)]
    [string]$Registry = "sunzheini1407",

    [Parameter(Mandatory=$false)]
    [string]$Namespace = "aegisai"
)

$ErrorActionPreference = "Stop"

Write-Host "=== AegisAI Kubernetes Deployment ===" -ForegroundColor Cyan
Write-Host "Registry: $Registry" -ForegroundColor Yellow
Write-Host "Namespace: $Namespace" -ForegroundColor Yellow
Write-Host ""

# Check if kubectl is available
try {
    kubectl version --client | Out-Null
} catch {
    Write-Error "kubectl is not installed or not in PATH"
    exit 1
}

# Navigate to k8s directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

# Update image references in deployment files
Write-Host "Updating image references..." -ForegroundColor Yellow
Get-ChildItem -Path "deployments/*.yaml" | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    $content = $content -replace 'your-registry', $Registry
    Set-Content $_.FullName -Value $content
}

Write-Host ""
Write-Host "Deploying to Kubernetes..." -ForegroundColor Green

# 1. Create namespace
Write-Host "  [1/8] Creating namespace..." -ForegroundColor Cyan
kubectl apply -f namespace.yaml

# 2. Create persistent volumes
Write-Host "  [2/8] Creating persistent volumes..." -ForegroundColor Cyan
kubectl apply -f volumes/persistent-volume.yaml

# 3. Create ConfigMaps and Secrets
Write-Host "  [3/8] Creating ConfigMaps and Secrets..." -ForegroundColor Cyan
kubectl apply -f configmaps/app-config.yaml
kubectl apply -f secrets/app-secrets.yaml

# 4. Deploy infrastructure
Write-Host "  [4/8] Deploying PostgreSQL..." -ForegroundColor Cyan
kubectl apply -f services/postgres.yaml

Write-Host "  [5/8] Deploying Redis..." -ForegroundColor Cyan
kubectl apply -f services/redis.yaml

# Wait for infrastructure to be ready
Write-Host "  [6/8] Waiting for infrastructure..." -ForegroundColor Cyan
Write-Host "      Waiting for PostgreSQL..." -ForegroundColor Gray
kubectl wait --for=condition=ready pod -l app=postgres -n $Namespace --timeout=120s 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "      PostgreSQL not ready yet (continuing anyway)" -ForegroundColor Yellow
}

Write-Host "      Waiting for Redis..." -ForegroundColor Gray
kubectl wait --for=condition=ready pod -l app=redis -n $Namespace --timeout=120s 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "      Redis not ready yet (continuing anyway)" -ForegroundColor Yellow
}

# 5. Deploy application services
Write-Host "  [7/8] Deploying application services..." -ForegroundColor Cyan
kubectl apply -f deployments/workflow-orchestrator.yaml
kubectl apply -f deployments/api-gateway.yaml
kubectl apply -f deployments/validation-service.yaml
kubectl apply -f deployments/extract-metadata-service.yaml
kubectl apply -f deployments/extract-content-service.yaml
kubectl apply -f deployments/ai-service.yaml

Write-Host "  [8/8] Deployment complete!" -ForegroundColor Green
Write-Host ""

# Display status
Write-Host "=== Deployment Status ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "Pods:" -ForegroundColor Yellow
kubectl get pods -n $Namespace

Write-Host ""
Write-Host "Services:" -ForegroundColor Yellow
kubectl get services -n $Namespace

Write-Host ""
Write-Host "Persistent Volume Claims:" -ForegroundColor Yellow
kubectl get pvc -n $Namespace

Write-Host ""
Write-Host "=== Next Steps ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Check pod status:" -ForegroundColor Yellow
Write-Host "   kubectl get pods -n $Namespace -w" -ForegroundColor Gray
Write-Host ""
Write-Host "2. View logs:" -ForegroundColor Yellow
Write-Host "   kubectl logs -n $Namespace -l app=api-gateway --tail=50" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Access API Gateway:" -ForegroundColor Yellow
Write-Host "   kubectl port-forward -n $Namespace service/api-gateway 8000:8000" -ForegroundColor Gray
Write-Host "   Then open: http://localhost:8000" -ForegroundColor Gray
Write-Host ""

Write-Host "Deployment script completed successfully!" -ForegroundColor Green

