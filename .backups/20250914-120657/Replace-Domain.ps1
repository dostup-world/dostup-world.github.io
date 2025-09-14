param(
  [string]$Path = ".",
  [string]$OldDomain = "dostup-plus.github.io",
  [string]$NewDomain = "dostup-world.github.io",
  [switch]$WhatIf
)

$ErrorActionPreference = 'SilentlyContinue'

# Root
$rootObj = Resolve-Path $Path
$root = $rootObj.Path

# Folders to skip
$excludeDirs = @(
  '.git','node_modules','dist','build','.next','out','.cache',
  'venv','.venv','.idea','.vscode','coverage','tmp','logs'
)

# Binary extensions to skip
$skipExt = @(
  '.png','.jpg','.jpeg','.gif','.webp','.avif','.ico',
  '.woff','.woff2','.ttf','.eot','.otf',
  '.pdf','.zip','.7z','.rar','.gz','.bz2','.xz',
  '.mp4','.mp3','.mov','.avi','.mkv'
)

function Test-IsExcluded([string]$fullPath) {
  foreach ($d in $excludeDirs) {
    $p = '(?i)(\\|/)' + [regex]::Escape($d) + '($|\\|/)'
    if ($fullPath -match $p) { return $true }
  }
  return $false
}

# Backup folder
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupRoot = Join-Path $root ('.backups\' + $timestamp)

# Precompile regex
$oldEsc = [regex]::Escape($OldDomain)

[int]$scanned = 0
[int]$changed = 0
[int]$skipped = 0

Write-Host "=== Domain replace ==="
Write-Host ("Root:   " + $root)
Write-Host ("From:   " + $OldDomain)
Write-Host ("To:     " + $NewDomain)
if ($WhatIf) { Write-Host "Mode:   WHATIF (no writes)" }

# Collect candidate files
$files = Get-ChildItem -Path $root -Recurse -File |
  Where-Object {
    -not (Test-IsExcluded $_.FullName) -and
    ($skipExt -notcontains ([IO.Path]::GetExtension($_.Name).ToLower()))
  }

if (-not $files -or $files.Count -eq 0) {
  Write-Host "No candidate files found. Nothing to do."
  exit 0
}

foreach ($f in $files) {
  $scanned++

  # Read as text (UTF-8 first, then default)
  $text = $null
  try { $text = Get-Content -LiteralPath $f.FullName -Raw -Encoding UTF8 } catch {}
  if ($null -eq $text) {
    try { $text = Get-Content -LiteralPath $f.FullName -Raw } catch {}
  }
  if ($null -eq $text) {
    $skipped++
    continue
  }

  $orig = $text

  # 1) http/https -> https://NewDomain
  $text = [regex]::Replace($text, "(?i)\bhttps?://$oldEsc\b", "https://$NewDomain")
  # 2) protocol-relative //OldDomain (not after http:)
  $text = [regex]::Replace($text, "(?i)(?<!https?:)//$oldEsc\b", "//$NewDomain")
  # 3) bare domain
  $text = [regex]::Replace($text, "\b$oldEsc\b", $NewDomain)

  if ($text -ne $orig) {
    if ($WhatIf) {
      Write-Host ("[WHATIF] would change: " + $f.FullName)
      continue
    }

    # Backup original
    $rel = $f.FullName.Substring($root.Length).TrimStart('\','/')
    $backupPath = Join-Path $backupRoot $rel
    $backupDir = Split-Path $backupPath -Parent
    if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir -Force | Out-Null }
    Copy-Item -LiteralPath $f.FullName -Destination $backupPath -Force

    # Write updated
    try {
      Set-Content -LiteralPath $f.FullName -Value $text -Encoding UTF8
      $changed++
      Write-Host ("Changed: " + $f.FullName)
    } catch {
      $skipped++
      Write-Host ("Skip (write error): " + $f.FullName)
    }
  }
}

Write-Host "=== Summary ==="
Write-Host ("Scanned:  " + $scanned)
Write-Host ("Changed:  " + $changed)
Write-Host ("Skipped:  " + $skipped)

# Quick leftover check
$left = Get-ChildItem -Path $root -Recurse -File |
  Where-Object { -not (Test-IsExcluded $_.FullName) } |
  Select-String -Pattern $OldDomain -SimpleMatch |
  Select-Object -First 1

if ($left) {
  Write-Host "Note: leftovers with OldDomain still exist (see a sample above)."
} else {
  Write-Host "Done: no occurrences of OldDomain left in scanned files."
}
