# Render figures 10.4 to 10.7 from the saved explanation values on Windows.
# & .\src\evaluation_demo\plot_explainability.ps1
[CmdletBinding()]
param(
    [string]$DataPath = (Join-Path $PSScriptRoot 'outputs/explainability_data.json'),
    [string]$FigureDirectory = (Join-Path $PSScriptRoot 'outputs/figures')
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$data = Get-Content -LiteralPath $DataPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (@($data.global).Count -ne 2 -or @($data.local).Count -ne 3 -or @($data.sweeps).Count -ne 4) {
    throw 'Expected two global summaries, three local explanations and four sweeps.'
}
[void](New-Item -ItemType Directory -Path $FigureDirectory -Force)

$palette = @{ ridge = '#196A9F'; rf = '#CE572E'; lgbm = '#008778' }
$modelNames = @{ ridge = 'Ridge'; rf = 'Random Forest'; lgbm = 'LightGBM' }
$categoryNames = @{ laptop = 'Laptop'; smartphone = 'Smartphone' }
$ink = '#172E43'; $muted = '#536778'; $grid = '#DFE6EB'
$positive = '#CE572E'; $negative = '#196A9F'
$brushes = @{}; $fonts = @{}; $pens = @{}
$culture = [Globalization.CultureInfo]::InvariantCulture

function Get-Brush([string]$color) {
    if (-not $brushes.ContainsKey($color)) {
        $brushes[$color] = [Drawing.SolidBrush]::new([Drawing.ColorTranslator]::FromHtml($color))
    }
    return $brushes[$color]
}

function Get-Pen([string]$color, [single]$width) {
    $key = "$color/$width"
    if (-not $pens.ContainsKey($key)) {
        $pens[$key] = [Drawing.Pen]::new([Drawing.ColorTranslator]::FromHtml($color), $width)
    }
    return $pens[$key]
}

function Add-Text($text, $x, $y, $width, $height, $size, $color, $align = 'Near', [switch]$Bold) {
    $key = "$size/$Bold"
    if (-not $fonts.ContainsKey($key)) {
        $style = if ($Bold) { [Drawing.FontStyle]::Bold } else { [Drawing.FontStyle]::Regular }
        $fonts[$key] = [Drawing.Font]::new('Segoe UI', $size, $style, [Drawing.GraphicsUnit]::Pixel)
    }
    $format = [Drawing.StringFormat]::new()
    try {
        $format.Alignment = $align
        $format.LineAlignment = 'Center'
        $format.Trimming = 'EllipsisCharacter'
        $format.FormatFlags = [Drawing.StringFormatFlags]::NoWrap
        $rect = [Drawing.RectangleF]::new($x, $y, $width, $height)
        $script:draw.DrawString([string]$text, $fonts[$key], (Get-Brush $color), $rect, $format)
    } finally { $format.Dispose() }
}

function Add-Line($x1, $y1, $x2, $y2, $color = $grid, $width = 2) {
    $script:draw.DrawLine((Get-Pen $color $width), [single]$x1, [single]$y1, [single]$x2, [single]$y2)
}

function Add-Rectangle($x, $y, $width, $height, $color) {
    $script:draw.FillRectangle((Get-Brush $color), [single]$x, [single]$y, [single]$width, [single]$height)
}

function Add-Dot($x, $y, $radius, $color) {
    $script:draw.FillEllipse((Get-Brush $color), [single]($x - $radius), [single]($y - $radius), [single](2 * $radius), [single](2 * $radius))
}

function Start-Canvas($height) {
    $script:bitmap = [Drawing.Bitmap]::new(2700, $height)
    $script:bitmap.SetResolution(300, 300)
    $script:draw = [Drawing.Graphics]::FromImage($script:bitmap)
    $script:draw.Clear([Drawing.Color]::White)
    $script:draw.SmoothingMode = 'AntiAlias'
    $script:draw.TextRenderingHint = 'AntiAliasGridFit'
}

function Close-Canvas {
    if ($null -ne $script:draw) { $script:draw.Dispose(); $script:draw = $null }
    if ($null -ne $script:bitmap) { $script:bitmap.Dispose(); $script:bitmap = $null }
}

function Save-Canvas($filename) {
    $path = Join-Path $FigureDirectory $filename
    $script:bitmap.Save($path, [Drawing.Imaging.ImageFormat]::Png)
    Write-Output $path
}

function Convert-Position($value, $low, $high, $start, $span) {
    return $start + $span * (($value - $low) / ($high - $low))
}

function Format-Number([double]$value, [string]$pattern = '0.00') {
    return $value.ToString($pattern, $culture)
}

function Get-ValueColor($value) {
    if ($null -eq $value) { return '#8795A0' }
    $index = [Math]::Min(8, [Math]::Max(0, [int][Math]::Floor(9 * $value)))
    return @('#2B79B5', '#4A91C4', '#70A9D1', '#9DC0DA', '#B4AEB7', '#D1958D', '#DA7D70', '#D16050', '#B74235')[$index]
}

function Write-GlobalFigure($summary) {
    $category = $categoryNames[[string]$summary.category]
    $number = if ($summary.category -eq 'laptop') { 4 } else { 5 }
    $features = @($summary.features)
    if ($features.Count -lt 1) { throw "No SHAP features for $category" }
    Start-Canvas 1510
    try {
        Add-Text "Figure 10.$number   SHAP summary | $category" 95 45 2490 92 61 $ink -Bold
        Add-Text "S4 LightGBM  /  $($summary.n_test) test listings  /  Top $($features.Count) features" 99 137 2470 60 33 $muted
        Add-Text 'SHAP values by listing' 530 270 1200 72 41 $ink -Bold
        Add-Text 'Mean absolute SHAP' 1885 270 710 72 41 $ink -Bold

        $sx = 530; $sw = 1210; $bx = 1885; $bw = 680
        $top = 365; $height = 805; $rowHeight = $height / $features.Count
        $absMax = 0.0; $meanMax = 0.0
        foreach ($feature in $features) {
            $meanMax = [Math]::Max($meanMax, [double]$feature.mean_abs)
            foreach ($point in @($feature.points)) { $absMax = [Math]::Max($absMax, [Math]::Abs([double]$point.shap)) }
        }
        $absMax = [Math]::Max(0.01, $absMax * 1.035)
        $meanMax = [Math]::Max(0.01, $meanMax * 1.12)

        for ($tick = -2; $tick -le 2; $tick++) {
            $value = $tick * $absMax / 2
            $position = Convert-Position $value (-$absMax) $absMax $sx $sw
            $rule = if ($tick -eq 0) { '#A3B1BD' } else { $grid }
            Add-Line $position $top $position ($top + $height) $rule
            Add-Text (Format-Number $value) ($position - 65) ($top + $height + 15) 130 44 26 $muted 'Center'
        }
        for ($tick = 0; $tick -le 4; $tick++) {
            $value = $tick * $meanMax / 4
            $position = Convert-Position $value 0 $meanMax $bx $bw
            Add-Line $position $top $position ($top + $height)
            Add-Text (Format-Number $value) ($position - 65) ($top + $height + 15) 130 44 26 $muted 'Center'
        }
        for ($i = 0; $i -lt $features.Count; $i++) {
            $feature = $features[$i]
            $y = $top + ($i + 0.5) * $rowHeight
            Add-Text $feature.label 95 ($y - 24) 400 48 31 $ink 'Far'
            Add-Line $sx $y ($sx + $sw) $y
            Add-Line $bx $y ($bx + $bw) $y
            foreach ($point in @($feature.points)) {
                $x = Convert-Position $point.shap (-$absMax) $absMax $sx $sw
                $offset = [Math]::Max(-0.35, [Math]::Min(0.35, [double]$point.offset))
                Add-Dot $x ($y + $offset * $rowHeight) 4.4 (Get-ValueColor $point.color_value)
            }
            Add-Rectangle $bx ($y - 17) ($bw * $feature.mean_abs / $meanMax) 34 '#257C80'
        }
        Add-Text 'Contribution to log1p(price)' $sx 1232 $sw 56 30 $ink 'Center'
        Add-Text 'Average magnitude in log1p(price)' $bx 1232 $bw 56 30 $ink 'Center'

        Add-Text 'Numeric feature value' 98 1362 370 55 31 $muted
        for ($i = 0; $i -lt 9; $i++) {
            Add-Rectangle (480 + 45 * $i) 1382 43 17 (Get-ValueColor ($i / 8))
        }
        Add-Text 'Low' 477 1410 120 45 26 $muted
        Add-Text 'High' 766 1410 120 45 26 $muted 'Far'
        Add-Dot 1040 1391 8 (Get-ValueColor $null)
        Add-Text 'Categorical feature' 1067 1362 500 55 31 $muted
        Add-Text 'Positive values push predicted price higher.' 1632 1362 990 55 31 $muted 'Far'

        Save-Canvas "fig_10_$($number)_shap_summary_$($summary.category).png"
    } finally { Close-Canvas }
}

function Write-WaterfallFigure($examples) {
    Start-Canvas 1660
    try {
        Add-Text 'Figure 10.6   How individual predictions add up' 95 45 2500 92 61 $ink -Bold
        Add-Text 'S4 LightGBM | Contributions allocated from log1p price to million VND' 99 137 2485 60 33 $muted
        for ($i = 0; $i -lt $examples.Count; $i++) {
            $example = $examples[$i]
            $left = 95 + 836 * $i
            $category = $categoryNames[[string]$example.category]
            Add-Text ("{0} | {1}" -f $example.tier, $category) $left 252 800 58 41 $ink -Bold
            Add-Text $example.name $left 317 792 64 31 $muted
            $baseline = $example.baseline_vnd / 1e6; $prediction = $example.predicted_vnd / 1e6
            $actual = $example.actual_vnd / 1e6
            Add-Text ("Recorded price  {0}M VND" -f (Format-Number $actual '0.00')) $left 388 800 45 27 $muted

            $rows = @([pscustomobject]@{label = 'Baseline'; start = 0; end = $baseline; delta = $baseline; total = $true})
            foreach ($step in @($example.steps)) {
                $rows += [pscustomobject]@{label = $step.label; start = $step.start_vnd / 1e6; end = $step.end_vnd / 1e6; delta = $step.delta_vnd / 1e6; total = $false}
            }
            $rows += [pscustomobject]@{label = 'Prediction'; start = 0; end = $prediction; delta = $prediction; total = $true}

            $low = 0.0; $high = 0.0
            foreach ($row in $rows) {
                $low = [Math]::Min($low, [Math]::Min([double]$row.start, [double]$row.end))
                $high = [Math]::Max($high, [Math]::Max([double]$row.start, [double]$row.end))
            }
            $bound = [Math]::Max(1.0, ($high - $low))
            $high += 0.07 * $bound
            $x1 = $left + 248; $span = 430
            $top = 476; $height = 835; $rowHeight = $height / $rows.Count
            for ($tick = 0; $tick -le 3; $tick++) {
                $x = $x1 + $span * $tick / 3
                $value = $low + ($high - $low) * $tick / 3
                Add-Line $x $top $x ($top + $height)
                Add-Text (Format-Number $value '0.#') ($x - 50) ($top + $height + 10) 100 46 26 $muted 'Center'
            }
            for ($j = 0; $j -lt $rows.Count; $j++) {
                $row = $rows[$j]
                $y = $top + ($j + 0.5) * $rowHeight
                $start = Convert-Position $row.start $low $high $x1 $span
                $end = Convert-Position $row.end $low $high $x1 $span
                $heightBar = [Math]::Min(48, $rowHeight * 0.52)
                $color = if ($row.total) { $ink } elseif ($row.delta -lt 0) { $negative } else { $positive }
                Add-Text $row.label $left ($y - 23) 227 46 27 $ink 'Far' -Bold:$row.total
                if ($j -lt $rows.Count - 1) {
                    Add-Line $end ($y + $heightBar / 2) $end ($y + $rowHeight - $heightBar / 2) '#9DADB9'
                }
                Add-Rectangle ([Math]::Min($start, $end)) ($y - $heightBar / 2) ([Math]::Max(3, [Math]::Abs($end - $start))) $heightBar $color
                $format = if ($row.total) { '0.00' } else { '+0.00;-0.00;0.00' }
                Add-Text (Format-Number $row.delta $format) ($x1 + $span + 15) ($y - 22) 107 44 27 $color 'Far' -Bold:$row.total
            }
            Add-Text 'Million VND' $x1 ($top + $height + 54) $span 49 28 $ink 'Center'
        }
        Add-Rectangle 95 1512 30 30 $positive
        Add-Text 'Raises prediction' 141 1497 375 60 31 $muted
        Add-Rectangle 555 1512 30 30 $negative
        Add-Text 'Lowers prediction' 601 1497 405 60 31 $muted
        Add-Text 'Baseline plus all contributions equals the model prediction.' 1060 1497 1533 60 31 $muted 'Far'
        Save-Canvas 'fig_10_6_shap_waterfall_examples.png'
    } finally { Close-Canvas }
}

function Write-SweepFigure($sweeps) {
    Start-Canvas 1720
    try {
        Add-Text 'Figure 10.7   How predictions respond to RAM and storage' 95 45 2500 92 61 $ink -Bold
        Add-Text 'S4 models | One reference configuration per category' 99 137 2470 60 33 $muted
        $legendX = 109
        foreach ($key in @('ridge', 'rf', 'lgbm')) {
            Add-Line $legendX 230 ($legendX + 72) 230 $palette[$key] 6
            Add-Dot ($legendX + 36) 230 8 $palette[$key]
            Add-Text $modelNames[$key] ($legendX + 86) 200 300 60 32 $ink
            $legendX += 440
        }
        foreach ($sweep in $sweeps) {
            $row = if ($sweep.category -eq 'laptop') { 0 } else { 1 }
            $column = if ($sweep.field -eq 'ram_gb') { 0 } else { 1 }
            $left = 95 + 1290 * $column; $top = 306 + 628 * $row
            $category = $categoryNames[[string]$sweep.category]
            $field = if ($column -eq 0) { 'RAM' } else { 'Storage' }
            Add-Text "$category | $field" $left $top 1210 58 41 $ink -Bold
            Add-Text $sweep.fixture_name $left ($top + 55) 1210 55 30 $muted
            $x1 = $left + 150; $span = 1030; $y1 = $top + 144; $height = 340
            $predictions = @($sweep.models | ForEach-Object { $_.predictions_vnd }) | Measure-Object -Minimum -Maximum
            $low = [double]$predictions.Minimum / 1e6; $high = [double]$predictions.Maximum / 1e6
            $logScale = $row -eq 1 -and $column -eq 0 -and $low -gt 0
            if ($logScale) {
                $low = [Math]::Log10($low); $high = [Math]::Log10($high)
            }
            $spread = [Math]::Max(0.25, $high - $low)
            $low -= 0.07 * $spread; $high += 0.07 * $spread
            $unit = if ($logScale) { 'Million VND (log scale)' } else { 'Million VND' }
            Add-Text $unit ($left + 147) ($y1 - 41) 550 40 27 $muted
            for ($tick = 0; $tick -le 4; $tick++) {
                $y = $y1 + $tick * $height / 4
                $value = $high - $tick * ($high - $low) / 4
                if ($logScale) { $value = [Math]::Pow(10, $value) }
                $pattern = if ($logScale) { '0' } else { '0.0' }
                Add-Line $x1 $y ($x1 + $span) $y
                Add-Text (Format-Number $value $pattern) ($left + 17) ($y - 23) 113 46 27 $muted 'Far'
            }

            $steps = @($sweep.grid); $plotX = @()
            for ($i = 0; $i -lt $steps.Count; $i++) {
                $x = $x1 + $span * ($i + 0.25) / ($steps.Count - 0.5)
                $plotX += $x
                Add-Line $x $y1 $x ($y1 + $height)
                $unseen = if ($null -ne $sweep.train_counts) { $sweep.train_counts[$i] -eq 0 } else { $logScale -and [double]$steps[$i] -ge 32 }
                $suffix = if ($unseen) { '*' } else { '' }
                Add-Text ("{0} GB{1}" -f $steps[$i], $suffix) ($x - 77) ($y1 + $height + 17) 154 49 29 $ink 'Center'
            }
            foreach ($model in @($sweep.models)) {
                $color = $palette[[string]$model.model]
                for ($i = 0; $i -lt $steps.Count; $i++) {
                    $value = [double]$model.predictions_vnd[$i] / 1e6
                    if ($logScale) { $value = [Math]::Log10($value) }
                    $y = Convert-Position $value $high $low $y1 $height
                    if ($i -gt 0) { Add-Line $plotX[$i - 1] $previousY $plotX[$i] $y $color 6 }
                    Add-Dot $plotX[$i] $y 9 $color
                    $previousY = $y
                }
            }
        }
        Add-Text 'One input changes at a time. Model interactions update while benchmark, store and review context stay fixed.' 95 1557 2520 55 29 $muted
        Add-Text '* No training listing in the category had this capacity. Treat predictions at these levels as extrapolations.' 95 1614 2520 55 29 $muted
        Save-Canvas 'fig_10_7_monotonicity_sanity_check.png'
    } finally { Close-Canvas }
}

try {
    foreach ($summary in @($data.global)) { Write-GlobalFigure $summary }
    Write-WaterfallFigure @($data.local)
    Write-SweepFigure @($data.sweeps)
} finally {
    foreach ($resource in @($fonts.Values) + @($brushes.Values) + @($pens.Values)) { $resource.Dispose() }
}
