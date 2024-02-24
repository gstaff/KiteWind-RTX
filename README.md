# KiteWind-RTX 🪁🍃
<h4>KiteWind-RTX is a chat-assisted web app creator powered by TensorRT-LLM</h4>

## Features
- Create lightweight apps in the browser with gradio-lite or stlite (streamlit)!
- Develop using text or voice AI assistance powered by the blazing fast NVIDIA TensorRT-LLM and Mistral-7B-Instruct-v0.2!
- Export as a standalone HTML file or copy a snippet to use in another webpage!

## System Requirements
### Hardware
#### GPU
This app uses NVIDIA TensorRT-LLM which requires an NVIDIA graphics card (GPU) with RTX support:
- 30 series cards e.g. NVIDIA GeForce RTX 3080, NVIDIA GeForce RTX 3090
- 40 series cards e.g. NVIDIA GeForce RTX 4080, NVIDIA GeForce RTX 4090

This app has also only been tested on cards with 12 GB of VRAM.
It can likely run on 8 GB cards as well.

#### RAM
Building the TensorRT-LLM engine may require at least 32 GB of RAM.

#### Disk Space
This app takes ~14 GB when dependencies are installed and the LLM engine files are included. The build dependencies for the LLM engine files take ~50 GB on disk but can be removed once the ~4 GB engine file is built.

#### Voice Input
You will need a microphone or other audio input device to interact via the voice button.

### OS
This app has only tested for Windows 11 machines.

### Browser
The app UI has only been tested on Chrome; other browsers may or may not be supported.

## Setup
### Prerequisites
#### System Software
This application uses NVIDIA TensorRT-LLM which has the following dependencies on Windows:
- Git for Windows
- Python 3.10
- CUDA 12.2
- Microsoft MPI
- cuDNN


Follow the steps here to install those on your machine: 
https://github.com/NVIDIA/TensorRT-LLM/tree/main/windows#quick-start

Summarizing:
1. Install [Git for Windows](https://git-scm.com/download/win) if you don't have it
2. `git clone https://github.com/NVIDIA/TensorRT-LLM.git`
3. From Powershell as Administrator in `TensorRT-LLM\windows`: `./setup_env.ps1` (skipping any dependencies already present)
4. Install cuDNN using installer at https://developer.nvidia.com/cudnn-downloads?target_os=Windows&target_arch=x86_64&target_version=10&target_type=exe_local
5. Add these CUDNN paths to your "Path" [System Environment Variable](https://www.howtogeek.com/787217/how-to-edit-environment-variables-on-windows-10-or-11/#:~:text=In%20the%20System%20Properties%20window,%2C%20and%20click%20%22OK.%22)
   1. `C:\Program Files\NVIDIA\CUDNN\v9.0\bin`
   2. `C:\Program Files\NVIDIA\CUDNN\v9.0\lib`


#### Building the TensorRT-LLM Engine
You will need to compile a LLM engine specific to your hardware.

If you already have the 3 engine files for your system place them in `.\engines\Mistral-7B-Instruct-v0.2`

Otherwise run `.\build_mistral_engine.bat`

The build dependencies will be installed under `.\TensorRT-LLM` and the engine files will be copied to `.\engines\Mistral-7B-Instruct-v0.2`

Note that the build process will take ~15-20 minutes and consume ~50 GB of disk space. Once you have a working engine for your system you can delete the engine build dependencies by deleting `.\TensorRT-LLM`

If the build script fails for you see the "Troubleshooting TensorRT-LLM Engine Build" section below.

### Installation
Install dependencies by running `.\install_dependencies.bat`

### Running the App
Run `.\run.bat` once dependencies are installed; the app will open in a browser tab.

## Current Limitations
- Only gradio-lite and stlite (streamlit) apps using libraries avialable for [pyodide](https://pyodide.org/en/stable/) are supported.
- The chat hasn't been fine-tuned on gradio or streamlit library data; it may make mistakes.

## Troubleshooting the TensorRT-LLM Engine Build

There are many steps to the engine build process

Read the commented commands in `.\build_mistral_engine.bat` and see the manual steps below for additional guidance:
1. Clone the Mistral model code to use as `model_dir`: `git clone https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.2/tree/main`
2. Download the 4-bit AWQ quantized models to use as `quant_ckpt_path` from NVIDIA here: https://catalog.ngc.nvidia.com/orgs/nvidia/models/mistral-7b-int4-chat/files?version=1.1
3. `git clone https://github.com/NVIDIA/TensorRT-LLM.git`
   1. You can reuse this from the previous step
4. Create a new venv in the repo if one doesn't exist with `python -m venv venv`
5. Activate the venv with `call venv\Scripts\activate`
6. Checkout the last supported tag for building engines on Windows with `git checkout tags/v0.6.1`
7. Install the `tensorrt_llm` package with `pip install tensorrt_llm --extra-index-url https://pypi.nvidia.com --extra-index-url https://download.pytorch.org/whl/cu121`
   1. You can verify it installed with `python -c "import tensorrt_llm; print(tensorrt_llm._utils.trt_version())"`
8. I needed to modify line 1188 of `examples\llama\weight.py` to `awq_llama = torch.load(quant_ckpt_path, map_location='cpu')` so the engine would build using my 32 GB RAM rather than my 12 GB VRAM.
9. I also needed to comment out line 333 of `examples\llama\run.py` as `max_kv_cache_length` was not recognized.
10. `cd examples\llama`
11. Finally try building with `python build.py --model_dir "C:\Users\<some>\<path>\TensorRTInstall\Mistral-7B-Instruct-v0.2" --quant_ckpt_path .\weights\quantized_int4-awq\mistral_tp1_rank0.npz --dtype float16 --use_gpt_attention_plugin float16 --use_gemm_plugin float16 --use_weight_only --weight_only_precision int4_awq --per_group --enable_context_fmha --max_batch_size 1 --max_input_len 3000 --max_output_len 1024 --output_dir .\mistral_engines`
    1. Sub in your paths from steps 1 and 2 for `model_dir` and `quant_ckpt_path`
12. If you get an error about `ModuleNotFoundError: No module named 'tensorrt_bindings'` try this running this fix from https://github.com/NVIDIA/Stable-Diffusion-WebUI-TensorRT/issues/27#issuecomment-1767570566
```bash
python -m pip install --upgrade pip
python -m pip install nvidia-cudnn-cu11==8.9.4.25 --no-cache-dir
python -m pip install --pre --extra-index-url https://pypi.nvidia.com/ tensorrt==9.0.1.post11.dev4 --no-cache-dir
python -m pip uninstall -y nvidia-cudnn-cu11
python -m pip install tensorrt_llm --extra-index-url https://pypi.nvidia.com --extra-index-url https://download.pytorch.org/whl/cu121
```
Then try to build again. A clean build may take at least 4 minutes using CPU.

13. If you see the 3 output files in `mistral_engines` then test to confirm the LLM engine is working with `python run.py --max_output_len=50 --tokenizer_dir "C:\Users\<some>\<path>\TensorRTInstall\Mistral-7B-Instruct-v0.2" --engine_dir=".\mistral_engines"`
    1. This should output some text about "Born in north-east France, Soyer trained as a..."
14. Once the engine files are generated place them in `.\engines\Mistral-7B-Instruct-v0.2` in this project
    1. There should be 3 files with these names
       - `config.json` - A small config file with details of the engine build.
       - `llama_float16_tp1_rank0.engine` - A ~4 GB file containing the compiled engine with the expected settings
         - Keep the `llama` naming; mistral shares the common builder config
       - `model.cache` - A small cache file