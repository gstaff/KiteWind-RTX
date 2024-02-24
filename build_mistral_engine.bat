@echo off

@REM Confirm before starting
set /p userInput=This will install the build dependencies and build a TensorRT-LLM engine for Mistral-7B-Instruct; it may take ~15 minutes and require 50 GB of free disk space. Press any key to proceed.

@REM Check if python executable is available
where python > nul 2>&1
if %errorlevel% neq 0 (
    echo Python 3.10 is not installed. Install it and ensure it is present on your PATH then try again.
    pause
    exit /b 1
)

@REM Get Python version
for /f "tokens=2 delims= " %%v in ('python -V 2^>^&1') do set pythonVersion=%%v

@REM Check if the major version is 3 and the minor version is 10
echo %pythonVersion% | findstr /r /c:"^3\.10\." > nul
if %errorlevel% equ 0 (
    echo Python 3.10 is installed.
) else (
    echo Python version %pythonVersion% is installed, but it's not Python 3.10. This may still work if it is 3.11+ but if there are failures retry with Python 3.10.
)


@REM Get TensorRT-LLM version ready for building
git clone https://github.com/gstaff/TensorRT-LLM.git

@REM Get Mistral-7B-instruct model definition files
git clone https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-AWQ

@REM Move to models dir
move .\Mistral-7B-Instruct-v0.2-AWQ .\TensorRT-LLM\examples\llama\models

@REM Get 4-bit AWQ weights pre-quantized by NVIDIA
git clone https://huggingface.co/gstaff/Mistral-7B-Instruct-v0.1-AWQ

@REM Move to weights dir
move .\Mistral-7B-Instruct-v0.1-AWQ .\TensorRT-LLM\examples\llama\weights

@REM Enter builder root directory
cd .\TensorRT-LLM

@REM Create and activate a new venv
python -m venv venv
call venv\Scripts\activate

echo Virtual environment activated.

@REM Check if the user is in a virtual environment
if not defined VIRTUAL_ENV (
    echo Error: You are not in a virtual environment.
    echo Please activate your virtual environment and run this script again.
    pause
    exit /b 1
)

@REM Install packages for the venv
python -m pip install --upgrade pip
python -m pip install nvidia-cudnn-cu11==8.9.4.25 --no-cache-dir
python -m pip install --pre --extra-index-url https://pypi.nvidia.com/ tensorrt==9.0.1.post11.dev4 --no-cache-dir
python -m pip uninstall -y nvidia-cudnn-cu11
python -m pip install tensorrt_llm --extra-index-url https://pypi.nvidia.com --extra-index-url https://download.pytorch.org/whl/cu121

@REM Enter the build directory
cd .\examples\llama

@REM Run the build script; this can take ~4 minutes using CPU
python build.py --model_dir ".\models\Mistral-7B-Instruct-v0.2-AWQ" --quant_ckpt_path .\weights\Mistral-7B-Instruct-v0.1-AWQ\mistral_tp1_rank0.npz --dtype float16 --use_gpt_attention_plugin float16 --use_gemm_plugin float16 --use_weight_only --weight_only_precision int4_awq --per_group --enable_context_fmha --max_batch_size 1 --max_input_len 3000 --max_output_len 1024 --output_dir .\mistral_engines

echo THIS IS A TEST OF THE ENGINE

@REM If successful the output will be in mistral_engines
python run.py --max_output_len=50 --tokenizer_dir ".\models\Mistral-7B-Instruct-v0.2-AWQ" --engine_dir=".\mistral_engines"

echo IF THE OUTPUT ABOVE LOOKS GOOD THE ENGINE FILES ARE READY

@REM Copy the engine out to the project root dir
xcopy ".\mistral_engines" "..\..\..\engines\Mistral-7B-Instruct-v0.2" /E /I /Y

@REM Pause for status before exiting
set /p userInput=The build has completed, you can find your TensorRT engine files in "engines\Mistral-7B-Instruct-v0.2"; press any key to exit.