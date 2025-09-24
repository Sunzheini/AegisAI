# Refined Project Plan: "AegisAI Media Intelligence Platform" based on points 1-7 from 'OpenPoints.xlsx'

##  Detailed Architecture & Services
We will split the monolith into highly cohesive, loosely coupled services.

1. API Gateway & Ingestion Service (FastAPI)
   - Purpose: Public-facing REST API for all interactions.
   - Framework: FastAPI with heavy use of async/await.
   - Key Endpoints:
     - POST /v1/upload: Async upload to cloud storage. Publishes a JOB_CREATED event to the Command Queue. Returns 202 Accepted with a job_id.
     - GET /v1/jobs/{job_id}: Checks the state of the entire workflow.
     - GET /v1/assets/{asset_id}: Retrieves processed assets and AI insights.
   - Key Features:
     - Concurrency: Handles hundreds of concurrent uploads using async I/O for S3 and queue operations.
     - Auth: Integrated with AWS Cognito (or Auth0) via OAuth2 flows. API Gateway uses a JWT authorizer.
     - Rate Limiting: Implemented at the API Gateway level (e.g., AWS API Gateway usage plans & API keys).

2. Workflow Orchestrator (LangGraph)
   - Purpose: The brain of the operation. This service defines and executes the stateful workflow for each job. This is a critical addition that covers "multiple services interacting through a queue" in a sophisticated way.
   - Framework: LangGraph to model the workflow as a state machine.
   - How it works:
     - It consumes the JOB_CREATED event from the Command Queue.
     - It creates a new LangGraph graph execution for the job_id.
     - The graph defines nodes and conditional edges:
       - Node: validate_file -> Calls the Validation Service via its queue.
       - Node: extract_metadata -> If validation passes, calls a metadata service.
       - Node: route_workflow -> (Conditional) Based on file type (image, video, pdf), triggers different chains.
         - Image Branch: generate_thumbnails -> analyze_image_with_ai
         - Video Branch: extract_audio -> transcribe_audio -> generate_video_summary
         - PDF Branch: extract_text -> summarize_document
     - Each "node" in the graph works by publishing a task to a specific Task Queue and waiting for a callback with the result on a Callback Queue.
     - The graph state is persisted (e.g., in DynamoDB), allowing for long-running, resilient workflows.
   - Why LangGraph? It perfectly demonstrates managing complex, conditional, and potentially long-running (e.g., video processing) chains of events, which is a classic producer-consumer setup on steroids.

3. Specialized Worker Services (Python + SQS Consumers)
These are the "muscle" that carry out the tasks defined by the LangGraph orchestrator. Each is a separate, scalable microservice.
   - Validation Worker: Validates file type, size, and integrity.
   - Media Processing Worker: Uses ProcessPoolExecutor for CPU-bound tasks (FFmpeg for video, Pillow for images). You will include benchmarks comparing single-threaded vs. multi-process performance.
   - AI Inference Worker (LangChain): This is where LangChain shines.
     - Purpose: Handles all AI interactions.
     - Implementation: Uses LangChain to create modular, reusable "chains" or "agents".
     - Example Chains:
       - Image Analysis Chain: Uses LangChain's StructuredOutputParser with an OpenAI GPT-4o or Anthropic Claude model to analyze an image and return a structured JSON response with tags, description, and NSFW confidence score.
       - Document Summary Chain: Uses LangChain's load_summarize_chain with a map-reduce approach over document chunks to handle long PDFs.
       - Multi-Modal Chain: A chain that takes both extracted text from a video and a generated image summary to create a rich content metadata object.
     - Key Feature: Demonstrates LangChain's ability to integrate with different models and tools seamlessly.

4. Data Storage & Sync Layer
   - AWS S3: Primary storage for raw and processed files.
     - Bucket 1 (Raw): Ingress bucket. Enforces AES-256 server-side encryption.
     - Bucket 2 (Processed): Egress bucket. Serves processed files via Amazon CloudFront (CDN) for performance optimization. Configured with OAI (Origin Access Identity) for security.
     - Bucket 3 (Transcoded): For large processed files like videos.
   - Conflict Resolution: Implement object versioning on all buckets. The system operates on a "last-write-wins" model, but the version history provides an audit trail.
   - Metadata Store: Amazon DynamoDB. Chosen for its scalability and seamless integration with serverless patterns. Stores all job state, AI-generated metadata, and user associations. This is the "source of truth" for an asset's state.

## Cloud Infrastructure & Deployment (AWS Focus)
1. Networking:
   - Create a custom VPC with Public and Private subnets.
   - NAT Gateways in public subnets allow workers in private subnets to access S3, SQS, and AI APIs.
   - API Gateway uses a VPC Link to privately connect to the internal Network Load Balancer (NLB) fronting the FastAPI service (running on ECS Fargate in private subnets). This is a crucial security artifact.

2. Compute & Orchestration:
   - AWS ECS on Fargate: Hosts all microservices (FastAPI, LangGraph Orchestrator, Workers). Defined via Terraform/CDK.
   - Scaling: Configure ECS Service Auto-Scaling based on SQS Queue depth (e.g., scale out when ApproximateNumberOfMessagesVisible > 50). This is a best-practice artifact.

3. Messaging:
   - Amazon SQS: Used for three purposes:
     - Command Queue: aegis-job-commands
     - Task Queues: aegis-task-validation, aegis-task-ai, etc.
     - Callback Queue: aegis-task-callbacks (for workers to signal task completion back to the LangGraph orchestrator).
   - Dead-Letter Queues (DLQs) are attached to all SQS queues to handle failed messages, demonstrating production-grade resiliency.

4. Security Artifacts:
   - IAM Roles: Every service (ECS Task Role) has a minimal IAM policy following the principle of least privilege (e.g., the Validation Worker only has s3:GetObject on the raw bucket and sqs:SendMessage to the callback queue).
   - Encryption: All data encrypted at rest (S3, DynamoDB) and in transit (TLS 1.2+ everywhere).
   - API Security: API Gateway uses Cognito for JWT-based authentication and authorisation.

5. Observability:
   - Prometheus & Grafana: Application metrics (e.g., langgraph_steps_completed, image_processing_duration_seconds, ai_model_latency_seconds) are scraped from the services and displayed on a dashboard.
   - AWS CloudWatch: Infrastructure logs and metrics (SQS queue depth, ECS CPU utilization, API Gateway 4xx/5xx errors).
   - Distributed Tracing: Implemented with AWS X-Ray to trace a request from the API through all queues and services, providing a visual workflow map.
