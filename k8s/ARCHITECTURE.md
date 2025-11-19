# AegisAI Kubernetes Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         External Users                               │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Ingress / LoadBalancer                          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        API Gateway (8000)                            │
│                     (2 replicas, autoscaling)                        │
└───────────┬──────────────────────────┬──────────────────────────────┘
            │                          │
            ▼                          ▼
    ┌───────────────┐          ┌──────────────┐
    │  PostgreSQL   │          │    Redis     │
    │    (5432)     │          │    (6379)    │
    └───────────────┘          └──────┬───────┘
                                      │
                             ┌────────┴────────┐
                             ▼                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Workflow Orchestrator (9000)                       │
│                     (2 replicas, autoscaling)                        │
└────────┬──────────┬──────────┬──────────┬─────────────────────────┘
         │          │          │          │
    ┌────▼────┐┌───▼────┐┌────▼────┐┌───▼─────┐
    │Validate ││Extract ││Extract  ││AI Service│
    │Service  ││Metadata││Content  ││         │
    │(9001)   ││(9002)  ││(9003)   ││(9004)   │
    │2 replica││2 replic││2 replica││2 replica│
    └─────────┘└────────┘└─────────┘└─────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Shared Storage  │
                    │  (PVC - 20Gi)   │
                    └─────────────────┘
```

## Components

### Infrastructure Layer

1. **PostgreSQL Database**
   - Single replica (consider HA for production)
   - 10Gi persistent storage
   - Port: 5432
   - Used by: API Gateway

2. **Redis Cache**
   - Single replica with persistence
   - 5Gi persistent storage
   - Port: 6379
   - Pub/Sub for inter-service communication
   - Used by: All services

3. **Shared Storage**
   - 20Gi persistent volume
   - ReadWriteMany access mode
   - Stores: raw, processed, transcoded files
   - Mounted in all worker services

### Gateway Layer

4. **API Gateway**
   - External-facing service (LoadBalancer)
   - 2 replicas (scales 2-10)
   - Resource limits: 512Mi-1Gi RAM, 250m-500m CPU
   - Handles: Authentication, request routing, file uploads
   - Health check: /health endpoint

### Orchestration Layer

5. **Workflow Orchestrator**
   - Internal service (ClusterIP)
   - 2 replicas (scales 2-8)
   - Resource limits: 512Mi-1Gi RAM, 250m-500m CPU
   - Manages: Job distribution, workflow coordination
   - Health check: /docs endpoint

### Worker Layer

6. **Validation Service** (Port 9001)
   - Validates uploaded files
   - 2 replicas (scales 2-8)
   - Resource limits: 256Mi-512Mi RAM, 200m-500m CPU

7. **Extract Metadata Service** (Port 9002)
   - Extracts file metadata
   - 2 replicas (scales 2-8)
   - Resource limits: 256Mi-512Mi RAM, 200m-500m CPU

8. **Extract Content Service** (Port 9003)
   - Extracts content from files
   - 2 replicas (scales 2-8)
   - Resource limits: 512Mi-1Gi RAM, 250m-500m CPU

9. **AI Service** (Port 9004)
   - AI/ML processing
   - 2 replicas (scales 2-6)
   - Resource limits: 1Gi-2Gi RAM, 500m-1000m CPU
   - External dependencies: OpenAI, Pinecone, etc.

## Resource Requirements

### Minimum Cluster Requirements

- **Nodes**: 3 (for HA)
- **Total CPU**: 8 cores
- **Total RAM**: 16 GB
- **Storage**: 40 GB persistent

### Per-Node Requirements (for 3-node cluster)

- **CPU**: 4 cores
- **RAM**: 8 GB
- **Storage**: 20 GB

### Storage Breakdown

- Shared Storage PVC: 20 GB (ReadWriteMany)
- PostgreSQL PVC: 10 GB (ReadWriteOnce)
- Redis PVC: 5 GB (ReadWriteOnce)
- System overhead: 5 GB

## Networking

### Service Types

- **LoadBalancer**: API Gateway (external access)
- **ClusterIP**: All other services (internal only)

### Ports

| Service | Internal Port | External Port | Type |
|---------|---------------|---------------|------|
| API Gateway | 8000 | 8000 | LoadBalancer |
| Workflow Orchestrator | 9000 | - | ClusterIP |
| Validation Service | 9001 | - | ClusterIP |
| Extract Metadata | 9002 | - | ClusterIP |
| Extract Content | 9003 | - | ClusterIP |
| AI Service | 9004 | - | ClusterIP |
| PostgreSQL | 5432 | - | ClusterIP |
| Redis | 6379 | - | ClusterIP |

### Network Policies (Optional)

Network policies restrict traffic between pods:
- API Gateway → Postgres, Redis, Orchestrator
- Orchestrator → Redis, All Workers
- Workers → Redis, Shared Storage
- Infrastructure services accept only from authorized pods

## Configuration Management

### ConfigMaps

`app-config` ConfigMap contains:
- Application settings (DEBUG, DOCKER, etc.)
- Storage paths
- Service URLs
- Database connection info (non-sensitive)
- AWS S3 bucket names
- AI service settings (non-sensitive)

### Secrets

`app-secrets` Secret contains (base64 encoded):
- Database password
- Secret keys
- AWS credentials
- OpenAI API key
- LangSmith API key
- Tavily API key
- Pinecone API key
- HuggingFace API token

## High Availability Features

### Replication

- All application services: 2+ replicas
- Infrastructure services: 1 replica (upgrade for production)

### Autoscaling (HPA)

All services configured with:
- CPU-based autoscaling (70-75% threshold)
- Memory-based autoscaling (80-85% threshold)
- Scale-up: Fast (60s stabilization)
- Scale-down: Slow (300s stabilization)

### Pod Disruption Budgets (PDB)

- Ensures minimum 1 pod available during:
  - Node maintenance
  - Cluster upgrades
  - Voluntary evictions

### Health Checks

**Liveness Probes**:
- Check if pod is alive
- Restart if failing
- Configured for all services

**Readiness Probes**:
- Check if pod is ready to receive traffic
- Remove from service endpoints if failing
- Faster intervals than liveness

## Deployment Strategies

### Rolling Update (Default)

- Zero downtime deployments
- Gradual pod replacement
- Automatic rollback on failure

### Blue-Green Deployment

1. Deploy new version alongside old
2. Test new version
3. Switch traffic
4. Remove old version

### Canary Deployment

1. Deploy new version to subset of pods
2. Monitor metrics
3. Gradually increase traffic
4. Full rollout or rollback

## Security Considerations

### Pod Security

- Run as non-root user (configure in Dockerfiles)
- Read-only root filesystem where possible
- Drop unnecessary capabilities
- Use security contexts

### Network Security

- Network policies to restrict pod-to-pod traffic
- TLS/SSL for external access
- mTLS for internal service mesh (optional)

### Secrets Management

**Current**: Kubernetes Secrets (base64)

**Production Options**:
- External Secrets Operator + AWS Secrets Manager
- External Secrets Operator + Azure Key Vault
- HashiCorp Vault
- Sealed Secrets (for GitOps)

### Image Security

- Use official base images
- Scan images for vulnerabilities
- Use private registry
- Implement image signing
- Regular updates

## Monitoring & Observability

### Metrics (Recommended Setup)

1. **Prometheus**
   - Scrape metrics from all pods
   - Store time-series data
   - Alert on anomalies

2. **Grafana**
   - Visualize metrics
   - Custom dashboards
   - Alert notifications

### Logging (Recommended Setup)

1. **ELK Stack**
   - Elasticsearch: Store logs
   - Logstash: Process logs
   - Kibana: Visualize logs

2. **Loki + Grafana**
   - Lightweight alternative
   - Native Grafana integration

### Tracing (Recommended Setup)

- Jaeger or Zipkin
- Distributed tracing
- Request flow visualization

## Backup & Disaster Recovery

### Database Backups

```yaml
# CronJob for PostgreSQL backup
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:15-alpine
            command:
            - /bin/sh
            - -c
            - pg_dump -h postgres -U postgres_user aegisai_db > /backup/backup-$(date +%Y%m%d).sql
