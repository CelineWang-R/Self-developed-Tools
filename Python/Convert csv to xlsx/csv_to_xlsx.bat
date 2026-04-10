@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo CSV to XLSX Converter
echo Folder: %~dp0
echo ==========================================
echo.

set "OUTDIR=%~dp0result_xlsx"
if not exist "%OUTDIR%" mkdir "%OUTDIR%"

set "LOGFILE=%~dp0conversion_log.txt"
set "PYFILE=%TEMP%\csv_to_xlsx_%RANDOM%%RANDOM%.py"

set "PYTHON_CMD="
where python >nul 2>nul && set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
    where py >nul 2>nul && set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
    echo [ERROR] Python 3 was not found.
    echo Install Python 3, then run this again.
    echo. > "%LOGFILE%"
    echo [ERROR] Python 3 was not found.>> "%LOGFILE%"
    pause
    exit /b 1
)

for /f "tokens=1 delims=:" %%A in ('findstr /n /b /c:"#PYTHON_CODE_START" "%~f0"') do set "PYLINE=%%A"

if not defined PYLINE (
    echo [ERROR] Could not find embedded Python code.
    > "%LOGFILE%" echo [ERROR] Could not find embedded Python code.
    pause
    exit /b 1
)

more +%PYLINE% "%~f0" > "%PYFILE%"

echo Running conversion...
echo Output folder: "%OUTDIR%"
echo Log file: "%LOGFILE%"
echo.

call %PYTHON_CMD% "%PYFILE%" > "%LOGFILE%" 2>&1
set "EXITCODE=%ERRORLEVEL%"

type "%LOGFILE%"
echo.

del "%PYFILE%" >nul 2>nul

if "%EXITCODE%"=="0" (
    echo Success! All CSV files were converted to XLSX.
    echo Files are in the "result_xlsx" folder.
) else if "%EXITCODE%"=="2" (
    echo No CSV files were found in this folder.
) else (
    echo Finished with errors.
    echo Please check conversion_log.txt for details.
)

echo.
pause
exit /b %EXITCODE%

#PYTHON_CODE_START
import csv
import sys
import subprocess
from pathlib import Path

def ensure_openpyxl():
    try:
        import openpyxl  # noqa: F401
        return True
    except ImportError:
        print("openpyxl not found. Trying to install it...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
            return True
        except Exception as e:
            print("Could not install openpyxl:", e)
            return False

def open_csv_with_fallback(path):
    encodings = ["utf-8-sig", "utf-8", "cp932", "mbcs", "latin-1"]
    last_error = None
    for enc in encodings:
        try:
            f = path.open("r", encoding=enc, newline="")
            return f, enc
        except Exception as e:
            last_error = e
    raise last_error

if not ensure_openpyxl():
    sys.exit(1)

from openpyxl import Workbook

base = Path.cwd()
outdir = base / "result_xlsx"
outdir.mkdir(exist_ok=True)

csv_files = sorted([p for p in base.glob("*.csv") if p.is_file()])

if not csv_files:
    print("No CSV files were found in this folder.")
    sys.exit(2)

converted = 0
failed = []

for csv_file in csv_files:
    try:
        fh, used_encoding = open_csv_with_fallback(csv_file)
        with fh:
            reader = csv.reader(fh)
            wb = Workbook()
            ws = wb.active
            ws.title = "Sheet1"
            for row in reader:
                ws.append(row)

        out_file = outdir / (csv_file.stem + ".xlsx")
        wb.save(out_file)
        converted += 1
        print(f"Converted: {csv_file.name} -> {out_file.name} [{used_encoding}]")
    except Exception as e:
        failed.append((csv_file.name, str(e)))
        print(f"Failed: {csv_file.name} | {e}")

print()
print("----------------------------------------")
print(f"CSV files found        : {len(csv_files)}")
print(f"Converted successfully : {converted}")
print(f"Failed                 : {len(failed)}")

if failed:
    print()
    print("Failed files:")
    for name, err in failed:
        print(f" - {name}: {err}")
    sys.exit(1)

sys.exit(0)