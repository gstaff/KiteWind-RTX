import logging
import re
import time
import typing
import warnings
from pathlib import Path

import gradio as gr
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline, Pipeline

from templates import starting_app_code, update_iframe_js, copy_snippet_js, download_code_js, load_js, DemoType, \
    copy_share_link_js
from text_generator import init_generator, TensorRTLLMGenerator

# Filter the UserWarning raised by the audio component.
warnings.filterwarnings("ignore", message='Trying to convert audio automatically from int32 to 16-bit int format')

logging.basicConfig(
    level=logging.INFO,  # Set the logging level to INFO or any other desired level
    format="%(asctime)s - %(message)s",  # Define the log message format
    datefmt="%Y-%m-%d %H:%M:%S",  # Define the timestamp format
)

logger = logging.getLogger("my_logger")


def init_llm() -> TensorRTLLMGenerator:
    print("Initializing LLM...")
    start = time.time()
    llm = init_generator(streaming=False)
    end = time.time()
    print(f"LLM initialized in {end - start:.2f} seconds")
    return llm


def init_speech_to_text_model() -> Pipeline:
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

    model_id = "distil-whisper/distil-medium.en"
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_id, torch_dtype=torch_dtype, use_safetensors=True
    )
    model.to(device)
    processor = AutoProcessor.from_pretrained(model_id)
    return pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        max_new_tokens=128,
        torch_dtype=torch_dtype,
        device=device,
    )


rtx_generator = init_llm()
whisper_pipe = init_speech_to_text_model()

code_pattern = re.compile(r'```python\n(.*?)```', re.DOTALL)


def generate_text(code: str, prompt: str) -> (str, str, str):
    logger.info(f"Calling API with prompt:\n{prompt}")
    prompt = f"```python\n{code}```\nGiven the code above return only updated code for the following request:\n{prompt}\n"
    start_time = time.time()
    assistant_reply = rtx_generator.generate(prompt)
    end_time = time.time()
    print(f'LLM GENERATED RESPONSE IN {end_time - start_time:.2f} seconds\n{assistant_reply}')
    logger.info(f'LLM RESPONSE\n{assistant_reply}')
    match = re.search(code_pattern, assistant_reply)
    if not match:
        return assistant_reply, code, None
    new_code = match.group(1)
    logger.info(f'NEW CODE:\nnew_code')
    return assistant_reply, new_code, None


def transcribe(audio: str) -> (str, str):
    start = time.time()
    result = whisper_pipe(audio)
    end = time.time()
    print(f"TRANSCRIBED AUDIO IN {end - start:.2f} seconds")
    return result["text"], None


def link_copy_notify(code: str, requirements: str):
    gr.Info("Share link copied!")


def copy_notify(code: str, requirements: str):
    gr.Info("App code snippet copied!")


def add_hotkeys() -> str:
    return Path("hotkeys.js").read_text()


def apply_query_params(request: gr.Request) -> ([str], str, [str], str, typing.Any):
    params = dict(request.query_params)
    demo_type = params.get('type')
    if demo_type == 'gradio':
        return [params.get('code') or starting_app_code(DemoType.GRADIO)], params.get('requirements') or '', [
            starting_app_code(
                DemoType.STREAMLIT)], '', gr.Tabs(selected=0)
    if demo_type == 'streamlit':
        return [starting_app_code(DemoType.GRADIO)], '', [
            params.get('code') or starting_app_code(DemoType.STREAMLIT)], params.get('requirements') or '', gr.Tabs(
            selected=1)
    return [params.get('code') or starting_app_code(DemoType.GRADIO)], params.get('requirements') or '', [
        starting_app_code(DemoType.STREAMLIT)], '', gr.Tabs(
        selected=0)


def update_state(code: str, requirements: [str], error: str, history: [str], current_index: int) -> (
        str, str, [str], int):
    # Only modify undo history if new code was added.
    if history[current_index] != code:
        history = history[:current_index + 1]
        history.append(code)
        current_index = len(history) - 1
    return '\n'.join(sorted(requirements)), error, history, current_index


def undo(code: str, history: [str], current_index: int) -> (str, int):
    if current_index > 0:
        current_index -= 1
        return history[current_index], current_index
    return code, current_index


def redo(code: str, history: [str], current_index: int) -> (str, int):
    if current_index < len(history) - 1:
        current_index += 1
        return history[current_index], current_index
    return code, current_index


