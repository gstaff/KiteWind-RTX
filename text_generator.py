# SPDX-FileCopyrightText: Copyright (c) 2022-2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import argparse
import csv
import json
from pathlib import Path
from typing import Union

import numpy as np
import torch
from transformers import LlamaTokenizerFast

import tensorrt_llm
from tensorrt_llm.quantization import QuantMode
from tensorrt_llm.runtime import ModelConfig, SamplingConfig

# from build import get_engine_name  # isort:skip

EOS_TOKEN = 2
PAD_TOKEN = 2


def throttle_generator(generator, stream_interval):
    for i, out in enumerate(generator):
        if not i % stream_interval:
            yield out

    if i % stream_interval:
        yield out


def read_config(config_path: Path):
    with open(config_path, 'r') as f:
        config = json.load(f)
    use_gpt_attention_plugin = config['plugin_config']['gpt_attention_plugin']
    remove_input_padding = config['plugin_config']['remove_input_padding']
    dtype = config['builder_config']['precision']
    gather_all_token_logits = config['builder_config'][
        'gather_all_token_logits']
    tp_size = config['builder_config']['tensor_parallel']
    pp_size = config['builder_config']['pipeline_parallel']
    world_size = tp_size * pp_size
    assert world_size == tensorrt_llm.mpi_world_size(), \
        f'Engine world size ({world_size}) != Runtime world size ({tensorrt_llm.mpi_world_size()})'
    num_heads = config['builder_config']['num_heads']
    hidden_size = config['builder_config']['hidden_size']
    vocab_size = config['builder_config']['vocab_size']
    num_layers = config['builder_config']['num_layers']
    num_kv_heads = config['builder_config'].get('num_kv_heads', num_heads)
    paged_kv_cache = config['plugin_config']['paged_kv_cache']
    tokens_per_block = config['plugin_config']['tokens_per_block']
    quant_mode = QuantMode(config['builder_config']['quant_mode'])
    if config['builder_config'].get('multi_query_mode', False):
        tensorrt_llm.logger.warning(
            "`multi_query_mode` config is deprecated. Please rebuild the engine."
        )
        num_kv_heads = 1
    num_kv_heads = (num_kv_heads + tp_size - 1) // tp_size
    assert (num_heads % tp_size) == 0
    num_heads = num_heads // tp_size
    hidden_size = hidden_size // tp_size
    use_custom_all_reduce = config['plugin_config'].get('use_custom_all_reduce',
                                                        False)
    max_prompt_embedding_table_size = config['builder_config'].get(
        'max_prompt_embedding_table_size', 0)

    model_config = ModelConfig(
        num_heads=num_heads,
        num_kv_heads=num_kv_heads,
        hidden_size=hidden_size,
        vocab_size=vocab_size,
        num_layers=num_layers,
        gpt_attention_plugin=use_gpt_attention_plugin,
        paged_kv_cache=paged_kv_cache,
        tokens_per_block=tokens_per_block,
        remove_input_padding=remove_input_padding,
        dtype=dtype,
        quant_mode=quant_mode,
        gather_all_token_logits=gather_all_token_logits,
        use_custom_all_reduce=use_custom_all_reduce,
        max_prompt_embedding_table_size=max_prompt_embedding_table_size)

    return model_config, tp_size, pp_size, dtype


