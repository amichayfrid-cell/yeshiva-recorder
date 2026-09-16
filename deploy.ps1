# ==============================================================================
# Yeshiva Recorder - Fast Remote Deployment Script
# ==============================================================================

$SERVER = "lessons@192.168.1.244"
$REMOTE_DIR = "/home/lessons/yeshiva-recorder"

Write-Host "==> [1/3] Packaging updated files into deploy_patch.tar.gz..." -ForegroundColor Cyan

$FILES_TO_DEPLOY = @(
    "config.py",
    "web/server.py",
    "web/static/rav_tzvi.js",
    "web/static/rav_tzvi.css",
    "web/static/rav_tzvi.html",
    "web/static/app.js",
    "web/static/style.css",
    "web/templates/admin.html",
    "web/templates/student.html",
    "web/templates/login.html"
)

tar -czf deploy_patch.tar.gz $FILES_TO_DEPLOY

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to package files." -ForegroundColor Red
    exit 1
}

Write-Host "==> [2/3] Transferring package to server ($SERVER)..." -ForegroundColor Cyan
scp deploy_patch.tar.gz "$($SERVER):$($REMOTE_DIR)/"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Transfer failed. Please check password." -ForegroundColor Red
    Remove-Item deploy_patch.tar.gz -ErrorAction SilentlyContinue
    exit 1
}

Remove-Item deploy_patch.tar.gz -ErrorAction SilentlyContinue

Write-Host "==> [3/3] Extracting on server and restarting web service..." -ForegroundColor Cyan
ssh -t $SERVER "cd $REMOTE_DIR && tar -xzf deploy_patch.tar.gz && rm -f deploy_patch.tar.gz && sudo systemctl restart web.service"

if ($LASTEXITCODE -eq 0) {
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host " SUCCESS: Server updated and restarted!   " -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Remote command exited with code $LASTEXITCODE" -ForegroundColor Yellow
}
