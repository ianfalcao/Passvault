$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ($env:OS -ne 'Windows_NT') { throw 'Execute o build em Windows.' }

function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Falha ao executar $Program (codigo $LASTEXITCODE)." }
}

$python = $null
foreach ($candidate in @('3.13','3.12')) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $path = & py "-$candidate" -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0) { $python = $path; break }
    }
}
if (-not $python) { $python = (Get-Command python).Source }
Invoke-Checked $python @('-c','import sys; sys.exit(sys.version_info[:2] not in ((3,12),(3,13)))')
Invoke-Checked $python @('-m','venv','.venv-build')
$venv = Join-Path $PSScriptRoot '.venv-build\Scripts\python.exe'
Invoke-Checked $venv @('-m','pip','install','-r','requirements.txt','-r','requirements-build.txt')
Invoke-Checked $venv @('-m','unittest','discover','-s','tests','-v')
foreach ($asset in @('passvault.ico','passvault.png','logo.png')) {
    if (-not (Test-Path "passvault/assets/$asset")) {
        Invoke-Checked $venv @('tools/make_icon.py')
        break
    }
}
Invoke-Checked $venv @('-m','PyInstaller','--noconfirm','--clean','PassVault.spec')
$exe = Get-Item 'dist\PassVault.exe'
$check = Start-Process -FilePath $exe.FullName -ArgumentList '--self-test' -Wait -PassThru
if ($check.ExitCode -ne 0) { throw "Autoteste falhou ($($check.ExitCode))." }
$hash = (Get-FileHash -Algorithm SHA256 $exe.FullName).Hash
Write-Output "$($exe.FullName)   $($exe.Length) bytes   SHA256 $hash"
Write-Output 'Abra PassVault.exe para iniciar o cofre.'
