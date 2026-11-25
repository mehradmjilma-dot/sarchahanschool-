@echo off
cd /d "%~dp0"
echo ==== Step 1: installing build tools (needs internet, one time only) ====
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

set ICON=
if exist app.ico set ICON=--icon app.ico

echo ==== Step 2: building the program ====
python -m PyInstaller --noconfirm --clean --windowed --name SarchahanSchool --paths school_server --hidden-import uvicorn.lifespan.off --hidden-import uvicorn.loops.asyncio --hidden-import uvicorn.protocols.http.h11_impl --hidden-import h11 %ICON% school_app.py
if errorlevel 1 goto :error

echo.
echo ==== DONE ====
echo The program folder is: dist\SarchahanSchool
echo Test it by running dist\SarchahanSchool\SarchahanSchool.exe
echo Then open installer.iss with Inno Setup and press Compile (F9) to make the Setup file.
pause
exit /b 0

:error
echo.
echo ==== BUILD FAILED. Read the messages above. ====
pause
exit /b 1
