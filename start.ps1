# ============================================================
# 多 Agent 系统一键启动脚本
# 使用方法：在 PowerShell 中直接双击或运行 .\start.ps1
# ============================================================

$dir = "D:\Multiple Ai Cooperating Operation System"

# ── 步骤 1：启动 One-API ────────────────────────────────────
Write-Host "▶ [1/3] 启动 One-API..." -ForegroundColor Cyan
$oneapi = Get-Process "one-api" -ErrorAction SilentlyContinue
if ($oneapi) {
    Write-Host "   One-API 已在运行，跳过启动" -ForegroundColor Yellow
} else {
    Start-Process -FilePath "$dir\one-api.exe" -WindowStyle Minimized
    Write-Host "   等待 One-API 初始化（3 秒）..."
    Start-Sleep -Seconds 3
}

# ── 步骤 2：在新窗口启动 MCP 服务器 ───────────────────────
Write-Host "▶ [2/3] 启动 MCP 文件服务器..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$dir'; " +
    "Write-Host '[MCP] 正在激活虚拟环境...' -ForegroundColor Green; " +
    ".\venv\Scripts\Activate.ps1; " +
    "Write-Host '[MCP] 服务器启动中，保持此窗口开启' -ForegroundColor Green; " +
    "npx -y @modelcontextprotocol/server-filesystem '$dir\workspace'"
)
Write-Host "   等待 MCP 服务器就绪（4 秒）..."
Start-Sleep -Seconds 4

# ── 步骤 3：在当前窗口运行主程序 ──────────────────────────
Write-Host "▶ [3/3] 启动主程序..." -ForegroundColor Cyan
Set-Location $dir
& ".\venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "════════════════════════════════════════" -ForegroundColor Green
Write-Host "  多 Agent 系统已就绪，在 >>> 后输入指令  " -ForegroundColor Green
Write-Host "════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
python main.py
