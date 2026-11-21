# Render figures 10.1 and 10.2 from saved TV5 held-out results on Windows.
[CmdletBinding()]
param(
    [string]$TableDirectory = (Join-Path $PSScriptRoot 'outputs/tables'),
    [string]$FigureDirectory = (Join-Path $PSScriptRoot 'outputs/figures')
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$predictionFile = Join-Path $TableDirectory 'test_predictions.csv'
$predictions = @(Import-Csv -LiteralPath $predictionFile -Encoding UTF8)
$tier = @(Import-Csv -LiteralPath (Join-Path $TableDirectory 'table_10_3_error_by_price_tier.csv') -Encoding UTF8)
$seller = @(Import-Csv -LiteralPath (Join-Path $TableDirectory 'table_10_4_error_by_brand_and_seller.csv') -Encoding UTF8 |
    Where-Object dimension -eq 'seller_name')
[void](New-Item -ItemType Directory -Path $FigureDirectory -Force)

$modelKeys = @('ridge', 'rf', 'lgbm')
$modelColors = @{ ridge = '#196A9F'; rf = '#CE572E'; lgbm = '#008778' }
$modelNames = @{ ridge = 'Ridge'; rf = 'Random Forest'; lgbm = 'LightGBM' }
$categories = @('laptop', 'smartphone')
$categoryNames = @{ laptop = 'Laptop'; smartphone = 'Smartphone' }
$tierKeys = @('under_10m', '10m_to_under_20m', '20m_to_35m', 'over_35m')
$tierLabels = @('<10', '10 to <20', '20 to 35', '>35')
$ink = '#172E43'; $muted = '#536778'; $grid = '#DFE6EB'; $reference = '#889BAA'
$culture = [Globalization.CultureInfo]::InvariantCulture
$brushes = @{}; $fonts = @{}; $pens = @{}

function Get-Brush([string]$color, [int]$alpha = 255) {
    $key = "$color/$alpha"
    if (-not $brushes.ContainsKey($key)) {
        $base = [Drawing.ColorTranslator]::FromHtml($color)
        $brushes[$key] = [Drawing.SolidBrush]::new([Drawing.Color]::FromArgb($alpha, $base))
    }
    return $brushes[$key]
}

function Add-Line($x1, $y1, $x2, $y2, $color = $grid, $width = 2) {
    $key = "$color/$width"
    if (-not $pens.ContainsKey($key)) {
        $pens[$key] = [Drawing.Pen]::new([Drawing.ColorTranslator]::FromHtml($color), $width)
    }
    $script:draw.DrawLine($pens[$key], [single]$x1, [single]$y1, [single]$x2, [single]$y2)
}

function Add-Text($text, $x, $y, $w, $h, $size, $color, $align = 'Near', [switch]$Bold) {
    $key = "$size/$Bold"
    if (-not $fonts.ContainsKey($key)) {
        $style = if ($Bold) { [Drawing.FontStyle]::Bold } else { [Drawing.FontStyle]::Regular }
        $fonts[$key] = [Drawing.Font]::new('Segoe UI', $size, $style, [Drawing.GraphicsUnit]::Pixel)
    }
    $format = [Drawing.StringFormat]::new()
    try {
        $format.Alignment = $align
        $format.LineAlignment = 'Center'
        $format.FormatFlags = [Drawing.StringFormatFlags]::NoWrap
        $format.Trimming = 'EllipsisCharacter'
        $rect = [Drawing.RectangleF]::new($x, $y, $w, $h)
        $script:draw.DrawString([string]$text, $fonts[$key], (Get-Brush $color), $rect, $format)
    } finally { $format.Dispose() }
}

function Start-Figure($title, $subtitle) {
    $script:bitmap = [Drawing.Bitmap]::new(2700, 1710)
    $script:bitmap.SetResolution(300, 300)
    $script:draw = [Drawing.Graphics]::FromImage($script:bitmap)
    $script:draw.Clear([Drawing.Color]::White)
    $script:draw.SmoothingMode = 'AntiAlias'
    $script:draw.TextRenderingHint = 'AntiAliasGridFit'
    Add-Text $title 95 36 2500 96 60 $ink -Bold
    Add-Text $subtitle 99 137 2500 62 32 $muted
    for ($i = 0; $i -lt $modelKeys.Count; $i++) {
        $key = $modelKeys[$i]
        $x = 100 + $i * 425
        $script:draw.FillRectangle((Get-Brush $modelColors[$key]), $x, 226, 34, 34)
        Add-Text $modelNames[$key] ($x + 49) 207 360 69 31 $ink
    }
}

function Save-Figure($filename) {
    $path = Join-Path $FigureDirectory $filename
    $script:bitmap.Save($path, [Drawing.Imaging.ImageFormat]::Png)
    Write-Output $path
}

function Close-Figure {
    if ($null -ne $script:draw) { $script:draw.Dispose(); $script:draw = $null }
    if ($null -ne $script:bitmap) { $script:bitmap.Dispose(); $script:bitmap = $null }
}

function Get-Panel($left, $top, $title, $unit, $xMin, $xMax, $yMin, $yMax) {
    Add-Text $title $left $top 1220 62 42 $ink -Bold
    Add-Text $unit ($left + 113) ($top + 63) 1080 47 27 $muted
    return @{
        left = $left + 113; top = $top + 117; width = 1080; height = 383;
        xMin = $xMin; xMax = $xMax; yMin = $yMin; yMax = $yMax
    }
}

function X-Position($p, $x) { return $p.left + $p.width * ($x - $p.xMin) / ($p.xMax - $p.xMin) }
function Y-Position($p, $y) { return $p.top + $p.height * ($p.yMax - $y) / ($p.yMax - $p.yMin) }

function Add-YGrid($p, $ticks, [switch]$LogPrice) {
    foreach ($tick in $ticks) {
        $yValue = if ($LogPrice) { [Math]::Log10($tick) } else { $tick }
        $y = Y-Position $p $yValue
        Add-Line $p.left $y ($p.left + $p.width) $y
        Add-Text $tick ($p.left - 105) ($y - 22) 83 44 27 $muted 'Far'
    }
}

function Get-Millions([string]$text) { return [double]::Parse($text, $culture) / 1000000 }

function Write-ResidualFigure {
    Start-Figure 'Figure 10.1   TV5 price predictions and residuals' 'Original TV5 models scored on the same held-out listings'
    try {
        $priceTicks = @(1, 2, 5, 10, 20, 50, 100, 200)
        $xLimit = [Math]::Log10(200)
        for ($i = 0; $i -lt $categories.Count; $i++) {
            $category = $categories[$i]
            $name = $categoryNames[$category]
            $top = 306 + 612 * $i
            $records = @($predictions | Where-Object category -eq $category)
            $listingCount = @($records | Where-Object model -eq 'ridge').Count
            $left = Get-Panel 95 $top "$name | Observed vs. predicted" 'Predicted price (million VND, log scale)' 0 $xLimit 0 $xLimit
            $min = if ($category -eq 'laptop') { -100 } else { -180 }
            $max = if ($category -eq 'laptop') { 50 } else { 60 }
            $yTicks = if ($category -eq 'laptop') { @(-100, -75, -50, -25, 0, 25, 50) } else { @(-180, -120, -60, 0, 60) }
            $right = Get-Panel 1393 $top "$name | Residuals ($listingCount listings)" 'Predicted minus observed price (million VND)' 0 $xLimit $min $max
            Add-YGrid $left $priceTicks -LogPrice
            Add-YGrid $right $yTicks
            foreach ($p in @($left, $right)) {
                foreach ($price in $priceTicks) {
                    $x = X-Position $p ([Math]::Log10($price))
                    Add-Line $x $p.top $x ($p.top + $p.height)
                    Add-Text $price ($x - 55) ($p.top + $p.height + 9) 110 40 27 $muted 'Center'
                }
                Add-Text 'Observed price (million VND, log scale)' $p.left ($p.top + $p.height + 52) $p.width 48 28 $ink 'Center'
            }
            Add-Line $left.left ($left.top + $left.height) ($left.left + $left.width) $left.top $reference 4
            $zero = Y-Position $right 0
            Add-Line $right.left $zero ($right.left + $right.width) $zero $reference 4
            foreach ($record in $records) {
                $actual = [Math]::Log10((Get-Millions $record.recorded_price_vnd))
                $guess = [Math]::Log10((Get-Millions $record.predicted_price_vnd))
                $residual = Get-Millions $record.signed_error_vnd
                $brush = Get-Brush $modelColors[$record.model] 118
                $script:draw.FillEllipse($brush, [single]((X-Position $left $actual) - 4.5), [single]((Y-Position $left $guess) - 4.5), 9, 9)
                $script:draw.FillEllipse($brush, [single]((X-Position $right $actual) - 4.5), [single]((Y-Position $right $residual) - 4.5), 9, 9)
            }
        }
        Add-Text 'Diagonal = exact prediction. Residuals below zero indicate underprediction.' 98 1584 2500 55 31 $muted
        Add-Text 'Price axes use logarithmic spacing. Residual axes are linear and have different ranges by device category.' 98 1634 2500 49 26 $muted
        Save-Figure 'fig_10_1_residual_and_actual_vs_pred.png'
    } finally { Close-Figure }
}

function Add-MaeBars($p, $data, $segments, $labels) {
    for ($i = 0; $i -lt $segments.Count; $i++) {
        $segment = $segments[$i]
        $rows = @($data | Where-Object segment -eq $segment)
        if ($rows.Count -ne 3 -or @($rows.n_test | Sort-Object -Unique).Count -ne 1) {
            throw "Expected three model metrics with matching counts for $segment"
        }
        $mid = X-Position $p ($i + 1)
        for ($j = 0; $j -lt $modelKeys.Count; $j++) {
            $key = $modelKeys[$j]
            $metric = $rows | Where-Object model -eq $key
            $y = Y-Position $p (Get-Millions $metric.mae_vnd)
            $script:draw.FillRectangle((Get-Brush $modelColors[$key]), [single]($mid + $j * 48 - 69), [single]$y, 43, [single]($p.top + $p.height - $y))
        }
        Add-Text $labels[$i] ($mid - 103) ($p.top + $p.height + 6) 206 43 29 $ink 'Center'
        Add-Text "n=$($rows[0].n_test)" ($mid - 103) ($p.top + $p.height + 47) 206 38 25 $muted 'Center'
    }
}

function Write-SlicedFigure {
    Start-Figure 'Figure 10.2   TV5 error by price tier and retailer' 'Mean absolute error (MAE) on the original TV5 test predictions'
    try {
        for ($i = 0; $i -lt $categories.Count; $i++) {
            $category = $categories[$i]
            $name = $categoryNames[$category]
            $top = 306 + 612 * $i
            $byPrice = @($tier | Where-Object category -eq $category)
            $bySeller = @($seller | Where-Object category -eq $category)
            $stores = @($bySeller.segment | Sort-Object -Unique)
            $highest = (@($byPrice + $bySeller) | Measure-Object -Property { Get-Millions $_.mae_vnd } -Maximum).Maximum
            $yMax = [Math]::Max(2, [Math]::Ceiling($highest / 2) * 2)
            $left = Get-Panel 95 $top "$name | Recorded price tier" 'MAE (million VND)' 0.5 ($tierKeys.Count + 0.5) 0 $yMax
            $right = Get-Panel 1393 $top "$name | Retailer" 'MAE (million VND)' 0.5 ($stores.Count + 0.5) 0 $yMax
            Add-YGrid $left (0..($yMax / 2) | ForEach-Object { $_ * 2 })
            Add-YGrid $right (0..($yMax / 2) | ForEach-Object { $_ * 2 })
            Add-MaeBars $left $byPrice $tierKeys $tierLabels
            Add-MaeBars $right $bySeller $stores $stores
        }
        Add-Text 'Recorded price tiers use million VND. n is the number of test listings in each group.' 98 1584 2500 55 31 $muted
        Add-Text 'Both panels for a device category use the same MAE scale. Small groups are sensitive to individual listings.' 98 1634 2500 49 26 $muted
        Save-Figure 'fig_10_2_error_by_price_tier_and_seller.png'
    } finally { Close-Figure }
}

try {
    Write-ResidualFigure
    Write-SlicedFigure
} finally {
    foreach ($item in @($brushes.Values) + @($fonts.Values) + @($pens.Values)) { $item.Dispose() }
}
