# Honeyswarm hive installer (Windows / PowerShell).
# Requires Docker Desktop (Linux containers). Run in an elevated PowerShell:
#   irm "<controller>/agent/install.ps1?token=<token>" | iex
$ErrorActionPreference = "Stop"

$HoneyswarmUrl = "__HONEYSWARM_URL__"
$EnrollToken   = "__ENROLL_TOKEN__"
$AgentImage    = "__AGENT_IMAGE__"
$ContainerName = "honeyswarm-agent"

Write-Host "[honeyswarm] Installing hive agent..."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Error "Docker not found. Install Docker Desktop (https://docs.docker.com/desktop/install/windows-install/) with Linux containers enabled, then re-run."
  exit 1
}

Write-Host "[honeyswarm] Pulling agent image $AgentImage ..."
docker pull $AgentImage

docker rm -f $ContainerName 2>$null | Out-Null

Write-Host "[honeyswarm] Starting agent ..."
docker run -d --name $ContainerName --restart unless-stopped `
  -v /var/run/docker.sock:/var/run/docker.sock `
  -v honeyswarm_agent_state:/var/lib/honeyswarm `
  -e HONEYSWARM_URL=$HoneyswarmUrl `
  -e ENROLL_TOKEN=$EnrollToken `
  $AgentImage

Write-Host "[honeyswarm] Done. Follow logs with: docker logs -f $ContainerName"
