# ─────────────────────────────────────────────────────────────────
# Script: importar_patrones.ps1
# Extrae patrones de aprendizaje de todas las planillas conciliadas
# y los sube al sistema para mejorar el match automatico.
#
# Uso: clic derecho → "Ejecutar con PowerShell"
# ─────────────────────────────────────────────────────────────────

$API_URL = "https://conciliacion-api.onrender.com"
$EMAIL   = "julietaarrazate@gmail.com"
$PWD_KEY = Read-Host "Ingresa tu contrasena para conectar al sistema"

Write-Host "`n[1/4] Conectando al sistema..."

# Login
try {
    $loginBody = @{ email=$EMAIL; password=$PWD_KEY } | ConvertTo-Json
    $loginResp = Invoke-RestMethod -Uri "$API_URL/auth/login" -Method POST `
        -ContentType "application/json" -Body $loginBody
    $token = $loginResp.access_token
    Write-Host "OK Conectado como $($loginResp.user.full_name)"
} catch {
    Write-Host "ERROR al conectar: $_"
    Read-Host "Presiona Enter para salir"
    exit
}

$headers = @{ Authorization = "Bearer $token" }

Write-Host "`n[2/4] Abriendo Excel..."
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false

$BASE_DIR = "$env:USERPROFILE\Desktop\Clientes\tt"
$archivos = Get-ChildItem -Path $BASE_DIR -Filter "*.xlsx" -Recurse |
    Where-Object { $_.FullName -notmatch "\\[Vv]arios\\" }

Write-Host "[3/4] Procesando $($archivos.Count) archivos..."

$todos_patrones = @()
$procesados = 0
$errores = 0

foreach ($archivo in $archivos) {
    # Extraer nombre del cliente del path (carpeta inmediatamente dentro de tt)
    $rel = $archivo.FullName.Substring($BASE_DIR.Length).TrimStart("\")
    $cliente = ($rel -split "\\")[0]

    try {
        $wb = $excel.Workbooks.Open($archivo.FullName)
        $ws = $wb.Sheets.Item(1)
        $maxRow = $ws.UsedRange.Rows.Count
        $maxCol = [Math]::Min($ws.UsedRange.Columns.Count, 12)

        for ($r = 1; $r -le $maxRow; $r++) {
            # Buscar "ok" en cualquier columna de esta fila
            $tieneOk = $false
            $titular = ""
            $cuit    = ""
            $monto   = 0.0

            $celdas = @()
            for ($c = 1; $c -le $maxCol; $c++) {
                $celdas += $ws.Cells.Item($r,$c).Text
            }

            # Verificar si hay "ok" en la fila
            $tieneOk = $celdas | Where-Object { $_.Trim().ToLower() -eq "ok" }
            if (-not $tieneOk) { continue }

            # Extraer datos de la fila
            foreach ($celda in $celdas) {
                $s = $celda.Trim()

                # Detectar CUIT (10-11 digitos, con o sin guiones)
                if (-not $cuit -and $s -match '^\$?\s*\d[\d\-\.]{8,12}\d\s*$') {
                    $numeros = $s -replace '[^\d]',''
                    if ($numeros.Length -ge 10 -and $numeros.Length -le 11) {
                        $cuit = $numeros
                    }
                }

                # Detectar monto (empieza con $, tiene . y ,)
                if (-not $monto -and $s -match '^\$') {
                    $montoStr = $s -replace '[\$\s\.]','' -replace ',','.'
                    $parsed = 0.0
                    if ([double]::TryParse($montoStr, [ref]$parsed) -and $parsed -gt 100) {
                        $monto = $parsed
                    }
                }

                # Detectar titular (texto largo, solo letras y espacios)
                if (-not $titular -and $s.Length -gt 5 -and $s -match '^[A-Za-zÀ-ɏ\s\.]+$' -and $s -notmatch '^\d') {
                    if ($s -notmatch '^(ok|mp|bancor|galicia|santander|macro|uala|naranja|nacion|modo|mercadopago)$') {
                        $titular = $s
                    }
                }
            }

            if ($titular -or $cuit) {
                $todos_patrones += @{
                    cliente  = $cliente
                    titular  = $titular
                    cuit     = $cuit
                    monto    = $monto
                }
            }
        }

        $wb.Close($false)
        $procesados++

        if ($procesados % 50 -eq 0) {
            Write-Host "  Procesados: $procesados/$($archivos.Count) archivos, $($todos_patrones.Count) patrones extraidos..."
        }
    } catch {
        $errores++
        try { $wb.Close($false) } catch {}
    }
}

$excel.Quit()

Write-Host "`n[4/4] Subiendo $($todos_patrones.Count) patrones al sistema..."

# Enviar en lotes de 200
$loteSize = 200
$subidos  = 0
for ($i = 0; $i -lt $todos_patrones.Count; $i += $loteSize) {
    $lote = $todos_patrones[$i..([Math]::Min($i + $loteSize - 1, $todos_patrones.Count - 1))]
    $body = @{ patrones = $lote } | ConvertTo-Json -Depth 4
    try {
        $resp = Invoke-RestMethod -Uri "$API_URL/auditoria/patrones/importar-historico" `
            -Method POST -ContentType "application/json" -Body $body -Headers $headers
        $subidos += $resp.creados + $resp.actualizados
        Write-Host "  Lote $([Math]::Ceiling($i/$loteSize)+1): $($resp.creados) creados, $($resp.actualizados) actualizados"
    } catch {
        Write-Host "  Error en lote: $_"
    }
}

Write-Host "`n=== COMPLETADO ==="
Write-Host "Archivos procesados : $procesados"
Write-Host "Errores             : $errores"
Write-Host "Patrones subidos    : $subidos"
Write-Host "`nEl sistema ahora reconoce los clientes historicos de Caneland."
Write-Host "Mañana cuando concilies el extracto nuevo, el match va a ser mucho mejor."
Read-Host "`nPresiona Enter para cerrar"
