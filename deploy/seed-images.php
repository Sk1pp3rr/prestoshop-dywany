<?php
/**
 * Seeder zdjec produktowych 3:4 dla sklepu Mosquito (PrestaShop 8.2).
 *
 * Zrodla:
 *  1. Lokalne zdjecia referencyjne z /tmp/sample-images (<REF>_1.jpg ...)
 *  2. Pobieranie zdjec dla strony glownej i glownych kategorii z /tmp/products.json (curl_multi)
 *  3. Wypelnienie brakujacych rekordow ps_image z puli zweryfikowanych zdjec 3:4
 *     oraz wygenerowanie zaslepek pl-default-* / en-default-* w proporcji 3:4.
 */

declare(strict_types=1);

const IMG_BASE_DIR = '/var/www/html/img/p';
const SAMPLE_DIR = '/tmp/sample-images';
const PRODUCTS_JSON = '/tmp/products.json';
const FALLBACK_DIR = IMG_BASE_DIR . '/_msq_pool';

$DEFAULT_TYPES = [
    'cart_default'   => [120, 160],
    'small_default'  => [99, 132],
    'home_default'   => [360, 480],
    'medium_default' => [450, 600],
    'large_default'  => [600, 800],
];

function loadDbConfig(): array
{
    $host = getenv('DB_SERVER') ?: 'db';
    $port = getenv('DB_PORT') ?: '3306';
    $name = getenv('DB_NAME') ?: 'prestashop';
    $user = getenv('DB_USER') ?: 'prestashop_user';
    $pass = getenv('DB_PASSWD') ?: '';
    $prefix = getenv('DB_PREFIX') ?: 'ps_';

    $paramsFile = '/var/www/html/app/config/parameters.php';
    if (is_file($paramsFile)) {
        $cfg = @include $paramsFile;
        if (is_array($cfg) && isset($cfg['parameters']) && is_array($cfg['parameters'])) {
            $p = $cfg['parameters'];
            $host = (string)($p['database_host'] ?? $host);
            $port = (string)($p['database_port'] ?? $port ?: '3306');
            $name = (string)($p['database_name'] ?? $name);
            $user = (string)($p['database_user'] ?? $user);
            $pass = (string)($p['database_password'] ?? $pass);
            $prefix = (string)($p['database_prefix'] ?? $prefix);
        }
    }

    return [
        'host' => $host,
        'port' => $port ?: '3306',
        'name' => $name,
        'user' => $user,
        'pass' => $pass,
        'prefix' => $prefix,
    ];
}

