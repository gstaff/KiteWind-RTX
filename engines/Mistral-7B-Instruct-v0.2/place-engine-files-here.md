# Engine Files Directory
The engine files you built with TensorRT for your machine should be placed in this folder.

## Files
When you built the Mistral engine you should have generated 3 files with the following names:
- `config.json` - A small config file with details of the engine build.
- `llama_float16_tp1_rank0.engine` - A ~4 GB file containing the compiled engine with the expected settings
  - Keep the `llama` naming; mistral shares the common builder config
- `model.cache` - A small cache file

Place those in this directory.