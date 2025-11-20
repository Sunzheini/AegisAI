# Build all Docker images for AegisAI services
# Usage: .\build-images.ps1 -Registry "your-registry" [-Tag "v1.0.0"] [-Push]

param(
    [Parameter(Mandatory=$false)]
    [string]$Registry = "your-registry",

    [Parameter(Mandatory=$false)]
    [string]$Tag = "latest",

    [Parameter(Mandatory=$false)]
    [switch]$Push = $false,

    [Parameter(Mandatory=$false)]
    [switch]$BuildCache = $true
)

$ErrorActionPreference = "Stop"

Write-Host "=== Building AegisAI Docker Images ===" -ForegroundColor Cyan
Write-Host "Registry: $Registry" -ForegroundColor Yellow
Write-Host "Tag: $Tag" -ForegroundColor Yellow
Write-Host "Push to registry: $Push" -ForegroundColor Yellow
Write-Host ""

# Change to project root
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptPath
Set-Location $projectRoot

# Services configuration
$services = @(
    @{Name="api-gateway"; Port=8000},
    @{Name="workflow-orchestrator"; Port=9000},
    @{Name="validation-service"; Port=9001},
    @{Name="extract-metadata-service"; Port=9002},
    @{Name="extract-content-service"; Port=9003},
    @{Name="ai-service"; Port=9004}
)

$buildErrors = @()
$buildSuccess = @()

foreach ($service in $services) {
    $serviceName = $service.Name
    $imageName = "aegisai-$serviceName"
    $fullImageName = "${Registry}/${imageName}:${Tag}"
    $dockerfilePath = "services/$serviceName-service/Dockerfile"

    Write-Host "Building $imageName..." -ForegroundColor Green
    Write-Host "  Dockerfile: $dockerfilePath" -ForegroundColor Gray
    Write-Host "  Image: $fullImageName" -ForegroundColor Gray

    try {
        # Build arguments
        $buildArgs = @(
            "build",
            "-f", $dockerfilePath,
            "-t", $fullImageName
        )

        if (-not $BuildCache) {
            $buildArgs += "--no-cache"
        }

        $buildArgs += "."

        # Execute build
        $startTime = Get-Date
        & docker $buildArgs

        if ($LASTEXITCODE -ne 0) {
            throw "Docker build failed with exit code $LASTEXITCODE"
        }

        $buildTime = (Get-Date) - $startTime
        Write-Host "  [SUCCESS] Built successfully in $($buildTime.TotalSeconds.ToString('F2'))s" -ForegroundColor Green
        $buildSuccess += $imageName

        # Push if requested
        if ($Push) {
            Write-Host "  Pushing to registry..." -ForegroundColor Yellow
            docker push $fullImageName

            if ($LASTEXITCODE -ne 0) {
                throw "Docker push failed with exit code $LASTEXITCODE"
            }

            Write-Host "  [SUCCESS] Pushed successfully" -ForegroundColor Green
        }

        # Also tag as latest if not already
        if ($Tag -ne "latest") {
            $latestImageName = "${Registry}/${imageName}:latest"
            docker tag $fullImageName $latestImageName

            if ($Push) {
                docker push $latestImageName
            }
        }

        Write-Host ""
    }
    catch {
        Write-Host "  [FAILED] Failed: $_" -ForegroundColor Red
        $buildErrors += @{Service=$imageName; Error=$_}
        Write-Host ""
    }
}

# Summary
Write-Host "=== Build Summary ===" -ForegroundColor Cyan
Write-Host "Successful builds: $($buildSuccess.Count)" -ForegroundColor Green
foreach ($success in $buildSuccess) {
    Write-Host "  [SUCCESS] $success" -ForegroundColor Green
}

if ($buildErrors.Count -gt 0) {
    Write-Host ""
    Write-Host "Failed builds: $($buildErrors.Count)" -ForegroundColor Red
    foreach ($error in $buildErrors) {
        Write-Host "  [FAILED] $($error.Service): $($error.Error)" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Build completed with errors!" -ForegroundColor Red
    exit 1
}
else {
    Write-Host ""
    Write-Host "All builds completed successfully!" -ForegroundColor Green

    if ($Push) {
        Write-Host "All images pushed to $Registry" -ForegroundColor Green
    }
    else {
        Write-Host "Images not pushed (use -Push to push to registry)" -ForegroundColor Yellow
    }
}

# Show image sizes
Write-Host ""
Write-Host "=== Image Sizes ===" -ForegroundColor Cyan
foreach ($service in $services) {
    $imageName = "aegisai-$($service.Name)"
    $fullImageName = "${Registry}/${imageName}:${Tag}"
    $imageInfo = docker images $fullImageName --format "{{.Size}}"
    Write-Host "  $imageName : $imageInfo" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green

