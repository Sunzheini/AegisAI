# AWS EKS Deployment Guide for AegisAI

This guide walks through deploying the AegisAI microservices platform to AWS EKS (Elastic Kubernetes Service).

## Prerequisites

- AWS CLI installed and configured
- kubectl installed
- eksctl installed
- Docker installed (for building images)
- AWS Account with appropriate permissions
- PowerShell (for Windows commands)

---

## Step 1: Install eksctl (if not already installed)

```powershell
choco install -y eksctl
```

**Explanation:** eksctl is a CLI tool for creating and managing EKS clusters. It automates many complex AWS operations.

---

## Step 2: Configure AWS Credentials

```powershell
aws configure
```

**What to enter:**
- AWS Access Key ID
- AWS Secret Access Key
- Default region: `eu-central-1`
- Default output format: `json` (or press Enter for default)

**Explanation:** This configures the AWS CLI with your credentials so it can interact with AWS services.

---

## Step 3: Get Your AWS Account ID

```powershell
aws sts get-caller-identity --query Account --output text
```

**Expected Output:** `519887759051` (your account ID)

**Explanation:** You'll need this account ID for IAM role ARNs in later steps. Save this value.

```powershell
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)
Write-Host "Your AWS Account ID is: $ACCOUNT_ID" -ForegroundColor Green
```

---

## Step 4: Build and Push Docker Images to ECR

**IMPORTANT:** Before deploying to EKS, you need to push your Docker images to AWS Elastic Container Registry (ECR).

### 4.1: Create ECR Repositories

```powershell
# Create ECR repositories for each service
aws ecr create-repository --repository-name aegisai/api-gateway --region eu-central-1
aws ecr create-repository --repository-name aegisai/workflow-orchestrator --region eu-central-1
aws ecr create-repository --repository-name aegisai/validation-service --region eu-central-1
aws ecr create-repository --repository-name aegisai/extract-metadata-service --region eu-central-1
aws ecr create-repository --repository-name aegisai/extract-content-service --region eu-central-1
aws ecr create-repository --repository-name aegisai/ai-service --region eu-central-1
```

**Explanation:** ECR is AWS's Docker container registry. Each microservice needs its own repository.

### 4.2: Authenticate Docker to ECR

```powershell
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.eu-central-1.amazonaws.com
```

**Explanation:** This logs Docker into your ECR registry so you can push images.

### 4.3: Build and Push Images

```powershell
# Navigate to project root
cd D:\Study\Projects\Github\AegisAI

# Build and push each service
$services = @(
    "api-gateway-service",
    "workflow-orchestrator-service",
    "validation-service",
    "extract-metadata-service",
    "extract-content-service",
    "ai-service"
)

foreach ($service in $services) {
    $imageName = $service -replace "-service", ""
    Write-Host "Building $service..." -ForegroundColor Cyan
    
    docker build -t aegisai/$imageName ./services/$service
    docker tag aegisai/$imageName:latest $ACCOUNT_ID.dkr.ecr.eu-central-1.amazonaws.com/aegisai/$imageName:latest
    docker push $ACCOUNT_ID.dkr.ecr.eu-central-1.amazonaws.com/aegisai/$imageName:latest
}
```

**Explanation:** This builds Docker images locally and pushes them to ECR where EKS can pull them.

### 4.4: Update Kubernetes Deployment Files

Update all deployment YAML files in `k8s/deployments/` to use ECR image paths:

```powershell
# Update image references in deployment files
$deploymentFiles = Get-ChildItem -Path k8s/deployments/*.yaml

foreach ($file in $deploymentFiles) {
    $content = Get-Content $file.FullName -Raw
    # Replace local image references with ECR paths
    $content = $content -replace 'image: aegisai/', "image: $ACCOUNT_ID.dkr.ecr.eu-central-1.amazonaws.com/aegisai/"
    Set-Content -Path $file.FullName -Value $content
}
```

---

