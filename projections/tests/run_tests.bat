@echo off
REM Wrapper script to run pytest in the correct environment
echo ==================================================
echo NeuroGlobe Test Runner
echo ==================================================
echo.

REM Check if conda is available
where conda >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Conda not found in PATH. Please install Anaconda/Miniconda.
    exit /b 1
)

REM Set working directory to project root (one level up from this script)
pushd "%~dp0.."

echo Activating 'allensdk' environment and running tests...
call conda run -n allensdk pytest %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FAILURE] Tests failed. See output above.
    popd
    exit /b %ERRORLEVEL%
)

popd
echo.
echo [SUCCESS] All tests passed!
