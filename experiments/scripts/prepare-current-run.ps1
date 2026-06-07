param(
    [string]$StagingDir = "experiments\runs\latest"
)

$ErrorActionPreference = "Stop"

function Resolve-RepoPath {
    param(
        [string]$RepoRoot,
        [string]$Path
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }
    return (Join-Path $RepoRoot $Path)
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$runsRoot = (Resolve-Path (Join-Path $repoRoot "experiments\runs")).Path
$stagingPath = Resolve-RepoPath -RepoRoot $repoRoot -Path $StagingDir

if (Test-Path -LiteralPath $stagingPath) {
    $resolvedStagingPath = (Resolve-Path -LiteralPath $stagingPath).Path
    if (-not $resolvedStagingPath.StartsWith($runsRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean a staging directory outside experiments\runs: $resolvedStagingPath"
    }
    if ((Split-Path -Leaf $resolvedStagingPath) -ne "latest") {
        throw "Refusing to clean non-staging run directory: $resolvedStagingPath"
    }
    Get-ChildItem -LiteralPath $resolvedStagingPath -Force | Remove-Item -Recurse -Force
} else {
    New-Item -ItemType Directory -Path $stagingPath -Force | Out-Null
    $resolvedStagingPath = (Resolve-Path -LiteralPath $stagingPath).Path
}

Write-Host "Prepared clean React experiment staging directory:"
Write-Host "  $resolvedStagingPath"
Write-Host "Export MASE viewer NDJSON/JSONL files here after the next manual run."
