# Honeyswarm hive installer (Windows / PowerShell).
# Requires Docker Desktop (Linux containers). Run in an elevated PowerShell:
#   irm "<controller>/agent/install.ps1?token=<token>" | iex
$ErrorActionPreference = "Stop"

$HoneyswarmUrl = "__HONEYSWARM_URL__"
$EnrollToken   = "__ENROLL_TOKEN__"
$AgentImage    = "__AGENT_IMAGE__"
$TlsVerify     = "__AGENT_TLS_VERIFY__"
$ContainerName = "honeyswarm-agent"

Write-Host "[honeyswarm] Installing hive agent..."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Error "Docker not found. Install Docker Desktop (https://docs.docker.com/desktop/install/windows-install/) with Linux containers enabled, then re-run."
  exit 1
}

Write-Host "[honeyswarm] Pulling agent image $AgentImage ..."
docker pull $AgentImage

docker rm -f $ContainerName 2>$null | Out-Null

# Detect the host's primary reachable IP + hostname here (the agent runs in a
# container and can't see the host's address itself).
$HostIp = $null
try {
  $HostIp = (Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway } | Select-Object -First 1).IPv4Address.IPAddress
} catch {}
$HostName = $env:COMPUTERNAME
Write-Host "[honeyswarm] Reporting host IP: $HostIp ($HostName)"

Write-Host "[honeyswarm] Starting agent ..."
# Same-path bind mount so honeypot containers launched via the daemon see the
# agent's rendered config + log dirs (resolved inside the Docker Desktop VM).
docker run -d --name $ContainerName --restart unless-stopped `
  -v /var/run/docker.sock:/var/run/docker.sock `
  -v /var/lib/honeyswarm:/var/lib/honeyswarm `
  -e HONEYSWARM_URL=$HoneyswarmUrl `
  -e ENROLL_TOKEN=$EnrollToken `
  -e HONEYSWARM_HOST_IP=$HostIp `
  -e HONEYSWARM_HOST_NAME=$HostName `
  -e HONEYSWARM_TLS_VERIFY=$TlsVerify `
  $AgentImage

Write-Host "[honeyswarm] Done. Follow logs with: docker logs -f $ContainerName"
