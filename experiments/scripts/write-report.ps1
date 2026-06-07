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

function Import-CsvIfPresent {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return @()
    }
    $rows = @(Import-Csv -Path $Path)
    return $rows
}

function Convert-ToDoubleOrNull {
    param($Value)

    if ($null -eq $Value -or "$Value" -eq "") {
        return $null
    }
    return [double]::Parse("$Value", [System.Globalization.CultureInfo]::InvariantCulture)
}

function Convert-ToIntOrZero {
    param($Value)

    if ($null -eq $Value -or "$Value" -eq "") {
        return 0
    }
    return [int]$Value
}

function Format-MarkdownCell {
    param($Value)

    if ($null -eq $Value -or "$Value" -eq "") {
        return "-"
    }
    $text = "$Value"
    $text = $text.Replace("&", "&amp;").Replace("<", "&lt;").Replace(">", "&gt;")
    $text = $text -replace "\r?\n", "<br>"
    $text = $text.Replace("|", "\|")
    return $text.Trim()
}

function Format-CodeCell {
    param($Value)

    $formatted = Format-MarkdownCell $Value
    if ($formatted -eq "-") {
        return "-"
    }
    return "``$formatted``"
}

function Format-NumberCell {
    param($Value)

    if ($null -eq $Value -or "$Value" -eq "") {
        return "-"
    }
    return "$Value"
}

function Format-Ms {
    param($Value)

    $number = Convert-ToDoubleOrNull $Value
    if ($null -eq $number) {
        return "-"
    }
    return $number.ToString("0.##", [System.Globalization.CultureInfo]::InvariantCulture)
}

function Get-Average {
    param([object[]]$Rows, [string]$Field)

    $values = @()
    foreach ($row in $Rows) {
        $number = Convert-ToDoubleOrNull $row.$Field
        if ($null -ne $number) {
            $values += $number
        }
    }
    if ($values.Count -eq 0) {
        return $null
    }
    return [math]::Round(($values | Measure-Object -Average).Average, 2)
}

function Get-Sum {
    param([object[]]$Rows, [string]$Field)

    $sum = 0.0
    $count = 0
    foreach ($row in $Rows) {
        $number = Convert-ToDoubleOrNull $row.$Field
        if ($null -ne $number) {
            $sum += $number
            $count++
        }
    }
    if ($count -eq 0) {
        return $null
    }
    return [math]::Round($sum, 2)
}

function Test-True {
    param($Value)

    return "$Value".ToLowerInvariant() -eq "true"
}

function Test-CcrsRun {
    param($Run)

    return (
        "$($Run.graph_name)" -like "*ccrs*" -or
        "$($Run.run_id)" -like "*ccrs*" -or
        (Test-True $Run.enable_contingency_escalation_tool)
    )
}

function Test-ReachedExit {
    param(
        $Run,
        [string]$FinalCell,
        [string]$ExitCell
    )

    if (-not $FinalCell) {
        return "-"
    }

    if ($ExitCell) {
        if ($FinalCell -eq $ExitCell -or $FinalCell -like "*/$ExitCell") {
            return "yes"
        }
        return "no"
    }

    if ($FinalCell -match "(^|/)cells/999$") {
        return "yes"
    }
    return "no"
}

function Get-DeltaFromOptimal {
    param(
        $OptimalMoves,
        $ActualMoves
    )

    if ($null -eq $OptimalMoves -or "$OptimalMoves" -eq "" -or $null -eq $ActualMoves -or "$ActualMoves" -eq "") {
        return $null
    }
    return (Convert-ToIntOrZero $ActualMoves) - (Convert-ToIntOrZero $OptimalMoves)
}

