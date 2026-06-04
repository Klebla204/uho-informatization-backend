# PowerShell helper to run RBAC migrations and seed data
# Usage: Open PowerShell in project root and run: .\backend\scripts\apply_rbac.ps1

$venvPath = Join-Path $PSScriptRoot "..\venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    Write-Host "Activating virtualenv..."
    . $venvPath
} else {
    Write-Host "Virtualenv activate script not found at $venvPath. Ensure you have a virtualenv at backend/venv or activate manually."
}

Write-Host "Making migrations and applying RBAC..."
python backend\manage.py apply_rbac

Write-Host "Done."