with gr.Blocks(title="KiteWind") as demo:
    gr.Markdown('<h1 align="center"><a href="https://huggingface.co/spaces/gstaff/KiteWind">KiteWind</a> 🪁🍃</h1>')
    gr.Markdown(
        '<h4 align="center">Chat-assisted web app creator by <a href="https://huggingface.co/gstaff">@gstaff</a></h4>')
    selectedTab = gr.State(value='gradio-lite')
    with gr.Tabs() as tabs:
        with gr.Tab('Gradio (gradio-lite)', id=0) as gradio_lite_tab:
            with gr.Row():
                with gr.Column():
                    gr.Markdown("## 1. Run your app in the browser!")
                    gr.HTML(value='<div id="gradioDemoDiv"></div>')
            gr.Markdown("## 2. Customize using voice requests!")
            with gr.Row():
                with gr.Column():
                    with gr.Group():
                        gradio_audio = gr.Microphone(
                            label="Record a voice request (click or press ctrl + ` to start/stop)",
                            type='filepath', elem_classes=["record-btn"])
                        gradio_prompt = gr.Textbox(label="Or type a text request and press Enter",
                                                   placeholder="Need an idea? Try one of these:\n- Add a button to reverse the name\n- Change the greeting to Spanish\n- Put the reversed name output into a separate textbox")
                    gradio_bot_text = gr.TextArea(label="🤖 Chat Assistant Response")
                    gradio_clear = gr.ClearButton([gradio_prompt, gradio_audio, gradio_bot_text])
                with gr.Column():
                    gradio_code_area = gr.Code(
                        label="App Code - You can also edit directly and then click Update App or ctrl + space",
                        language='python', value=starting_app_code(DemoType.GRADIO), interactive=True)
                    gradio_requirements_area = gr.Code(
                        label="App Requirements (additional modules pip installed for pyodide)", interactive=True)
                    with gr.Group():
                        gradio_update_btn = gr.Button("Update App (Ctrl + Space)", variant="primary",
                                                      elem_classes=["update-btn"])
                        gradio_undo_btn = gr.Button("Undo")
                        gradio_redo_btn = gr.Button("Redo")
                    gradio_error = gr.State()
                    gradio_history = gr.State(value=[])
                    gradio_index = gr.State(value=0)
                    gradio_code_update_params = {'fn': update_state,
                                                 'inputs': [gradio_code_area, gradio_requirements_area, gradio_error,
                                                            gradio_history, gradio_index],
                                                 'outputs': [gradio_requirements_area, gradio_error, gradio_history,
                                                             gradio_index],
                                                 'js': update_iframe_js(DemoType.GRADIO)}
                    gradio_gen_text_params = {'fn': generate_text, 'inputs': [gradio_code_area, gradio_prompt],
                                              'outputs': [gradio_bot_text, gradio_code_area]}
                    gradio_transcribe_params = {'fn': transcribe, 'inputs': [gradio_audio],
                                                'outputs': [gradio_prompt, gradio_audio]}
                    gradio_update_btn.click(**gradio_code_update_params)
                    gradio_undo_btn.click(undo, [gradio_code_area, gradio_history, gradio_index],
                                          [gradio_code_area, gradio_index]).then(**gradio_code_update_params)
                    gradio_redo_btn.click(redo, [gradio_code_area, gradio_history, gradio_index],
                                          [gradio_code_area, gradio_index]).then(**gradio_code_update_params)
                    gradio_prompt.submit(**gradio_gen_text_params).then(**gradio_code_update_params)
                    gradio_audio.stop_recording(**gradio_transcribe_params).then(**gradio_gen_text_params).then(
                        **gradio_code_update_params)
            with gr.Row():
                with gr.Column():
                    gr.Markdown("## 3. Export your app to share!")
                    gradio_share_link_btn = gr.Button("🔗 Copy share link to clipboard")
                    gradio_share_link_btn.click(link_copy_notify, [gradio_code_area, gradio_requirements_area], None,
                                                js=copy_share_link_js(DemoType.GRADIO))
                    gradio_copy_snippet_btn = gr.Button("✂️ Copy app snippet to paste into another page")
                    gradio_copy_snippet_btn.click(copy_notify, [gradio_code_area, gradio_requirements_area], None,
                                                  js=copy_snippet_js(DemoType.GRADIO))
                    gradio_download_btn = gr.Button("🗎 Download app as a standalone file")
                    gradio_download_btn.click(None, [gradio_code_area, gradio_requirements_area], None,
                                              js=download_code_js(DemoType.GRADIO))
            with gr.Row():
                with gr.Column():
                    gr.Markdown("## Current limitations")
                    with gr.Accordion("Click to view", open=False):
                        gr.Markdown(
                            "- Only gradio-lite apps using the libraries available in pyodide are supported\n- The chat hasn't been tuned on gradio library data; it may make mistakes")
        with gr.Tab('Streamlit (stlite)', id=1) as stlite_tab:
            with gr.Row():
                with gr.Column():
                    gr.Markdown("## 1. Run your app in the browser!")
                    gr.HTML(value='<div id="stliteDemoDiv"></div>')
            gr.Markdown("## 2. Customize using voice requests!")
            with gr.Row():
                with gr.Column():
                    with gr.Group():
                        stlite_audio = gr.Microphone(
                            label="Record a voice request (click or press ctrl + ` to start/stop)",
                            type='filepath', elem_classes=["record-btn"])
                        stlite_prompt = gr.Textbox(label="Or type a text request and press Enter",
                                                   placeholder="Need an idea? Try one of these:\n- Add a button to reverse the name\n- Change the greeting to Spanish\n- Change the theme to soft")
                    stlite_bot_text = gr.TextArea(label="🤖 Chat Assistant Response")
                    stlite_clear_btn = gr.ClearButton([stlite_prompt, stlite_audio, stlite_bot_text])
                with gr.Column():
                    stlite_code_area = gr.Code(
                        label="App Code - You can also edit directly and then click Update App or ctrl + space",
                        language='python', value=starting_app_code(DemoType.STREAMLIT), interactive=True)
                    stlite_requirements_area = gr.Code(
                        label="App Requirements (additional modules pip installed for pyodide)", interactive=True)
                    with gr.Group():
                        stlite_update_btn = gr.Button("Update App (Ctrl + Space)", variant="primary",
                                                      elem_classes=["update-btn"])
                        stlite_undo_btn = gr.Button("Undo")
                        stlite_redo_btn = gr.Button("Redo")
                    stlite_error = gr.State()
                    stlite_history = gr.State(value=[])
                    stlite_index = gr.State(value=0)
                    stlite_code_update_params = {'fn': update_state,
                                                 'inputs': [stlite_code_area, stlite_requirements_area, stlite_error,
                                                            stlite_history, stlite_index],
                                                 'outputs': [stlite_requirements_area, stlite_error, stlite_history,
                                                             stlite_index],
                                                 'js': update_iframe_js(DemoType.STREAMLIT)}
                    stlite_gen_text_params = {'fn': generate_text, 'inputs': [stlite_code_area, stlite_prompt],
                                              'outputs': [stlite_bot_text, stlite_code_area]}
                    stlite_transcribe_params = {'fn': transcribe, 'inputs': [stlite_audio],
                                                'outputs': [stlite_prompt, stlite_audio]}
                    stlite_update_btn.click(**stlite_code_update_params)
                    stlite_undo_btn.click(undo, [stlite_code_area, stlite_history, stlite_index],
                                          [stlite_code_area, stlite_index]).then(**stlite_code_update_params)
                    stlite_redo_btn.click(redo, [stlite_code_area, stlite_history, stlite_index],
                                          [stlite_code_area, stlite_index]).then(**stlite_code_update_params)
                    stlite_prompt.submit(**stlite_gen_text_params).then(**stlite_code_update_params)
                    stlite_audio.stop_recording(**stlite_transcribe_params).then(**stlite_gen_text_params).then(
                        **stlite_code_update_params)
            with gr.Row():
                with gr.Column():
                    gr.Markdown("## 3. Export your app to share!")
                    stlite_share_link_btn = gr.Button("🔗 Copy share link to clipboard")
                    stlite_share_link_btn.click(link_copy_notify, [stlite_code_area, stlite_requirements_area], None,
                                                js=copy_share_link_js(DemoType.STREAMLIT))
                    stlite_copy_snippet_btn = gr.Button("✂️ Copy app snippet into paste in another page")
                    stlite_copy_snippet_btn.click(copy_notify, [stlite_code_area, stlite_requirements_area], None,
                                                  js=copy_snippet_js(DemoType.STREAMLIT))
                    stlite_download_btn = gr.Button("🗎 Download app as a standalone file")
                    stlite_download_btn.click(None, [stlite_code_area, stlite_requirements_area], None,
                                              js=download_code_js(DemoType.STREAMLIT))
            with gr.Row():
                with gr.Column():
                    gr.Markdown("## Current limitations")
                    with gr.Accordion("Click to view", open=False):
                        gr.Markdown(
                            "- Only Streamlit apps using libraries available in pyodide are supported\n- The chat hasn't been tuned on Streamlit library data; it may make mistakes")
    gradio_lite_tab.select(lambda: "gradio-lite", None, selectedTab).then(None, None, None,
                                                                          js=load_js(DemoType.GRADIO))
    stlite_tab.select(lambda: "stlite", None, selectedTab).then(None, None, None, js=load_js(DemoType.STREAMLIT))
    demo.load(None, None, None, js=add_hotkeys())
    demo.load(apply_query_params, [],
              [gradio_history, gradio_requirements_area, stlite_history, stlite_requirements_area, tabs]).then(
        lambda x, y: [x[0], y[0]],
        [gradio_history, stlite_history],
        [gradio_code_area, stlite_code_area])
    demo.css = "footer {visibility: hidden}"

if __name__ == "__main__":
    demo.queue().launch(favicon_path='favicon-96x96.png', show_api=False, inbrowser=True)
