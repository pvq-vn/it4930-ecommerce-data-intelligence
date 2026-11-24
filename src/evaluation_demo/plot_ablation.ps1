# Render figure 10.3 from the repo root in PowerShell on Windows.
# & .\src\evaluation_demo\plot_ablation.ps1
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms.DataVisualization
Add-Type -AssemblyName System.Drawing

$output = Join-Path $PSScriptRoot 'outputs'
$table = Import-Csv (Join-Path $output 'tables/table_10_2_ablation_and_tv7_sensitivity.csv')
$stock = Import-Csv (Join-Path $output 'tables/s2_charger_comparison.csv') | Where-Object test_subset -eq 'all'
$scores = @{}
foreach ($row in $table) { $scores["$($row.stage)/$($row.category)/$($row.model)"] = $row }
foreach ($row in $stock) { $scores["S2A/$($row.category)/$($row.model)"] = $row }

$palette = @{ ridge = '#196A9F'; rf = '#CE572E'; lgbm = '#008778' }
$modelNames = @{ ridge = 'Ridge'; rf = 'Random Forest'; lgbm = 'LightGBM' }
$ink = [Drawing.ColorTranslator]::FromHtml('#172E43')
$muted = [Drawing.ColorTranslator]::FromHtml('#536778')
$grid = [Drawing.ColorTranslator]::FromHtml('#DFE6EB')
$culture = [Globalization.CultureInfo]::InvariantCulture

function Read-Value($stage, $category, $key, $field) {
    $row = $scores["$stage/$category/$key"]
    if ($null -eq $row -or [string]::IsNullOrWhiteSpace($row.$field)) {
        throw "Missing value for $stage/$category/$key/$field"
    }
    return [double]::Parse($row.$field, $culture)
}

function Add-Label($text, $x, $y, $w, $h, $size, $color, [switch]$bold) {
    $title = [Windows.Forms.DataVisualization.Charting.Title]::new($text)
    $style = if ($bold) { [Drawing.FontStyle]::Bold } else { [Drawing.FontStyle]::Regular }
    $title.Font = [Drawing.Font]::new('Segoe UI', $size, $style)
    $title.ForeColor = $color
    $title.Alignment = [Drawing.ContentAlignment]::MiddleLeft
    $title.Position = [Windows.Forms.DataVisualization.Charting.ElementPosition]::new($x, $y, $w, $h)
    $chart.Titles.Add($title)
}

function Add-Panel($name, $x, $y, $labels, $values, $yTitle, $bars) {
    $area = [Windows.Forms.DataVisualization.Charting.ChartArea]::new($name)
    $area.Position = [Windows.Forms.DataVisualization.Charting.ElementPosition]::new($x, $y, 46, 32)
    $area.InnerPlotPosition = [Windows.Forms.DataVisualization.Charting.ElementPosition]::new(16, 5, 81, 84)
    $area.AxisX.Minimum = 0.5
    $area.AxisX.Maximum = $labels.Count + 0.5
    $area.AxisX.IsMarksNextToAxis = $false
    $area.AxisX.MajorGrid.Enabled = $false
    $area.AxisX.MajorTickMark.Enabled = $false
    for ($i = 0; $i -lt $labels.Count; $i++) {
        [void]$area.AxisX.CustomLabels.Add($i + 0.5, $i + 1.5, $labels[$i])
    }
    $area.AxisY.Title = $yTitle
    $area.AxisY.TitleFont = [Drawing.Font]::new('Segoe UI', 18)
    $area.AxisY.TitleForeColor = $muted
    $area.AxisY.MajorGrid.LineColor = $grid
    $area.AxisY.LabelStyle.Format = if ($bars) { '0;-0;0' } else { '0.00' }
    $area.AxisY.IsStartedFromZero = $bars
    foreach ($axis in @($area.AxisX, $area.AxisY)) {
        $axis.IsLabelAutoFit = $false
        $axis.LabelStyle.Font = [Drawing.Font]::new('Segoe UI', 21)
        $axis.LabelStyle.ForeColor = $ink
        $axis.LineColor = $grid
        $axis.MajorTickMark.LineColor = $grid
    }
    $chart.ChartAreas.Add($area)
    foreach ($key in @('ridge', 'rf', 'lgbm')) {
        $series = [Windows.Forms.DataVisualization.Charting.Series]::new("$name-$key")
        $series.ChartArea = $name
        $series.Color = [Drawing.ColorTranslator]::FromHtml($palette[$key])
        $series.LegendText = $modelNames[$key]
        $series.IsVisibleInLegend = $name -eq 'laptop-ablation'
        $series.ChartType = if ($bars) { 'Column' } else { 'Line' }
        if (-not $bars) {
            $series.BorderWidth = 6
            $series.MarkerStyle = 'Circle'
            $series.MarkerSize = 13
        }
        for ($i = 0; $i -lt $labels.Count; $i++) {
            [void]$series.Points.AddXY(($i + 1), $values[$key][$i])
        }
        $chart.Series.Add($series)
    }
}