def parse_input(input_text: str, input_file: str, tokenizer, end_id: int,
                remove_input_padding: bool, input_tokens_limit: Union[int,
        None]):
    input_tokens = []
    if input_file is None:
        input_tokens.append(
            tokenizer.encode(input_text, add_special_tokens=False))
    else:
        if input_file.endswith('.csv'):
            with open(input_file, 'r') as csv_file:
                csv_reader = csv.reader(csv_file, delimiter=',')
                for line in csv_reader:
                    input_tokens.append(np.array(line, dtype='int32'))
        elif input_file.endswith('.npy'):
            inputs = np.load(input_file)
            for row in inputs:
                row = row[row != end_id]
                input_tokens.append(row)
        elif input_file.endswith('.txt'):
            with open(input_file, 'r', encoding='utf-8',
                      errors='replace') as txt_file:
                input_text = txt_file.read()
                input_tokens.append(
                    tokenizer.encode(input_text, add_special_tokens=False))
        else:
            print('Input file format not supported.')
            raise SystemExit

    # Cap max input tokens
    if input_tokens_limit is not None:
        print(
            f"Maximum input number of tokens found as {max([len(x) for x in input_tokens])};"
            f" will be capped to {input_tokens_limit}")
        input_tokens = [x[-input_tokens_limit:] for x in input_tokens]

    input_ids = None
    input_lengths = torch.tensor([len(x) for x in input_tokens],
                                 dtype=torch.int32,
                                 device='cuda')
    if remove_input_padding:
        input_ids = np.concatenate(input_tokens)
        input_ids = torch.tensor(input_ids, dtype=torch.int32,
                                 device='cuda').unsqueeze(0)
    else:
        input_ids = torch.nested.to_padded_tensor(
            torch.nested.nested_tensor(input_tokens, dtype=torch.int32),
            end_id).cuda()

    return input_ids, input_lengths


def ptuning_setup(prompt_table, dtype, hidden_size, tasks, input_ids,
                  input_lengths, remove_input_padding):
    if prompt_table is not None:
        prompt_table = torch.from_numpy(np.load(prompt_table))
        task_vocab_size = torch.tensor([prompt_table.shape[1]],
                                       dtype=torch.int32,
                                       device="cuda")
        prompt_table = prompt_table.view(
            (prompt_table.shape[0] * prompt_table.shape[1],
             prompt_table.shape[2]))
        prompt_table = prompt_table.cuda().to(
            dtype=tensorrt_llm._utils.str_dtype_to_torch(dtype))
    else:
        prompt_table = torch.empty([1, hidden_size]).cuda()
        task_vocab_size = torch.zeros([1]).cuda()

    num_sequences = input_lengths.size(
        0) if remove_input_padding else input_ids.size(0)

    if tasks is not None:
        tasks = torch.tensor([int(t) for t in tasks.split(',')],
                             dtype=torch.int32,
                             device="cuda")
        assert tasks.shape[
                   0] == num_sequences, "Number of supplied tasks must match input batch size"
    else:
        tasks = torch.zeros([num_sequences]).cuda()

    return [prompt_table, tasks, task_vocab_size]


def print_output(output_ids, input_lengths, max_output_len, tokenizer,
                 output_csv, output_npy, sequence_lengths):
    num_beams = output_ids.size(1)
    if output_csv is None and output_npy is None:
        for b in range(input_lengths.size(0)):
            inputs = output_ids[b][0][:input_lengths[b]].tolist()
            input_text = tokenizer.decode(inputs)
            # print(f'Input: \"{input_text}\"')
            for beam in range(num_beams):
                output_begin = input_lengths[b]
                output_length = sequence_lengths[b][beam] - input_lengths[b]
                output_end = input_lengths[b] + output_length
                outputs = output_ids[b][beam][output_begin:output_end].tolist()
                output_text = tokenizer.decode(outputs)
                # print(f'Output: \"{output_text}\"')
                return output_text

    output_ids = output_ids.reshape((-1, output_ids.size(2)))

    if output_csv is not None:
        output_file = Path(output_csv)
        output_file.parent.mkdir(exist_ok=True, parents=True)
        outputs = output_ids.tolist()
        with open(output_file, 'w') as csv_file:
            writer = csv.writer(csv_file, delimiter=',')
            writer.writerows(outputs)

    if output_npy is not None:
        output_file = Path(output_npy)
        output_file.parent.mkdir(exist_ok=True, parents=True)
        outputs = np.array(output_ids.cpu().contiguous(), dtype='int32')
        np.save(output_file, outputs)


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max_output_len', type=int)
    parser.add_argument('--max_kv_cache_len',
                        type=int,
                        default=None,
                        help='The max kv cache length. \
              If the final sequence length exceeds the kv cache length, we will enable cyclic kv cache. \
              If it is set to None, we will use the max sequence length.')
    parser.add_argument('--log_level', type=str, default='error')
    parser.add_argument('--engine_dir', type=str, default='llama_outputs')
    parser.add_argument('--tokenizer_dir',
                        type=str,
                        default=".",
                        help="Directory containing the tokenizer.model.")
    parser.add_argument('--input_text',
                        type=str,
                        default='Born in north-east France, Soyer trained as a')
    parser.add_argument(
        '--input_tokens',
        dest='input_file',
        type=str,
        help=
        'CSV or Numpy file containing tokenized input. Alternative to text input.',
        default=None)
    parser.add_argument(
        '--input_tokens_limit',
        type=int,
        help='Truncate input tokens if number exceeds the set limit value',
        default=None)
    parser.add_argument('--output_csv',
                        type=str,
                        help='CSV file where the tokenized output is stored.',
                        default=None)
    parser.add_argument('--output_npy',
                        type=str,
                        help='Numpy file where the tokenized output is stored.',
                        default=None)
    parser.add_argument('--num_beams',
                        type=int,
                        help="Use beam search if num_beams >1",
                        default=1)
    parser.add_argument('--streaming', default=False, action='store_true')
    parser.add_argument('--streaming_interval',
                        type=int,
                        help="How often to return tokens when streaming.",
                        default=5)
    parser.add_argument(
        '--prompt_table',
        type=Path,
        help="Path to .npy file, exported by nemo_prompt_convert.py")
    parser.add_argument(
        '--tasks',
        help="Comma-separated list of tasks for prompt tuning: ex 0,3,1,0")
    return parser.parse_args()


