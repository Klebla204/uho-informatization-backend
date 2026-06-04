# PowerShell helper to install backend dependencies and run RBAC apply
# Usage: Open PowerShell in project root and run: .\backend\scripts\setup_backend.ps1

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

. .venv\Scripts\Activate.ps1

Write-Host "Installing backend dependencies..."
pip install -r backend\requirements.txt

Write-Host "Applying RBAC (migrations + seed)..."
python backend\manage.py apply_rbac

Write-Host "Done."