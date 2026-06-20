<#
.SYNOPSIS
  Move Claude Code CLI chat history for THIS repo between your own machines.

  Claude Code stores each terminal session as a .jsonl transcript under
  ~/.claude/projects/<project-slug>/ where <project-slug> is the repo's
  absolute path with every non-alphanumeric character replaced by '-'. That
  slug differs per machine (different drive/username/path), so you can't just
  copy the folder verbatim if the paths differ -- this script recomputes the
  slug on each side.

  EXPORT (old machine):  zips this repo's session transcripts.
  IMPORT (new machine):  unzips them into the matching local project folder,
                         so `claude --resume` lists them.

  Same Claude account on both machines is assumed (you authenticate normally).

.EXAMPLE
  # on the OLD machine, from anywhere inside the GP repo:
  pwsh tools/claude_sessions.ps1 export
  #   -> writes  ~/gp-claude-sessions.zip   (transfer this file)

.EXAMPLE
  # on the NEW machine, after `git clone` + `cd GP`:
  pwsh tools/claude_sessions.ps1 import -Zip C:\path\to\gp-claude-sessions.zip
  cd <repo> ; claude --resume        # pick the session from the list
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory, Position = 0)][ValidateSet('export', 'import')]
  [string]$Action,
  [string]$Zip                       # export: output path; import: input path
)
$ErrorActionPreference = 'Stop'

# repo root (git if available, else current dir) -> Claude project slug
$repo = (& git rev-parse --show-toplevel 2>$null)
if (-not $repo) { $repo = (Get-Location).Path }
$abs  = (Resolve-Path $repo).Path
$slug = ($abs -replace '[^A-Za-z0-9]', '-')
$proj = Join-Path $env:USERPROFILE ".claude\projects\$slug"

if ($Action -eq 'export') {
  if (-not (Test-Path $proj)) { throw "No Claude sessions found at $proj" }
  $out = if ($Zip) { $Zip } else { Join-Path $env:USERPROFILE 'gp-claude-sessions.zip' }
  if (Test-Path $out) { Remove-Item $out -Force }
  Compress-Archive -Path (Join-Path $proj '*.jsonl') -DestinationPath $out -Force
  $n = (Get-ChildItem (Join-Path $proj '*.jsonl')).Count
  Write-Host "Exported $n session(s) from"
  Write-Host "  $proj"
  Write-Host "to  $out"
  Write-Host "Transfer that .zip to the other machine, then run the import."
}
else {
  if (-not $Zip -or -not (Test-Path $Zip)) { throw "Pass -Zip <path-to-gp-claude-sessions.zip>" }
  New-Item -ItemType Directory -Force $proj | Out-Null
  Expand-Archive -Path $Zip -DestinationPath $proj -Force
  $n = (Get-ChildItem (Join-Path $proj '*.jsonl')).Count
  Write-Host "Imported into"
  Write-Host "  $proj"
  Write-Host "Now: cd '$abs'  then  claude --resume   ($n session(s) available)"
}