$chart = [Windows.Forms.DataVisualization.Charting.Chart]::new()
$chart.Size = [Drawing.Size]::new(2700, 1660)
$chart.BackColor = [Drawing.Color]::White
$chart.AntiAliasing = 'All'
$chart.TextAntiAliasingQuality = 'High'
$legend = [Windows.Forms.DataVisualization.Charting.Legend]::new('Models')
$legend.Position = [Windows.Forms.DataVisualization.Charting.ElementPosition]::new(5, 8, 90, 4)
$legend.LegendStyle = 'Row'
$legend.Font = [Drawing.Font]::new('Segoe UI', 24)
$legend.ForeColor = $ink
$chart.Legends.Add($legend)

try {
    Add-Label 'Figure 10.3   Model ablation and anomaly sensitivity' 4 1 92 6 37 $ink -bold
    foreach ($category in @('laptop', 'smartphone')) {
        $ablation, $sensitivity = @{}, @{}
        foreach ($key in @('ridge', 'rf', 'lgbm')) {
            $ablation[$key] = @(foreach ($stage in @('S1', 'S2A', 'S3', 'S4')) {
                $field = if ($stage -eq 'S2A') { 'without_charger_mae_vnd' } else { 'mae_vnd' }
                (Read-Value $stage $category $key $field) / 1000000
            })
            $sensitivity[$key] = @(foreach ($stage in @('S5a', 'S5b')) {
                Read-Value $stage $category $key 'mae_change_vs_s4_pct'
            })
        }
        $label = if ($category -eq 'laptop') { 'Laptop' } else { 'Smartphone' }
        $top = if ($category -eq 'laptop') { 16 } else { 56 }
        Add-Label "$label | Feature ablation" 8 ($top - 4) 42 4 24 $ink -bold
        Add-Label "$label | TV7 delivered flags" 55 ($top - 4) 42 4 24 $ink -bold
        Add-Panel "$category-ablation" 3 $top @('S1', 'S2A', 'S3', 'S4') $ablation 'MAE (million VND)' $false
        Add-Panel "$category-sensitivity" 50 $top @('S5a', 'S5b') $sensitivity 'MAE change vs S4 (%)' $true
    }
    Add-Label 'S2A omits charger fields. S5a drops extreme flags; S5b drops all combined flags. Negative change indicates lower MAE.' 4 90 92 5 20 $muted
    Add-Label 'All stages use the same test listings: 819 laptops and 797 smartphones.' 4 95 92 4 20 $muted

    $figures = Join-Path $output 'figures'
    [void](New-Item -ItemType Directory -Path $figures -Force)
    $path = Join-Path $figures 'fig_10_3_ablation_and_sensitivity_chart.png'
    $bitmap = [Drawing.Bitmap]::new($chart.Width, $chart.Height)
    try {
        $bitmap.SetResolution(300, 300)
        $chart.DrawToBitmap($bitmap, [Drawing.Rectangle]::new(0, 0, $chart.Width, $chart.Height))
        $bitmap.Save($path, [Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $bitmap.Dispose()
    }
    Write-Output $path
} finally {
    $chart.Dispose()
}
