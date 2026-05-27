@echo off
chcp 65001 >nul
echo ============================================================
echo    四川农业大学研究生毕业晚会 - 投票系统
echo ============================================================
echo.

:: Kill any existing process on port 3000
echo [1/2] 正在启动投票系统...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000" ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

:: Start the Flask app
start "Vote System" "C:\Users\DELL\AppData\Local\Programs\Python\Python314\python.exe" "D:\Desktop\vote-app\app.py"

echo.
echo  ╔════════════════════════════════════════════════╗
echo  ║    投票系统已启动！                           ║
echo  ║                                              ║
echo  ║  本机投票:  http://localhost:3000             ║
echo  ║  管理后台:  http://localhost:3000/admin       ║
echo  ║                                              ║
echo  ║  ★ ★ ★  重要提示  ★ ★ ★                    ║
echo  ║  线上观众投票需要用内网穿透工具               ║
echo  ║  推荐 natapp (国内速度快):                    ║
echo  ║  1. 访问 https://natapp.cn 注册并下载         ║
echo  ║  2. 运行: natapp -authtoken=你的token -port=3000║
echo  ║  3. 获得公网地址后打开管理后台                ║
echo  ║     管理后台内的二维码会自动更新为公网地址     ║
echo  ╚════════════════════════════════════════════════╝
echo.
echo 按任意键退出系统...
pause >nul

:: Kill the server on exit
taskkill /F /FI "WINDOWTITLE eq Vote System" >nul 2>&1
echo 系统已关闭。
