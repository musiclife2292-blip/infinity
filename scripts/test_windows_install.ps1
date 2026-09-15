param([Parameter(Mandatory=$true)][string]$Installer,
      [string]$Report = "evidence\windows-install-result.json",
      [switch]$RuntimeOnly)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if ($env:OS -ne "Windows_NT") { throw "Cần Windows x64 thật hoặc VM Windows." }
if (Test-Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\InfinityAudio") {
    throw "Máy đã có Infinity audio. Dùng VM sạch để tránh thay đổi đăng ký của bản đang cài."
}
$installerPath = (Resolve-Path $Installer).Path
$testDir = Join-Path $env:LOCALAPPDATA ("InfinityAudio-InstallTest-" + [Guid]::NewGuid().ToString("N"))
$reportPath = [IO.Path]::GetFullPath($Report)
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $reportPath) | Out-Null
$originalPath = $env:PATH
$originalPythonPath = $env:PYTHONPATH
$originalQtPlatform = $env:QT_QPA_PLATFORM
if ($RuntimeOnly) {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot;$env:SystemRoot\System32\Wbem"
    Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
}
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
$env:INFINITY_STRICT_FSYNC = "1"
$result = [ordered]@{
    date_utc = [DateTime]::UtcNow.ToString("o")
    os = [Environment]::OSVersion.VersionString
    is_64_bit = [Environment]::Is64BitOperatingSystem
    cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)
    ram_bytes = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
    installer_sha256 = (Get-FileHash $installerPath -Algorithm SHA256).Hash
    installed = $false; launched = $false; uninstalled = $false
    frozen_diagnostic_passed = $false
    second_launch_diagnostic_passed = $false
    developer_tools_removed_from_path = [bool]$RuntimeOnly
    native_qt_platform = "windows"
    clean_machine_confirmed = $false
    audio_hardware_verified = $false
    note = "Automated install/Qt launch/uninstall only. Complete the manual clean-machine checklist separately."
}
try {
    $process = Start-Process -FilePath $installerPath -ArgumentList @("/S", "/D=$testDir") -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "Installer exit code $($process.ExitCode)" }
    $exe = Join-Path $testDir "InfinityAudio.exe"
    $result.installed = Test-Path $exe
    if (-not $result.installed) { throw "Không tìm thấy executable sau cài đặt." }
    $p = Start-Process -FilePath $exe -ArgumentList "--smoke-test" -PassThru
    if (-not $p.WaitForExit(45000)) { $p.Kill(); throw "Ứng dụng không hoàn tất smoke test trong 45s." }
    if ($p.ExitCode -ne 0) { throw "App exit code $($p.ExitCode)" }
    $result.launched = $true
    $selfTestReport = Join-Path (Split-Path -Parent $reportPath) "installed-selftest.json"
    $p = Start-Process -FilePath $exe -ArgumentList @("--self-test", "`"$selfTestReport`"") -PassThru
    if (-not $p.WaitForExit(240000)) { $p.Kill(); throw "Installed app diagnostic timeout" }
    if ($p.ExitCode -ne 0 -or -not (Test-Path $selfTestReport)) { throw "Installed app diagnostic failed, code $($p.ExitCode)" }
    $result.frozen_diagnostic_passed = (Get-Content $selfTestReport -Raw | ConvertFrom-Json).passed
    if (-not $result.frozen_diagnostic_passed) { throw "Installed application diagnostic did not pass." }
    $secondReport = Join-Path (Split-Path -Parent $reportPath) "installed-second-launch.json"
    $p = Start-Process -FilePath $exe -ArgumentList @("--self-test", "`"$secondReport`"") -PassThru
    if (-not $p.WaitForExit(240000)) { $p.Kill(); throw "Second launch diagnostic timeout" }
    if ($p.ExitCode -ne 0 -or -not (Test-Path $secondReport)) { throw "Second launch diagnostic failed, code $($p.ExitCode)" }
    $result.second_launch_diagnostic_passed = (Get-Content $secondReport -Raw | ConvertFrom-Json).passed
    if (-not $result.second_launch_diagnostic_passed) { throw "Second launch diagnostic did not pass." }
    # A user's document in the install directory must survive uninstall.
    $userDocument = Join-Path $testDir "user-project.txt"
    [IO.File]::WriteAllText($userDocument, "preserve this user document")
    $uninstall = Join-Path $testDir "Uninstall.exe"
    $p = Start-Process -FilePath $uninstall -ArgumentList @("/S", "_?=$testDir") -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Uninstaller exit code $($p.ExitCode)" }
    $result.uninstalled = -not (Test-Path $exe) -and -not (Test-Path (Join-Path $testDir "_internal")) -and
        -not (Test-Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\InfinityAudio") -and
        (Test-Path $userDocument)
    if (-not $result.uninstalled) { throw "Ứng dụng vẫn tồn tại sau gỡ cài đặt." }
} finally {
    $env:PATH = $originalPath
    $env:PYTHONPATH = $originalPythonPath
    $env:QT_QPA_PLATFORM = $originalQtPlatform
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $reportPath) | Out-Null
    $result | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $reportPath
}
