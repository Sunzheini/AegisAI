# Makefile for AegisAI Kubernetes Deployment

.PHONY: help build push deploy clean status logs shell

# Variables
REGISTRY ?= your-registry
NAMESPACE ?= aegisai
TAG ?= latest

# Service names
SERVICES = api-gateway workflow-orchestrator validation-service extract-metadata-service extract-content-service ai-service

help:
	@echo "AegisAI Kubernetes Deployment"
	@echo ""
	@echo "Available targets:"
	@echo "  build              - Build all Docker images"
	@echo "  push               - Push all Docker images to registry"
	@echo "  build-push         - Build and push all images"
	@echo "  deploy             - Deploy to Kubernetes"
	@echo "  deploy-infra       - Deploy only infrastructure (PostgreSQL, Redis)"
	@echo "  deploy-services    - Deploy only application services"
	@echo "  deploy-monitoring  - Deploy HPA and PDB"
	@echo "  update             - Update running deployments with new images"
	@echo "  status             - Show deployment status"
	@echo "  logs               - Show logs from all services"
	@echo "  clean              - Remove all Kubernetes resources"
	@echo "  shell              - Open shell in a pod"
	@echo ""
	@echo "Variables:"
	@echo "  REGISTRY=$(REGISTRY)"
	@echo "  NAMESPACE=$(NAMESPACE)"
	@echo "  TAG=$(TAG)"
	@echo ""
	@echo "Example: make build REGISTRY=myregistry.azurecr.io TAG=v1.0.0"

# Build all Docker images
build:
	@echo "Building Docker images..."
	@for service in $(SERVICES); do \
		echo "Building aegisai-$$service..."; \
		docker build -f services/$$service-service/Dockerfile \
			-t $(REGISTRY)/aegisai-$$service:$(TAG) .; \
	done
	@echo "Build complete!"

# Push all Docker images
push:
	@echo "Pushing Docker images..."
	@for service in $(SERVICES); do \
		echo "Pushing aegisai-$$service..."; \
		docker push $(REGISTRY)/aegisai-$$service:$(TAG); \
	done
	@echo "Push complete!"

# Build and push
build-push: build push

# Update image references in deployment files
update-refs:
	@echo "Updating image references to $(REGISTRY)..."
	@find k8s/deployments -name "*.yaml" -type f -exec sed -i '' "s|your-registry|$(REGISTRY)|g" {} \; || \
		find k8s/deployments -name "*.yaml" -type f -exec sed -i "s|your-registry|$(REGISTRY)|g" {} \;
	@find k8s/deployments -name "*.yaml" -type f -exec sed -i '' "s|:latest|:$(TAG)|g" {} \; || \
		find k8s/deployments -name "*.yaml" -type f -exec sed -i "s|:latest|:$(TAG)|g" {} \;

# Deploy everything to Kubernetes
deploy: update-refs
	@echo "Deploying to Kubernetes..."
	kubectl apply -f k8s/namespace.yaml
	kubectl apply -f k8s/volumes/persistent-volume.yaml
	kubectl apply -f k8s/configmaps/app-config.yaml
	kubectl apply -f k8s/secrets/app-secrets.yaml
	$(MAKE) deploy-infra
	@echo "Waiting for infrastructure to be ready..."
	kubectl wait --for=condition=ready pod -l app=postgres -n $(NAMESPACE) --timeout=120s || true
	kubectl wait --for=condition=ready pod -l app=redis -n $(NAMESPACE) --timeout=120s || true
	$(MAKE) deploy-services
	@echo "Deployment complete!"

# Deploy infrastructure only
deploy-infra:
	@echo "Deploying infrastructure..."
	kubectl apply -f k8s/services/postgres.yaml
	kubectl apply -f k8s/services/redis.yaml

# Deploy application services only
deploy-services:
	@echo "Deploying application services..."
	kubectl apply -f k8s/deployments/workflow-orchestrator.yaml
	kubectl apply -f k8s/deployments/api-gateway.yaml
	kubectl apply -f k8s/deployments/validation-service.yaml
	kubectl apply -f k8s/deployments/extract-metadata-service.yaml
	kubectl apply -f k8s/deployments/extract-content-service.yaml
	kubectl apply -f k8s/deployments/ai-service.yaml

# Deploy monitoring resources
deploy-monitoring:
	@echo "Deploying HPA and PDB..."
	kubectl apply -f k8s/hpa.yaml
	kubectl apply -f k8s/pdb.yaml

# Deploy ingress
deploy-ingress:
	@echo "Deploying Ingress..."
	kubectl apply -f k8s/ingress.yaml

