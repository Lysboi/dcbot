@echo off
title NoceBOT
:start
python bot.py
echo Bot kapandi veya hata olustu! 3 saniye icinde yeniden baslatiliyor...
timeout /t 3 /nobreak
goto start 