function Get-CcrsInvocationCyclesByRun {
    param([object[]]$ContingencyRows)

    $byRun = @{}
    foreach ($row in @($ContingencyRows | Where-Object { $_.react_event -eq "react.ccrs.contingency.escalation.activated" })) {
        $runId = "$($row.run_id)"
        if (-not $byRun.ContainsKey($runId)) {
            $byRun[$runId] = [System.Collections.ArrayList]::new()
        }
        [void]$byRun[$runId].Add($row)
    }

    $result = @{}
    foreach ($runId in $byRun.Keys) {
        $result[$runId] = @($byRun[$runId] | Sort-Object @{ Expression = { Convert-ToIntOrZero $_.cycle }; Ascending = $true })
    }
    return $result
}

function Get-CycleRowsForRuns {
    param(
        [object[]]$Cycles,
        [object[]]$Runs,
        [bool]$Ccrs
    )

    $runIds = @($Runs | Where-Object { (Test-CcrsRun $_) -eq $Ccrs } | ForEach-Object { $_.run_id })
    if ($runIds.Count -eq 0) {
        return @()
    }
    return @($Cycles | Where-Object { $runIds -contains $_.run_id })
}

function Get-CcrsOppAverage {
    param(
        [object[]]$Cycles,
        [object[]]$Runs,
        [hashtable]$InvocationCyclesByRun,
        [int]$OpportunisticCount
    )

    $ccrsRunIds = @($Runs | Where-Object { Test-CcrsRun $_ } | ForEach-Object { $_.run_id })
    $rows = @($Cycles | Where-Object {
        $ccrsRunIds -contains $_.run_id -and
        (Convert-ToIntOrZero $_.opportunistic_prompt_visible_count) -eq $OpportunisticCount
    })

    $nonContingencyRows = @()
    foreach ($row in $rows) {
        $invocationCycles = @()
        if ($InvocationCyclesByRun.ContainsKey($row.run_id)) {
            $invocationCycles = @($InvocationCyclesByRun[$row.run_id] | ForEach-Object { "$($_.cycle)" })
        }
        if ($invocationCycles -notcontains "$($row.cycle)") {
            $nonContingencyRows += $row
        }
    }

    return Get-Average -Rows $nonContingencyRows -Field "duration_ms"
}

function Get-CcrsInvocationAverage {
    param(
        [object[]]$Cycles,
        [hashtable]$InvocationCyclesByRun,
        [int]$InvocationIndex
    )

    $rows = @()
    foreach ($runId in $InvocationCyclesByRun.Keys) {
        $invocations = @($InvocationCyclesByRun[$runId])
        if ($invocations.Count -lt $InvocationIndex) {
            continue
        }
        $cycle = "$($invocations[$InvocationIndex - 1].cycle)"
        $cycleRows = @($Cycles | Where-Object { $_.run_id -eq $runId -and "$($_.cycle)" -eq $cycle })
        if ($cycleRows.Count -gt 0) {
            $rows += $cycleRows[0]
        }
    }

    return Get-Average -Rows $rows -Field "duration_ms"
}

function Get-ScenarioReportMetadata {
    param([string]$BatchName)

    if ($BatchName -match "(?i)((^|[-_])v1($|[-_])|mazev1)") {
        return [pscustomobject][ordered]@{
            name = "CcrsMazeV1"
            description = "Scenario CcrsMazeV1 contains 3 locked cells. The baseline agent cannot complete the maze because it has no recovery mechanism for lock interactions. This scenario tests whether CCRS enables completion through contingency recovery, and separates normal opportunistic guidance from expensive contingency invocations."
            optimal_moves = 138
            exit_cell = "http://127.0.1.1:8080/cells/999"
            zone_optimal_moves = @{
                signifier = 19
                stigmergy = 24
                mixed = 57
                "construction-site" = 19
                social = 19
            }
        }
    }

    if ($BatchName -match "(?i)((^|[-_])v2($|[-_])|mazev2)") {
        return [pscustomobject][ordered]@{
            name = "CcrsMazeV2"
            description = "Scenario CcrsMazeV2 contains no locked cells. It is the baseline traversal scenario: both agents can reach the exit without contingency recovery, so the comparison focuses on path efficiency, opportunistic CCRS influence, movement count, and normal cycle-time overhead."
            optimal_moves = 116
            exit_cell = "http://127.0.1.1:8080/cells/999"
            zone_optimal_moves = @{
                signifier = 17
                stigmergy = 24
                mixed = 37
                "construction-site" = 19
                social = 19
            }
        }
    }

    return [pscustomobject][ordered]@{
        name = "unknown"
        description = "Scenario metadata is not configured for this batch."
        optimal_moves = $null
        exit_cell = $null
        zone_optimal_moves = @{}
    }
}

