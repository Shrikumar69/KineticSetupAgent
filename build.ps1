# build.ps1 - Build EpicorSetupAgent.exe
# Run: .\build.ps1
$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  EpicorSetupAgent - Build Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
$venvPy = "$ProjectRoot\.venv\Scripts\python.exe"
$candidates = @("$ProjectRoot\.venv\Scripts\python.exe","$env:LOCALAPPDATA\Programs\Python\Python312\python.exe")
$pyexe = $null
foreach ($c in $candidates) { if ($c -and (Test-Path $c)) { $pyexe = $c; break } }
if (-not $pyexe) { Write-Error "Python not found."; exit 1 }
Write-Host "Python: $pyexe" -ForegroundColor Green
if (-not (Test-Path $venvPy)) { & $pyexe -m venv "$ProjectRoot\.venv" }
& $venvPy -m pip install --upgrade pip pyinstaller -r "$ProjectRoot\requirements.txt" -q
foreach ($d in @("$ProjectRoot\dist","$ProjectRoot\build")) {
    if (Test-Path $d) { Remove-Item $d -Recurse -Force }
}
Set-Location $ProjectRoot
& $venvPy -m PyInstaller EpicorSetupAgent.spec --noconfirm
$exePath = "$ProjectRoot\dist\EpicorSetupAgent.exe"
if (Test-Path $exePath) {
    $size = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
    Write-Host "BUILD SUCCESS: $exePath ($size MB)" -ForegroundColor Green
    Write-Host "Copy dist\EpicorSetupAgent.exe to your shared network path." -ForegroundColor Yellow
} else { Write-Error "Build failed."; exit 1 }
