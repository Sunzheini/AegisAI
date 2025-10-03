# workflow-orchestrator-service notes

What is the Workflow Orchestrator?
The Workflow Orchestrator is a dedicated service that manages the entire lifecycle of a media processing job. Its main role is to coordinate the sequence of processing steps (validation, metadata extraction, AI analysis, etc.) for each uploaded file, ensuring each step happens in the correct order and handling failures or retries as needed.

What are the "jobs" it orchestrates?
A "job" is created whenever a user uploads a file via the API Gateway & Ingestion Service. Each job represents the full processing workflow for that file, which may include:
Validating the file (type, size, integrity)
Extracting metadata (e.g., file properties, user info)
Branching into different processing chains based on file type:
Images: generate thumbnails, run AI image analysis
Videos: extract audio, transcribe, summarize
PDFs: extract text, summarize
Storing results and updating job status
Each of these steps is a "task" in the workflow, and the orchestrator ensures they are executed in the right order.

How to implement the Workflow Orchestrator
Choose a Workflow Engine
Use a state machine or workflow library (your plan suggests LangGraph, but alternatives like Temporal, Step Functions, or custom code are possible).
Event-Driven Architecture
The orchestrator listens for "JOB_CREATED" events (e.g., from a message queue like Redis Pub/Sub or AWS SQS).
When a new job is created (file uploaded), the orchestrator starts a new workflow instance for that job.
Define the Workflow as a Graph
Model the workflow as a directed graph or state machine.
Each node is a processing step (e.g., validate_file, extract_metadata).
Edges define the order and conditional logic (e.g., if file is image, go to image branch).
Task Dispatching
For each step, the orchestrator publishes a task message to the appropriate worker queue (e.g., validation, AI analysis).
Workers pick up tasks, process them, and send results back (via callback queues or direct API calls).
State Persistence
The orchestrator keeps track of each job’s state (current step, results, errors) in a database (locally: SQLite/Redis; AWS: DynamoDB).
This allows for recovery, retries, and long-running workflows.
Handling Results and Progression
When a worker completes a task, it sends a result message.
The orchestrator updates the job state and determines the next step.
If all steps are complete, it marks the job as finished and updates the metadata store.
Error Handling and Retries
If a step fails, the orchestrator can retry, skip, or mark the job as failed, depending on your business logic.

Example Flow
User uploads a file → API Gateway creates a job and publishes JOB_CREATED.
Orchestrator receives JOB_CREATED, starts workflow for job_id.
Orchestrator sends "validate_file" task to Validation Worker.
Validation Worker processes and sends result back.
Orchestrator receives result, updates state, and dispatches next task (e.g., extract_metadata).
If file is an image, orchestrator dispatches "generate_thumbnails" and "analyze_image_with_ai" tasks.
Each result is tracked; when all branches complete, orchestrator marks job as done.

Summary
The orchestrator is the "conductor" that ensures each uploaded file is processed through all required steps, in the right order, with error handling and state tracking.
Jobs are the end-to-end processing pipelines for each uploaded file.
Implementation involves event-driven task dispatch, state management, and workflow logic, using a workflow engine or state machine library.
This approach gives you flexibility, reliability, and scalability—locally and in the cloud.