## Step 5: Create EKS Cluster

```powershell
eksctl create cluster --name aegisai-cluster --region eu-central-1 --node-type t3.small --nodes 2 --with-oidc
```

**Explanation:** 
- Creates an EKS cluster named "aegisai-cluster"
- Uses t3.small EC2 instances (2 vCPU, 2GB RAM each)
- Starts with 2 worker nodes
- `--with-oidc` enables IAM roles for service accounts (needed for EBS/EFS)

**Duration:** ~15-20 minutes

**What happens:**
- Creates VPC with subnets
- Sets up security groups
- Provisions EC2 worker nodes
- Configures kubectl context automatically

---

## Step 6: Set Up EBS CSI Driver (for Block Storage)

### 6.1: Create IAM Service Account for EBS CSI Driver

```powershell
eksctl create iamserviceaccount `
  --name ebs-csi-controller-sa `
  --namespace kube-system `
  --cluster aegisai-cluster `
  --region eu-central-1 `
  --attach-policy-arn arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy `
  --approve `
  --role-only `
  --role-name AmazonEKS_EBS_CSI_DriverRole
```

**Explanation:** 
- Creates an IAM role with permissions to manage EBS volumes
- EBS (Elastic Block Store) provides persistent block storage for databases like PostgreSQL

### 6.2: Install EBS CSI Driver Addon

```powershell
eksctl create addon `
  --name aws-ebs-csi-driver `
  --cluster aegisai-cluster `
  --region eu-central-1 `
  --service-account-role-arn arn:aws:iam::${ACCOUNT_ID}:role/AmazonEKS_EBS_CSI_DriverRole `
  --force
```

**Explanation:** Installs the EBS CSI driver as an EKS addon, allowing Kubernetes to provision EBS volumes dynamically.

---

## Step 7: Set Up EFS (Elastic File System) for Shared Storage

### 7.1: Create EFS Filesystem

```powershell
Write-Host "Creating EFS filesystem..." -ForegroundColor Cyan

$EFS_ID = (aws efs create-file-system `
  --region eu-central-1 `
  --performance-mode generalPurpose `
  --encrypted `
  --tags Key=Name,Value=aegisai-shared-storage `
  --query FileSystemId `
  --output text)

Write-Host "Your EFS ID is: $EFS_ID" -ForegroundColor Green
```

**Expected Output:** `fs-0b2e30d4135cc1785` (your EFS ID)

**Explanation:** 
- Creates an encrypted EFS filesystem for shared storage across pods
- `generalPurpose` mode is suitable for most workloads
- This is used for the shared media processing storage

### 7.2: Get VPC Information

```powershell
# Get VPC ID created by EKS
$VPC_ID = (aws eks describe-cluster `
  --name aegisai-cluster `
  --region eu-central-1 `
  --query "cluster.resourcesVpcConfig.vpcId" `
  --output text)

Write-Host "VPC ID: $VPC_ID" -ForegroundColor Green

# Get all subnet IDs in the VPC
$SUBNET_IDS = (aws ec2 describe-subnets `
  --filters "Name=vpc-id,Values=$VPC_ID" `
  --query "Subnets[*].SubnetId" `
  --output text)

Write-Host "Subnet IDs: $SUBNET_IDS" -ForegroundColor Green

# Get VPC CIDR block
$VPC_CIDR = (aws ec2 describe-vpcs `
  --vpc-ids $VPC_ID `
  --query "Vpcs[0].CidrBlock" `
  --output text)

