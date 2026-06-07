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

function New-MoveDurationRows {
    param([object[]]$Moves)

    $rows = [System.Collections.ArrayList]::new()
    foreach ($group in ($Moves | Group-Object run_id | Sort-Object Name)) {
        $sortedMoves = @($group.Group | Sort-Object @{ Expression = { Convert-ToIntOrZero $_.sequence }; Ascending = $true })
        for ($i = 0; $i -lt $sortedMoves.Count; $i++) {
            $current = $sortedMoves[$i]
            $durationMs = $null
            if ($i -gt 0) {
                $previousTimestamp = Convert-ToDoubleOrNull $sortedMoves[$i - 1].timestamp
                $currentTimestamp = Convert-ToDoubleOrNull $current.timestamp
                if ($null -ne $previousTimestamp -and $null -ne $currentTimestamp) {
                    $durationMs = [math]::Round($currentTimestamp - $previousTimestamp, 3)
                }
            }
            [void]$rows.Add([pscustomobject][ordered]@{
                batch_id = $current.batch_id
                run_id = $current.run_id
                sequence = Convert-ToIntOrZero $current.sequence
                cycle = Convert-ToIntOrZero $current.sequence
                cycle_timestamp = $current.timestamp
                duration_ms = $durationMs
                cell = $current.cell
            })
        }
    }
    return @($rows)
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

function Convert-ToSvgText {
    param($Value)

    if ($null -eq $Value) {
        return ""
    }
    return [System.Security.SecurityElement]::Escape("$Value")
}

function Get-StepAxisTicks {
    param(
        [double]$MaxStep,
        [int]$Interval = 25
    )

    $ticks = [System.Collections.Generic.List[double]]::new()
    $tick = 0
    while ($tick -le $MaxStep) {
        $ticks.Add([double]$tick)
        $tick += $Interval
    }

    if (-not $ticks.Contains([double]$MaxStep)) {
        $ticks.Add([double]$MaxStep)
    }

    return @($ticks | Sort-Object -Unique)
}

function Format-CellLabel {
    param($Cell)

    if ($null -eq $Cell -or "$Cell" -eq "") {
        return "unknown cell"
    }

    $text = "$Cell"
    if ($text -match "/cells/(.+)$") {
        return "cells/$($matches[1])"
    }

    return $text
}

function Get-ChartStep {
    param($Row)

    if ($Row -and $Row.PSObject.Properties["sequence"] -and "$($Row.sequence)" -ne "") {
        return Convert-ToIntOrZero $Row.sequence
    }
    if ($Row -and $Row.PSObject.Properties["move_sequence"] -and "$($Row.move_sequence)" -ne "") {
        return Convert-ToIntOrZero $Row.move_sequence
    }
    return 0
}

function Add-EndpointLabel {
    param(
        [System.Collections.Generic.List[string]]$Svg,
        [double]$PointX,
        [double]$PointY,
        [string]$Color,
        [string]$Label,
        [int]$SeriesIndex,
        [double]$PlotX,
        [double]$PlotY,
        [double]$PlotWidth,
        [double]$PlotHeight
    )

    $labelText = Convert-ToSvgText $Label
    $labelWidth = [math]::Max(96, [math]::Min(210, ($Label.Length * 6.2) + 12))
    $isRightEdge = $PointX -gt ($PlotX + $PlotWidth - 150)
    $anchor = if ($isRightEdge) { "end" } else { "start" }
    $labelXValue = if ($isRightEdge) {
        [math]::Max($PlotX + $labelWidth + 8, $PointX - 14)
    } else {
        [math]::Min($PlotX + $PlotWidth - $labelWidth - 8, $PointX + 14)
    }
    $offsetY = if (($SeriesIndex % 2) -eq 0) { -45 } else { 48 }
    $labelYValue = [math]::Min([math]::Max($PlotY + 12, $PointY + $offsetY), $PlotY + $PlotHeight - 12)
    $pointXText = $PointX.ToString("0.##", [System.Globalization.CultureInfo]::InvariantCulture)
    $pointYText = $PointY.ToString("0.##", [System.Globalization.CultureInfo]::InvariantCulture)
    $rectX = ($PointX - 3).ToString("0.##", [System.Globalization.CultureInfo]::InvariantCulture)
    $rectY = ($PointY - 3).ToString("0.##", [System.Globalization.CultureInfo]::InvariantCulture)
    $labelX = $labelXValue.ToString("0.##", [System.Globalization.CultureInfo]::InvariantCulture)
    $labelY = $labelYValue.ToString("0.##", [System.Globalization.CultureInfo]::InvariantCulture)

    $Svg.Add("<rect x=""$rectX"" y=""$rectY"" width=""6"" height=""6"" fill=""#ffffff"" stroke=""$Color"" stroke-width=""2""/>")
    $Svg.Add("<line x1=""$pointXText"" y1=""$pointYText"" x2=""$labelX"" y2=""$labelY"" stroke=""$Color"" stroke-width=""1"" opacity=""0.65""/>")
    $Svg.Add("<text x=""$labelX"" y=""$labelY"" text-anchor=""$anchor"" dominant-baseline=""middle"" font-family=""Arial, sans-serif"" font-size=""11"" fill=""#222"">$labelText</text>")
}

function Write-CycleDurationChart {
    param(
        [object[]]$Cycles,
        [object[]]$Runs,
        [object[]]$Agents,
        [string]$Path,
        [string]$Title = "Cycle duration comparison",
        [string]$Description = "Line chart comparing cycle duration by step for React experiment runs. The y-axis is linear milliseconds.",
        [string]$SubtitlePrefix = "Y-axis is linear duration in ms.",
        [string]$XAxisLabel = "Step number",
        [string]$MarkdownLabel = "duration",
        [object[]]$HttpRows = @(),
        [double]$DurationLinearThresholdMs = 0,
        [double]$DurationLinearScaleFraction = 0.67,
        [double]$DurationLogBase = 100,
        [switch]$DurationLogScale,
        [double]$DurationAxisMinMs = 1,
        [double]$DurationAxisMaxMs = 0,
        [object[]]$DurationTickValues = @(),
        [int]$HttpAxisMaxCalls = 0,
        [int]$HttpAxisTickInterval = 1
    )

    $pointsByRun = [ordered]@{}
    $runMetadata = @{}
    foreach ($run in $Runs) {
        $runId = "$($run.run_id)"
        $rows = @($Cycles |
            Where-Object {
                "$($_.run_id)" -eq $runId -and
                $null -ne (Convert-ToDoubleOrNull $_.duration_ms)
            } |
            Sort-Object @{ Expression = { Get-ChartStep $_ }; Ascending = $true })

        if ($rows.Count -eq 0) {
            continue
        }

        $agentRow = Get-AgentRowForRun -AgentRows $Agents -Run $run
        $runMetadata[$runId] = [pscustomobject][ordered]@{
            isCcrs = Test-CcrsRun $run
            finalCell = if ($agentRow) { "$($agentRow.final_cell)" } else { "" }
        }
        $pointsByRun[$runId] = @($rows | ForEach-Object {
            [pscustomobject][ordered]@{
                step = Get-ChartStep $_
                duration = Convert-ToDoubleOrNull $_.duration_ms
            }
        })
    }

    if ($pointsByRun.Count -eq 0) {
        return $false
    }

    $allPoints = @()
    foreach ($runId in $pointsByRun.Keys) {
        $allPoints += @($pointsByRun[$runId])
    }

    $minStep = 0
    $maxStep = [int]($allPoints | Measure-Object -Property step -Maximum).Maximum
    $maxDuration = [double]($allPoints | Measure-Object -Property duration -Maximum).Maximum
    $maxHttpCalls = 0
    foreach ($row in $HttpRows) {
        $maxHttpCalls = [math]::Max($maxHttpCalls, (Convert-ToIntOrZero $row.action_count))
    }
    if ($maxStep -le $minStep) {
        $maxStep = $minStep + 1
    }
    if ($maxDuration -le 0) {
        $maxDuration = 1
    }
    $durationAxisMax = $maxDuration
    if ($DurationAxisMaxMs -gt 0) {
        $durationAxisMax = [math]::Max($maxDuration, $DurationAxisMaxMs)
    }
    if ($DurationAxisMinMs -le 0) {
        $DurationAxisMinMs = 1
    }
    $useHybridDurationScale = (
        -not $DurationLogScale -and
        $DurationLinearThresholdMs -gt 0 -and
        $durationAxisMax -gt $DurationLinearThresholdMs
    )
    $httpAxisMax = $maxHttpCalls
    if ($HttpAxisMaxCalls -gt 0) {
        $httpAxisMax = [math]::Max($maxHttpCalls, $HttpAxisMaxCalls)
    }
    if ($HttpAxisTickInterval -le 0) {
        $HttpAxisTickInterval = 1
    }

    $width = 1040
    $height = 520
    $left = 72
    $top = 128
    $plotWidth = 880
    $plotHeight = 300
    $baselineColor = "#1f77b4"
    $ccrsColor = "#d62728"
    $otherColors = @("#2ca02c", "#9467bd", "#ff7f0e", "#0891b2")

    function Get-X {
        param([int]$Step)
        return $left + (($Step - $minStep) / ($maxStep - $minStep)) * $plotWidth
    }

    function Get-Y {
        param([double]$Duration)
        if ($DurationLogScale) {
            $clampedDuration = [math]::Max($DurationAxisMinMs, [math]::Min($Duration, $durationAxisMax))
            $logRange = [math]::Max(1.0, [math]::Log(($durationAxisMax / $DurationAxisMinMs), $DurationLogBase))
            $logValue = [math]::Log(($clampedDuration / $DurationAxisMinMs), $DurationLogBase)
            return $top + ($plotHeight - (($logValue / $logRange) * $plotHeight))
        }
        if (-not $useHybridDurationScale) {
            return $top + ($plotHeight - (($Duration / $durationAxisMax) * $plotHeight))
        }
        if ($Duration -le $DurationLinearThresholdMs) {
            $linearHeight = $plotHeight * $DurationLinearScaleFraction
            return $top + $plotHeight - (($Duration / $DurationLinearThresholdMs) * $linearHeight)
        }
        $logHeight = $plotHeight * (1.0 - $DurationLinearScaleFraction)
        $logRange = [math]::Max(1.0, [math]::Log(($durationAxisMax / $DurationLinearThresholdMs), $DurationLogBase))
        $logValue = [math]::Log(($Duration / $DurationLinearThresholdMs), $DurationLogBase)
        return $top + ($logHeight - (($logValue / $logRange) * $logHeight))
    }

    function Get-DurationTicks {
        if ($DurationTickValues.Count -gt 0) {
            $ticks = [System.Collections.Generic.List[double]]::new()
            foreach ($tick in $DurationTickValues) {
                $tickValue = Convert-ToDoubleOrNull $tick
                if ($null -ne $tickValue -and $tickValue -le $durationAxisMax -and (-not $DurationLogScale -or $tickValue -ge $DurationAxisMinMs)) {
                    $ticks.Add([double]$tickValue)
                }
            }
            if ($maxDuration -gt $durationAxisMax -and -not $ticks.Contains([double]$maxDuration)) {
                $ticks.Add([double]$maxDuration)
            }
            return @($ticks | Sort-Object -Unique)
        }

        if (-not $useHybridDurationScale) {
            $ticks = [System.Collections.Generic.List[double]]::new()
            for ($tick = 0; $tick -le 5; $tick++) {
                $ticks.Add(($durationAxisMax / 5) * $tick)
            }
            return @($ticks)
        }

        $ticks = [System.Collections.Generic.List[double]]::new()
        foreach ($tick in @(0, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000)) {
            if ($tick -le $DurationLinearThresholdMs -and $tick -le $durationAxisMax) {
                $ticks.Add([double]$tick)
            }
        }
        $multiplier = 1.0
        while (($DurationLinearThresholdMs * $multiplier) -lt $durationAxisMax) {
            $multiplier *= $DurationLogBase
            $tickValue = $DurationLinearThresholdMs * $multiplier
            if ($tickValue -le ($durationAxisMax * 1.05)) {
                $ticks.Add([double][math]::Min($tickValue, $durationAxisMax))
            }
        }
        if (-not $ticks.Contains([double]$durationAxisMax)) {
            $ticks.Add([double]$durationAxisMax)
        }
        return @($ticks | Sort-Object -Unique)
    }

    $svg = [System.Collections.Generic.List[string]]::new()
    $svg.Add('<svg xmlns="http://www.w3.org/2000/svg" width="' + $width + '" height="' + $height + '" viewBox="0 0 ' + $width + ' ' + $height + '" role="img" aria-labelledby="title desc">')
    $svg.Add('<title id="title">' + (Convert-ToSvgText $Title) + '</title>')
    $svg.Add('<desc id="desc">' + (Convert-ToSvgText $Description) + '</desc>')
    $svg.Add('<rect width="100%" height="100%" fill="#ffffff"/>')
    $svg.Add('<text x="' + $left + '" y="28" font-family="Arial, sans-serif" font-size="14" font-weight="700">' + (Convert-ToSvgText $Title) + '</text>')
    $scaleText = if ($DurationLogScale) {
        "Y-axis is log-base-" + $DurationLogBase.ToString("0.##", [System.Globalization.CultureInfo]::InvariantCulture) + " duration in ms."
    } elseif ($useHybridDurationScale) {
        "Y-axis is linear to " + $DurationLinearThresholdMs.ToString("0", [System.Globalization.CultureInfo]::InvariantCulture) + " ms, then log-base-" + $DurationLogBase.ToString("0.##", [System.Globalization.CultureInfo]::InvariantCulture) + "."
    } else {
        $SubtitlePrefix
    }
    $svg.Add('<text x="' + $left + '" y="50" font-family="Arial, sans-serif" font-size="12" fill="#555">' + (Convert-ToSvgText $scaleText) + ' Max observed: ' + $maxDuration.ToString("0.##", [System.Globalization.CultureInfo]::InvariantCulture) + ' ms.</text>')
    $svg.Add(('<line x1="{0}" y1="{1}" x2="{2}" y2="{1}" stroke="#333" stroke-width="1"/>' -f $left, ($top + $plotHeight), ($left + $plotWidth)))
    $svg.Add(('<line x1="{0}" y1="{1}" x2="{0}" y2="{2}" stroke="#333" stroke-width="1"/>' -f $left, $top, ($top + $plotHeight)))
    if ($httpAxisMax -gt 0) {
        $rightAxisX = $left + $plotWidth
        $svg.Add(('<line x1="{0}" y1="{1}" x2="{0}" y2="{2}" stroke="#666" stroke-width="1"/>' -f $rightAxisX, $top, ($top + $plotHeight)))
        $httpTicks = [System.Collections.Generic.List[int]]::new()
        for ($tick = 0; $tick -le $httpAxisMax; $tick += $HttpAxisTickInterval) {
            $httpTicks.Add($tick)
        }
        if (-not $httpTicks.Contains($httpAxisMax)) {
            $httpTicks.Add($httpAxisMax)
        }
        foreach ($tick in $httpTicks) {
            $y = $top + ($plotHeight - (($tick / $httpAxisMax) * $plotHeight))
            $svg.Add(('<text x="{0}" y="{1:0.##}" dominant-baseline="middle" font-family="Arial, sans-serif" font-size="10" fill="#555">{2}</text>' -f ($rightAxisX + 8), $y, $tick))
        }
        $svg.Add(('<text x="{0}" y="{1}" text-anchor="middle" transform="rotate(90 {0} {1})" font-family="Arial, sans-serif" font-size="12" fill="#555">HTTP calls</text>' -f ($rightAxisX + 44), ($top + ($plotHeight / 2))))
        $barLegendY = 74
        $barLegendItems = @(
            @("baseline HTTP success", "#93c5fd"),
            @("baseline HTTP failure", "#1e3a8a"),
            @("CCRS HTTP success", "#fca5a5"),
            @("CCRS HTTP failure", "#991b1b")
        )
        for ($legendIndex = 0; $legendIndex -lt $barLegendItems.Count; $legendIndex++) {
            $item = $barLegendItems[$legendIndex]
            $legendItemX = $left + 610 + (($legendIndex % 2) * 150)
            $legendItemY = $barLegendY + ([math]::Floor($legendIndex / 2) * 18)
            $svg.Add(('<rect x="{0}" y="{1}" width="10" height="10" fill="{2}" opacity="0.65"/>' -f $legendItemX, ($legendItemY - 8), $item[1]))
            $svg.Add(('<text x="{0}" y="{1}" dominant-baseline="middle" font-family="Arial, sans-serif" font-size="11" fill="#555">{2}</text>' -f ($legendItemX + 15), ($legendItemY - 3), (Convert-ToSvgText $item[0])))
        }
    }

    foreach ($value in Get-DurationTicks) {
        $y = Get-Y $value
        $label = ([double]$value).ToString("0", [System.Globalization.CultureInfo]::InvariantCulture)
        $svg.Add(('<line x1="{0}" y1="{1:0.##}" x2="{2}" y2="{1:0.##}" stroke="#e5e7eb" stroke-width="1"/>' -f $left, $y, ($left + $plotWidth)))
        $svg.Add(('<text x="{0}" y="{1:0.##}" text-anchor="end" dominant-baseline="middle" font-family="Arial, sans-serif" font-size="11" fill="#222">{2}</text>' -f ($left - 8), $y, $label))
    }

    $xTicks = Get-StepAxisTicks -MaxStep $maxStep -Interval 25
    foreach ($step in $xTicks) {
        $x = Get-X $step
        $label = ([double]$step).ToString("0.##", [System.Globalization.CultureInfo]::InvariantCulture)
        $svg.Add(('<line x1="{0:0.##}" y1="{1}" x2="{0:0.##}" y2="{2}" stroke="#333" stroke-width="1"/>' -f $x, ($top + $plotHeight), ($top + $plotHeight + 5)))
        $svg.Add(('<text x="{0:0.##}" y="{1}" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#222">{2}</text>' -f $x, ($top + $plotHeight + 18), $label))
    }

    $svg.Add(('<text x="{0}" y="{1}" text-anchor="middle" font-family="Arial, sans-serif" font-size="13">{2}</text>' -f ($left + ($plotWidth / 2)), ($height - 24), (Convert-ToSvgText $XAxisLabel)))
    $svg.Add(('<text x="18" y="{0}" text-anchor="middle" transform="rotate(-90 18 {0})" font-family="Arial, sans-serif" font-size="13">Duration ms</text>' -f ($top + ($plotHeight / 2))))

    $legendX = $left + 610
    $legendY = 34
    $index = 0
    $otherColorIndex = 0
    $runOrder = @($pointsByRun.Keys)
    if ($httpAxisMax -gt 0) {
        $barGroupWidth = [math]::Min(18, [math]::Max(6, ($plotWidth / [math]::Max(1, $maxStep)) * 0.7))
        $barWidth = [math]::Max(2, $barGroupWidth / [math]::Max(1, $runOrder.Count))
        for ($runIndex = 0; $runIndex -lt $runOrder.Count; $runIndex++) {
            $runId = $runOrder[$runIndex]
            $metadata = $runMetadata[$runId]
            $successColor = if ($metadata.isCcrs) { "#fca5a5" } else { "#93c5fd" }
            $failureColor = if ($metadata.isCcrs) { "#991b1b" } else { "#1e3a8a" }
            foreach ($row in @($HttpRows | Where-Object { $_.run_id -eq $runId } | Sort-Object @{ Expression = { Get-ChartStep $_ }; Ascending = $true })) {
                $step = Get-ChartStep $row
                $successCount = Convert-ToIntOrZero $row.http_success_count
                $failureCount = Convert-ToIntOrZero $row.http_failure_count
                $xCenter = Get-X $step
                $x = $xCenter - ($barGroupWidth / 2) + ($runIndex * $barWidth)
                $successHeight = ($successCount / $httpAxisMax) * $plotHeight
                $failureHeight = ($failureCount / $httpAxisMax) * $plotHeight
                $successY = $top + $plotHeight - $successHeight
                $failureY = $successY - $failureHeight
                if ($successCount -gt 0) {
                    $svg.Add(('<rect x="{0:0.##}" y="{1:0.##}" width="{2:0.##}" height="{3:0.##}" fill="{4}" opacity="0.45"/>' -f $x, $successY, ($barWidth - 0.5), $successHeight, $successColor))
                }
                if ($failureCount -gt 0) {
                    $svg.Add(('<rect x="{0:0.##}" y="{1:0.##}" width="{2:0.##}" height="{3:0.##}" fill="{4}" opacity="0.7"/>' -f $x, $failureY, ($barWidth - 0.5), $failureHeight, $failureColor))
                }
            }
        }
    }
    foreach ($runId in $pointsByRun.Keys) {
        $metadata = $runMetadata[$runId]
        $color = if ($metadata.isCcrs) {
            $ccrsColor
        } elseif ($index -eq 0) {
            $baselineColor
        } else {
            $otherColors[$otherColorIndex % $otherColors.Count]
        }
        if (-not $metadata.isCcrs -and $index -ne 0) {
            $otherColorIndex++
        }

        $points = @($pointsByRun[$runId] | ForEach-Object {
            "{0:0.##},{1:0.##}" -f (Get-X $_.step), (Get-Y $_.duration)
        })
        $svg.Add(('<polyline points="{0}" fill="none" stroke="{1}" stroke-width="2"/>' -f ($points -join " "), $color))
        $seriesLegendY = $legendY + ($index * 20)
        $svg.Add(('<line x1="{0}" y1="{1}" x2="{2}" y2="{1}" stroke="{3}" stroke-width="2"/>' -f $legendX, $seriesLegendY, ($legendX + 30), $color))
        $svg.Add(('<text x="{0}" y="{1}" dominant-baseline="middle" font-family="Arial, sans-serif" font-size="12">{2}</text>' -f ($legendX + 38), $seriesLegendY, (Convert-ToSvgText $runId)))

        $lastPoint = @($pointsByRun[$runId])[-1]
        if ($lastPoint) {
            Add-EndpointLabel `
                -Svg $svg `
                -PointX (Get-X $lastPoint.step) `
                -PointY (Get-Y $lastPoint.duration) `
                -Color $color `
                -Label ((Format-CellLabel $metadata.finalCell) + " at step " + $lastPoint.step) `
                -SeriesIndex $index `
                -PlotX $left `
                -PlotY $top `
                -PlotWidth $plotWidth `
                -PlotHeight $plotHeight
        }
        $index++
    }

    $svg.Add('</svg>')
    $svg | Set-Content -Path $Path -Encoding UTF8
    return $true
}

function Write-HttpCallsChart {
    param(
        [object[]]$Rows,
        [object[]]$Runs,
        [string]$Path,
        [int]$HttpAxisMaxCalls = 35,
        [int]$HttpAxisTickInterval = 2
    )

    $rowsByRun = [ordered]@{}
    foreach ($run in $Runs) {
        $runId = "$($run.run_id)"
        $runRows = @($Rows |
            Where-Object { "$($_.run_id)" -eq $runId } |
            Sort-Object @{ Expression = { Get-ChartStep $_ }; Ascending = $true })
        if ($runRows.Count -gt 0) {
            $rowsByRun[$runId] = $runRows
        }
    }

    if ($rowsByRun.Count -eq 0) {
        return $false
    }

    $allRows = @()
    foreach ($runId in $rowsByRun.Keys) {
        $allRows += @($rowsByRun[$runId])
    }

    $minStep = 0
    $maxStep = [int]($allRows | ForEach-Object { Get-ChartStep $_ } | Measure-Object -Maximum).Maximum
    if ($maxStep -le $minStep) {
        $maxStep = $minStep + 1
    }

    $maxObserved = 0
    foreach ($row in $allRows) {
        $maxObserved = [math]::Max($maxObserved, (Convert-ToIntOrZero $row.action_count))
    }
    $axisMax = [math]::Max($maxObserved, $HttpAxisMaxCalls)
    if ($axisMax -le 0) {
        $axisMax = 1
    }
    if ($HttpAxisTickInterval -le 0) {
        $HttpAxisTickInterval = 1
    }

    $width = 1040
    $height = 520
    $left = 72
    $top = 128
    $plotWidth = 880
    $plotHeight = 300
    $baselineSuccessColor = "#93c5fd"
    $baselineFailureColor = "#1e3a8a"
    $ccrsSuccessColor = "#fca5a5"
    $ccrsFailureColor = "#991b1b"

    function Get-X {
        param([int]$Step)
        return $left + (($Step - $minStep) / ($maxStep - $minStep)) * $plotWidth
    }

    function Get-Y {
        param([double]$Value)
        return $top + ($plotHeight - (($Value / $axisMax) * $plotHeight))
    }

    $svg = [System.Collections.Generic.List[string]]::new()
    $svg.Add('<svg xmlns="http://www.w3.org/2000/svg" width="' + $width + '" height="' + $height + '" viewBox="0 0 ' + $width + ' ' + $height + '" role="img" aria-labelledby="title desc">')
    $svg.Add('<title id="title">HTTP calls by move window</title>')
    $svg.Add('<desc id="desc">Stacked bar chart of successful and failed HTTP calls per movement step for React experiment runs.</desc>')
    $svg.Add('<rect width="100%" height="100%" fill="#ffffff"/>')
    $svg.Add('<text x="' + $left + '" y="28" font-family="Arial, sans-serif" font-size="14" font-weight="700">HTTP calls by move window</text>')
    $svg.Add('<text x="' + $left + '" y="50" font-family="Arial, sans-serif" font-size="12" fill="#555">Y-axis is linear HTTP calls per move window. Max observed: ' + $maxObserved + '.</text>')
    $svg.Add(('<line x1="{0}" y1="{1}" x2="{2}" y2="{1}" stroke="#333" stroke-width="1"/>' -f $left, ($top + $plotHeight), ($left + $plotWidth)))
    $svg.Add(('<line x1="{0}" y1="{1}" x2="{0}" y2="{2}" stroke="#333" stroke-width="1"/>' -f $left, $top, ($top + $plotHeight)))

    $httpTicks = [System.Collections.Generic.List[int]]::new()
    for ($tick = 0; $tick -le $axisMax; $tick += $HttpAxisTickInterval) {
        $httpTicks.Add($tick)
    }
    if (-not $httpTicks.Contains($axisMax)) {
        $httpTicks.Add($axisMax)
    }
    foreach ($tick in $httpTicks) {
        $y = Get-Y $tick
        $svg.Add(('<line x1="{0}" y1="{1:0.##}" x2="{2}" y2="{1:0.##}" stroke="#e5e7eb" stroke-width="1"/>' -f $left, $y, ($left + $plotWidth)))
        $svg.Add(('<text x="{0}" y="{1:0.##}" text-anchor="end" dominant-baseline="middle" font-family="Arial, sans-serif" font-size="11" fill="#222">{2}</text>' -f ($left - 8), $y, $tick))
    }

    $xTicks = Get-StepAxisTicks -MaxStep $maxStep -Interval 25
    foreach ($step in $xTicks) {
        $x = Get-X $step
        $svg.Add(('<line x1="{0:0.##}" y1="{1}" x2="{0:0.##}" y2="{2}" stroke="#333" stroke-width="1"/>' -f $x, ($top + $plotHeight), ($top + $plotHeight + 5)))
        $svg.Add(('<text x="{0:0.##}" y="{1}" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#222">{2}</text>' -f $x, ($top + $plotHeight + 18), $step))
    }

    $runOrder = @($rowsByRun.Keys)
    $barGroupWidth = [math]::Min(18, [math]::Max(6, ($plotWidth / [math]::Max(1, $maxStep)) * 0.7))
    $barWidth = [math]::Max(2, $barGroupWidth / [math]::Max(1, $runOrder.Count))
    for ($runIndex = 0; $runIndex -lt $runOrder.Count; $runIndex++) {
        $runId = $runOrder[$runIndex]
        $run = @($Runs | Where-Object { "$($_.run_id)" -eq $runId })[0]
        $isCcrs = Test-CcrsRun $run
        $successColor = if ($isCcrs) { $ccrsSuccessColor } else { $baselineSuccessColor }
        $failureColor = if ($isCcrs) { $ccrsFailureColor } else { $baselineFailureColor }
        foreach ($row in $rowsByRun[$runId]) {
            $step = Get-ChartStep $row
            $successCount = Convert-ToIntOrZero $row.http_success_count
            $failureCount = Convert-ToIntOrZero $row.http_failure_count
            $xCenter = Get-X $step
            $x = $xCenter - ($barGroupWidth / 2) + ($runIndex * $barWidth)
            $successHeight = ($successCount / $axisMax) * $plotHeight
            $failureHeight = ($failureCount / $axisMax) * $plotHeight
            $successY = $top + $plotHeight - $successHeight
            $failureY = $successY - $failureHeight
            if ($successCount -gt 0) {
                $svg.Add(('<rect x="{0:0.##}" y="{1:0.##}" width="{2:0.##}" height="{3:0.##}" fill="{4}" opacity="0.55"/>' -f $x, $successY, ($barWidth - 0.5), $successHeight, $successColor))
            }
            if ($failureCount -gt 0) {
                $svg.Add(('<rect x="{0:0.##}" y="{1:0.##}" width="{2:0.##}" height="{3:0.##}" fill="{4}" opacity="0.75"/>' -f $x, $failureY, ($barWidth - 0.5), $failureHeight, $failureColor))
            }
        }
    }

    $legendItems = @(
        @("baseline HTTP success", $baselineSuccessColor),
        @("baseline HTTP failure", $baselineFailureColor),
        @("CCRS HTTP success", $ccrsSuccessColor),
        @("CCRS HTTP failure", $ccrsFailureColor)
    )
    for ($legendIndex = 0; $legendIndex -lt $legendItems.Count; $legendIndex++) {
        $item = $legendItems[$legendIndex]
        $legendItemX = $left + 610 + (($legendIndex % 2) * 150)
        $legendItemY = 72 + ([math]::Floor($legendIndex / 2) * 18)
        $svg.Add(('<rect x="{0}" y="{1}" width="10" height="10" fill="{2}" opacity="0.75"/>' -f $legendItemX, ($legendItemY - 8), $item[1]))
        $svg.Add(('<text x="{0}" y="{1}" dominant-baseline="middle" font-family="Arial, sans-serif" font-size="11" fill="#555">{2}</text>' -f ($legendItemX + 15), ($legendItemY - 3), (Convert-ToSvgText $item[0])))
    }

    $svg.Add(('<text x="{0}" y="{1}" text-anchor="middle" font-family="Arial, sans-serif" font-size="13">Movement step number</text>' -f ($left + ($plotWidth / 2)), ($height - 24)))
    $svg.Add(('<text x="18" y="{0}" text-anchor="middle" transform="rotate(-90 18 {0})" font-family="Arial, sans-serif" font-size="13">HTTP calls</text>' -f ($top + ($plotHeight / 2))))
    $svg.Add('</svg>')
    $svg | Set-Content -Path $Path -Encoding UTF8
    return $true
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
$maseMoves = @(Import-CsvIfPresent (Join-Path $outputPath "mase-agent-moved.csv"))
$cycles = @(Import-CsvIfPresent (Join-Path $outputPath "cycle-durations.csv"))
$decisions = @(Import-CsvIfPresent (Join-Path $outputPath "decisions.csv"))
$contingency = @(Import-CsvIfPresent (Join-Path $outputPath "contingency.csv"))
$opportunistic = @(Import-CsvIfPresent (Join-Path $outputPath "opportunistic.csv"))
$actions = @(Import-CsvIfPresent (Join-Path $outputPath "actions.csv"))
$moveActionCorrelation = @(Import-CsvIfPresent (Join-Path $outputPath "move-action-correlation.csv"))
$moveDurationRows = @(Import-CsvIfPresent (Join-Path $outputPath "move-durations.csv"))
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

$moveDurationChartName = "move-duration-comparison.svg"
$moveDurationChartPath = Join-Path $outputPath $moveDurationChartName
$hasMoveDurationChart = Write-CycleDurationChart `
    -Cycles $moveDurationRows `
    -Runs $runs `
    -Agents $agents `
    -Path $moveDurationChartPath `
    -Title "Move duration comparison" `
    -Description "Line chart comparing move-to-move duration by movement step for React experiment runs using a log duration axis." `
    -SubtitlePrefix "Y-axis is log-scaled move-to-move duration in ms." `
    -XAxisLabel "Movement step number" `
    -DurationLogScale `
    -DurationLogBase 2 `
    -DurationAxisMinMs 1000 `
    -DurationAxisMaxMs 80000 `
    -DurationTickValues @(1000, 2000, 4000, 8000, 16000, 32000, 64000, 80000)

$httpCallsChartName = "http-calls-by-move.svg"
$httpCallsChartPath = Join-Path $outputPath $httpCallsChartName
$hasHttpCallsChart = Write-HttpCallsChart `
    -Rows $moveDurationRows `
    -Runs $runs `
    -Path $httpCallsChartPath `
    -HttpAxisMaxCalls 35 `
    -HttpAxisTickInterval 2

$cycleDurationChartName = "cycle-duration-comparison.svg"
$cycleDurationChartPath = Join-Path $outputPath $cycleDurationChartName
$hasCycleDurationChart = Write-CycleDurationChart `
    -Cycles $cycles `
    -Runs $runs `
    -Agents $agents `
    -Path $cycleDurationChartPath `
    -Title "Cycle duration comparison" `
    -Description "Line chart comparing actual React loop cycle duration by cycle step. Fresh runs use react.loop.cycle events emitted from state cycle updates." `
    -SubtitlePrefix "Y-axis is linear React loop-cycle duration in ms." `
    -XAxisLabel "Cycle step number"

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
        "Total moves", "Avg move duration", "Final cell"
    )
    foreach ($run in $runs) {
        $runMoveDurations = @($moveDurationRows | Where-Object { $_.run_id -eq $run.run_id })
        $avgCycleMs = Get-Average -Rows $runMoveDurations -Field "duration_ms"
        $totalDurationMs = Get-Sum -Rows $runMoveDurations -Field "duration_ms"
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

$lines.Add("## Move Duration Summary")
$lines.Add("")
$moveSummaryHeaders = @("Baseline move avg ms", "CCRS move avg ms")
Add-TableHeader -Lines $lines -Headers $moveSummaryHeaders
$baselineMoveRows = Get-CycleRowsForRuns -Cycles $moveDurationRows -Runs $runs -Ccrs $false
$ccrsMoveRows = Get-CycleRowsForRuns -Cycles $moveDurationRows -Runs $runs -Ccrs $true
$moveSummaryCells = @(
    (Format-Ms (Get-Average -Rows $baselineMoveRows -Field "duration_ms")),
    (Format-Ms (Get-Average -Rows $ccrsMoveRows -Field "duration_ms"))
)
$lines.Add("| " + ($moveSummaryCells -join " | ") + " |")
$lines.Add("")
$lines.Add("Move averages use `move-durations.csv`, derived from `move-action-correlation.csv`. HTTP calls use the same move windows and are plotted separately.")
$lines.Add("")
if ($hasMoveDurationChart) {
    $lines.Add("## Move Duration Chart")
    $lines.Add("")
    $lines.Add("![Move duration by step]($moveDurationChartName)")
    $lines.Add("")
    $lines.Add("X-axis is movement step number; y-axis is log-scaled move duration with ticks at 1000, 2000, 4000, 8000, 16000, 32000, 64000, and 80000 ms.")
    $lines.Add("")
}

if ($hasHttpCallsChart) {
    $lines.Add("## HTTP Calls Chart")
    $lines.Add("")
    $lines.Add("![HTTP calls by move window]($httpCallsChartName)")
    $lines.Add("")
    $lines.Add("X-axis is movement step number; y-axis is linear HTTP calls from 0 to 35 in 2-call steps, stacked by success and failure per agent.")
    $lines.Add("")
}

$lines.Add("## Cycle Duration Summary")
$lines.Add("")
$cycleSummaryHeaders = @("Baseline cycle avg ms", "CCRS cycle avg ms")
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
$lines.Add('Cycle averages use `cycle-durations.csv`. Fresh runs populate this from `react.loop.cycle` events emitted from the React state cycle channel; historical CCRS-only rows may fall back to older structured CCRS cycle events. Opportunistic CCRS cycle averages exclude cycles where contingency CCRS was activated.')
$lines.Add("")
if ($hasCycleDurationChart) {
    $lines.Add("## Cycle Duration Chart")
    $lines.Add("")
    $lines.Add("![Cycle duration by step]($cycleDurationChartName)")
    $lines.Add("")
    $lines.Add("X-axis is React loop-cycle step number; y-axis is linear cycle duration in milliseconds.")
    $lines.Add("")
}

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
    "move-action-correlation.csv",
    "move-durations.csv",
    "java-library-evidence.csv",
    "move-duration-comparison.svg",
    "http-calls-by-move.svg",
    "cycle-duration-comparison.svg",
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
    moveActionCorrelationRowCount = $moveActionCorrelation.Count
    moveDurationRowCount = $moveDurationRows.Count
    javaEvidenceCount = $javaEvidence.Count
    summaryMarkdown = "summary.md"
    metricsDocumentation = "..\..\METRICS.md"
    artifacts = $artifactNames
}
$summaryObject | ConvertTo-Json -Depth 8 | Set-Content -Path $summaryJsonPath -Encoding UTF8

Write-Host "Wrote React experiment report."
Write-Host "Summary: $summaryPath"
Write-Host "Metrics: $(Join-Path $repoRoot 'experiments\METRICS.md')"
