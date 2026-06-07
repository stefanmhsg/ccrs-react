param(
    [string]$SourceDir = "experiments\runs\latest",
    [string]$BatchId = ("manual-" + (Get-Date -Format "yyyyMMdd-HHmmss")),
    [string]$RunId,
    [Parameter(Mandatory = $true)]
    [string]$AgentName,
    [Parameter(Mandatory = $true)]
    [string]$GraphName,
    [string]$RunMode = "manual",
    [Parameter(Mandatory = $true)]
    [string]$ReactLog,
    [string]$JavaLog,
    [switch]$EnableContingencyEscalationTool,
    [string]$ScenarioId,
    [int]$OptimalMoves,
    [string]$ExitCell,
    [string]$OutputRoot = "experiments\runs",
    [switch]$KeepSource,
    [string]$Notes
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

function ConvertTo-SafeName {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return "manual"
    }
    $safe = $Text -replace "[^A-Za-z0-9._-]+", "_"
    $safe = $safe.Trim("_")
    if (-not $safe) {
        return "manual"
    }
    if ($safe.Length -gt 90) {
        return $safe.Substring(0, 90)
    }
    return $safe
}

function New-UniqueDirectory {
    param([string]$BasePath)

    if (-not (Test-Path -LiteralPath $BasePath)) {
        return (New-Item -ItemType Directory -Path $BasePath)
    }
    for ($i = 1; $i -lt 1000; $i++) {
        $candidate = "$BasePath-$i"
        if (-not (Test-Path -LiteralPath $candidate)) {
            return (New-Item -ItemType Directory -Path $candidate)
        }
    }
    throw "Could not allocate a unique run directory for $BasePath"
}

function Get-JsonValue {
    param(
        $Record,
        [string]$Name
    )

    if ($null -eq $Record) {
        return $null
    }
    $property = $Record.PSObject.Properties[$Name]
    if ($property) {
        return $property.Value
    }
    return $null
}

function Get-EventType {
    param($Record)

    $type = Get-JsonValue $Record "type"
    if ($type) {
        return [string]$type
    }
    $event = Get-JsonValue $Record "event"
    if ($event) {
        $nestedType = Get-JsonValue $event "type"
        if ($nestedType) {
            return [string]$nestedType
        }
    }
    return $null
}

function Get-EventAgentValues {
    param($Record)

    $values = @()
    $agent = Get-JsonValue $Record "agent"
    if ($agent) {
        $values += [string]$agent
    }
    $event = Get-JsonValue $Record "event"
    if ($event) {
        $nestedAgent = Get-JsonValue $event "agent"
        if ($nestedAgent) {
            $values += [string]$nestedAgent
        }
    }
    return @($values | Where-Object { $_ } | Select-Object -Unique)
}

function Add-NdjsonRecord {
    param(
        [System.IO.StreamWriter]$Writer,
        $Record
    )

    $Writer.WriteLine(($Record | ConvertTo-Json -Depth 32 -Compress))
}

function Normalize-MaseExports {
    param(
        [System.IO.FileInfo[]]$Files,
        [string]$TargetPath
    )

    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    $writer = [System.IO.StreamWriter]::new($TargetPath, $false, $utf8NoBom)
    $eventCount = 0
    $parseErrors = 0
    $eventTypes = @{}
    $agents = @{}

    try {
        foreach ($file in $Files) {
            $raw = Get-Content -LiteralPath $file.FullName -Raw
            if ([string]::IsNullOrWhiteSpace($raw)) {
                continue
            }

            $trimmed = $raw.TrimStart()
            if ($trimmed.StartsWith("[")) {
                try {
                    foreach ($record in ($raw | ConvertFrom-Json)) {
                        $type = Get-EventType -Record $record
                        if ($type) {
                            $eventTypes[$type] = 1 + $(if ($eventTypes.ContainsKey($type)) { $eventTypes[$type] } else { 0 })
                        }
                        foreach ($agent in Get-EventAgentValues -Record $record) {
                            $agents[$agent] = $true
                        }
                        Add-NdjsonRecord -Writer $writer -Record $record
                        $eventCount++
                    }
                } catch {
                    $parseErrors++
                }
                continue
            }

            foreach ($line in ($raw -split "\r?\n")) {
                if ([string]::IsNullOrWhiteSpace($line)) {
                    continue
                }
                try {
                    $record = $line | ConvertFrom-Json
                    $type = Get-EventType -Record $record
                    if ($type) {
                        $eventTypes[$type] = 1 + $(if ($eventTypes.ContainsKey($type)) { $eventTypes[$type] } else { 0 })
                    }
                    foreach ($agent in Get-EventAgentValues -Record $record) {
                        $agents[$agent] = $true
                    }
                    $writer.WriteLine($line)
                    $eventCount++
                } catch {
                    $parseErrors++
                }
            }
        }
    } finally {
        $writer.Dispose()
    }

    return [pscustomobject][ordered]@{
        eventCount = $eventCount
        parseErrors = $parseErrors
        eventTypes = $eventTypes
        agents = @($agents.Keys | Sort-Object)
    }
}