Write-Host "VPC CIDR: $VPC_CIDR" -ForegroundColor Green
```

**Explanation:** 
- Retrieves networking information from the EKS cluster
- Needed to configure EFS mount targets and security groups

### 7.3: Create Security Group for EFS

```powershell
# Create security group
$SG_ID = (aws ec2 create-security-group `
  --group-name aegisai-efs-sg `
  --description "EFS for AegisAI" `
  --vpc-id $VPC_ID `
  --query GroupId `
  --output text)

Write-Host "Security Group ID: $SG_ID" -ForegroundColor Green

# Allow NFS traffic (port 2049) from VPC
aws ec2 authorize-security-group-ingress `
  --group-id $SG_ID `
  --protocol tcp `
  --port 2049 `
  --cidr $VPC_CIDR
```

**Explanation:** 
- Creates a security group allowing NFS traffic on port 2049
- Only allows traffic from within the VPC for security
- Press 'q' to exit the output if it opens in a pager

### 7.4: Create EFS Mount Targets

```powershell
Write-Host "Creating EFS mount targets in all subnets..." -ForegroundColor Cyan

foreach ($subnet in $SUBNET_IDS.Split()) {
    if ($subnet.Trim()) {
        Write-Host "Creating mount target in subnet: $subnet" -ForegroundColor Yellow
        aws efs create-mount-target `
          --file-system-id $EFS_ID `
          --subnet-id $subnet.Trim() `
          --security-groups $SG_ID
    }
}

Write-Host "Waiting 60 seconds for mount targets to become available..." -ForegroundColor Yellow
Start-Sleep -Seconds 60
```

**Explanation:** 
- Creates mount targets in each subnet so pods can access EFS from any availability zone
- Wait time ensures mount targets are ready before proceeding

---

## Step 8: Install EFS CSI Driver

### 8.1: Install EFS CSI Driver

```powershell
kubectl apply -k "github.com/kubernetes-sigs/aws-efs-csi-driver/deploy/kubernetes/overlays/stable/?ref=release-1.7"
```

**Explanation:** Installs the EFS CSI driver in your cluster, enabling Kubernetes to use EFS volumes.

### 8.2: Verify EFS CSI Driver Installation

```powershell
kubectl get pods -n kube-system | Select-String "efs"
```

**Expected Output:** Should show `efs-csi-controller` and `efs-csi-node` pods running.

---

## Step 9: Configure Storage Classes and Persistent Volumes

### 9.1: Update Storage Classes with Your EFS ID

```powershell
(Get-Content k8s\eks\storage-classes.yaml) -replace 'fileSystemId: fs-XXXXXXXXX', "fileSystemId: $EFS_ID" | Set-Content k8s\eks\storage-classes.yaml
```

**Explanation:** Updates the storage class configuration with your actual EFS filesystem ID.

### 9.2: Apply Storage Configuration

```powershell
cd D:\Study\Projects\Github\AegisAI

# Create namespace
kubectl apply -f k8s/namespace.yaml

# Apply storage classes
kubectl apply -f k8s/eks/storage-classes.yaml

# Apply persistent volumes
kubectl apply -f k8s/eks/persistent-volumes-eks.yaml
```

**Explanation:** 
- Creates the `aegisai` namespace
- Sets up storage classes for EBS (gp3) and EFS
- Creates persistent volumes for shared storage

---

## Step 10: Deploy Configuration and Secrets

```powershell
# Apply secrets (passwords, API keys, etc.)
kubectl apply -f k8s/secrets/app-secrets.yaml

# Apply config maps (application configuration)
kubectl apply -f k8s/configmaps/app-config.yaml
kubectl apply -f k8s/configmaps/postgres-init.yaml
```

**Explanation:** 
- Secrets: Stores sensitive data like database passwords, AWS credentials
- ConfigMaps: Stores non-sensitive configuration like environment variables

**IMPORTANT:** Make sure `app-secrets.yaml` contains base64-encoded values for all secrets.

---

## Step 11: Deploy Database and Cache Services

```powershell
# Deploy PostgreSQL database
kubectl apply -f k8s/services/postgres.yaml

# Deploy Redis cache
kubectl apply -f k8s/services/redis.yaml

