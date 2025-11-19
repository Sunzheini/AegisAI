#!/bin/bash

# AegisAI Kubernetes Deployment Script (Bash version)
# This script automates the deployment of AegisAI to Kubernetes

set -e

# Default values
REGISTRY="${REGISTRY:-your-registry}"
NAMESPACE="aegisai"
BUILD_IMAGES=false
PUSH_IMAGES=false
DEPLOY=true

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --registry)
            REGISTRY="$2"
            shift 2
            ;;
        --build)
            BUILD_IMAGES=true
            shift
            ;;
        --push)
            PUSH_IMAGES=true
            shift
            ;;
        --no-deploy)
            DEPLOY=false
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--registry <registry>] [--build] [--push] [--no-deploy]"
            exit 1
            ;;
    esac
done

echo "=== AegisAI Kubernetes Deployment ==="
echo "Registry: $REGISTRY"
echo "Namespace: $NAMESPACE"
echo ""

# Services to build and deploy
SERVICES=(
    "api-gateway"
    "workflow-orchestrator"
    "validation-service"
    "extract-metadata-service"
    "extract-content-service"
    "ai-service"
)

# Build Docker images
if [ "$BUILD_IMAGES" = true ]; then
    echo "Building Docker images..."

    for service in "${SERVICES[@]}"; do
        image_name="aegisai-$service"
        dockerfile_path="services/${service}-service/Dockerfile"

        echo "  Building $image_name..."
        docker build -f "$dockerfile_path" -t "${REGISTRY}/${image_name}:latest" .
    done

    echo "All images built successfully!"
    echo ""
fi

# Push Docker images
if [ "$PUSH_IMAGES" = true ]; then
    echo "Pushing Docker images to registry..."

    for service in "${SERVICES[@]}"; do
        image_name="aegisai-$service"

        echo "  Pushing $image_name..."
        docker push "${REGISTRY}/${image_name}:latest"
    done

    echo "All images pushed successfully!"
    echo ""
fi

# Deploy to Kubernetes
if [ "$DEPLOY" = true ]; then
    echo "Deploying to Kubernetes..."

    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        echo "Error: kubectl is not installed or not in PATH"
        exit 1
    fi

    # Update image references in deployment files
    echo "  Updating image references..."
    find k8s/deployments -name "*.yaml" -type f -exec sed -i "s|your-registry|${REGISTRY}|g" {} \;

    # 1. Create namespace
    echo "  Creating namespace..."
    kubectl apply -f k8s/namespace.yaml

    # 2. Create persistent volumes
    echo "  Creating persistent volumes..."
    kubectl apply -f k8s/volumes/persistent-volume.yaml

    # 3. Create ConfigMaps and Secrets
    echo "  Creating ConfigMaps and Secrets..."
    kubectl apply -f k8s/configmaps/app-config.yaml
    kubectl apply -f k8s/secrets/app-secrets.yaml

    # 4. Deploy infrastructure
    echo "  Deploying PostgreSQL..."
    kubectl apply -f k8s/services/postgres.yaml

    echo "  Deploying Redis..."
    kubectl apply -f k8s/services/redis.yaml

    # Wait for infrastructure to be ready
    echo "  Waiting for PostgreSQL to be ready..."
    kubectl wait --for=condition=ready pod -l app=postgres -n "$NAMESPACE" --timeout=120s

    echo "  Waiting for Redis to be ready..."
    kubectl wait --for=condition=ready pod -l app=redis -n "$NAMESPACE" --timeout=120s

    # 5. Deploy workflow orchestrator
    echo "  Deploying Workflow Orchestrator..."
    kubectl apply -f k8s/deployments/workflow-orchestrator.yaml

    # 6. Deploy API Gateway
    echo "  Deploying API Gateway..."
    kubectl apply -f k8s/deployments/api-gateway.yaml

    # 7. Deploy worker services
    echo "  Deploying Validation Service..."
    kubectl apply -f k8s/deployments/validation-service.yaml

    echo "  Deploying Extract Metadata Service..."
    kubectl apply -f k8s/deployments/extract-metadata-service.yaml

    echo "  Deploying Extract Content Service..."
    kubectl apply -f k8s/deployments/extract-content-service.yaml

    echo "  Deploying AI Service..."
    kubectl apply -f k8s/deployments/ai-service.yaml

    echo ""
    echo "Deployment complete!"
    echo ""

    # Display status
    echo "=== Deployment Status ==="
    echo ""

    echo "Pods:"
    kubectl get pods -n "$NAMESPACE"

    echo ""
    echo "Services:"
    kubectl get services -n "$NAMESPACE"

    echo ""
    echo "Persistent Volume Claims:"
    kubectl get pvc -n "$NAMESPACE"

    echo ""
    echo "=== Access Information ==="
    echo "To view logs:"
    echo "  kubectl logs -n $NAMESPACE -l app=api-gateway --tail=50"
    echo ""
fi

echo "Script completed successfully!"

