@echo off
rem Builds "PvZ Horror English.exe" into source\dist\  (needs Python 3.10 64-bit)
cd /d "%~dp0"
python -m pip install -r requirements.txt || goto :error
python -m PyInstaller --noconfirm --onefile --noconsole --name "PvZ Horror English" --icon app.ico ^
  --add-data "data;data" --add-data "translator.js;." --add-data "dict_code.json;." --add-data "fingerprint.json;." ^
  --collect-all UnityPy --collect-all fmod_toolkit --collect-all texture2ddecoder --collect-all etcpak ^
  --collect-all astc_encoder --collect-all archspec --collect-all frida ^
  --exclude-module cv2 --exclude-module matplotlib --exclude-module PyInstaller ^
  pvz_english_app.py || goto :error
echo.
echo Done: %~dp0dist\PvZ Horror English.exe
exit /b 0
:error
echo.
echo Build failed.
exit /b 1