# Wait for databases to be ready
Write-Host "Waiting 30 seconds for databases to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Check database pods
kubectl get pods -n aegisai
```

**Explanation:** 
- PostgreSQL: Primary database for storing metadata, workflow state
- Redis: In-memory cache and message broker for Celery (if used)

**Expected:** Both pods should show `Running` status.

---

## Step 12: Deploy Application Services

```powershell
# Deploy all microservices
kubectl apply -f k8s/deployments/api-gateway.yaml
kubectl apply -f k8s/deployments/workflow-orchestrator.yaml
kubectl apply -f k8s/deployments/validation-service.yaml
kubectl apply -f k8s/deployments/extract-metadata-service.yaml
kubectl apply -f k8s/deployments/extract-content-service.yaml
kubectl apply -f k8s/deployments/ai-service.yaml

Write-Host "Waiting for pods to start..." -ForegroundColor Yellow
```

**Explanation:** Deploys all 6 microservices that make up the AegisAI platform.

---

## Step 13: Configure Auto-Scaling and High Availability

```powershell
# Apply Horizontal Pod Autoscaler (scales pods based on CPU/memory)
kubectl apply -f k8s/hpa.yaml

# Apply Pod Disruption Budget (ensures availability during updates)
kubectl apply -f k8s/pdb.yaml
```

**Explanation:** 
- HPA: Automatically scales pods up/down based on resource usage
- PDB: Ensures minimum number of pods stay running during disruptions

---

## Step 14: Verify Deployment

### 14.1: Check All Pods

```powershell
kubectl get pods -n aegisai
```

**Expected Output:** All pods should show `Running` status and `1/1` or `2/2` ready.

**If pods are not ready:**
```powershell
# Check specific pod logs
kubectl logs -n aegisai <pod-name>

