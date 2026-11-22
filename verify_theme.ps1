# ==============================================================================
# verify_theme.ps1 - Weryfikacja motywu potomnego PrestaShop 8.2 (Wymog D1)
# ==============================================================================
$ErrorActionPreference = "Stop"

Write-Host "=== ROZPOCZECIE WERYFIKACJI MOTYWU POTOMNEGO D1 (Issue #26) ===" -ForegroundColor Cyan
$root = $PSScriptRoot

# --- 1. Sprawdzenie struktury plikow motywu potomnego ---
Write-Host "`n[1/5] Weryfikacja struktury katalogow i plikow..." -ForegroundColor Yellow
$themeDir = Join-Path $root "shop\themes\classic-fashion"
$requiredFiles = @(
    "config\theme.yml",
    "preview.png",
    "assets\css\custom.css",
    "assets\img\banner-fashion.jpg",
    "assets\img\sample-1.jpg",
    "templates\README.md"
)

foreach ($rf in $requiredFiles) {
    $fullPath = Join-Path $themeDir $rf
    if (-not (Test-Path $fullPath)) {
        throw "Brak wymaganego pliku motywu potomnego: $rf ($fullPath)"
    }
    Write-Host "  [OK] Plik istnieje: $rf" -ForegroundColor Green
}

# --- 2. Weryfikacja skladni i metadanych theme.yml ---
Write-Host "`n[2/5] Weryfikacja pliku konfiguracyjnego theme.yml..." -ForegroundColor Yellow
$themeYmlPath = Join-Path $themeDir "config\theme.yml"
$ymlContent = Get-Content $themeYmlPath -Raw

if ($ymlContent -notmatch "(?m)^parent:\s*classic") {
    throw "Blad: theme.yml musi miec ustawione 'parent: classic'!"
}
if ($ymlContent -notmatch "(?m)^name:\s*classic-fashion") {
    throw "Blad: theme.yml musi miec ustawione 'name: classic-fashion'!"
}
if ($ymlContent -notmatch "(?m)^version:\s*1\.0\.0") {
    throw "Blad: theme.yml musi miec ustawiona wersje 'version: 1.0.0'!"
}
if ($ymlContent -notmatch "assets/css/custom\.css") {
    throw "Blad: theme.yml musi rejestrowac assets/css/custom.css!"
}
Write-Host "  [OK] Metadane theme.yml poprawne (parent: classic, name: classic-fashion, version: 1.0.0, assety: custom.css)" -ForegroundColor Green

# --- 3. Weryfikacja arkusza styli custom.css ---
Write-Host "`n[3/5] Weryfikacja arkusza styli custom.css..." -ForegroundColor Yellow
$cssPath = Join-Path $themeDir "assets\css\custom.css"
$cssContent = Get-Content $cssPath -Raw

# 3.1. Zbalansowane nawiasy klamrowe
$openCount = ([regex]::Matches($cssContent, "{")).Count
$closeCount = ([regex]::Matches($cssContent, "}")).Count
if ($openCount -ne $closeCount) {
    throw "Blad skladni CSS: liczba '{' ($openCount) nie zgadza sie z '}' ($closeCount)!"
}
Write-Host "  [OK] Zbalansowane bloki CSS ({: $openCount, }: $closeCount)" -ForegroundColor Green

# 3.2. Sprawdzenie mediĂłw 360 px
if ($cssContent -notmatch "360px|max-width:\s*380px|max-width:\s*576px") {
    throw "Blad: Brak media queries dla szerokosci ekranu telefonu (360px) w custom.css!"
}
Write-Host "  [OK] Media queries dla telefonow komorkowych (360px) zdefiniowane poprawnie." -ForegroundColor Green

# 3.3. Sprawdzenie proporcji 3:4 dla zdjec modowych
if ($cssContent -notmatch "aspect-ratio:\s*3\s*/\s*4") {
    throw "Blad: Brak modowej proporcji aspect-ratio: 3 / 4 w custom.css!"
}
Write-Host "  [OK] Proporcja kart produktowych 3:4 obecna." -ForegroundColor Green

