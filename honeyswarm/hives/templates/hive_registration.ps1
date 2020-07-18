Write-Host "Setting Execution Policy"
Set-ExecutionPolicy bypass
Write-Host "Fetching Minion Installer"
# We need to fix the default TLS version
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$minion_url = "https://raw.githubusercontent.com/saltstack/salt-bootstrap/develop/bootstrap-salt.ps1"
$honeyswarm_host = "{{honeyswarm_host}}"
$minion_id = "{{salt_minion_id}}"
Invoke-WebRequest $minion_url -OutFile bootstrap-salt.ps1
Write-Host "Installing Minion $minion_id"
./bootstrap-salt.ps1 -pythonVersion 3 -minion $minion_id -master $honeyswarm_host

# we may need to fix the AppRestart

#ssm set salt-minion AppRestartDelay 60000