# Describe pod for events
kubectl describe pod -n aegisai <pod-name>
```

### 14.2: Check Services

```powershell
kubectl get svc -n aegisai
```

**Explanation:** Shows all services and their external IPs/hostnames.

### 14.3: Get Load Balancer URL

```powershell
# Get the API Gateway LoadBalancer URL
$LB_URL = (kubectl get svc api-gateway -n aegisai -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
Write-Host "API Gateway URL: http://$LB_URL:8000" -ForegroundColor Green
```

**Note:** Your previous URL was: `http://a82c56439d26f40fa93ca7822cc734fb-704687242.eu-central-1.elb.amazonaws.com:8000`

### 14.4: Test Health Endpoint

```powershell
# Wait for load balancer to be ready (can take 2-3 minutes)
Write-Host "Waiting for load balancer to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 120

# Test health endpoint
curl http://$LB_URL:8000/health

# Or open in browser
start http://$LB_URL:8000/health
```

**Expected Response:** `{"status":"healthy"}` or similar.

### 14.5: Test File Upload

```powershell
# Test uploading a file
$testFile = "D:\Study\Projects\Github\AegisAI\files_for_testing\pdf_files\ATmega32A.pdf"

curl -X POST http://$LB_URL:8000/upload `
  -F "file=@$testFile" `
  -F "user_id=test-user"
```

---

## Step 15: Monitor and Troubleshoot

### View Logs

```powershell
# Tail logs from a specific service
kubectl logs -f -n aegisai deployment/api-gateway

# View logs from all pods with a label
kubectl logs -n aegisai -l app=api-gateway --tail=100
```

### Get Resource Usage

```powershell
# Check resource usage
kubectl top nodes
kubectl top pods -n aegisai
```

### Access Pod Shell

```powershell
# Get a shell in a pod for debugging
kubectl exec -it -n aegisai <pod-name> -- /bin/bash
```

### Check Events

```powershell
# View cluster events
kubectl get events -n aegisai --sort-by='.lastTimestamp'
```

---

## Step 16: Cleanup and Delete Resources

### Delete Cluster (and all resources)

```powershell
# This deletes EVERYTHING
eksctl delete cluster --name aegisai-cluster --region eu-central-1
```

**Explanation:** 
- Deletes the entire EKS cluster, worker nodes, and associated resources
- Load balancers and volumes are also deleted
- **Duration:** ~10-15 minutes

### Manual Cleanup (if needed)

```powershell
# Delete EFS filesystem (if it wasn't automatically deleted)
# First, delete all mount targets
$MOUNT_TARGETS = (aws efs describe-mount-targets --file-system-id $EFS_ID --region eu-central-1 --query 'MountTargets[*].MountTargetId' --output text)
foreach ($mt in $MOUNT_TARGETS.Split()) {
    if ($mt.Trim()) {
        aws efs delete-mount-target --mount-target-id $mt.Trim() --region eu-central-1
    }
}

# Wait for mount targets to be deleted
Start-Sleep -Seconds 30

# Delete the filesystem
aws efs delete-file-system --file-system-id $EFS_ID --region eu-central-1

# Delete security group
aws ec2 delete-security-group --group-id $SG_ID --region eu-central-1

# Delete ECR repositories (if you want to remove images)
aws ecr delete-repository --repository-name aegisai/api-gateway --region eu-central-1 --force
aws ecr delete-repository --repository-name aegisai/workflow-orchestrator --region eu-central-1 --force
aws ecr delete-repository --repository-name aegisai/validation-service --region eu-central-1 --force
aws ecr delete-repository --repository-name aegisai/extract-metadata-service --region eu-central-1 --force
aws ecr delete-repository --repository-name aegisai/extract-content-service --region eu-central-1 --force
aws ecr delete-repository --repository-name aegisai/ai-service --region eu-central-1 --force

# Delete IAM policies (if created)
aws iam delete-policy --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy --region eu-central-1
```

---

## Cost Optimization Tips

1. **Use Spot Instances** for non-critical workloads:
   ```powershell
   eksctl create cluster --name aegisai-cluster --region eu-central-1 --node-type t3.small --nodes 2 --nodes-min 1 --nodes-max 4 --spot
   ```

2. **Enable Cluster Autoscaler** to scale nodes based on demand

3. **Use smaller instance types** during development (t3.micro or t3.small)

4. **Delete cluster when not in use** to avoid charges

5. **Monitor costs** using AWS Cost Explorer

6. **Use Reserved Instances** for production long-term workloads

---

## Troubleshooting Common Issues

### Issue: Pods stuck in `Pending` state
**Solution:** Check if nodes have enough resources:
```powershell
kubectl describe pod -n aegisai <pod-name>
kubectl top nodes
```

### Issue: Pods stuck in `ImagePullBackOff`
**Solution:** Verify ECR image paths and permissions:
```powershell
# Check deployment image
kubectl get deployment -n aegisai api-gateway -o yaml | Select-String "image:"

# Verify ECR login
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.eu-central-1.amazonaws.com

# Check if images exist in ECR
aws ecr list-images --repository-name aegisai/api-gateway --region eu-central-1
```

### Issue: `CrashLoopBackOff`
**Solution:** Check application logs:
```powershell
kubectl logs -n aegisai <pod-name> --previous
```

### Issue: Cannot connect to Load Balancer
**Solution:** 
- Wait 2-3 minutes for ALB provisioning
- Check security groups allow inbound traffic on port 8000
- Verify service is listening on correct port
```powershell
kubectl get svc -n aegisai
kubectl describe svc api-gateway -n aegisai
```

### Issue: Database connection errors
**Solution:** 
- Verify secrets are correctly base64 encoded
- Check if PostgreSQL pod is running
- Ensure services can resolve DNS names
```powershell
kubectl get pods -n aegisai | Select-String "postgres"
kubectl logs -n aegisai postgres-0
```

### Issue: EFS mount failures
**Solution:**
- Verify EFS ID is correct in storage-classes.yaml
- Check mount targets are created in all subnets
- Verify security group allows NFS traffic
```powershell
aws efs describe-mount-targets --file-system-id $EFS_ID --region eu-central-1
```

---

## What Was Missing from Your Original Commands

1. **ECR Setup (Step 4):** You need to create ECR repositories and push Docker images before deploying
2. **Update deployment YAMLs:** Must update image references to use ECR paths
3. **Helm installation:** Not mentioned but needed if using AWS Load Balancer Controller
4. **IAM policy for Load Balancer Controller:** Required for advanced ingress
5. **Mount target cleanup:** Need to delete mount targets before deleting EFS
6. **ECR authentication:** Must login to ECR before pushing images
7. **Better error handling:** Added troubleshooting section
8. **Resource verification:** Added steps to verify each component

---

## Next Steps

1. **Set up CI/CD Pipeline** (GitHub Actions, GitLab CI, Jenkins)
2. **Configure monitoring** with Prometheus/Grafana
3. **Set up logging** with ELK or CloudWatch Logs
4. **Implement backup strategy** for PostgreSQL data
5. **Configure custom domain** with Route53
6. **Enable HTTPS** with AWS Certificate Manager (ACM)
7. **Implement authentication** (OAuth2, JWT, Cognito)
8. **Set up VPN or Bastion host** for secure access
9. **Configure AWS WAF** for security
10. **Set up AWS Backup** for automated backups

---

## Useful Commands Reference

```powershell
# Get cluster info
kubectl cluster-info
eksctl get cluster --region eu-central-1

# Get all resources in namespace
kubectl get all -n aegisai

# Watch pod status
kubectl get pods -n aegisai -w

# Port forward for local testing
kubectl port-forward -n aegisai svc/api-gateway 8000:8000

# Scale deployment manually
kubectl scale deployment/api-gateway -n aegisai --replicas=3

# Update deployment image
kubectl set image deployment/api-gateway -n aegisai api-gateway=$ACCOUNT_ID.dkr.ecr.eu-central-1.amazonaws.com/aegisai/api-gateway:v2

# Restart deployment
kubectl rollout restart deployment/api-gateway -n aegisai

# View rollout history
kubectl rollout history deployment/api-gateway -n aegisai

# Rollback to previous version
kubectl rollout undo deployment/api-gateway -n aegisai

# Check HPA status
kubectl get hpa -n aegisai

# Describe HPA for details
kubectl describe hpa -n aegisai

# Get PV and PVC status
kubectl get pv,pvc -n aegisai

# Check ingress status
kubectl get ingress -n aegisai

# Get node information
kubectl get nodes -o wide
```

---

## Important Notes

- **Costs:** Running this cluster will incur AWS charges:
  - EKS Control Plane: ~$0.10/hour (~$73/month)
  - EC2 t3.small x2: ~$0.0208/hour each (~$30/month per instance)
  - EBS volumes: ~$0.10/GB/month
  - EFS: ~$0.30/GB/month
  - Load Balancer: ~$0.0225/hour (~$16/month)
  - **Total estimated: ~$150-200/month**

- **Security:** 
  - Never commit secrets to Git
  - Use AWS Secrets Manager in production
  - Enable encryption at rest and in transit
  - Use IAM roles for service accounts (IRSA)
  - Implement network policies

- **Backups:** 
  - Set up automated PostgreSQL backups
  - Use EBS snapshots
  - Consider cross-region replication for disaster recovery

- **Updates:** 
  - Regularly update EKS version
  - Keep worker nodes up to date
  - Update CSI drivers and controllers

- **Monitoring:** 
  - Set up CloudWatch alarms for critical metrics
  - Monitor pod resource usage
  - Track application errors

---

## Resources

- [EKS Documentation](https://docs.aws.amazon.com/eks/)
- [eksctl Documentation](https://eksctl.io/)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
- [AWS EBS CSI Driver](https://github.com/kubernetes-sigs/aws-ebs-csi-driver)
- [AWS EFS CSI Driver](https://github.com/kubernetes-sigs/aws-efs-csi-driver)
- [AWS Load Balancer Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)

