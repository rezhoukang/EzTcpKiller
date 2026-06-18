@echo off
chcp 65001 >nul
title EzTcpKiller 打包脚本

echo ============================================
echo   EzTcpKiller — PyInstaller 打包脚本
echo ============================================
echo.

:: 检查 PyInstaller
pyinstaller --version >nul 2>&1 || pip install pyinstaller

:: 清理旧构建
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del /q "*.spec"

:: 打包
pyinstaller -F -w main.py

echo.
echo ============================================
echo   ✓ 打包成功！
echo   输出文件：dist\main.exe
echo ============================================
pause
