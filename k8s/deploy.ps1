# AegisAI Kubernetes Deployment Script
Write-Host "Script completed successfully!" -ForegroundColor Green

}
    Write-Host ""
    Write-Host "  kubectl logs -n $Namespace -l app=api-gateway --tail=50" -ForegroundColor Yellow
    Write-Host "To view logs:" -ForegroundColor Cyan
    Write-Host ""

    }
        Write-Host "  http://<node-ip>:$nodePort" -ForegroundColor Yellow
        Write-Host "API Gateway is available at:" -ForegroundColor Green
        $nodePort = $apiGatewayService.spec.ports[0].nodePort
    } elseif ($apiGatewayService.spec.type -eq "NodePort") {
        Write-Host "  Run: kubectl get service api-gateway -n $Namespace -w" -ForegroundColor Yellow
        Write-Host "  Waiting for external IP..." -ForegroundColor Yellow
        Write-Host "API Gateway will be available at:" -ForegroundColor Green
    if ($apiGatewayService.spec.type -eq "LoadBalancer") {

    $apiGatewayService = kubectl get service api-gateway -n $Namespace -o json | ConvertFrom-Json
    Write-Host "=== Access Information ===" -ForegroundColor Cyan
    Write-Host ""

    kubectl get pvc -n $Namespace
    Write-Host "Persistent Volume Claims:" -ForegroundColor Yellow
    Write-Host ""

    kubectl get services -n $Namespace
    Write-Host "Services:" -ForegroundColor Yellow
    Write-Host ""

    kubectl get pods -n $Namespace
    Write-Host "Pods:" -ForegroundColor Yellow

    Write-Host ""
    Write-Host "=== Deployment Status ===" -ForegroundColor Cyan
    # Display status

    Write-Host ""
    Write-Host "Deployment complete!" -ForegroundColor Green
    Write-Host ""

    kubectl apply -f k8s/deployments/ai-service.yaml
    Write-Host "  Deploying AI Service..." -ForegroundColor Yellow

    kubectl apply -f k8s/deployments/extract-content-service.yaml
    Write-Host "  Deploying Extract Content Service..." -ForegroundColor Yellow

    kubectl apply -f k8s/deployments/extract-metadata-service.yaml
    Write-Host "  Deploying Extract Metadata Service..." -ForegroundColor Yellow

    kubectl apply -f k8s/deployments/validation-service.yaml
    Write-Host "  Deploying Validation Service..." -ForegroundColor Yellow
    # 7. Deploy worker services

    kubectl apply -f k8s/deployments/api-gateway.yaml
    Write-Host "  Deploying API Gateway..." -ForegroundColor Yellow
    # 6. Deploy API Gateway

    kubectl apply -f k8s/deployments/workflow-orchestrator.yaml
    Write-Host "  Deploying Workflow Orchestrator..." -ForegroundColor Yellow
    # 5. Deploy workflow orchestrator

    kubectl wait --for=condition=ready pod -l app=redis -n $Namespace --timeout=120s
    Write-Host "  Waiting for Redis to be ready..." -ForegroundColor Yellow

    kubectl wait --for=condition=ready pod -l app=postgres -n $Namespace --timeout=120s
    Write-Host "  Waiting for PostgreSQL to be ready..." -ForegroundColor Yellow
    # Wait for infrastructure to be ready

    kubectl apply -f k8s/services/redis.yaml
    Write-Host "  Deploying Redis..." -ForegroundColor Yellow

    kubectl apply -f k8s/services/postgres.yaml
    Write-Host "  Deploying PostgreSQL..." -ForegroundColor Yellow
    # 4. Deploy infrastructure

    kubectl apply -f k8s/secrets/app-secrets.yaml
    kubectl apply -f k8s/configmaps/app-config.yaml
    Write-Host "  Creating ConfigMaps and Secrets..." -ForegroundColor Yellow
    # 3. Create ConfigMaps and Secrets

    kubectl apply -f k8s/volumes/persistent-volume.yaml
    Write-Host "  Creating persistent volumes..." -ForegroundColor Yellow
    # 2. Create persistent volumes

    kubectl apply -f k8s/namespace.yaml
    Write-Host "  Creating namespace..." -ForegroundColor Yellow
    # 1. Create namespace

    }
        Set-Content $_.FullName -Value $content
        $content = $content -replace 'your-registry', $Registry
        $content = Get-Content $_.FullName -Raw
    Get-ChildItem -Path "k8s/deployments/*.yaml" | ForEach-Object {
    Write-Host "  Updating image references..." -ForegroundColor Yellow
    # Update image references in deployment files

    }
        exit 1
        Write-Error "kubectl is not installed or not in PATH"
    } catch {
        kubectl version --client | Out-Null
    try {
    # Check if kubectl is available

    Write-Host "Deploying to Kubernetes..." -ForegroundColor Green
if ($Deploy) {
# Deploy to Kubernetes

}
    Write-Host ""
    Write-Host "All images pushed successfully!" -ForegroundColor Green

    }
        }
            exit 1
            Write-Error "Failed to push $imageName"
        if ($LASTEXITCODE -ne 0) {

        docker push "${Registry}/${imageName}:latest"
        Write-Host "  Pushing $imageName..." -ForegroundColor Yellow

        $imageName = "aegisai-$service"
    foreach ($service in $services) {

    Write-Host "Pushing Docker images to registry..." -ForegroundColor Green
if ($PushImages) {
# Push Docker images

}
    Write-Host ""
    Write-Host "All images built successfully!" -ForegroundColor Green

    }
        }
            exit 1
            Write-Error "Failed to build $imageName"
        if ($LASTEXITCODE -ne 0) {

        docker build -f $dockerfilePath -t "${Registry}/${imageName}:latest" .
        Write-Host "  Building $imageName..." -ForegroundColor Yellow

        $dockerfilePath = "services/$service-service/Dockerfile"
        $imageName = "aegisai-$service"
    foreach ($service in $services) {

    Write-Host "Building Docker images..." -ForegroundColor Green
if ($BuildImages) {
# Build Docker images

)
    "ai-service"
    "extract-content-service",
    "extract-metadata-service",
    "validation-service",
    "workflow-orchestrator",
    "api-gateway",
$services = @(
# Services to build and deploy

Write-Host ""
Write-Host "Namespace: $Namespace" -ForegroundColor Yellow
Write-Host "Registry: $Registry" -ForegroundColor Yellow
Write-Host "=== AegisAI Kubernetes Deployment ===" -ForegroundColor Cyan

$ErrorActionPreference = "Stop"

)
    [string]$Namespace = "aegisai"
    [Parameter(Mandatory=$false)]

    [switch]$Deploy = $true,
    [Parameter(Mandatory=$false)]

    [switch]$PushImages = $false,
    [Parameter(Mandatory=$false)]

    [switch]$BuildImages = $false,
    [Parameter(Mandatory=$false)]

    [string]$Registry = "your-registry",
    [Parameter(Mandatory=$false)]
param(

# This script automates the deployment of AegisAI to Kubernetes