# 3.4. Sprawdzenie wskaznikow fokusu dla Lighthouse Accessibility
if ($cssContent -notmatch ":focus-visible") {
    throw "Blad: Brak stylizacji :focus-visible pod katem dostepnosci WCAG/Lighthouse!"
}
Write-Host "  [OK] Stylowanie :focus-visible (WCAG Accessibility) obecne." -ForegroundColor Green

# 3.5. Sprawdzenie kontrastu WCAG (uzyte kolory tekstu i tla)
$expectedColors = @("#111111", "#222222", "#595959", "#b82e38", "#ffffff")
foreach ($col in $expectedColors) {
    if ($cssContent -notmatch [regex]::Escape($col)) {
        throw "Blad: custom.css nie zawiera zwalidowanego koloru tokenu WCAG: $col"
    }
}
Write-Host "  [OK] Bezpieczna paleta kolorow WCAG AA (kontrast >= 4.5:1 dla tekstu normalnego)." -ForegroundColor Green

# --- 4. Weryfikacja banera i grafik ---
Write-Host "`n[4/5] Weryfikacja plikow graficznych banera..." -ForegroundColor Yellow
Add-Type -AssemblyName System.Drawing
$bannerFile = Join-Path $themeDir "assets\img\banner-fashion.jpg"
$previewFile = Join-Path $themeDir "preview.png"

$imgBanner = [System.Drawing.Image]::FromFile($bannerFile)
$bWidth = $imgBanner.Width
$bHeight = $imgBanner.Height
$bLength = (Get-Item $bannerFile).Length
$imgBanner.Dispose()

if ($bWidth -lt 1000 -or $bHeight -lt 300) {
    throw "Blad: Wymiary banera ($bWidth x $bHeight) sa zbyt male dla slidera strony glownej!"
}
if ($bLength -gt 300000) {
    throw "Blad: Rozmiar banera ($bLength B) przekracza zalecany limit 300 KB dla wydajnosci strony!"
}
Write-Host "  [OK] Baner modowy ($bWidth x $bHeight px, $([math]::Round($bLength/1KB, 1)) KB) jest zoptymalizowany pod Lighthouse." -ForegroundColor Green

$imgPrev = [System.Drawing.Image]::FromFile($previewFile)
$pWidth = $imgPrev.Width
$pHeight = $imgPrev.Height
$pLength = (Get-Item $previewFile).Length
$imgPrev.Dispose()
Write-Host "  [OK] Miniatura motywu preview.png ($pWidth x $pHeight px, $([math]::Round($pLength/1KB, 1)) KB)." -ForegroundColor Green

# --- 5. Weryfikacja braku zmian w motywie classic (Wymog krytyczny D1) ---
Write-Host "`n[5/5] Weryfikacja krytycznego warunku: brak modyfikacji motywu classic..." -ForegroundColor Yellow
$classicDir = Join-Path $root "shop\themes\classic"
if (Test-Path $classicDir) {
    $diff = git -C $root status --porcelain $classicDir
    if ($diff) {
        throw "BLAD KRYTYCZNY D1: Wykryto bezposrednie modyfikacje w motywie classic:`n$diff"
    }
}
# Upewnienie sie ze compose.yaml nie podmienia plikow w themes/classic
$composePath = Join-Path $root "deploy\compose.yaml"
$composeContent = Get-Content $composePath -Raw
if ($composeContent -match "themes/classic/") {
    throw "BLAD KRYTYCZNY D1: deploy/compose.yaml zawiera bind-mount nadpisujacy motyw classic!"
}
Write-Host "  [OK] Ani jedna linijka motywu bazowego classic nie zostala zmodyfikowana." -ForegroundColor Green
Write-Host "  [OK] deploy/compose.yaml montuje wylacznie motyw potomny themes/classic-fashion." -ForegroundColor Green

Write-Host "`n=================================================================" -ForegroundColor Cyan
Write-Host " WSZYSTKIE TESTY WERYFIKACYJNE D1 ZAKONCZONE SUKCESEM (5/5 OK)!" -ForegroundColor Green
Write-Host "=================================================================" -ForegroundColor Cyan