# Deploy network policies
deploy-network-policies:
	@echo "Deploying Network Policies..."
	kubectl apply -f k8s/network-policies.yaml

# Update running deployments
update:
	@echo "Updating deployments..."
	@for service in $(SERVICES); do \
		echo "Updating aegisai-$$service..."; \
		kubectl set image deployment/$$service \
			$$service=$(REGISTRY)/aegisai-$$service:$(TAG) \
			-n $(NAMESPACE); \
	done
	@echo "Update complete!"

# Show deployment status
status:
	@echo "=== Namespace ==="
	@kubectl get namespace $(NAMESPACE) || echo "Namespace not found"
	@echo ""
	@echo "=== Persistent Volumes ==="
	@kubectl get pv | grep aegisai || echo "No PVs found"
	@echo ""
	@echo "=== Persistent Volume Claims ==="
	@kubectl get pvc -n $(NAMESPACE) || echo "No PVCs found"
	@echo ""
	@echo "=== Pods ==="
	@kubectl get pods -n $(NAMESPACE) -o wide || echo "No pods found"
	@echo ""
	@echo "=== Services ==="
	@kubectl get services -n $(NAMESPACE) || echo "No services found"
	@echo ""
	@echo "=== Deployments ==="
	@kubectl get deployments -n $(NAMESPACE) || echo "No deployments found"

# Show logs from all services
logs:
	@echo "Fetching logs..."
	@echo "=== API Gateway ==="
	@kubectl logs -n $(NAMESPACE) -l app=api-gateway --tail=20 || true
	@echo ""
	@echo "=== Workflow Orchestrator ==="
	@kubectl logs -n $(NAMESPACE) -l app=workflow-orchestrator --tail=20 || true

# Show logs for a specific service
logs-service:
	@read -p "Enter service name (api-gateway, workflow-orchestrator, etc.): " service; \
	kubectl logs -n $(NAMESPACE) -l app=$$service --tail=100 -f

# Open shell in a pod
shell:
	@read -p "Enter service name (api-gateway, workflow-orchestrator, etc.): " service; \
	pod=$$(kubectl get pod -n $(NAMESPACE) -l app=$$service -o jsonpath='{.items[0].metadata.name}'); \
	kubectl exec -it $$pod -n $(NAMESPACE) -- /bin/bash || \
	kubectl exec -it $$pod -n $(NAMESPACE) -- /bin/sh

# Restart a deployment
restart:
	@read -p "Enter service name (api-gateway, workflow-orchestrator, etc.): " service; \
	kubectl rollout restart deployment/$$service -n $(NAMESPACE)

# Scale a deployment
scale:
	@read -p "Enter service name: " service; \
	read -p "Enter number of replicas: " replicas; \
	kubectl scale deployment/$$service --replicas=$$replicas -n $(NAMESPACE)

# Clean up all resources
clean:
	@echo "Removing all Kubernetes resources..."
	@read -p "Are you sure you want to delete all resources in $(NAMESPACE)? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		kubectl delete namespace $(NAMESPACE) || true; \
		kubectl delete pv shared-storage-pv postgres-pv redis-pv || true; \
		echo "Cleanup complete!"; \
	else \
		echo "Cleanup cancelled."; \
	fi

# Port forward to a service
port-forward:
	@echo "Available services:"
	@echo "  1. api-gateway (8000)"
	@echo "  2. workflow-orchestrator (9000)"
	@echo "  3. postgres (5432)"
	@echo "  4. redis (6379)"
	@read -p "Enter service name: " service; \
	read -p "Enter local port (or press Enter for default): " local_port; \
	case $$service in \
		api-gateway) port=8000;; \
		workflow-orchestrator) port=9000;; \
		postgres) port=5432;; \
		redis) port=6379;; \
		*) port=8000;; \
	esac; \
	[ -z "$$local_port" ] && local_port=$$port; \
	echo "Port forwarding $$service:$$port to localhost:$$local_port"; \
	kubectl port-forward -n $(NAMESPACE) service/$$service $$local_port:$$port

# Describe a resource
describe:
	@read -p "Enter resource type (pod, deployment, service, etc.): " type; \
	read -p "Enter resource name: " name; \
	kubectl describe $$type/$$name -n $(NAMESPACE)

# Get events
events:
	@kubectl get events -n $(NAMESPACE) --sort-by='.lastTimestamp'

# Check health
health:
	@echo "Checking service health..."
	@for service in $(SERVICES); do \
		echo -n "$$service: "; \
		kubectl get deployment $$service -n $(NAMESPACE) -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' 2>/dev/null || echo "Not found"; \
		echo ""; \
	done