function connectDb(array $cfg): PDO
{
    $dsn = sprintf('mysql:host=%s;port=%s;dbname=%s;charset=utf8mb4', $cfg['host'], $cfg['port'], $cfg['name']);
    return new PDO($dsn, $cfg['user'], $cfg['pass'], [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);
}

function imageSubdir(int $idImage): string
{
    return IMG_BASE_DIR . '/' . implode('/', str_split((string)$idImage));
}

function ensureDir(string $dir): void
{
    if (!is_dir($dir) && !@mkdir($dir, 0775, true) && !is_dir($dir)) {
        throw new RuntimeException('Cannot create directory: ' . $dir);
    }
}

/**
 * Tworzy warianty rozmiarowe JPEG (proporcje 3:4, przyciecie od gory ze wzgledu na sylwetke).
 * Zwraca tablice [typ => sciezka_docelowa] wlaczajac '__orig__' => '{dir}/{id}.jpg'.
 */
function renderProductImageVariants(string $rawBytes, int $idImage, array $types): ?array
{
    $src = @imagecreatefromstring($rawBytes);
    if ($src === false) {
        return null;
    }

    $srcW = imagesx($src);
    $srcH = imagesy($src);
    if ($srcW < 40 || $srcH < 40) {
        imagedestroy($src);
        return null;
    }

    $dir = imageSubdir($idImage);
    ensureDir($dir);

    $generated = [];

    // Wyliczenie najwiekszego rozmiaru jako bazowego dla oryginalu {id}.jpg
    $maxW = 600;
    $maxH = 800;
    foreach ($types as [$tw, $th]) {
        if ($tw > $maxW) {
            $maxW = $tw;
            $maxH = $th;
        }
    }

    $renderSize = static function ($sourceImg, int $sw, int $sh, int $dw, int $dh, string $destPath): bool {
        $srcRatio = $sw / $sh;
        $dstRatio = $dw / $dh;

        if ($srcRatio > $dstRatio) {
            $cropH = $sh;
            $cropW = max(1, (int)round($sh * $dstRatio));
            $cropX = max(0, (int)round(($sw - $cropW) / 2));
            $cropY = 0;
        } else {
            $cropW = $sw;
            $cropH = max(1, (int)round($sw / $dstRatio));
            $cropX = 0;
            // Lekki offset od gory (10%), aby zachowac glowe modelki na zdjeciach fashion
            $cropY = max(0, (int)round(($sh - $cropH) * 0.10));
        }

        $dst = imagecreatetruecolor($dw, $dh);
        if ($dst === false) {
            return false;
        }
        $bg = imagecolorallocate($dst, 248, 246, 244);
        imagefill($dst, 0, 0, $bg);
        imagealphablending($dst, true);
        imagecopyresampled($dst, $sourceImg, 0, 0, $cropX, $cropY, $dw, $dh, $cropW, $cropH);
        imageinterlace($dst, true);
        $ok = imagejpeg($dst, $destPath, 88);
        imagedestroy($dst);
        return $ok;
    };

    $origPath = $dir . '/' . $idImage . '.jpg';
    if ($renderSize($src, $srcW, $srcH, $maxW, $maxH, $origPath)) {
        $generated['__orig__'] = $origPath;
    }

    foreach ($types as $typeName => [$tw, $th]) {
        $destPath = $dir . '/' . $idImage . '-' . $typeName . '.jpg';
        if ($renderSize($src, $srcW, $srcH, (int)$tw, (int)$th, $destPath)) {
            $generated[$typeName] = $destPath;
        }
    }

    imagedestroy($src);
    return count($generated) > 0 ? $generated : null;
}

function linkOrCopy(string $src, string $dst): bool
{
    if ($src === $dst || !is_file($src)) {
        return false;
    }
    if (is_file($dst)) {
        @unlink($dst);
    }
    if (@link($src, $dst)) {
        return true;
    }
    return @copy($src, $dst);
}

function createPlaceholderVariants(array $types): void
{
    $makePlaceholder = static function (int $w, int $h, string $path): void {
        if (is_file($path)) {
            return;
        }
        $img = imagecreatetruecolor($w, $h);
        if ($img === false) {
            return;
        }
        $bg = imagecolorallocate($img, 245, 243, 240);
        $border = imagecolorallocate($img, 232, 228, 223);
        $accent = imagecolorallocate($img, 180, 174, 168);
        imagefill($img, 0, 0, $bg);
        imagerectangle($img, 0, 0, $w - 1, $h - 1, $border);
        if ($w >= 200) {
            imagestring($img, 3, max(10, (int)(($w - 72) / 2)), (int)($h / 2) - 8, 'MOSQUITO', $accent);
        }
        imagejpeg($img, $path, 85);
        imagedestroy($img);
    };

    ensureDir(IMG_BASE_DIR);
    foreach (['pl', 'en'] as $iso) {
        $makePlaceholder(600, 800, IMG_BASE_DIR . "/{$iso}.jpg");
        foreach ($types as $typeName => [$tw, $th]) {
            $makePlaceholder((int)$tw, (int)$th, IMG_BASE_DIR . "/{$iso}-default-{$typeName}.jpg");
        }
    }
    foreach ($types as $typeName => [$tw, $th]) {
        $makePlaceholder((int)$tw, (int)$th, IMG_BASE_DIR . "/default-{$typeName}.jpg");
    }
}

function fetchUrlsBatch(array $urlMap, int $concurrency = 16): array
{
    if (!function_exists('curl_multi_init') || count($urlMap) === 0) {
        return [];
    }

    $results = [];
    $chunks = array_chunk($urlMap, $concurrency, true);

    foreach ($chunks as $chunk) {
        $mh = curl_multi_init();
        $handles = [];
        foreach ($chunk as $key => $url) {
            $ch = curl_init($url);
            if ($ch === false) {
                continue;
            }
            curl_setopt_array($ch, [
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_FOLLOWLOCATION => true,
                CURLOPT_MAXREDIRS      => 4,
                CURLOPT_CONNECTTIMEOUT => 3,
                CURLOPT_TIMEOUT        => 7,
                CURLOPT_SSL_VERIFYPEER => true,
                CURLOPT_USERAGENT      => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                CURLOPT_HTTPHEADER     => ['Accept: image/avif,image/webp,image/apng,image/jpeg,*/*;q=0.8'],
            ]);
            curl_multi_add_handle($mh, $ch);
            $handles[$key] = $ch;
        }

        do {
            $status = curl_multi_exec($mh, $active);
            if ($active) {
                curl_multi_select($mh, 0.25);
            }
        } while ($active && $status === CURLM_OK);

        foreach ($handles as $key => $ch) {
            $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
            $body = curl_multi_getcontent($ch);
            if ($code >= 200 && $code < 300 && is_string($body) && strlen($body) > 1024) {
                $results[$key] = $body;
            }
            curl_multi_remove_handle($mh, $ch);
            curl_close($ch);
        }
        curl_multi_close($mh);
    }

    return $results;
}

// --- Glowny przebieg ---
try {
    $cfg = loadDbConfig();
    $pdo = connectDb($cfg);
    $p = $cfg['prefix'];

    // Pobranie rozmiarow obrazkow z bazy (fallback do $DEFAULT_TYPES)
    $types = $DEFAULT_TYPES;
    $stmtTypes = $pdo->query("SELECT name, width, height FROM `{$p}image_type` WHERE products = 1");
    $dbTypes = $stmtTypes ? $stmtTypes->fetchAll() : [];
    if (count($dbTypes) > 0) {
        $types = [];
        foreach ($dbTypes as $row) {
            $types[(string)$row['name']] = [(int)$row['width'], (int)$row['height']];
        }
    }

    createPlaceholderVariants($types);

    // Pobranie wszystkich obrazkow produktowych z DB
    $allImages = $pdo->query("
        SELECT i.id_image, i.id_product, i.position, IFNULL(i.cover, 0) AS cover, p.reference
        FROM `{$p}image` i
        JOIN `{$p}product` p ON p.id_product = i.id_product
        ORDER BY i.id_product ASC, IFNULL(i.cover, 0) DESC, i.position ASC, i.id_image ASC
    ")->fetchAll();

    $imagesByProduct = [];
    $imagesByRef = [];
    foreach ($allImages as $row) {
        $pid = (int)$row['id_product'];
        $iid = (int)$row['id_image'];
        $ref = trim((string)($row['reference'] ?? ''));
        $imagesByProduct[$pid][] = $iid;
        if ($ref !== '') {
            $imagesByRef[$ref][] = $iid;
        }
    }

    $seededPool = [];   // lista wygenerowanych map [typ => path] do dalszego fallbacku
    $seededImageIds = [];

    // KROK A: Lokalne zdjecia referencyjne z scraper-results/images (/tmp/sample-images)
    $localSeedCount = 0;
    if (is_dir(SAMPLE_DIR)) {
        $files = glob(SAMPLE_DIR . '/*.{jpg,jpeg,JPG,JPEG,png,PNG,webp,WEBP}', GLOB_BRACE) ?: [];
        sort($files);
        foreach ($files as $file) {
            $base = pathinfo($file, PATHINFO_FILENAME);
            if (preg_match('/^(.+)_(\d+)$/', $base, $m)) {
                $ref = $m[1];
                $idx = max(0, (int)$m[2] - 1);
            } else {
                $ref = $base;
                $idx = 0;
            }

            $bytes = @file_get_contents($file);
            if ($bytes === false || strlen($bytes) < 512) {
                continue;
            }

            if (isset($imagesByRef[$ref][$idx])) {
                $targetId = (int)$imagesByRef[$ref][$idx];
                $variants = renderProductImageVariants($bytes, $targetId, $types);
                if ($variants !== null) {
                    $seededImageIds[$targetId] = true;
                    $seededPool[] = $variants;
                    $localSeedCount++;
                }
            }
        }
    }
    echo "[seed-images] Krok A (lokalne zdjecia): {$localSeedCount} obrazkow.\n";

    // KROK B: Pobieranie zdjec z products.json dla strony glownej i top kategorii
    $remoteAttempted = 0;
    $remoteSucceeded = 0;
    if (is_file(PRODUCTS_JSON)) {
        $jsonRaw = @file_get_contents(PRODUCTS_JSON);
        $productsData = is_string($jsonRaw) ? json_decode($jsonRaw, true) : null;
        if (is_array($productsData)) {
            $urlsByRef = [];
            foreach ($productsData as $item) {
                if (!is_array($item)) {
                    continue;
                }
                $extId = trim((string)($item['external_id'] ?? ''));
                $imgUrls = $item['image_urls'] ?? [];
                if ($extId !== '' && is_array($imgUrls) && count($imgUrls) > 0) {
                    $urlsByRef[$extId] = $imgUrls;
                }
            }

            $priorityProductIds = [];
            $addIds = static function (array $ids) use (&$priorityProductIds): void {
                foreach ($ids as $id) {
                    $priorityProductIds[(int)$id] = true;
                }
            };

            // 1. Produkty ze strony glownej (id_category = 2)
            $addIds($pdo->query("
                SELECT DISTINCT p.id_product
                FROM `{$p}product` p
                LEFT JOIN `{$p}category_product` cp ON cp.id_product = p.id_product
                WHERE p.active = 1 AND (p.id_category_default = 2 OR cp.id_category = 2)
                LIMIT 24
            ")->fetchAll(PDO::FETCH_COLUMN));

            // 2. 20 najnowszych produktow
            $addIds($pdo->query("
                SELECT id_product FROM `{$p}product` WHERE active = 1 ORDER BY id_product DESC LIMIT 20
            ")->fetchAll(PDO::FETCH_COLUMN));

            // 3. Produkty przecenione (Promocje)
            $addIds($pdo->query("
                SELECT DISTINCT id_product FROM `{$p}specific_price` LIMIT 20
            ")->fetchAll(PDO::FETCH_COLUMN));

            // 4. Pierwsze 12 produktow kazdej kategorii z menu gornego
            foreach ([32, 11, 15, 20, 17, 13, 12, 29] as $catId) {
                $stmtCat = $pdo->prepare("
                    SELECT DISTINCT cp.id_product
                    FROM `{$p}category_product` cp
                    JOIN `{$p}product` p ON p.id_product = cp.id_product
                    WHERE cp.id_category = ? AND p.active = 1
                    ORDER BY cp.position ASC, cp.id_product DESC
                    LIMIT 12
                ");
                $stmtCat->execute([$catId]);
                $addIds($stmtCat->fetchAll(PDO::FETCH_COLUMN));
            }

            // Mapowanie id_image -> URL (bez nadpisywania juz zaseedowanych z Kroku A)
            $downloadQueue = [];
            $refStmt = $pdo->prepare("SELECT id_product, reference FROM `{$p}product` WHERE id_product = ?");
            foreach (array_keys($priorityProductIds) as $pid) {
                if (empty($imagesByProduct[$pid])) {
                    continue;
                }
                $refStmt->execute([$pid]);
                $row = $refStmt->fetch();
                $ref = trim((string)($row['reference'] ?? ''));
                if ($ref === '' || empty($urlsByRef[$ref])) {
                    continue;
                }
                // Zdjecie okladkowe [0] dla wszystkich priorytetowych produktow
                $coverImgId = (int)$imagesByProduct[$pid][0];
                if (!isset($seededImageIds[$coverImgId]) && !empty($urlsByRef[$ref][0])) {
                    $downloadQueue[$coverImgId] = (string)$urlsByRef[$ref][0];
                }
                if (count($downloadQueue) >= 120) {
                    break;
                }
            }

            $remoteAttempted = count($downloadQueue);
            if ($remoteAttempted > 0) {
                $downloaded = fetchUrlsBatch($downloadQueue, 16);
                foreach ($downloaded as $iid => $bytes) {
                    $variants = renderProductImageVariants($bytes, (int)$iid, $types);
                    if ($variants !== null) {
                        $seededImageIds[(int)$iid] = true;
                        $seededPool[] = $variants;
                        $remoteSucceeded++;
                    }
                }
            }
        }
    }
    echo "[seed-images] Krok B (pobieranie zdjec): {$remoteSucceeded}/{$remoteAttempted} obrazkow.\n";

    // KROK C: Uzupelnienie pozostalych brakujacych obrazkow na dysku twardym przez hardlinki do puli 3:4
    $poolCount = count($seededPool);
    $fallbackCount = 0;
    if ($poolCount > 0) {
        foreach ($allImages as $row) {
            $iid = (int)$row['id_image'];
            $dir = imageSubdir($iid);
            $homePath = $dir . '/' . $iid . '-home_default.jpg';
            if (isset($seededImageIds[$iid]) && is_file($homePath)) {
                continue;
            }
            if (is_file($homePath) && is_file($dir . '/' . $iid . '.jpg')) {
                continue;
            }

            $template = $seededPool[$iid % $poolCount];
            ensureDir($dir);
            if (isset($template['__orig__'])) {
                linkOrCopy($template['__orig__'], $dir . '/' . $iid . '.jpg');
            }
            foreach ($types as $typeName => $_dims) {
                if (isset($template[$typeName])) {
                    linkOrCopy($template[$typeName], $dir . '/' . $iid . '-' . $typeName . '.jpg');
                }
            }
            $fallbackCount++;
        }
    }
    echo "[seed-images] Krok C (fallback puli 3:4): uzupelniono {$fallbackCount} obrazkow produktowych.\n";

} catch (Throwable $e) {
    fwrite(STDERR, '[seed-images] ERROR: ' . $e->getMessage() . "\n");
    exit(1);
}
