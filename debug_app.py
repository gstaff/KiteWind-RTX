import gradio as gr


def greet(name):
    return "Hello " + name + "!"


with gr.Blocks() as demo:
  codeA = gr.Code(label='Works', language='python', interactive=True)
  codeB = gr.Code(label='Bugged', value='# Test code here', language='python', interactive=True)

if __name__ == "__main__":
    demo.launch()