function Copy-UniqueFile {
    param(
        [System.IO.FileInfo]$File,
        [string]$DestinationDirectory
    )

    $target = Join-Path $DestinationDirectory $File.Name
    if (Test-Path -LiteralPath $target) {
        $stem = [System.IO.Path]::GetFileNameWithoutExtension($File.Name)
        $extension = [System.IO.Path]::GetExtension($File.Name)
        for ($i = 1; $i -lt 1000; $i++) {
            $candidate = Join-Path $DestinationDirectory ("{0}-{1}{2}" -f $stem, $i, $extension)
            if (-not (Test-Path -LiteralPath $candidate)) {
                $target = $candidate
                break
            }
        }
    }
    Copy-Item -LiteralPath $File.FullName -Destination $target
    return (Split-Path -Leaf $target)
}

function Copy-OrMoveSourceFile {
    param(
        [System.IO.FileInfo]$File,
        [string]$DestinationDirectory,
        [switch]$CopyOnly
    )

    $target = Join-Path $DestinationDirectory $File.Name
    if (Test-Path -LiteralPath $target) {
        $stem = [System.IO.Path]::GetFileNameWithoutExtension($File.Name)
        $extension = [System.IO.Path]::GetExtension($File.Name)
        for ($i = 1; $i -lt 1000; $i++) {
            $candidate = Join-Path $DestinationDirectory ("{0}-{1}{2}" -f $stem, $i, $extension)
            if (-not (Test-Path -LiteralPath $candidate)) {
                $target = $candidate
                break
            }
        }
    }
    if ($CopyOnly) {
        Copy-Item -LiteralPath $File.FullName -Destination $target
    } else {
        Move-Item -LiteralPath $File.FullName -Destination $target
    }
    return (Split-Path -Leaf $target)
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$sourcePath = Resolve-RepoPath -RepoRoot $repoRoot -Path $SourceDir
$outputRootPath = Resolve-RepoPath -RepoRoot $repoRoot -Path $OutputRoot
$reactLogPath = Resolve-RepoPath -RepoRoot $repoRoot -Path $ReactLog
$javaLogPath = if ($JavaLog) { Resolve-RepoPath -RepoRoot $repoRoot -Path $JavaLog } else { $null }

if (-not (Test-Path -LiteralPath $reactLogPath -PathType Leaf)) {
    throw "React log not found: $reactLogPath"
}
if ($javaLogPath -and -not (Test-Path -LiteralPath $javaLogPath -PathType Leaf)) {
    throw "Java companion log not found: $javaLogPath"
}
if (-not (Test-Path -LiteralPath $sourcePath)) {
    New-Item -ItemType Directory -Path $sourcePath -Force | Out-Null
}

New-Item -ItemType Directory -Path $outputRootPath -Force | Out-Null
$batchDir = Join-Path $outputRootPath $BatchId
New-Item -ItemType Directory -Path $batchDir -Force | Out-Null

if (-not $RunId) {
    $existingCount = @(Get-ChildItem -Path $batchDir -Directory -ErrorAction SilentlyContinue).Count
    $RunId = "{0:D3}-{1}" -f ($existingCount + 1), (ConvertTo-SafeName -Text $AgentName)
}

$runDir = (New-UniqueDirectory -BasePath (Join-Path $batchDir (ConvertTo-SafeName -Text $RunId))).FullName
$sourceArchiveDir = Join-Path $runDir "source-exports"
New-Item -ItemType Directory -Path $sourceArchiveDir -Force | Out-Null

$sourceFiles = @()
if (Test-Path -LiteralPath $sourcePath) {
    $sourceFiles = @(Get-ChildItem -LiteralPath $sourcePath -File)
}

$maseExportFiles = @($sourceFiles | Where-Object {
    $_.Extension -in @(".ndjson", ".jsonl") -or
    ($_.Extension -eq ".json" -and $_.Name -match "mase-viewer|mase-events|event-archive|viewer-log")
})
$metadataFiles = @($sourceFiles | Where-Object { $maseExportFiles.FullName -notcontains $_.FullName })

$maseSummary = [pscustomobject][ordered]@{
    eventCount = 0
    parseErrors = 0
    eventTypes = @{}
    agents = @()
}
$sourceExportFiles = @()
$metadataArchiveFiles = @()

if ($maseExportFiles.Count -gt 0) {
    $maseEventsPath = Join-Path $runDir "mase-events.jsonl"
    $maseSummary = Normalize-MaseExports -Files $maseExportFiles -TargetPath $maseEventsPath
    foreach ($file in $maseExportFiles) {
        $sourceExportFiles += Copy-OrMoveSourceFile -File $file -DestinationDirectory $sourceArchiveDir -CopyOnly:$KeepSource
    }
}

foreach ($file in $metadataFiles) {
    $metadataArchiveFiles += Copy-OrMoveSourceFile -File $file -DestinationDirectory $sourceArchiveDir -CopyOnly:$KeepSource
}

$reactLogFile = Copy-UniqueFile -File (Get-Item -LiteralPath $reactLogPath) -DestinationDirectory $runDir
$javaLogFile = if ($javaLogPath) { Copy-UniqueFile -File (Get-Item -LiteralPath $javaLogPath) -DestinationDirectory $runDir } else { $null }

$importedAt = Get-Date
$maseCaptureStatus = if ($maseSummary.parseErrors -gt 0) {
    "partial"
} elseif ($maseSummary.eventCount -gt 0) {
    "completed"
} elseif ($maseExportFiles.Count -gt 0) {
    "empty"
} else {
    "missing"
}

$run = [ordered]@{
    batchId = $BatchId
    runId = Split-Path -Leaf $runDir
    agentName = $AgentName
    agentNames = @($AgentName)
    graphName = $GraphName
    runMode = $RunMode
    scenarioId = $ScenarioId
    optimalMoves = if ($PSBoundParameters.ContainsKey("OptimalMoves")) { $OptimalMoves } else { $null }
    exitCell = $ExitCell
    command = "manual"
    importedAt = $importedAt.ToString("o")
    sourceDir = (Resolve-Path -LiteralPath $sourcePath).Path
    status = "manual_import"
    reactLogFile = $reactLogFile
    javaLogFile = $javaLogFile
    logFiles = @($reactLogFile) + @($(if ($javaLogFile) { $javaLogFile } else { @() }))
    enableContingencyEscalationTool = [bool]$EnableContingencyEscalationTool
    maseMode = "manual"
    maseEventCapture = if ($maseExportFiles.Count -gt 0) { "viewer_export" } else { "none" }
    maseCaptureStatus = $maseCaptureStatus
    maseCaptureFile = if ($maseSummary.eventCount -gt 0) { "mase-events.jsonl" } else { $null }
    maseCaptureEventCount = $maseSummary.eventCount
    maseCaptureParseErrors = $maseSummary.parseErrors
    maseCaptureAgents = $maseSummary.agents
    maseEventTypeCounts = $maseSummary.eventTypes
    sourceExportFiles = $sourceExportFiles
    metadataFiles = $metadataArchiveFiles
    notes = $Notes
}

$run | ConvertTo-Json -Depth 12 | Set-Content -Path (Join-Path $runDir "run.json") -Encoding UTF8

$runs = @()
foreach ($dir in Get-ChildItem -Path $batchDir -Directory | Sort-Object Name) {
    $candidateRunJson = Join-Path $dir.FullName "run.json"
    if (Test-Path -LiteralPath $candidateRunJson) {
        $runs += (Get-Content -Path $candidateRunJson -Raw | ConvertFrom-Json)
    }
}

[ordered]@{
    batchId = $BatchId
    createdOrUpdatedAt = (Get-Date).ToString("o")
    repoRoot = $repoRoot
    sourceDir = (Resolve-Path -LiteralPath $sourcePath).Path
    importedBy = "experiments/scripts/import-manual-run.ps1"
    runs = $runs
} | ConvertTo-Json -Depth 12 | Set-Content -Path (Join-Path $batchDir "manifest.json") -Encoding UTF8

Write-Host "Imported React manual run: $($run.runId)"
Write-Host "Run directory: $runDir"
Write-Host "React log: $reactLogFile"
if ($javaLogFile) {
    Write-Host "Java log: $javaLogFile"
}
Write-Host "MASE events: $($maseSummary.eventCount); parse errors: $($maseSummary.parseErrors)"
Write-Host "Generate or refresh parsed CSV artifacts with:"
Write-Host "  powershell -ExecutionPolicy Bypass -File experiments/scripts/parse-experiment-logs.ps1 -BatchId $BatchId"
