@echo off
title GitHub Push - NoceBOT

echo GitHub'a yukleme islemi basliyor...
echo.

REM Git repo kontrolu
if not exist .git (
    echo Git repository olusturuluyor...
    git init
    echo.
)

REM Dosyalari staging area'ya ekle
echo Dosyalar ekleniyor...
git add .
echo.

REM Commit mesaji al
set /p commit_message=Commit mesajini girin: 

REM Commit olustur
echo.
echo Commit olusturuluyor...
git commit -m "%commit_message%"
echo.

REM Remote kontrol et ve ekle
git remote -v | findstr "origin" > nul
if errorlevel 1 (
    set /p repo_url=GitHub repository URL'sini girin: 
    git remote add origin %repo_url%
)

REM Push islemi
echo.
echo GitHub'a yukleniyor...
git push -u origin master
echo.

echo Islem tamamlandi!
echo.

pause 