def template_input(user_input):
    template = f"""<s>[INST] {user_input} [/INST]"""
    return template


class TensorRTLLMGenerator:

    def __init__(self, input_file, tokenizer, model_config, input_tokens_limit, decoder, max_output_len,
                 num_beams, prompt_table, dtype, tasks, sampling_config, streaming, streaming_interval, runtime_rank,
                 output_csv, output_npy, runtime_mapping):
        self.input_file = input_file
        self.tokenizer = tokenizer
        self.model_config = model_config
        self.input_tokens_limit = input_tokens_limit
        self.decoder = decoder
        self.max_output_len = max_output_len
        self.num_beams = num_beams
        self.prompt_table = prompt_table
        self.dtype = dtype
        self.tasks = tasks
        self.sampling_config = sampling_config
        self.streaming = streaming
        self.streaming_interval = streaming_interval
        self.runtime_rank = runtime_rank
        self.output_csv = output_csv
        self.output_npy = output_npy
        self.runtime_mapping = runtime_mapping

    def generate(self, input_text):
        # input_text = self.input_text
        input_file = self.input_file
        tokenizer = self.tokenizer
        model_config = self.model_config
        input_tokens_limit = self.input_tokens_limit
        decoder = self.decoder
        max_output_len = self.max_output_len
        num_beams = self.num_beams
        prompt_table = self.prompt_table
        dtype = self.dtype
        tasks = self.tasks
        sampling_config = self.sampling_config
        streaming = self.streaming
        streaming_interval = self.streaming_interval
        runtime_rank = self.runtime_rank
        output_csv = self.output_csv
        output_npy = self.output_npy
        runtime_mapping = self.runtime_mapping

        input_ids, input_lengths = parse_input(
            template_input(input_text),
            input_file,
            tokenizer,
            EOS_TOKEN,
            model_config.remove_input_padding,
            input_tokens_limit=input_tokens_limit)

        max_input_length = torch.max(input_lengths).item()
        decoder.setup(input_lengths.size(0),
                      max_input_length,
                      max_output_len,
                      num_beams)
        # max_kv_cache_length=max_kv_cache_len)

        ptuning_args = [] if model_config.max_prompt_embedding_table_size == 0 else ptuning_setup(
            prompt_table, dtype, model_config.hidden_size, tasks, input_ids,
            input_lengths, model_config.remove_input_padding)

        outputs = decoder.decode(input_ids,
                                 input_lengths,
                                 sampling_config,
                                 *ptuning_args,
                                 streaming=streaming,
                                 output_sequence_lengths=True,
                                 return_dict=True)
        torch.cuda.synchronize()
        if streaming:
            for outputs_dict in throttle_generator(outputs, streaming_interval):
                if runtime_rank == 0:
                    output_ids = outputs_dict['output_ids']
                    sequence_lengths = outputs_dict['sequence_lengths']
                    return print_output(output_ids, input_lengths, max_output_len,
                                       tokenizer, output_csv, output_npy,
                                       sequence_lengths)
        else:
            if runtime_rank == 0:
                output_ids = outputs['output_ids']
                sequence_lengths = outputs['sequence_lengths']
                return print_output(output_ids, input_lengths, max_output_len, tokenizer,
                                    output_csv, output_npy, sequence_lengths)

            if model_config.gather_all_token_logits:
                if runtime_mapping.is_last_pp_rank():
                    print(
                        f"context_logits.shape: {outputs['context_logits'].shape}")
                    print(
                        f"generation_logits.shape: {len(outputs['generation_logits']), outputs['generation_logits'][0].shape}"
                    )
                    print(outputs['context_logits'])
                    print(outputs['generation_logits'])