function Get-RunOptimalMoves {
    param(
        $Run,
        $ScenarioMetadata
    )

    if ($null -ne $Run.optimal_moves -and "$($Run.optimal_moves)" -ne "") {
        return $Run.optimal_moves
    }
    return $ScenarioMetadata.optimal_moves
}

function Get-RunExitCell {
    param(
        $Run,
        $ScenarioMetadata
    )

    if ($null -ne $Run.exit_cell -and "$($Run.exit_cell)" -ne "") {
        return "$($Run.exit_cell)"
    }
    return $ScenarioMetadata.exit_cell
}

function Get-RankedOpportunisticRows {
    param([object[]]$Rows)

    return @($Rows |
        Where-Object { $_.react_event -eq "react.ccrs.opportunistic.detected" -and "$($_.target)" -ne "" } |
        Sort-Object `
            @{ Expression = {
                $number = Convert-ToDoubleOrNull $_.utility
                if ($null -eq $number) { [double]::NegativeInfinity } else { $number }
            }; Descending = $true },
            @{ Expression = { Convert-ToIntOrZero $_.line }; Ascending = $true },
            @{ Expression = { "$($_.target)" }; Ascending = $true })
}

function Get-SelectedOpportunisticRank {
    param(
        $Decision,
        [object[]]$RankedRows
    )

    $selectedUri = "$($Decision.selected_uri)"
    if (-not $selectedUri) {
        return $null
    }

    $rank = 1
    foreach ($row in $RankedRows) {
        if ("$($row.target)" -eq $selectedUri) {
            return $rank
        }
        $rank++
    }
    return $null
}

function New-AdvisoryBucket {
    param(
        $Run,
        [int]$OpportunisticCount,
        [int]$MaxRank
    )

    $fields = [ordered]@{
        batch_id = $Run.batch_id
        run_id = $Run.run_id
        opportunistic_count = $OpportunisticCount
        selection_count = 0
    }
    for ($rank = 1; $rank -le $MaxRank; $rank++) {
        $fields[("selected_rank_{0}_count" -f $rank)] = 0
    }
    $fields["selected_none_count"] = 0
    $fields["rank_unavailable_count"] = 0
    return [pscustomobject]$fields
}

function Add-AdvisorySelection {
    param(
        $Bucket,
        $Decision,
        [object[]]$RankedRows
    )

    $Bucket.selection_count = [int]$Bucket.selection_count + 1
    $opportunisticCount = Convert-ToIntOrZero $Decision.opportunistic_count
    if ($opportunisticCount -eq 0) {
        return
    }

    if ($RankedRows.Count -eq 0) {
        $Bucket.rank_unavailable_count = [int]$Bucket.rank_unavailable_count + 1
        return
    }

    $selectedRank = Get-SelectedOpportunisticRank -Decision $Decision -RankedRows $RankedRows
    if ($null -eq $selectedRank) {
        $Bucket.selected_none_count = [int]$Bucket.selected_none_count + 1
        return
    }

    $property = "selected_rank_{0}_count" -f $selectedRank
    if ($Bucket.PSObject.Properties[$property]) {
        $Bucket.PSObject.Properties[$property].Value = [int]$Bucket.PSObject.Properties[$property].Value + 1
    }
}

function New-AdvisoryFollowRows {
    param(
        [object[]]$Runs,
        [object[]]$Decisions,
        [object[]]$OpportunisticRows,
        [int]$MaxRank
    )

    $rows = [System.Collections.ArrayList]::new()
    foreach ($run in $Runs) {
        $runDecisions = @($Decisions | Where-Object { $_.run_id -eq $run.run_id })
        if ($runDecisions.Count -eq 0) {
            continue
        }

        $runMaxCount = 0
        foreach ($decision in $runDecisions) {
            $runMaxCount = [math]::Max($runMaxCount, (Convert-ToIntOrZero $decision.opportunistic_count))
        }

        $buckets = @{}
        for ($count = 0; $count -le $runMaxCount; $count++) {
            $bucket = New-AdvisoryBucket -Run $run -OpportunisticCount $count -MaxRank $MaxRank
            $buckets["$count"] = $bucket
            [void]$rows.Add($bucket)
        }

        $runOpportunisticRows = @($OpportunisticRows | Where-Object { $_.run_id -eq $run.run_id })
        foreach ($decision in $runDecisions) {
            $opportunisticCount = Convert-ToIntOrZero $decision.opportunistic_count
            $bucket = $buckets["$opportunisticCount"]
            $rankedRows = Get-RankedOpportunisticRows @($runOpportunisticRows | Where-Object { "$($_.cycle)" -eq "$($decision.cycle)" })
            Add-AdvisorySelection -Bucket $bucket -Decision $decision -RankedRows $rankedRows
        }
    }
    return @($rows)
}

function Write-AdvisoryFollowCsv {
    param(
        [object[]]$Rows,
        [string]$Path,
        [int]$MaxRank
    )

    $headers = @("batch_id", "run_id", "opportunistic_count", "selection_count")
    for ($rank = 1; $rank -le $MaxRank; $rank++) {
        $headers += ("selected_rank_{0}_count" -f $rank)
    }
    $headers += @("selected_none_count", "rank_unavailable_count")

    if ($Rows.Count -gt 0) {
        $Rows | Select-Object $headers | Export-Csv -Path $Path -NoTypeInformation -Encoding UTF8
    } else {
        $headerLine = '"' + ($headers -join '","') + '"'
        $headerLine | Set-Content -Path $Path -Encoding UTF8
    }
}

function Get-AgentRowForRun {
    param(
        [object[]]$AgentRows,
        $Run
    )

    $rows = @($AgentRows | Where-Object { $_.run_id -eq $Run.run_id })
    if ($rows.Count -eq 0) {
        return $null
    }

    $agentName = "$($Run.agent_name)"
    if ($agentName) {
        $match = @($rows | Where-Object {
            $_.agent -eq $agentName -or
            $_.agent -like "*/$agentName" -or
            $_.agent -like "*agents/$agentName"
        } | Select-Object -First 1)
        if ($match.Count -gt 0) {
            return $match[0]
        }
    }

    if ($rows.Count -eq 1) {
        return $rows[0]
    }
    return $null
}

function Add-TableHeader {
    param(
        [System.Collections.Generic.List[string]]$Lines,
        [string[]]$Headers
    )

    $headerLine = "| " + ($Headers -join " | ") + " |"
    $separatorLine = "| " + (($Headers | ForEach-Object { "---" }) -join " | ") + " |"
    $Lines.Add($headerLine)
    $Lines.Add($separatorLine)
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
$parserPath = Join-Path $PSScriptRoot "parse-experiment-logs.ps1"

$parseArgs = @{}
if ($BatchId) { $parseArgs["BatchId"] = $BatchId }
if ($RunRoot) { $parseArgs["RunRoot"] = $runRootPath }
if ($OutputDir) { $parseArgs["OutputDir"] = $outputPath }
& $parserPath @parseArgs

$runs = @(Import-CsvIfPresent (Join-Path $outputPath "runs.csv"))
$agents = @(Import-CsvIfPresent (Join-Path $outputPath "agents.csv"))
$cycles = @(Import-CsvIfPresent (Join-Path $outputPath "cycle-durations.csv"))
$decisions = @(Import-CsvIfPresent (Join-Path $outputPath "decisions.csv"))
$contingency = @(Import-CsvIfPresent (Join-Path $outputPath "contingency.csv"))
$opportunistic = @(Import-CsvIfPresent (Join-Path $outputPath "opportunistic.csv"))
$actions = @(Import-CsvIfPresent (Join-Path $outputPath "actions.csv"))
$javaEvidence = @(Import-CsvIfPresent (Join-Path $outputPath "java-library-evidence.csv"))

$maxAdvisoryRank = 1
foreach ($decision in $decisions) {
    $maxAdvisoryRank = [math]::Max($maxAdvisoryRank, (Convert-ToIntOrZero $decision.opportunistic_count))
}
$advisoryFollowRows = New-AdvisoryFollowRows -Runs $runs -Decisions $decisions -OpportunisticRows $opportunistic -MaxRank $maxAdvisoryRank
$advisoryFollowPath = Join-Path $outputPath "advisory-follow.csv"
Write-AdvisoryFollowCsv -Rows $advisoryFollowRows -Path $advisoryFollowPath -MaxRank $maxAdvisoryRank

$invocationCyclesByRun = Get-CcrsInvocationCyclesByRun -ContingencyRows $contingency
$maxOppCountForCycleSummary = 0
foreach ($cycleRow in @($cycles | Where-Object { Test-CcrsRun $_ })) {
    $maxOppCountForCycleSummary = [math]::Max($maxOppCountForCycleSummary, (Convert-ToIntOrZero $cycleRow.opportunistic_prompt_visible_count))
}
$maxContingencyInvocation = 0
foreach ($runId in $invocationCyclesByRun.Keys) {
    $maxContingencyInvocation = [math]::Max($maxContingencyInvocation, @($invocationCyclesByRun[$runId]).Count)
}

$reportTitle = if ($BatchId) { $BatchId } else { Split-Path -Leaf $runRootPath }
$scenarioMetadata = Get-ScenarioReportMetadata -BatchName $reportTitle
$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("# React Experiment Summary: $reportTitle")
$lines.Add("")
$lines.Add("Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')")
$lines.Add("")
$lines.Add("Run root: ``$runRootPath``")
$lines.Add("")
$lines.Add("Metric definitions: [METRICS.md](../../METRICS.md)")
$lines.Add("")

$lines.Add("## Core Metrics")
$lines.Add("")
if ($runs.Count -eq 0) {
    $lines.Add("No imported runs were found.")
} else {
    Add-TableHeader -Lines $lines -Headers @(
        "Run", "Agent", "Graph", "Mode", "Reached exit", "Total duration ms",
        "Total moves", "Avg agent cycle duration", "Final cell"
    )
    foreach ($run in $runs) {
        $runCycles = @($cycles | Where-Object { $_.run_id -eq $run.run_id })
        $avgCycleMs = Get-Average -Rows $runCycles -Field "duration_ms"
        $totalDurationMs = Get-Sum -Rows $runCycles -Field "duration_ms"
        $agentRow = Get-AgentRowForRun -AgentRows $agents -Run $run
        $finalCell = if ($agentRow) { $agentRow.final_cell } else { $null }
        $exitCell = Get-RunExitCell -Run $run -ScenarioMetadata $scenarioMetadata
        $lines.Add("| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} |" -f @(
            (Format-CodeCell $run.run_id),
            (Format-MarkdownCell $run.agent_name),
            (Format-CodeCell $run.graph_name),
            (Format-MarkdownCell $run.run_mode),
            (Format-MarkdownCell (Test-ReachedExit -Run $run -FinalCell $finalCell -ExitCell $exitCell)),
            (Format-Ms $totalDurationMs),
            (Format-NumberCell $run.mase_move_count),
            (Format-Ms $avgCycleMs),
            (Format-CodeCell $finalCell)
        ))
    }
}
$lines.Add("")

$lines.Add("## Move Optimality")
$lines.Add("")
Add-TableHeader -Lines $lines -Headers @("Run", "Agent", "Optimal moves", "Actual moves", "Delta from optimal")
foreach ($run in $runs) {
    $optimalMoves = Get-RunOptimalMoves -Run $run -ScenarioMetadata $scenarioMetadata
    $agentRow = Get-AgentRowForRun -AgentRows $agents -Run $run
    $finalCell = if ($agentRow) { $agentRow.final_cell } else { $null }
    $exitCell = Get-RunExitCell -Run $run -ScenarioMetadata $scenarioMetadata
    $reachedExit = Test-ReachedExit -Run $run -FinalCell $finalCell -ExitCell $exitCell
    $delta = if ($reachedExit -eq "yes") {
        Get-DeltaFromOptimal -OptimalMoves $optimalMoves -ActualMoves $run.mase_move_count
    } else {
        $null
    }
    $lines.Add("| {0} | {1} | {2} | {3} | {4} |" -f @(
        (Format-CodeCell $run.run_id),
        (Format-MarkdownCell $run.agent_name),
        (Format-NumberCell $optimalMoves),
        (Format-NumberCell $run.mase_move_count),
        (Format-NumberCell $delta)
    ))
}
$lines.Add("")

$lines.Add("## Cycle Duration Summary")
$lines.Add("")
$cycleSummaryHeaders = @("Baseline avg ms", "CCRS avg ms")
for ($count = 0; $count -le $maxOppCountForCycleSummary; $count++) {
    $cycleSummaryHeaders += ("CCRS opp {0} avg ms" -f $count)
}
for ($index = 1; $index -le $maxContingencyInvocation; $index++) {
    $cycleSummaryHeaders += ("CCRS cont invocation {0} avg ms" -f $index)
}
Add-TableHeader -Lines $lines -Headers $cycleSummaryHeaders
$baselineCycleRows = Get-CycleRowsForRuns -Cycles $cycles -Runs $runs -Ccrs $false
$ccrsCycleRows = Get-CycleRowsForRuns -Cycles $cycles -Runs $runs -Ccrs $true
$cycleSummaryCells = @(
    (Format-Ms (Get-Average -Rows $baselineCycleRows -Field "duration_ms")),
    (Format-Ms (Get-Average -Rows $ccrsCycleRows -Field "duration_ms"))
)
for ($count = 0; $count -le $maxOppCountForCycleSummary; $count++) {
    $cycleSummaryCells += (Format-Ms (Get-CcrsOppAverage -Cycles $cycles -Runs $runs -InvocationCyclesByRun $invocationCyclesByRun -OpportunisticCount $count))
}
for ($index = 1; $index -le $maxContingencyInvocation; $index++) {
    $cycleSummaryCells += (Format-Ms (Get-CcrsInvocationAverage -Cycles $cycles -InvocationCyclesByRun $invocationCyclesByRun -InvocationIndex $index))
}
$lines.Add("| " + ($cycleSummaryCells -join " | ") + " |")
$lines.Add("")
$lines.Add("Opportunistic CCRS cycle averages exclude cycles where contingency CCRS was activated. Contingency columns are dynamically generated ordered invocation cycles, not counts per cycle.")
$lines.Add("")

$lines.Add("## Advisory-Follow Evidence")
$lines.Add("")
if ($decisions.Count -eq 0) {
    $lines.Add('No `react.ccrs.opportunistic.selection` rows were found. Historical logs still parse, but advisory-follow metrics are unavailable until fresh runs include the new selection event.')
} else {
    $headers = @("Run", "Opp CCRS present", "Selections")
    for ($rank = 1; $rank -le $maxAdvisoryRank; $rank++) {
        if ($rank -eq 1) {
            $headers += "Selected rank 1 (highest)"
        } else {
            $headers += ("Selected rank {0}" -f $rank)
        }
    }
    $headers += @("Selected none", "Rank unavailable")
    Add-TableHeader -Lines $lines -Headers $headers

    foreach ($row in $advisoryFollowRows) {
        $opportunisticCount = Convert-ToIntOrZero $row.opportunistic_count
        $cells = @(
            (Format-CodeCell $row.run_id),
            (Format-NumberCell $opportunisticCount),
            (Format-NumberCell $row.selection_count)
        )
        for ($rank = 1; $rank -le $maxAdvisoryRank; $rank++) {
            if ($rank -le $opportunisticCount) {
                $property = "selected_rank_{0}_count" -f $rank
                $cells += (Format-NumberCell $row.$property)
            } else {
                $cells += "-"
            }
        }
        if ($opportunisticCount -gt 0) {
            $cells += (Format-NumberCell $row.selected_none_count)
            $cells += (Format-NumberCell $row.rank_unavailable_count)
        } else {
            $cells += "-"
            $cells += "-"
        }
        $lines.Add("| " + ($cells -join " | ") + " |")
    }
    $lines.Add("")
    $lines.Add('Ranks are inferred by joining each selection to `react.ccrs.opportunistic.detected` rows in the same run and cycle, ordered by descending utility. `Selected none` means the selected URI matched none of those ranked opportunistic targets.')
}
$lines.Add("")

$lines.Add("## Generated Artifacts")
$lines.Add("")
$artifactNames = @(
    "runs.csv",
    "agents.csv",
    "mase-events.csv",
    "mase-agent-moved.csv",
    "mase-transactions.csv",
    "cycle-durations.csv",
    "decisions.csv",
    "advisory-follow.csv",
    "contingency.csv",
    "opportunistic.csv",
    "actions.csv",
    "java-library-evidence.csv",
    "path-analysis-inputs/",
    "summary.json",
    "summary.md"
)
foreach ($artifact in $artifactNames) {
    $lines.Add(("- ``{0}``" -f $artifact))
}
$lines.Add("")

$lines.Add("## Scope Notes")
$lines.Add("")
$lines.Add("- This first report version intentionally reports only metrics with clear current sources.")
$lines.Add("- Java companion logs are reported as library evidence and are kept separate from React adapter selection metrics.")
$lines.Add("- BDI overrule and option-reordering metrics are not applicable to React advisory prompt injection.")

$summaryPath = Join-Path $outputPath "summary.md"
$lines | Set-Content -Path $summaryPath -Encoding UTF8

$summaryJsonPath = Join-Path $outputPath "summary.json"
$summaryObject = [ordered]@{
    batchId = $reportTitle
    generatedAt = (Get-Date).ToString("o")
    runRoot = (Resolve-Path -LiteralPath $runRootPath).Path
    outputDir = (Resolve-Path -LiteralPath $outputPath).Path
    runCount = $runs.Count
    maseEventCount = ($runs | ForEach-Object { [int]$_.mase_event_count } | Measure-Object -Sum).Sum
    decisionCount = $decisions.Count
    advisoryFollowRowCount = $advisoryFollowRows.Count
    contingencyRowCount = $contingency.Count
    opportunisticRowCount = $opportunistic.Count
    actionRowCount = $actions.Count
    javaEvidenceCount = $javaEvidence.Count
    summaryMarkdown = "summary.md"
    metricsDocumentation = "..\..\METRICS.md"
    artifacts = $artifactNames
}
$summaryObject | ConvertTo-Json -Depth 8 | Set-Content -Path $summaryJsonPath -Encoding UTF8

Write-Host "Wrote React experiment report."
Write-Host "Summary: $summaryPath"
Write-Host "Metrics: $(Join-Path $repoRoot 'experiments\METRICS.md')"
