param(
    [string]$BatchId,
    [string]$RunRoot,
    [string]$OutputDir
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

function ConvertTo-TypedValue {
    param([string]$Text)

    if ($null -eq $Text -or $Text -eq "null") { return $null }
    if ($Text -eq "true") { return $true }
    if ($Text -eq "false") { return $false }

    $number = 0.0
    if ([double]::TryParse(
        $Text,
        [System.Globalization.NumberStyles]::Float,
        [System.Globalization.CultureInfo]::InvariantCulture,
        [ref]$number
    )) {
        if ($Text -notmatch "[\.\-+eE]") {
            return [int64]$number
        }
        return $number
    }
    return $Text
}

function Unescape-QuotedValue {
    param([string]$Text)

    if ($null -eq $Text) { return $null }
    $value = $Text
    $value = $value.Replace('\t', "`t")
    $value = $value.Replace('\r', "`r")
    $value = $value.Replace('\n', "`n")
    $value = $value.Replace('\"', '"')
    $value = $value.Replace('\\', '\')
    return $value
}

function ConvertFrom-KeyValueLine {
    param([string]$Line)

    $prefixes = @("[REACT-CCRS-EVENT]", "[CCRS-EVENT]")
    $start = -1
    $prefix = $null
    foreach ($candidate in $prefixes) {
        $idx = $Line.IndexOf($candidate)
        if ($idx -ge 0) {
            $start = $idx + $candidate.Length
            $prefix = $candidate
            break
        }
    }
    if ($start -lt 0) {
        return $null
    }

    $payload = $Line.Substring($start).Trim()
    $result = @{}
    $result["_prefix"] = $prefix

    $regex = [regex]'([A-Za-z_][A-Za-z0-9_.-]*)=("(?:\\.|[^"\\])*"|[^ \t\r\n]+)'
    foreach ($match in $regex.Matches($payload)) {
        $key = $match.Groups[1].Value
        $raw = $match.Groups[2].Value
        if ($raw.StartsWith('"') -and $raw.EndsWith('"')) {
            $raw = Unescape-QuotedValue -Text $raw.Substring(1, $raw.Length - 2)
        }
        $result[$key] = ConvertTo-TypedValue -Text $raw
    }
    return $result
}

function Get-MapValue {
    param(
        $Map,
        [string[]]$Key,
        $Default = $null
    )

    if (-not $Map) {
        return $Default
    }
    foreach ($candidate in $Key) {
        if ($Map -is [System.Collections.IDictionary] -and $Map.Contains($candidate)) {
            return $Map[$candidate]
        }
        $property = $Map.PSObject.Properties[$candidate]
        if ($property) {
            return $property.Value
        }
    }
    return $Default
}

function Get-EventType {
    param($Record)

    $type = Get-MapValue $Record "type"
    if ($type) { return [string]$type }
    $event = Get-MapValue $Record "event"
    if ($event) {
        $nestedType = Get-MapValue $event "type"
        if ($nestedType) { return [string]$nestedType }
    }
    return $null
}

function Get-NestedValue {
    param(
        $Record,
        [string]$TopName,
        [string]$NestedName
    )

    $value = Get-MapValue $Record $TopName
    if ($value) { return $value }
    $event = Get-MapValue $Record "event"
    if ($event) {
        return (Get-MapValue $event $NestedName)
    }
    return $null
}

function ConvertTo-PathAnalysisCell {
    param([string]$Cell)

    if (-not $Cell) {
        return $null
    }
    $match = [regex]::Match($Cell, "(?i)/cells/[^/?#\s]+/[^/?#\s]+")
    if ($match.Success) {
        return $match.Value
    }
    return $Cell
}

function Get-ResourceLabel {
    param(
        [string]$Value,
        [string]$PathPrefix
    )

    if (-not $Value) {
        return "unknown"
    }
    if ($Value -match ("(?i)/" + [regex]::Escape($PathPrefix.Trim("/")) + "/([^/?#\s]+)")) {
        return $matches[1]
    }

    $trimmed = $Value.TrimEnd("/", "#")
    $last = [regex]::Match($trimmed, "[^/#?]+$")
    if ($last.Success) {
        return $last.Value
    }
    return $Value
}

function Test-ExperimentAgent {
    param(
        [object]$RunMeta,
        [string]$Agent
    )

    if (-not $Agent -or -not $RunMeta.agentNames) {
        return $false
    }

    $agentLabel = Get-ResourceLabel -Value $Agent -PathPrefix "agents"
    foreach ($candidate in @($RunMeta.agentNames)) {
        if (-not $candidate) {
            continue
        }
        $candidateLabel = Get-ResourceLabel -Value ([string]$candidate) -PathPrefix "agents"
        if ($candidate -eq $Agent -or $candidateLabel -eq $agentLabel) {
            return $true
        }
    }
    return $false
}

function ConvertTo-SafeFileName {
    param([string]$Text)

    if (-not $Text) {
        return "unknown"
    }
    $safe = $Text -replace "[^A-Za-z0-9._-]+", "_"
    $safe = $safe.Trim("_")
    if (-not $safe) {
        return "unknown"
    }
    if ($safe.Length -gt 80) {
        return $safe.Substring(0, 80)
    }
    return $safe
}

function Get-LineTimestamp {
    param([string]$Line)

    $match = [regex]::Match($Line, "^(?<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})")
    if ($match.Success) {
        return $match.Groups["timestamp"].Value
    }
    return $null
}

function Add-CycleEvent {
    param(
        [hashtable]$Cycles,
        [object]$RunMeta,
        [hashtable]$Fields,
        [string]$EventName,
        [string]$FileName,
        [int]$LineNumber
    )

    $cycle = Get-MapValue $Fields "cycle"
    if ($null -eq $cycle -or "$cycle" -eq "") {
        return
    }
    $key = "$cycle"
    if (-not $Cycles.ContainsKey($key)) {
        $Cycles[$key] = [ordered]@{
            batch_id = $RunMeta.batchId
            run_id = $RunMeta.runId
            agent_name = $RunMeta.agentName
            graph_name = $RunMeta.graphName
            cycle = $key
            cycle_timestamp = Get-MapValue $Fields "cycle_timestamp"
            first_file = $FileName
            first_line = $LineNumber
            event_count = 0
            opportunistic_detected_count = 0
            opportunistic_prompt_visible_count = 0
            selection_count = 0
            contingency_event_count = 0
            contingency_guidance_event_count = 0
        }
    }
    $row = $Cycles[$key]
    $row.event_count++
    if (-not $row.cycle_timestamp) {
        $row.cycle_timestamp = Get-MapValue $Fields "cycle_timestamp"
    }
    if ($EventName -eq "react.ccrs.opportunistic.detected") {
        $row.opportunistic_detected_count++
    }
    if ($EventName -eq "react.ccrs.prompt_context.visible") {
        $row.opportunistic_prompt_visible_count += [int](Get-MapValue $Fields "opportunistic_count" 0)
    }
    if ($EventName -eq "react.ccrs.opportunistic.selection") {
        $row.selection_count++
    }
    if ($EventName -like "react.ccrs.contingency.*") {
        $row.contingency_event_count++
    }
    if ($EventName -like "react.ccrs.opportunistic_guidance_by_contingency_ccrs.*") {
        $row.contingency_guidance_event_count++
    }
}

function Write-CsvRows {
    param(
        [object[]]$Rows,
        [string]$Path,
        [string[]]$Headers
    )

    if ($Rows -and $Rows.Count -gt 0) {
        $Rows | Select-Object $Headers | Export-Csv -Path $Path -NoTypeInformation -Encoding UTF8
    } else {
        Set-Content -Path $Path -Value (($Headers -join ",") + "`n") -Encoding UTF8
    }
}

function ConvertTo-EpochMilliseconds {
    param($Timestamp)

    if ($null -eq $Timestamp -or "$Timestamp" -eq "") {
        return $null
    }
    $text = "$Timestamp"
    $number = 0L
    if ([int64]::TryParse($text, [ref]$number)) {
        return $number
    }
    $formats = @("yyyy-MM-dd HH:mm:ss,fff", "yyyy-MM-dd HH:mm:ss.fff", "yyyy-MM-ddTHH:mm:ss.fffK")
    foreach ($format in $formats) {
        try {
            $date = [datetime]::ParseExact(
                $text,
                $format,
                [System.Globalization.CultureInfo]::InvariantCulture
            )
            return [int64](($date.ToUniversalTime() - [datetime]'1970-01-01T00:00:00Z').TotalMilliseconds)
        } catch {
        }
    }
    try {
        $date = [datetime]::Parse($text, [System.Globalization.CultureInfo]::InvariantCulture)
        return [int64](($date.ToUniversalTime() - [datetime]'1970-01-01T00:00:00Z').TotalMilliseconds)
    } catch {
        return $null
    }
}

function Get-ContingencyInvocationForTimestamp {
    param(
        [object[]]$Invocations,
        $TimestampMs
    )

    if ($null -eq $TimestampMs) {
        return $null
    }

    foreach ($invocation in $Invocations) {
        if ($null -eq $invocation.evaluate_timestamp_ms) {
            continue
        }
        $returnedMs = $invocation.returned_timestamp_ms
        if ($TimestampMs -ge $invocation.evaluate_timestamp_ms -and ($null -eq $returnedMs -or $TimestampMs -le $returnedMs)) {
            return $invocation
        }
    }

    return $null
}

function ConvertFrom-ToolResultJson {
    param([string]$Line)

    $match = [regex]::Match($Line, "\[TOOL_NODE\] Tool result: (?<json>\{.*\})\s*$")
    if (-not $match.Success) {
        return $null
    }
    try {
        return ($match.Groups["json"].Value | ConvertFrom-Json)
    } catch {
        return $null
    }
}

function Update-LatestActionWithToolResult {
    param(
        [System.Collections.ArrayList]$ActionRows,
        $RunMeta,
        $ToolResult,
        [string]$Line,
        [int]$LineNumber
    )

    if ($null -eq $ToolResult) {
        return
    }

    $toolName = Get-MapValue $ToolResult "tool_name"
    $target = Get-MapValue $ToolResult "target"
    for ($idx = $ActionRows.Count - 1; $idx -ge 0; $idx--) {
        $row = $ActionRows[$idx]
        if ($row.run_id -ne $RunMeta.runId) {
            continue
        }
        if ($row.result_line -and "$($row.result_line)" -ne "") {
            continue
        }
        if ($toolName -and $row.action_type -ne $toolName) {
            continue
        }
        if ($target -and $row.target -ne $target) {
            continue
        }

        $row.tool_call_id = Get-MapValue $ToolResult "tool_call_id"
        $row.outcome = Get-MapValue $ToolResult "outcome" $row.outcome
        $row.http_status = Get-MapValue $ToolResult "http_status"
        $row.http_ok = Get-MapValue $ToolResult "http_ok"
        $row.response_length = Get-MapValue $ToolResult "response_length"
        $row.content_type = Get-MapValue $ToolResult "content_type"
        $row.error = Get-MapValue $ToolResult "error"
        $row.error_type = Get-MapValue $ToolResult "error_type"
        $row.result_line = $LineNumber
        $row.result_timestamp = Get-LineTimestamp -Line $Line
        return
    }
}

function New-MoveActionCorrelationRows {
    param(
        [object[]]$Runs,
        [object[]]$ActionRows,
        [object[]]$MoveRows
    )

    $rows = [System.Collections.ArrayList]::new()
    foreach ($run in $Runs) {
        $runId = $run.run_id
        $actions = @($ActionRows | Where-Object { $_.run_id -eq $runId } | Sort-Object `
            @{ Expression = { $value = ConvertTo-EpochMilliseconds $_.timestamp; if ($null -eq $value) { [int64]::MaxValue } else { $value } }; Ascending = $true },
            @{ Expression = { [int]$_.line }; Ascending = $true })
        $moves = @($MoveRows | Where-Object { $_.run_id -eq $runId } | Sort-Object @{ Expression = { [int]$_.sequence }; Ascending = $true })

        $starts = @()
        $searchStart = 0
        foreach ($move in $moves) {
            $moveTimestamp = ConvertTo-EpochMilliseconds $move.timestamp
            $matchedIndex = -1
            for ($idx = $searchStart; $idx -lt $actions.Count; $idx++) {
                $action = $actions[$idx]
                if ($action.action_type -ne "http_post") {
                    continue
                }
                if ($action.target -ne $move.cell) {
                    continue
                }
                $actionTimestamp = ConvertTo-EpochMilliseconds $action.timestamp
                if ($null -ne $moveTimestamp -and $null -ne $actionTimestamp -and $actionTimestamp -gt ($moveTimestamp + 10000)) {
                    continue
                }
                $matchedIndex = $idx
                break
            }

            if ($matchedIndex -ge 0) {
                $starts += [pscustomobject][ordered]@{
                    move = $move
                    action_index = $matchedIndex
                }
                $searchStart = $matchedIndex + 1
            }
        }

        for ($i = 0; $i -lt $starts.Count; $i++) {
            $start = $starts[$i]
            $endIndex = if ($i + 1 -lt $starts.Count) { $starts[$i + 1].action_index } else { $actions.Count }
            $windowActions = @()
            for ($idx = $start.action_index; $idx -lt $endIndex; $idx++) {
                $windowActions += $actions[$idx]
            }
            $statusCodes = @($windowActions | Where-Object { $_.http_status -ne $null -and "$($_.http_status)" -ne "" } | ForEach-Object { "$($_.http_status)" })
            $httpErrorCount = @($windowActions | Where-Object {
                $status = Get-MapValue $_ "http_status"
                ($status -ne $null -and "$status" -ne "" -and [int]$status -ge 400) -or $_.outcome -eq "error"
            }).Count

            [void]$rows.Add([pscustomobject][ordered]@{
                batch_id = $run.batch_id
                run_id = $runId
                move_sequence = $start.move.sequence
                move_cell = $start.move.cell
                move_timestamp = $start.move.timestamp
                move_line = $start.move.line
                start_action_line = $actions[$start.action_index].line
                start_action_timestamp = $actions[$start.action_index].timestamp
                end_before_action_line = if ($endIndex -lt $actions.Count) { $actions[$endIndex].line } else { "" }
                action_count = $windowActions.Count
                get_count = @($windowActions | Where-Object { $_.action_type -eq "http_get" }).Count
                post_count = @($windowActions | Where-Object { $_.action_type -eq "http_post" }).Count
                http_error_count = $httpErrorCount
                status_codes = ($statusCodes -join ";")
                action_lines = (($windowActions | ForEach-Object { "$($_.line)" }) -join ";")
                action_targets = (($windowActions | ForEach-Object { "$($_.target)" }) -join ";")
                match_quality = "target_timestamp_order"
            })
        }
    }
    return @($rows)
}

function New-MoveDurationRows {
    param([object[]]$MoveActionRows)

    $rows = [System.Collections.ArrayList]::new()
    foreach ($group in ($MoveActionRows | Group-Object run_id | Sort-Object Name)) {
        $moves = @($group.Group | Sort-Object @{ Expression = { [int]$_.move_sequence }; Ascending = $true })
        for ($i = 0; $i -lt $moves.Count; $i++) {
            $current = $moves[$i]
            $durationMs = $null
            if ($i -gt 0) {
                $previousTimestamp = ConvertTo-EpochMilliseconds $moves[$i - 1].move_timestamp
                $currentTimestamp = ConvertTo-EpochMilliseconds $current.move_timestamp
                if ($null -ne $previousTimestamp -and $null -ne $currentTimestamp) {
                    $durationMs = $currentTimestamp - $previousTimestamp
                }
            }
            $actionCount = [int]$current.action_count
            $failureCount = [int]$current.http_error_count
            $successCount = [math]::Max(0, $actionCount - $failureCount)
            [void]$rows.Add([pscustomobject][ordered]@{
                batch_id = $current.batch_id
                run_id = $current.run_id
                move_sequence = $current.move_sequence
                move_cell = $current.move_cell
                move_timestamp = $current.move_timestamp
                duration_ms = $durationMs
                action_count = $actionCount
                http_success_count = $successCount
                http_failure_count = $failureCount
                get_count = $current.get_count
                post_count = $current.post_count
                status_codes = $current.status_codes
            })
        }
    }
    return @($rows)
}

function New-RunMeta {
    param(
        [System.IO.DirectoryInfo]$RunDir,
        $Raw
    )

    [pscustomobject][ordered]@{
        batchId = Get-MapValue $Raw @("batchId", "batch_id") (Split-Path -Leaf (Split-Path -Parent $RunDir.FullName))
        runId = Get-MapValue $Raw @("runId", "run_id") $RunDir.Name
        agentName = Get-MapValue $Raw @("agentName", "agent_name") ""
        graphName = Get-MapValue $Raw @("graphName", "graph_name") ""
        runMode = Get-MapValue $Raw @("runMode", "run_mode") "manual"
        agentNames = @(Get-MapValue $Raw @("agentNames", "agent_names", "maseCaptureAgentNames", "mase_capture_agent_names") @())
        scenarioId = Get-MapValue $Raw @("scenarioId", "scenario_id") ""
        optimalMoves = Get-MapValue $Raw @("optimalMoves", "optimal_moves")
        exitCell = Get-MapValue $Raw @("exitCell", "exit_cell") ""
        enableContingencyEscalationTool = Get-MapValue $Raw @("enableContingencyEscalationTool", "enable_contingency_escalation_tool") $false
        reactLogFile = Get-MapValue $Raw @("reactLogFile", "react_log_file")
        javaLogFile = Get-MapValue $Raw @("javaLogFile", "java_log_file")
        maseCaptureStatus = Get-MapValue $Raw @("maseCaptureStatus", "mase_capture_status") "missing"
        maseCaptureEventCount = Get-MapValue $Raw @("maseCaptureEventCount", "mase_capture_event_count") 0
        importedAt = Get-MapValue $Raw "importedAt"
        notes = Get-MapValue $Raw "notes"
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $RunRoot) {
    if (-not $BatchId) {
        throw "Provide -BatchId or -RunRoot."
    }
    $RunRoot = Join-Path "experiments\runs" $BatchId
}
if (-not $OutputDir) {
    if ($BatchId) {
        $OutputDir = Join-Path "experiments\reports" $BatchId
    } else {
        $OutputDir = Join-Path "experiments\reports" (Split-Path -Leaf $RunRoot)
    }
}

$runRootPath = Resolve-RepoPath -RepoRoot $repoRoot -Path $RunRoot
$outputPath = Resolve-RepoPath -RepoRoot $repoRoot -Path $OutputDir
if (-not (Test-Path -LiteralPath $runRootPath -PathType Container)) {
    throw "Run root does not exist: $runRootPath"
}
New-Item -ItemType Directory -Path $outputPath -Force | Out-Null

$runsRows = [System.Collections.ArrayList]::new()
$decisionRows = [System.Collections.ArrayList]::new()
$contingencyRows = [System.Collections.ArrayList]::new()
$opportunisticRows = [System.Collections.ArrayList]::new()
$actionRows = [System.Collections.ArrayList]::new()
$moveActionCorrelationRows = @()
$javaRows = [System.Collections.ArrayList]::new()
$maseRows = [System.Collections.ArrayList]::new()
$moveRows = [System.Collections.ArrayList]::new()
$transactionRows = [System.Collections.ArrayList]::new()
$agentRows = [System.Collections.ArrayList]::new()
$cycleRows = [System.Collections.ArrayList]::new()

foreach ($runDir in Get-ChildItem -Path $runRootPath -Directory | Sort-Object Name) {
    $runJsonPath = Join-Path $runDir.FullName "run.json"
    if (-not (Test-Path -LiteralPath $runJsonPath -PathType Leaf)) {
        continue
    }

    $rawRun = Get-Content -Path $runJsonPath -Raw | ConvertFrom-Json
    $runMeta = New-RunMeta -RunDir $runDir -Raw $rawRun
    $cycles = @{}
    $loopCycles = @{}
    $reactEventCount = 0
    $selectionEventCount = 0
    $promptVisibleEventCount = 0
    $contingencyEventCount = 0
    $opportunisticDetectedCount = 0
    $javaEvidenceCount = 0

    $reactLogFile = if ($runMeta.reactLogFile) {
        Join-Path $runDir.FullName $runMeta.reactLogFile
    } else {
        $candidate = @(Get-ChildItem -Path $runDir.FullName -File -Filter "*.log" | Where-Object { $_.Name -notlike "*.java.log" } | Select-Object -First 1)
        if ($candidate.Count -gt 0) { $candidate[0].FullName } else { $null }
    }

    if ($reactLogFile -and (Test-Path -LiteralPath $reactLogFile -PathType Leaf)) {
        $lineNumber = 0
        $contingencyInvocation = 0
        $activeContingencyInvocation = 0
        $pendingContingencyContext = $null
        $contingencyInvocations = [System.Collections.ArrayList]::new()
        foreach ($line in Get-Content -LiteralPath $reactLogFile) {
            $lineNumber++
            $fields = ConvertFrom-KeyValueLine -Line $line
            if ($fields -and $fields["_prefix"] -eq "[REACT-CCRS-EVENT]") {
                $reactEventCount++
                $eventName = [string](Get-MapValue $fields "event")
                if ($eventName -eq "react.loop.cycle") {
                    Add-CycleEvent -Cycles $loopCycles -RunMeta $runMeta -Fields $fields -EventName $eventName -FileName (Split-Path -Leaf $reactLogFile) -LineNumber $lineNumber
                } else {
                    Add-CycleEvent -Cycles $cycles -RunMeta $runMeta -Fields $fields -EventName $eventName -FileName (Split-Path -Leaf $reactLogFile) -LineNumber $lineNumber
                }

                if ($eventName -eq "react.ccrs.prompt_context.visible") {
                    $promptVisibleEventCount++
                }
                if ($eventName -eq "react.ccrs.opportunistic.detected") {
                    $opportunisticDetectedCount++
                }
                if ($eventName -like "react.ccrs.contingency.*" -or $eventName -like "react.ccrs.opportunistic_guidance_by_contingency_ccrs.*") {
                    $contingencyEventCount++
                    if ($eventName -eq "react.ccrs.contingency.escalation.activated") {
                        $pendingContingencyContext = [pscustomobject][ordered]@{
                            cycle = Get-MapValue $fields "cycle"
                            cycle_timestamp = Get-MapValue $fields "cycle_timestamp"
                            situation_type = Get-MapValue $fields "situation_type"
                            trigger = Get-MapValue $fields "trigger"
                            current_resource = Get-MapValue $fields "current_resource"
                            target_resource = Get-MapValue $fields "target_resource"
                            failed_action = Get-MapValue $fields "failed_action"
                        }
                    }
                    if ($eventName -eq "react.ccrs.contingency.evaluate") {
                        $contingencyInvocation++
                        $activeContingencyInvocation = $contingencyInvocation
                        [void]$contingencyInvocations.Add([pscustomobject][ordered]@{
                            invocation = $activeContingencyInvocation
                            evaluate_timestamp_ms = ConvertTo-EpochMilliseconds (Get-LineTimestamp -Line $line)
                            returned_timestamp_ms = $null
                            cycle = if (Get-MapValue $fields "cycle") { Get-MapValue $fields "cycle" } elseif ($pendingContingencyContext) { $pendingContingencyContext.cycle } else { "" }
                            cycle_timestamp = if (Get-MapValue $fields "cycle_timestamp") { Get-MapValue $fields "cycle_timestamp" } elseif ($pendingContingencyContext) { $pendingContingencyContext.cycle_timestamp } else { "" }
                            situation_type = if (Get-MapValue $fields "situation_type") { Get-MapValue $fields "situation_type" } elseif ($pendingContingencyContext) { $pendingContingencyContext.situation_type } else { "" }
                            trigger = if (Get-MapValue $fields "trigger") { Get-MapValue $fields "trigger" } elseif ($pendingContingencyContext) { $pendingContingencyContext.trigger } else { "" }
                            current_resource = if (Get-MapValue $fields "current_resource") { Get-MapValue $fields "current_resource" } elseif ($pendingContingencyContext) { $pendingContingencyContext.current_resource } else { "" }
                            target_resource = if (Get-MapValue $fields "target_resource") { Get-MapValue $fields "target_resource" } elseif ($pendingContingencyContext) { $pendingContingencyContext.target_resource } else { "" }
                            failed_action = if (Get-MapValue $fields "failed_action") { Get-MapValue $fields "failed_action" } elseif ($pendingContingencyContext) { $pendingContingencyContext.failed_action } else { "" }
                        })
                    } elseif ($eventName -eq "react.ccrs.contingency.returned" -and $activeContingencyInvocation -eq 0) {
                        $contingencyInvocation++
                        $activeContingencyInvocation = $contingencyInvocation
                        [void]$contingencyInvocations.Add([pscustomobject][ordered]@{
                            invocation = $activeContingencyInvocation
                            evaluate_timestamp_ms = ConvertTo-EpochMilliseconds (Get-LineTimestamp -Line $line)
                            returned_timestamp_ms = $null
                            cycle = if (Get-MapValue $fields "cycle") { Get-MapValue $fields "cycle" } elseif ($pendingContingencyContext) { $pendingContingencyContext.cycle } else { "" }
                            cycle_timestamp = if (Get-MapValue $fields "cycle_timestamp") { Get-MapValue $fields "cycle_timestamp" } elseif ($pendingContingencyContext) { $pendingContingencyContext.cycle_timestamp } else { "" }
                            situation_type = if (Get-MapValue $fields "situation_type") { Get-MapValue $fields "situation_type" } elseif ($pendingContingencyContext) { $pendingContingencyContext.situation_type } else { "" }
                            trigger = if (Get-MapValue $fields "trigger") { Get-MapValue $fields "trigger" } elseif ($pendingContingencyContext) { $pendingContingencyContext.trigger } else { "" }
                            current_resource = if (Get-MapValue $fields "current_resource") { Get-MapValue $fields "current_resource" } elseif ($pendingContingencyContext) { $pendingContingencyContext.current_resource } else { "" }
                            target_resource = if (Get-MapValue $fields "target_resource") { Get-MapValue $fields "target_resource" } elseif ($pendingContingencyContext) { $pendingContingencyContext.target_resource } else { "" }
                            failed_action = if (Get-MapValue $fields "failed_action") { Get-MapValue $fields "failed_action" } elseif ($pendingContingencyContext) { $pendingContingencyContext.failed_action } else { "" }
                        })
                    }
                    [void]$contingencyRows.Add([pscustomobject][ordered]@{
                        batch_id = $runMeta.batchId
                        run_id = $runMeta.runId
                        agent_name = $runMeta.agentName
                        graph_name = $runMeta.graphName
                        file = Split-Path -Leaf $reactLogFile
                        line = $lineNumber
                        react_event = $eventName
                        invocation = if ($activeContingencyInvocation -gt 0) { $activeContingencyInvocation } else { "" }
                        cycle = Get-MapValue $fields "cycle"
                        cycle_timestamp = Get-MapValue $fields "cycle_timestamp"
                        strategy_id = Get-MapValue $fields @("strategy_id", "top_strategy_id")
                        trace_id = Get-MapValue $fields "trace_id"
                        top_action = Get-MapValue $fields @("top_action", "top_action_type")
                        stop = Get-MapValue $fields "stop"
                        reason = Get-MapValue $fields "reason"
                        target = Get-MapValue $fields @("target", "target_resource", "current_resource")
                        situation_type = Get-MapValue $fields "situation_type"
                        trigger = Get-MapValue $fields "trigger"
                        current_resource = Get-MapValue $fields "current_resource"
                        target_resource = Get-MapValue $fields "target_resource"
                        failed_action = Get-MapValue $fields "failed_action"
                        evaluations = Get-MapValue $fields "evaluations"
                        suggestions = Get-MapValue $fields "suggestions"
                        no_help = Get-MapValue $fields "no_help"
                        opportunistic_guidance = Get-MapValue $fields "opportunistic_guidance"
                        result_type = ""
                        action_type = ""
                        action_target = ""
                        confidence = ""
                        evaluation_time_ms = ""
                        has_opportunistic_guidance = ""
                        no_help_reason = ""
                        rationale = ""
                        matched_entries = Get-MapValue $fields "matched_entries"
                        active_entries = Get-MapValue $fields "active_entries"
                    })
                    if ($eventName -eq "react.ccrs.contingency.returned") {
                        foreach ($invocation in $contingencyInvocations) {
                            if ($invocation.invocation -eq $activeContingencyInvocation) {
                                $invocation.returned_timestamp_ms = ConvertTo-EpochMilliseconds (Get-LineTimestamp -Line $line)
                                if (-not $invocation.cycle) { $invocation.cycle = Get-MapValue $fields "cycle" }
                                if (-not $invocation.cycle_timestamp) { $invocation.cycle_timestamp = Get-MapValue $fields "cycle_timestamp" }
                                break
                            }
                        }
                        $activeContingencyInvocation = 0
                        $pendingContingencyContext = $null
                    }
                }
                if ($eventName -like "react.ccrs.opportunistic.*" -and $eventName -ne "react.ccrs.opportunistic.selection") {
                    [void]$opportunisticRows.Add([pscustomobject][ordered]@{
                        batch_id = $runMeta.batchId
                        run_id = $runMeta.runId
                        agent_name = $runMeta.agentName
                        graph_name = $runMeta.graphName
                        file = Split-Path -Leaf $reactLogFile
                        line = $lineNumber
                        react_event = $eventName
                        cycle = Get-MapValue $fields "cycle"
                        cycle_timestamp = Get-MapValue $fields "cycle_timestamp"
                        tool_call_id = Get-MapValue $fields "tool_call_id"
                        tool_name = Get-MapValue $fields "tool_name"
                        target = Get-MapValue $fields "target"
                        type = Get-MapValue $fields "type"
                        pattern_id = Get-MapValue $fields "pattern_id"
                        utility = Get-MapValue $fields "utility"
                        entries = Get-MapValue $fields "entries"
                        reason = Get-MapValue $fields "reason"
                    })
                }
                if ($eventName -eq "react.ccrs.opportunistic.selection") {
                    $selectionEventCount++
                    [void]$decisionRows.Add([pscustomobject][ordered]@{
                        batch_id = $runMeta.batchId
                        run_id = $runMeta.runId
                        agent_name = $runMeta.agentName
                        graph_name = $runMeta.graphName
                        file = Split-Path -Leaf $reactLogFile
                        line = $lineNumber
                        cycle = Get-MapValue $fields "cycle"
                        cycle_timestamp = Get-MapValue $fields "cycle_timestamp"
                        tool_name = Get-MapValue $fields "tool_name"
                        tool_call_id = Get-MapValue $fields "tool_call_id"
                        selected_uri = Get-MapValue $fields "selected_uri"
                        selection_mode = Get-MapValue $fields "selection_mode"
                        opportunistic_count = Get-MapValue $fields "opportunistic_count" 0
                        contingency_guidance_count = Get-MapValue $fields "contingency_guidance_count" 0
                        followed_top_opportunistic = Get-MapValue $fields "followed_top_opportunistic" $false
                        followed_top_contingency_guidance = Get-MapValue $fields "followed_top_contingency_guidance" $false
                        followed_any_top_guidance = Get-MapValue $fields "followed_any_top_guidance" $false
                        top_opportunistic_target = Get-MapValue $fields "top_opportunistic_target"
                        top_contingency_guidance_target = Get-MapValue $fields "top_contingency_guidance_target"
                        prompt_context_id = Get-MapValue $fields "prompt_context_id"
                        metric_quality = "selection_event"
                    })
                }
                continue
            }

            $actionMatch = [regex]::Match($line, "\[TOOL_NODE\] Invoking tool: (?<tool>\S+) with args: (?<args>.*)$")
            if ($actionMatch.Success) {
                $argsText = $actionMatch.Groups["args"].Value
                $target = $null
                $targetMatch = [regex]::Match($argsText, '["'']url["'']\s*:\s*["''](?<url>[^"'']+)["'']')
                if ($targetMatch.Success) {
                    $target = $targetMatch.Groups["url"].Value
                }
                [void]$actionRows.Add([pscustomobject][ordered]@{
                    batch_id = $runMeta.batchId
                    run_id = $runMeta.runId
                    agent_name = $runMeta.agentName
                    graph_name = $runMeta.graphName
                    file = Split-Path -Leaf $reactLogFile
                    line = $lineNumber
                    timestamp = Get-LineTimestamp -Line $line
                    tool_call_id = ""
                    action_type = $actionMatch.Groups["tool"].Value
                    target = $target
                    outcome = "invoked"
                    http_status = ""
                    http_ok = ""
                    response_length = ""
                    content_type = ""
                    error = ""
                    error_type = ""
                    result_line = ""
                    result_timestamp = ""
                })
                continue
            }

            $toolResult = ConvertFrom-ToolResultJson -Line $line
            if ($toolResult) {
                Update-LatestActionWithToolResult -ActionRows $actionRows -RunMeta $runMeta -ToolResult $toolResult -Line $line -LineNumber $lineNumber
            }
        }
    }

    $javaLogFile = if ($runMeta.javaLogFile) {
        Join-Path $runDir.FullName $runMeta.javaLogFile
    } else {
        $candidate = @(Get-ChildItem -Path $runDir.FullName -File -Filter "*.java.log" | Select-Object -First 1)
        if ($candidate.Count -gt 0) { $candidate[0].FullName } else { $null }
    }
    if ($javaLogFile -and (Test-Path -LiteralPath $javaLogFile -PathType Leaf)) {
        $lineNumber = 0
        foreach ($line in Get-Content -LiteralPath $javaLogFile) {
            $lineNumber++
            if ($line.Contains("[JAVA-CCRS]") -or $line.Contains("[CCRS-EVENT]")) {
                $javaEvidenceCount++
                $fields = ConvertFrom-KeyValueLine -Line $line
                $javaEvent = if ($fields) { Get-MapValue $fields "event" } else { "" }
                [void]$javaRows.Add([pscustomobject][ordered]@{
                    batch_id = $runMeta.batchId
                    run_id = $runMeta.runId
                    agent_name = $runMeta.agentName
                    graph_name = $runMeta.graphName
                    file = Split-Path -Leaf $javaLogFile
                    line = $lineNumber
                    timestamp = Get-LineTimestamp -Line $line
                    java_event = $javaEvent
                    prefix = if ($fields) { Get-MapValue $fields "_prefix" } else { "[JAVA-CCRS]" }
                    message = $line
                })
                if ($javaEvent -eq "ccrs.contingency.strategy.evaluated") {
                    $invocationContext = Get-ContingencyInvocationForTimestamp `
                        -Invocations @($contingencyInvocations) `
                        -TimestampMs (ConvertTo-EpochMilliseconds (Get-LineTimestamp -Line $line))
                    [void]$contingencyRows.Add([pscustomobject][ordered]@{
                        batch_id = $runMeta.batchId
                        run_id = $runMeta.runId
                        agent_name = $runMeta.agentName
                        graph_name = $runMeta.graphName
                        file = Split-Path -Leaf $javaLogFile
                        line = $lineNumber
                        react_event = $javaEvent
                        invocation = if ($invocationContext) { $invocationContext.invocation } else { "" }
                        cycle = if ($invocationContext) { $invocationContext.cycle } else { "" }
                        cycle_timestamp = if ($invocationContext) { $invocationContext.cycle_timestamp } else { "" }
                        strategy_id = Get-MapValue $fields "strategy_id"
                        trace_id = ""
                        top_action = Get-MapValue $fields "action_type"
                        stop = if ((Get-MapValue $fields "action_type") -eq "stop") { $true } else { "" }
                        reason = Get-MapValue $fields "no_help_reason"
                        target = Get-MapValue $fields "action_target"
                        situation_type = if ($invocationContext) { $invocationContext.situation_type } else { "" }
                        trigger = if ($invocationContext) { $invocationContext.trigger } else { "" }
                        current_resource = if ($invocationContext) { $invocationContext.current_resource } else { "" }
                        target_resource = if ($invocationContext) { $invocationContext.target_resource } else { "" }
                        failed_action = if ($invocationContext) { $invocationContext.failed_action } else { "" }
                        evaluations = ""
                        suggestions = if ((Get-MapValue $fields "result_type") -eq "suggestion") { 1 } else { 0 }
                        no_help = if ((Get-MapValue $fields "result_type") -eq "no_help") { 1 } else { 0 }
                        opportunistic_guidance = Get-MapValue $fields "has_opportunistic_guidance"
                        result_type = Get-MapValue $fields "result_type"
                        action_type = Get-MapValue $fields "action_type"
                        action_target = Get-MapValue $fields "action_target"
                        confidence = Get-MapValue $fields "confidence"
                        evaluation_time_ms = Get-MapValue $fields "evaluation_time_ms"
                        has_opportunistic_guidance = Get-MapValue $fields "has_opportunistic_guidance"
                        no_help_reason = Get-MapValue $fields "no_help_reason"
                        rationale = Get-MapValue $fields "rationale"
                        matched_entries = ""
                        active_entries = ""
                    })
                }
            }
        }
    }

    $maseFile = Join-Path $runDir.FullName "mase-events.jsonl"
    $moveSequenceByAgent = @{}
    $maseEventCount = 0
    $maseMoveCount = 0
    $maseTransactionCount = 0
    if (Test-Path -LiteralPath $maseFile -PathType Leaf) {
        $lineNumber = 0
        foreach ($line in Get-Content -LiteralPath $maseFile) {
            $lineNumber++
            if ([string]::IsNullOrWhiteSpace($line)) {
                continue
            }
            try {
                $record = $line | ConvertFrom-Json
            } catch {
                continue
            }

            $type = Get-EventType -Record $record
            $agent = Get-NestedValue -Record $record -TopName "agent" -NestedName "agent"
            $cell = Get-NestedValue -Record $record -TopName "cell" -NestedName "cell"
            $graph = Get-NestedValue -Record $record -TopName "graph" -NestedName "graph"
            $timestamp = Get-NestedValue -Record $record -TopName "timestamp" -NestedName "timestamp"
            $transactionId = Get-NestedValue -Record $record -TopName "transactionId" -NestedName "transactionId"

            if ($runMeta.agentNames -and @($runMeta.agentNames).Count -gt 0 -and -not (Test-ExperimentAgent -RunMeta $runMeta -Agent $agent)) {
                continue
            }

            $maseEventCount++
            [void]$maseRows.Add([pscustomobject][ordered]@{
                batch_id = $runMeta.batchId
                run_id = $runMeta.runId
                line = $lineNumber
                mase_run_id = Get-MapValue $record "runId"
                type = $type
                timestamp = $timestamp
                agent = $agent
                cell = $cell
                graph = $graph
                transaction_id = $transactionId
                archive_id = Get-MapValue $record "archiveId"
            })
            if ($type -eq "AGENT_MOVED") {
                $maseMoveCount++
                $agentKey = if ($agent) { [string]$agent } else { "unknown" }
                if (-not $moveSequenceByAgent.ContainsKey($agentKey)) {
                    $moveSequenceByAgent[$agentKey] = 0
                }
                $moveSequenceByAgent[$agentKey]++
                [void]$moveRows.Add([pscustomobject][ordered]@{
                    batch_id = $runMeta.batchId
                    run_id = $runMeta.runId
                    sequence = $moveSequenceByAgent[$agentKey]
                    line = $lineNumber
                    timestamp = $timestamp
                    agent = $agent
                    cell = $cell
                    path_analysis_cell = ConvertTo-PathAnalysisCell -Cell $cell
                })
            }
            if ($type -eq "TRANSACTION") {
                $event = Get-MapValue $record "event"
                $maseTransactionCount++
                [void]$transactionRows.Add([pscustomobject][ordered]@{
                    batch_id = $runMeta.batchId
                    run_id = $runMeta.runId
                    line = $lineNumber
                    timestamp = $timestamp
                    agent = $agent
                    graph = $graph
                    transaction_id = $transactionId
                    trigger = Get-MapValue $event "trigger"
                    status = Get-MapValue $event "status"
                    error = Get-MapValue $event "error"
                    rule_count = Get-MapValue $event "ruleCount"
                    started_at = Get-MapValue $event "startedAt"
                    finished_at = Get-MapValue $event "finishedAt"
                })
            }
        }
    }

    $runMoveRows = @($moveRows | Where-Object { $_.run_id -eq $runMeta.runId })
    foreach ($group in ($runMoveRows | Group-Object { Get-ResourceLabel -Value $_.agent -PathPrefix "agents" } | Sort-Object Name)) {
        $agentMoves = @($group.Group | Sort-Object @{ Expression = { [int]$_.sequence } })
        $agent = if ($agentMoves.Count -gt 0) { $agentMoves[0].agent } else { $group.Name }
        [void]$agentRows.Add([pscustomobject][ordered]@{
            batch_id = $runMeta.batchId
            run_id = $runMeta.runId
            agent = $agent
            move_count = $agentMoves.Count
            first_cell = if ($agentMoves.Count -gt 0) { $agentMoves[0].cell } else { $null }
            final_cell = if ($agentMoves.Count -gt 0) { $agentMoves[$agentMoves.Count - 1].cell } else { $null }
        })
    }

    $cycleSource = if ($loopCycles.Count -gt 0) { $loopCycles } else { $cycles }
    $sortedCycles = @($cycleSource.Values | Sort-Object @{ Expression = { [int]$_.cycle } })
    if ($sortedCycles.Count -gt 0) {
        for ($i = 0; $i -lt $sortedCycles.Count; $i++) {
            $current = $sortedCycles[$i]
            $durationMs = $null
            if ($i -gt 0 -and $current.cycle_timestamp -and $sortedCycles[$i - 1].cycle_timestamp) {
                try {
                    $prevTime = [datetimeoffset]::Parse([string]$sortedCycles[$i - 1].cycle_timestamp)
                    $currentTime = [datetimeoffset]::Parse([string]$current.cycle_timestamp)
                    $durationMs = [math]::Round(($currentTime - $prevTime).TotalMilliseconds, 3)
                } catch {
                    $durationMs = $null
                }
            }
            [void]$cycleRows.Add([pscustomobject][ordered]@{
                batch_id = $current.batch_id
                run_id = $current.run_id
                agent_name = $current.agent_name
                graph_name = $current.graph_name
                sequence = $i + 1
                cycle = $current.cycle
                cycle_timestamp = $current.cycle_timestamp
                duration_ms = $durationMs
                file = $current.first_file
                line = $current.first_line
                event_count = $current.event_count
                opportunistic_detected_count = $current.opportunistic_detected_count
                opportunistic_prompt_visible_count = $current.opportunistic_prompt_visible_count
                selection_count = $current.selection_count
                contingency_event_count = $current.contingency_event_count
                contingency_guidance_event_count = $current.contingency_guidance_event_count
            })
        }
    }

    [void]$runsRows.Add([pscustomobject][ordered]@{
        batch_id = $runMeta.batchId
        run_id = $runMeta.runId
        agent_name = $runMeta.agentName
        graph_name = $runMeta.graphName
        run_mode = $runMeta.runMode
        scenario_id = $runMeta.scenarioId
        optimal_moves = $runMeta.optimalMoves
        exit_cell = $runMeta.exitCell
        enable_contingency_escalation_tool = $runMeta.enableContingencyEscalationTool
        imported_at = $runMeta.importedAt
        react_log_file = if ($reactLogFile) { Split-Path -Leaf $reactLogFile } else { $null }
        java_log_file = if ($javaLogFile) { Split-Path -Leaf $javaLogFile } else { $null }
        mase_capture_status = $runMeta.maseCaptureStatus
        mase_event_count = $maseEventCount
        mase_move_count = $maseMoveCount
        mase_transaction_count = $maseTransactionCount
        react_event_count = $reactEventCount
        prompt_visible_event_count = $promptVisibleEventCount
        selection_event_count = $selectionEventCount
        opportunistic_detected_count = $opportunisticDetectedCount
        contingency_event_count = $contingencyEventCount
        java_library_evidence_count = $javaEvidenceCount
        decision_metric_quality = if ($selectionEventCount -gt 0) { "selection_event" } else { "missing_selection_event" }
        notes = $runMeta.notes
    })
}

$moveActionCorrelationRows = New-MoveActionCorrelationRows -Runs $runsRows -ActionRows $actionRows -MoveRows $moveRows
$moveDurationRows = New-MoveDurationRows -MoveActionRows $moveActionCorrelationRows

$pathInputDir = Join-Path $outputPath "path-analysis-inputs"
if (Test-Path -LiteralPath $pathInputDir -PathType Container) {
    Get-ChildItem -LiteralPath $pathInputDir -Force | Remove-Item -Recurse -Force
} else {
    New-Item -ItemType Directory -Path $pathInputDir -Force | Out-Null
}
foreach ($group in ($moveRows | Group-Object run_id, agent)) {
    $first = $group.Group[0]
    $safeName = "{0}.{1}.cells.txt" -f (ConvertTo-SafeFileName $first.run_id), (ConvertTo-SafeFileName $first.agent)
    $cells = @($group.Group | Sort-Object @{ Expression = { [int]$_.sequence } } | ForEach-Object { $_.path_analysis_cell } | Where-Object { $_ })
    Set-Content -Path (Join-Path $pathInputDir $safeName) -Value ($cells -join "`n") -Encoding UTF8
}

Write-CsvRows -Rows $runsRows -Path (Join-Path $outputPath "runs.csv") -Headers @(
    "batch_id", "run_id", "agent_name", "graph_name", "run_mode", "scenario_id",
    "optimal_moves", "exit_cell", "enable_contingency_escalation_tool",
    "imported_at", "react_log_file", "java_log_file", "mase_capture_status",
    "mase_event_count", "mase_move_count", "mase_transaction_count",
    "react_event_count", "prompt_visible_event_count", "selection_event_count",
    "opportunistic_detected_count", "contingency_event_count",
    "java_library_evidence_count", "decision_metric_quality", "notes"
)
Write-CsvRows -Rows $agentRows -Path (Join-Path $outputPath "agents.csv") -Headers @(
    "batch_id", "run_id", "agent", "move_count", "first_cell", "final_cell"
)
Write-CsvRows -Rows $maseRows -Path (Join-Path $outputPath "mase-events.csv") -Headers @(
    "batch_id", "run_id", "line", "mase_run_id", "type", "timestamp", "agent",
    "cell", "graph", "transaction_id", "archive_id"
)
Write-CsvRows -Rows $moveRows -Path (Join-Path $outputPath "mase-agent-moved.csv") -Headers @(
    "batch_id", "run_id", "sequence", "line", "timestamp", "agent", "cell",
    "path_analysis_cell"
)
Write-CsvRows -Rows $transactionRows -Path (Join-Path $outputPath "mase-transactions.csv") -Headers @(
    "batch_id", "run_id", "line", "timestamp", "agent", "graph",
    "transaction_id", "trigger", "status", "error", "rule_count", "started_at",
    "finished_at"
)
Write-CsvRows -Rows $cycleRows -Path (Join-Path $outputPath "cycle-durations.csv") -Headers @(
    "batch_id", "run_id", "agent_name", "graph_name", "sequence", "cycle",
    "cycle_timestamp", "duration_ms", "file", "line", "event_count",
    "opportunistic_detected_count", "opportunistic_prompt_visible_count",
    "selection_count", "contingency_event_count", "contingency_guidance_event_count"
)
Write-CsvRows -Rows $decisionRows -Path (Join-Path $outputPath "decisions.csv") -Headers @(
    "batch_id", "run_id", "agent_name", "graph_name", "file", "line", "cycle",
    "cycle_timestamp", "tool_name", "tool_call_id", "selected_uri",
    "selection_mode", "opportunistic_count", "contingency_guidance_count",
    "followed_top_opportunistic", "followed_top_contingency_guidance",
    "followed_any_top_guidance", "top_opportunistic_target",
    "top_contingency_guidance_target", "prompt_context_id", "metric_quality"
)
Write-CsvRows -Rows $contingencyRows -Path (Join-Path $outputPath "contingency.csv") -Headers @(
    "batch_id", "run_id", "agent_name", "graph_name", "file", "line",
    "react_event", "invocation", "cycle", "cycle_timestamp", "strategy_id",
    "trace_id", "top_action", "stop", "reason", "target", "situation_type",
    "trigger", "current_resource", "target_resource", "failed_action",
    "evaluations", "suggestions", "no_help", "opportunistic_guidance",
    "result_type", "action_type", "action_target", "confidence",
    "evaluation_time_ms", "has_opportunistic_guidance", "no_help_reason",
    "rationale",
    "matched_entries", "active_entries"
)
Write-CsvRows -Rows $opportunisticRows -Path (Join-Path $outputPath "opportunistic.csv") -Headers @(
    "batch_id", "run_id", "agent_name", "graph_name", "file", "line",
    "react_event", "cycle", "cycle_timestamp", "tool_call_id", "tool_name",
    "target", "type", "pattern_id", "utility", "entries", "reason"
)
Write-CsvRows -Rows $actionRows -Path (Join-Path $outputPath "actions.csv") -Headers @(
    "batch_id", "run_id", "agent_name", "graph_name", "file", "line",
    "timestamp", "tool_call_id", "action_type", "target", "outcome",
    "http_status", "http_ok", "response_length", "content_type",
    "error", "error_type", "result_line", "result_timestamp"
)
Write-CsvRows -Rows $moveActionCorrelationRows -Path (Join-Path $outputPath "move-action-correlation.csv") -Headers @(
    "batch_id", "run_id", "move_sequence", "move_cell", "move_timestamp",
    "move_line", "start_action_line", "start_action_timestamp",
    "end_before_action_line", "action_count", "get_count", "post_count",
    "http_error_count", "status_codes", "action_lines", "action_targets",
    "match_quality"
)
Write-CsvRows -Rows $moveDurationRows -Path (Join-Path $outputPath "move-durations.csv") -Headers @(
    "batch_id", "run_id", "move_sequence", "move_cell", "move_timestamp",
    "duration_ms", "action_count", "http_success_count", "http_failure_count",
    "get_count", "post_count", "status_codes"
)
Write-CsvRows -Rows $javaRows -Path (Join-Path $outputPath "java-library-evidence.csv") -Headers @(
    "batch_id", "run_id", "agent_name", "graph_name", "file", "line",
    "timestamp", "java_event", "prefix", "message"
)

$summary = [ordered]@{
    batchId = if ($BatchId) { $BatchId } else { Split-Path -Leaf $runRootPath }
    generatedAt = (Get-Date).ToString("o")
    runRoot = (Resolve-Path -LiteralPath $runRootPath).Path
    outputDir = (Resolve-Path -LiteralPath $outputPath).Path
    runCount = $runsRows.Count
    maseEventCount = $maseRows.Count
    decisionCount = $decisionRows.Count
    contingencyRowCount = $contingencyRows.Count
    moveActionCorrelationRowCount = $moveActionCorrelationRows.Count
    moveDurationRowCount = $moveDurationRows.Count
    javaEvidenceCount = $javaRows.Count
    artifacts = @(
        "runs.csv",
        "agents.csv",
        "mase-events.csv",
        "mase-agent-moved.csv",
        "mase-transactions.csv",
        "cycle-durations.csv",
        "decisions.csv",
        "contingency.csv",
        "opportunistic.csv",
        "actions.csv",
        "move-action-correlation.csv",
        "move-durations.csv",
        "java-library-evidence.csv",
        "path-analysis-inputs"
    )
}
$summary | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $outputPath "summary.json") -Encoding UTF8

Write-Host "Parsed React experiment batch."
Write-Host "Run root: $runRootPath"
Write-Host "Output directory: $outputPath"
Write-Host "Runs: $($runsRows.Count); MASE events: $($maseRows.Count); decisions: $($decisionRows.Count); contingency rows: $($contingencyRows.Count)"
