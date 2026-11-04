@echo off
chcp 65001 >nul
title Cath Unhas - Inicializador
cd /d "%~dp0"
echo ========================================
echo           CATH UNHAS
echo ========================================
where py >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale Python 3.11+ em https://www.python.org/downloads/
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  echo Criando ambiente virtual...
  py -m venv .venv
  if errorlevel 1 (echo Falha ao criar ambiente virtual.& pause & exit /b 1)
)
echo Instalando/atualizando dependencias...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo Nao foi possivel instalar Flask. Verifique sua conexao com a internet.
  pause
  exit /b 1
)
echo Iniciando Cath Unhas...
echo Acesse: http://127.0.0.1:5000
echo Painel: http://127.0.0.1:5000/login
echo Login inicial: admin  ^| Senha: admin123
echo Para encerrar, pressione CTRL+C nesta janela.
.venv\Scripts\python.exe app.py
pause