```

### Storage Backups

- Snapshot persistent volumes
- Sync to cloud storage (S3, Azure Blob)
- Test restore procedures

### Disaster Recovery Plan

1. **RPO** (Recovery Point Objective): < 24 hours
2. **RTO** (Recovery Time Objective): < 4 hours
3. Maintain infrastructure as code (IaC)
4. Document recovery procedures
5. Regular DR drills

## Cost Optimization

### Resource Right-Sizing

- Monitor actual usage
- Adjust requests/limits
- Use Vertical Pod Autoscaler (VPA)

### Spot Instances (Cloud)

- Use spot/preemptible instances for worker nodes
- Set up node affinity/anti-affinity

### Storage Optimization

- Use appropriate storage classes
- Implement data lifecycle policies
- Archive old data

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy to K8s
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Build images
        run: cd k8s && ./build-images.ps1 -Registry ${{ secrets.REGISTRY }}
      - name: Deploy
        run: cd k8s && make deploy REGISTRY=${{ secrets.REGISTRY }}
```

### GitOps with ArgoCD

- Declare desired state in Git
- ArgoCD syncs cluster to Git state
- Automatic deployments
- Easy rollbacks

## Scaling Guidelines

### Horizontal Scaling

- Add more pod replicas
- HPA handles automatically based on metrics

### Vertical Scaling

- Increase resource requests/limits
- Requires pod restart

### Cluster Scaling

- Add more nodes to cluster
- Cloud: Use cluster autoscaler
- On-prem: Add physical/virtual machines

## Troubleshooting Guide

### Common Issues

1. **Pods stuck in Pending**
   - Check: Resource availability, PVC binding, node selectors

2. **Pods in CrashLoopBackOff**
   - Check: Logs, liveness probes, configuration

3. **Service unreachable**
   - Check: Service selectors, endpoints, network policies

4. **Image pull errors**
   - Check: Registry credentials, image name, network access

5. **Storage issues**
   - Check: PV/PVC status, storage class, node permissions

### Debug Commands

```bash
# Get pod details
kubectl describe pod <pod> -n aegisai

# Get pod logs
kubectl logs <pod> -n aegisai

# Previous container logs
kubectl logs <pod> -n aegisai --previous

# Events
kubectl get events -n aegisai --sort-by='.lastTimestamp'

# Resource usage
kubectl top pods -n aegisai
kubectl top nodes
```

## Next Steps

1. Set up monitoring (Prometheus/Grafana)
2. Configure log aggregation
3. Implement CI/CD pipeline
4. Set up backup automation
5. Configure SSL/TLS certificates
6. Implement secrets management
7. Set up disaster recovery
8. Performance testing and optimization
9. Security hardening
10. Documentation and runbooks

