# Prepare a fresh local read-only QMT instance. Start the generated service separately.
param(
    [Parameter(Mandatory=$true)][string]$Root,
    [Parameter(Mandatory=$true)][string]$QmtTerminal,
    [Parameter(Mandatory=$true)][string]$HostPython,
    [Parameter(Mandatory=$true)][string]$WtPythonw,
    [Parameter(Mandatory=$true)][string]$License,
    [Parameter(Mandatory=$true)][string]$SdkManifest,
    [ValidateRange(1024,65535)][int]$Port = 18159,
    [ValidateRange(0.1,60)][double]$ReconnectSeconds = 0.2,
    [ValidatePattern('^[A-Za-z0-9_]+$')][string]$StrategyName = 'GH_WT_MEMORY_VERIFY',
    [string]$MarketProfile,
    [switch]$Synthetic
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $Root) {
    throw 'Root must be a new directory.'
}
foreach ($file in @($QmtTerminal, $HostPython, $WtPythonw, $License, $SdkManifest)) {
    if (-not [IO.Path]::IsPathRooted($file) -or -not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "Expected an existing absolute file path: $file"
    }
}
if ($MarketProfile -and
    (-not [IO.Path]::IsPathRooted($MarketProfile) -or -not (Test-Path -LiteralPath $MarketProfile -PathType Leaf))) {
    throw 'MarketProfile must be an existing absolute JSON file path.'
}
function Get-Sha([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Save-Json([string]$Path, $Value) {
    [IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 30), [Text.UTF8Encoding]::new($false))
}
function New-SecretHex {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
}
if ((Get-Sha $License) -ne 'b9a6d9320b8f2693e8d41e496ce56caadacaddcca9be2a64a61749278f425cf2') {
    throw 'CPython license SHA256 does not match the repository.'
}
$examples = Join-Path (Split-Path -Parent $PSScriptRoot) 'connectors/qmt_shm/examples'
$terminalPath = (Get-Item -LiteralPath $QmtTerminal).FullName
$terminal = @(Get-Process -Name ([IO.Path]::GetFileNameWithoutExtension($terminalPath)) |
    Where-Object Path -eq $terminalPath)
if ($terminal.Count -ne 1 -or $terminal[0].SessionId -ne (Get-Process -Id $PID).SessionId) {
    throw 'Use the same Windows session as exactly one selected QMT terminal.'
}
if ($Synthetic) {
    $accountId = 'SYNTHETIC'
} else {
    $secure = Read-Host 'Enter the stock account ID shown in QMT' -AsSecureString
    $accountId = [Net.NetworkCredential]::new('', $secure).Password.Trim()
    $secure.Dispose()
    if ([string]::IsNullOrWhiteSpace($accountId)) { throw 'The account ID is required.' }
}
$instanceId = [Guid]::NewGuid().ToString()
$tag = $instanceId.Substring(0, 8)
& $HostPython -I -B -c 'import sys; from guanheng_qmt_shm.private_files import create_private_control_directory; create_private_control_directory(sys.argv[1], inherit=True)' $Root
if ($LASTEXITCODE -ne 0) { throw 'Use a new private root with an existing ordinary parent on a local fixed Windows volume with persistent ACLs.' }
$Root = (Get-Item -LiteralPath $Root).FullName
$hostControl = Join-Path $Root 'host-control'
$wtControl = Join-Path $Root 'wt-control'
$generations = Join-Path $Root 'generations'
$currentRoot = Join-Path $Root 'current'
foreach ($dir in @($hostControl, $wtControl, $generations, $currentRoot)) {
    New-Item -ItemType Directory -Path $dir | Out-Null
}
$policy = Join-Path $Root 'qmt-operation-policy.json'
Copy-Item -LiteralPath (Join-Path $examples 'qmt-operation-policy.example.json') -Destination $policy
$sdk = Join-Path $Root 'qmt-memory-sdk.json'
Copy-Item -LiteralPath $SdkManifest -Destination $sdk

$config = Get-Content -Raw -LiteralPath (Join-Path $examples 'qmt-trade-config.example.json') | ConvertFrom-Json
$config.trade_binding.account_id = $AccountId
$config.trade_binding.binding_id = "qmt-$tag"
$config.trade_binding.strategy_name = $StrategyName
$config.operation_profiles.'account.trade_detail'.limits.account_binding.account_id = $AccountId
$config.route.route_id = "qmt-$tag"
$config.route.executor_id = "wt-$tag"
$config.transport.name = "qmt-broker-$tag"
$config.transport.windows_session_id = $terminal[0].SessionId
$config.listen_host = '127.0.0.1'
$config.listen_port = $Port
$config.http_key_id = "qmt-$tag"
$config.journal_path = Join-Path $Root 'communication.sqlite'
$config.operation_policies_path = $policy
$config.writes_enabled = $false
if (Compare-Object @('account.trade_detail') @($config.read_operations)) {
    throw 'The supplied template must declare only the account read operation.'
}
$configPath = Join-Path $Root 'qmt-trade-config.json'
Save-Json $configPath $config
$digest = & $HostPython -I -B -c "import sys,json,hashlib; from pathlib import Path; from guanheng_qmt_shm_agent.protocol import canonical; c=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')); print(hashlib.sha256(canonical(c['trade_binding'])).hexdigest())" $configPath
if ($LASTEXITCODE -ne 0 -or $digest -notmatch '^[a-f0-9]{64}$') { throw 'Cannot compute binding SHA256.' }
$config.trade_profile.binding_sha256 = $digest
Save-Json $configPath $config

$pair = Join-Path $Root 'pair'
$oldIpc = [Environment]::GetEnvironmentVariable($config.ipc_secret_env, 'Process')
$oldHttp = [Environment]::GetEnvironmentVariable($config.http_secret_env, 'Process')
try {
    [Environment]::SetEnvironmentVariable($config.ipc_secret_env, (New-SecretHex), 'Process')
    [Environment]::SetEnvironmentVariable($config.http_secret_env, (New-SecretHex), 'Process')
    if ($MarketProfile) {
        & $HostPython -I -B (Join-Path $PSScriptRoot 'qmt_readonly_market.py') prepare --account-config $configPath `
            --profile $MarketProfile --sdk-manifest $sdk --stdlib-license $License --reconnect-seconds $ReconnectSeconds --output $pair
    } else {
        & $HostPython -I -B -m guanheng_qmt_shm.trade_cli pair --config $configPath --memory-sdk-manifest $sdk --stdlib-license $License --reconnect-seconds $ReconnectSeconds --source-mode strategy_tick --output $pair
    }
    if ($LASTEXITCODE -ne 0) { throw 'Pair generation failed.' }
} finally {
    [Environment]::SetEnvironmentVariable($config.ipc_secret_env, $oldIpc, 'Process')
    [Environment]::SetEnvironmentVariable($config.http_secret_env, $oldHttp, 'Process')
}

$manifestPath = Join-Path $pair 'manifest.json'
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
# Market preparation verifies the completed source before publishing companion materials.
if (!$MarketProfile) {
    & $HostPython -I -B -m guanheng_qmt_shm.trade_cli verify --directory $pair --installed-agent $manifest.agent_package
    if ($LASTEXITCODE -ne 0) { throw 'Pair verification failed.' }
}

$descriptor = Join-Path $Root 'trade-host.json'
Save-Json $descriptor @{
    schema = 'qmt.trade-host-process.v1'
    pythonw = $manifest.host_python
    pythonw_sha256 = $manifest.host_python_sha256
    pair_directory = $pair
    pair_manifest_sha256 = Get-Sha $manifestPath
    installed_agent = $manifest.agent_package
    control_root = $hostControl
    startup_seconds = 60
    stop_seconds = 45
    max_output_bytes = 1048576
}
$runtime = Join-Path $Root 'runtime.json'
Save-Json $runtime @{
    schema = 'guanheng.wt-runtime.v1'
    instance_id = $instanceId
    startup_seconds = 90
    stop_seconds = 60
    components = @{
        trade_host = @{ kind = 'qmt_trade'; descriptor = $descriptor; sha256 = Get-Sha $descriptor }
    }
}
$environment = Join-Path $Root 'environment.json'
Save-Json $environment @{ GUANHENG_QMT_INSTANCE_ID = $instanceId }
Save-Json (Join-Path $Root 'service.json') @{
    schema = 'guanheng.wt-service.v1'
    pythonw = $WtPythonw
    pythonw_sha256 = Get-Sha $WtPythonw
    bootstrap_configuration = $runtime
    bootstrap_configuration_sha256 = Get-Sha $runtime
    control_root = $wtControl
    generation_root = $generations
    current_file = Join-Path $currentRoot 'CURRENT.json'
    environment_file = $environment
    environment_sha256 = Get-Sha $environment
}
if ($Synthetic) { Write-Output 'Synthetic account: use these outputs for offline validation only.' }
Write-Output "WT service: $(Join-Path $Root 'service.json')"
Write-Output "QMT script: $(Join-Path $pair 'strategy.py')"
