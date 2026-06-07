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
        foreach ($line in Get-Content -LiteralPath $reactLogFile) {
            $lineNumber++
            $fields = ConvertFrom-KeyValueLine -Line $line
            if ($fields -and $fields["_prefix"] -eq "[REACT-CCRS-EVENT]") {
                $reactEventCount++
                $eventName = [string](Get-MapValue $fields "event")
                Add-CycleEvent -Cycles $cycles -RunMeta $runMeta -Fields $fields -EventName $eventName -FileName (Split-Path -Leaf $reactLogFile) -LineNumber $lineNumber

                if ($eventName -eq "react.ccrs.prompt_context.visible") {
                    $promptVisibleEventCount++
                }
                if ($eventName -eq "react.ccrs.opportunistic.detected") {
                    $opportunisticDetectedCount++
                }
                if ($eventName -like "react.ccrs.contingency.*" -or $eventName -like "react.ccrs.opportunistic_guidance_by_contingency_ccrs.*") {
                    $contingencyEventCount++
                    [void]$contingencyRows.Add([pscustomobject][ordered]@{
                        batch_id = $runMeta.batchId
                        run_id = $runMeta.runId
                        agent_name = $runMeta.agentName
                        graph_name = $runMeta.graphName
                        file = Split-Path -Leaf $reactLogFile
                        line = $lineNumber
                        react_event = $eventName
                        cycle = Get-MapValue $fields "cycle"
                        cycle_timestamp = Get-MapValue $fields "cycle_timestamp"
                        strategy_id = Get-MapValue $fields "strategy_id"
                        trace_id = Get-MapValue $fields "trace_id"
                        top_action = Get-MapValue $fields "top_action"
                        stop = Get-MapValue $fields "stop"
                        reason = Get-MapValue $fields "reason"
                        target = Get-MapValue $fields @("target", "current_resource")
                        matched_entries = Get-MapValue $fields "matched_entries"
                        active_entries = Get-MapValue $fields "active_entries"
                    })
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
                    action_type = $actionMatch.Groups["tool"].Value
                    target = $target
                    outcome = "invoked"
                })
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
                [void]$javaRows.Add([pscustomobject][ordered]@{
                    batch_id = $runMeta.batchId
                    run_id = $runMeta.runId
                    agent_name = $runMeta.agentName
                    graph_name = $runMeta.graphName
                    file = Split-Path -Leaf $javaLogFile
                    line = $lineNumber
                    timestamp = Get-LineTimestamp -Line $line
                    java_event = if ($fields) { Get-MapValue $fields "event" } else { "" }
                    prefix = if ($fields) { Get-MapValue $fields "_prefix" } else { "[JAVA-CCRS]" }
                    message = $line
                })
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

    $sortedCycles = @($cycles.Values | Sort-Object @{ Expression = { [int]$_.cycle } })
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
    "react_event", "cycle", "cycle_timestamp", "strategy_id", "trace_id",
    "top_action", "stop", "reason", "target", "matched_entries", "active_entries"
)
Write-CsvRows -Rows $opportunisticRows -Path (Join-Path $outputPath "opportunistic.csv") -Headers @(
    "batch_id", "run_id", "agent_name", "graph_name", "file", "line",
    "react_event", "cycle", "cycle_timestamp", "tool_call_id", "tool_name",
    "target", "type", "pattern_id", "utility", "entries", "reason"
)
Write-CsvRows -Rows $actionRows -Path (Join-Path $outputPath "actions.csv") -Headers @(
    "batch_id", "run_id", "agent_name", "graph_name", "file", "line",
    "timestamp", "action_type", "target", "outcome"
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
        "java-library-evidence.csv",
        "path-analysis-inputs"
    )
}
$summary | ConvertTo-Json -Depth 8 | Set-Content -Path (Join-Path $outputPath "summary.json") -Encoding UTF8

Write-Host "Parsed React experiment batch."
Write-Host "Run root: $runRootPath"
Write-Host "Output directory: $outputPath"
Write-Host "Runs: $($runsRows.Count); MASE events: $($maseRows.Count); decisions: $($decisionRows.Count); contingency rows: $($contingencyRows.Count)"
