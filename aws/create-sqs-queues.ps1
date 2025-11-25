# Create SQS Queues for AegisAI
# Run this script to create all required SQS queues in AWS
# Prerequisites: AWS CLI configured with credentials

$REGION = "eu-central-1"
$QUEUES = @(
    "aegis-job-commands",
    "aegis-task-validation",
    "aegis-task-extract-metadata",
    "aegis-task-extract-content",
    "aegis-task-ai-inference",
    "aegis-task-callbacks"
)

Write-Host "Creating SQS queues in region: $REGION" -ForegroundColor Green

foreach ($queue in $QUEUES) {
    Write-Host "`nCreating queue: $queue" -ForegroundColor Yellow

    # Create main queue
    aws sqs create-queue --queue-name $queue --region $REGION --attributes VisibilityTimeout=300,MessageRetentionPeriod=345600,ReceiveMessageWaitTimeSeconds=10

    # Create Dead Letter Queue (DLQ)
    $dlqName = "$queue-dlq"
    Write-Host "Creating DLQ: $dlqName" -ForegroundColor Cyan

    $dlqUrl = aws sqs create-queue --queue-name $dlqName --region $REGION --attributes MessageRetentionPeriod=1209600 --query 'QueueUrl' --output text

    if ($dlqUrl) {
        # Get DLQ ARN
        $dlqArn = aws sqs get-queue-attributes --queue-url $dlqUrl --region $REGION --attribute-names QueueArn --query 'Attributes.QueueArn' --output text

        # Update main queue with DLQ
        $queueUrl = aws sqs get-queue-url --queue-name $queue --region $REGION --query 'QueueUrl' --output text

        if ($queueUrl -and $dlqArn) {
            $redrivePolicy = "{`"deadLetterTargetArn`":`"$dlqArn`",`"maxReceiveCount`":`"3`"}"
            aws sqs set-queue-attributes --queue-url $queueUrl --region $REGION --attributes RedrivePolicy=$redrivePolicy
        }

        Write-Host "Created $queue with DLQ" -ForegroundColor Green
    } else {
        Write-Host "Failed to create DLQ for $queue" -ForegroundColor Red
    }
}

Write-Host "`nAll queues created successfully!" -ForegroundColor Green
Write-Host "`nQueue URLs:" -ForegroundColor Yellow

foreach ($queue in $QUEUES) {
    $url = aws sqs get-queue-url --queue-name $queue --region $REGION --query 'QueueUrl' --output text
    Write-Host "$queue : $url"
}