def build_generator(
        max_output_len: int,
        log_level: str = 'error',
        engine_dir: str = 'llama_outputs',
        input_text: str = 'Born in north-east France, Soyer trained as a',
        input_file: str = None,
        output_csv: str = None,
        output_npy: str = None,
        tokenizer_dir: str = None,
        max_kv_cache_len: int = None,
        num_beams: int = 1,
        streaming: bool = False,
        streaming_interval: int = 5,
        prompt_table: Path = None,
        tasks: str = None,
        input_tokens_limit: Union[None, int] = None,
):
    tensorrt_llm.logger.set_level(log_level)

    engine_dir = Path(engine_dir)
    config_path = engine_dir / 'config.json'
    model_config, tp_size, pp_size, dtype = read_config(config_path)
    world_size = tp_size * pp_size

    runtime_rank = tensorrt_llm.mpi_rank()
    runtime_mapping = tensorrt_llm.Mapping(world_size,
                                           runtime_rank,
                                           tp_size=tp_size,
                                           pp_size=pp_size)
    torch.cuda.set_device(runtime_rank % runtime_mapping.gpus_per_node)

    tokenizer = LlamaTokenizerFast.from_pretrained(tokenizer_dir, legacy=False)

    sampling_config = SamplingConfig(end_id=EOS_TOKEN,
                                     pad_id=PAD_TOKEN,
                                     num_beams=num_beams)

    # engine_name = get_engine_name('llama', dtype, tp_size, pp_size,
    #                               runtime_rank)
    engine_name = "llama_float16_tp1_rank0.engine"
    serialize_path = engine_dir / engine_name
    with open(serialize_path, 'rb') as f:
        engine_buffer = f.read()
    decoder = tensorrt_llm.runtime.GenerationSession(model_config,
                                                     engine_buffer,
                                                     runtime_mapping,
                                                     debug_mode=False,
                                                     debug_tensors_to_save=None)
    if runtime_rank == 0:
        print(f"Running the {dtype} engine ...")

    generator = TensorRTLLMGenerator(input_file, tokenizer, model_config, input_tokens_limit, decoder, max_output_len,
                                     num_beams, prompt_table, dtype, tasks, sampling_config, streaming,
                                     streaming_interval, runtime_rank, output_csv, output_npy, runtime_mapping)
    return generator


def init_generator(max_output_len=512, tokenizer_dir=r".\tokenizers\\Mistral-7B-Instruct-v0.2",
                   engine_dir=r".\engines\Mistral-7B-Instruct-v0.2", streaming=True):
    args = parse_arguments()
    args.max_output_len = max_output_len
    args.tokenizer_dir = tokenizer_dir
    args.engine_dir = engine_dir
    args.streaming = streaming
    generator = build_generator(**vars(args))
    return generator

# Sample command to run from this dir (cd examples llama)
# python run_echo.py --max_output_len=512 --tokenizer_dir ".\tokenizers\Mistral-7B-Instruct-v0.2" --engine_dir=".\engines\Mistral-7B-Instruct-v0.2" --streaming
