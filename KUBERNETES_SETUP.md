# AegisAI Kubernetes Deployment
Complete Kubernetes deployment for the AegisAI microservices platform.


## 📁 Deployment Files Location
All Kubernetes configuration and deployment files are in the **`k8s/`** directory.

```
k8s/
├── DEPLOYMENT_GUIDE.md          ⭐ START HERE - Complete deployment guide
├── README.md                    📋 Quick reference and file index
├── ARCHITECTURE.md              🏗️ System architecture
├── HPA_FIX.md                   📊 Autoscaling guide
├── deployments/                 🚀 Microservice deployments
├── services/                    🏗️ Infrastructure (PostgreSQL, Redis)
├── configmaps/                  ⚙️ Configuration
├── secrets/                     🔐 Secrets (update before deploying!)
├── volumes/                     💾 Storage
├── build-images.ps1             🐋 Build Docker images
└── deploy-k8s.ps1              ☸️ Deploy to Kubernetes
```


## Start
### Prerequisites
- Kubernetes cluster (Minikube, Docker Desktop, or cloud provider)
- kubectl installed and configured
- Docker installed
- Docker Hub account (free)

### Deploy in 6 Steps
1. Login to Docker Hub
   ```powershell
   docker login
   ```

2. Build and Push Images
   ```powershell
   cd k8s
   .\build-images.ps1 -Registry "sunzheini1407" -Tag "latest" -Push
   ```

3. Update Secrets
    ```powershell
    # 1. Edit secrets file
    # Edit: D:\Study\Projects\Github\AegisAI\k8s\secrets\app-secrets.yaml with the latest base64-encoded secrets
    
    # 2. Apply updated secrets
    kubectl apply -f D:\Study\Projects\Github\AegisAI\k8s\secrets\app-secrets.yaml
    
    # 3. Restart pods to pick up new secrets
    kubectl delete pods --all -n aegisai
    ```

4. Deploy to Kubernetes
   ```powershell
   .\deploy-k8s.ps1 -Registry "sunzheini1407"
   ```
   
5. Apply autoscaling
    ```powershell
   kubectl apply -f hpa.yaml
   kubectl apply -f pdb.yaml
   ```

6. Verify Deployment
   ```powershell
   kubectl get pods -n aegisai
   ```

7. Port Forwarding to Access Application
   ```powershell
   kubectl port-forward -n aegisai service/api-gateway 8000:8000 
   kubectl port-forward -n aegisai svc/workflow-orchestrator 9000:9000
   kubectl port-forward -n aegisai svc/ai-service 9004:9004
   
   use the frontend
   ```
   
8. Update: after code changes
   ```powershell
   .\build-images.ps1 -Registry "sunzheini1407" -Push
   kubectl rollout restart deployment -n aegisai
   ```

9. Monitor and Access
    ```powershell
    # Check status
    kubectl get pods -n aegisai
    
    # View logs
    kubectl logs -n aegisai -l app=api-gateway --tail=50
    
    # Check autoscaling
    kubectl get hpa -n aegisai
    ```
   
10. Scale Services
    ```powershell
    # Manual scaling
    kubectl scale deployment/api-gateway -n aegisai --replicas=3
    kubectl scale deployment/workflow-orchestrator -n aegisai --replicas=2
    
    # View autoscaling status (if HPA is enabled)
    kubectl get hpa -n aegisai
    ```

11. Cleanup
    ```powershell
    # Delete everything
    kubectl delete namespace aegisai
    ```
