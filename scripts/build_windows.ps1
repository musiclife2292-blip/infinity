param([string]$Python = "py", [string]$Makensis = "")
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
foreach ($required in @("packaging/InfinityAudio.spec", "packaging/installer.nsi", "requirements-dev.txt", "launch.py", "LICENSE")) {
    if (-not (Test-Path (Join-Path $root $required))) { throw "Source checkout thiếu file bắt buộc: $required" }
}
if (-not [Environment]::Is64BitOperatingSystem -or $env:OS -ne "Windows_NT") {
    throw "Build này cần máy Windows x64; không hỗ trợ cross-build từ Linux."
}
function Assert-Exit([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "Bước '$Step' thất bại, exit code $LASTEXITCODE" }
}
New-Item -ItemType Directory -Force -Path "evidence\windows-build" | Out-Null
$env:INFINITY_STRICT_FSYNC = "1"
if ($Python -eq "py") { & py -3.12 -m venv .venv } else { & $Python -m venv .venv }
Assert-Exit "venv"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
Assert-Exit "pip"
& $venvPython -m pip install -r requirements-dev.txt
Assert-Exit "dependencies"
& $venvPython -m pip install -e . --no-deps
Assert-Exit "editable source"
& $venvPython -m pip freeze --all | Set-Content "evidence\windows-build\dependencies.txt" -Encoding utf8
Assert-Exit "dependency snapshot"
$env:QT_QPA_PLATFORM = "offscreen"
& $venvPython -m pytest -q --junitxml=evidence/windows-pytest.xml
Assert-Exit "tests"
& $venvPython scripts/collect_licenses.py
Assert-Exit "license inventory"
& $venvPython scripts/make_icon.py
Assert-Exit "icon"
& $venvPython scripts/validate_release.py evidence/windows-build
Assert-Exit "DSP, codecs and bounded stress"
if ($env:INFINITY_TEST_VST3) {
    & $venvPython launch.py --self-test evidence/windows-build/source-selftest.json
    Assert-Exit "source diagnostic with real VST3"
}
& $venvPython -m PyInstaller --noconfirm --clean packaging/InfinityAudio.spec
Assert-Exit "PyInstaller"
$smoke = Start-Process -FilePath ".\dist\InfinityAudio\InfinityAudio.exe" -ArgumentList "--smoke-test" -PassThru
if (-not $smoke.WaitForExit(45000)) { $smoke.Kill(); throw "Frozen Qt smoke timeout" }
if ($smoke.ExitCode -ne 0) { throw "Frozen Qt smoke exit code $($smoke.ExitCode)" }
$diagnosticReport = Join-Path $root "evidence\windows-build\frozen-selftest.json"
$diagnostic = Start-Process -FilePath ".\dist\InfinityAudio\InfinityAudio.exe" -ArgumentList @("--self-test", "`"$diagnosticReport`"") -PassThru
if (-not $diagnostic.WaitForExit(240000)) { $diagnostic.Kill(); throw "Frozen diagnostic timeout" }
if ($diagnostic.ExitCode -ne 0) { throw "Frozen diagnostic exit code $($diagnostic.ExitCode). See $diagnosticReport" }
if (-not (Test-Path $diagnosticReport) -or -not (Get-Content $diagnosticReport -Raw | ConvertFrom-Json).passed) {
    throw "Frozen diagnostic did not produce a passing report."
}
Remove-Item Env:QT_QPA_PLATFORM
if (-not $Makensis) {
    $possible = @("${env:ProgramFiles(x86)}\NSIS\makensis.exe", "$env:ProgramFiles\NSIS\makensis.exe")
    $Makensis = $possible | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $Makensis -or -not (Test-Path $Makensis)) { throw "Cài NSIS 3.x (makensis.exe) trước bước tạo bộ cài." }
Push-Location packaging
try { & $Makensis installer.nsi; Assert-Exit "NSIS" } finally { Pop-Location }
Get-FileHash dist\Infinity-audio-0.1.0-alpha.2-win64-setup.exe -Algorithm SHA256 | Format-List
(Get-FileHash dist\Infinity-audio-0.1.0-alpha.2-win64-setup.exe -Algorithm SHA256).Hash.ToLower() + "  Infinity-audio-0.1.0-alpha.2-win64-setup.exe" |
    Set-Content dist\Infinity-audio-0.1.0-alpha.2-win64-setup.exe.sha256 -Encoding ascii
Write-Host "Đã BUILD bản alpha. Chưa được xem là release đã nghiệm thu. Chạy scripts/test_windows_install.ps1 và checklist Windows sạch."
