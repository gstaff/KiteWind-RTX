@echo off

rem Confirm before starting
set /p userInput=This will install the dependencies for KiteWind-RTX in the local python venv, creating one if needed, press any key to proceed.

rem Check if python executable is available
where python > nul 2>&1
if %errorlevel% neq 0 (
    echo Python 3.10 is not installed. Install it and ensure it is present on your PATH then try again.
    pause
    exit /b 1
)

rem Get Python version
for /f "tokens=2 delims= " %%v in ('python -V 2^>^&1') do set pythonVersion=%%v

rem Check if the major version is 3 and the minor version is 10
echo %pythonVersion% | findstr /r /c:"^3\.10\." > nul
if %errorlevel% equ 0 (
    echo Python 3.10 is installed.
) else (
    echo Python version %pythonVersion% is installed, but it's not Python 3.10. This may still work if it is 3.11+ but if there are failures retry with Python 3.10.
)

rem Check if CUDA 12.2 is installed
set "cudaToolkitPath=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.2"

if exist "%cudaToolkitPath%\bin\nvcc.exe" (
    echo CUDA 12.2 is installed.
) else (
    echo CUDA 12.2 is not found. You can install using the instructions here: https://github.com/NVIDIA/TensorRT-LLM/tree/main/windows#cuda
)

rem Check if the virtual environment exists, if not, create it
if not exist venv (
    echo No existing venv found, will create a venv in local folder "venv"
    python -m venv venv
)

rem Activate the virtual environment (you may need to adjust this based on your OS)
call venv\Scripts\activate

rem Continue with other commands...

echo Virtual environment activated.

rem Check if the user is in a virtual environment
if not defined VIRTUAL_ENV (
    echo Error: You are not in a virtual environment.
    echo Please activate your virtual environment and run this script again.
    pause
    exit /b 1
)

rem Install dependencies using pip
python -m pip install --upgrade pip
python -m pip install nvidia-cudnn-cu11==8.9.4.25 --no-cache-dir
python -m pip install --pre --extra-index-url https://pypi.nvidia.com/ tensorrt==9.0.1.post11.dev4 --no-cache-dir
python -m pip uninstall -y nvidia-cudnn-cu11
python -m pip install tensorrt_llm --extra-index-url https://pypi.nvidia.com --extra-index-url https://download.pytorch.org/whl/cu121
python -m pip install accelerate gradio==4.11.0 pynvml


echo Dependencies installed successfully. Press any key to close this install script.
pause
exit /b 0