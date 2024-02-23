import gradio as gr

def greet(name):
    return "Hello " + name + "!"

with gr.Blocks(theme="monochrome") as demo:
    name = gr.Textbox(label="Name", value="World")
    output = gr.Textbox(label="Output Box")
    greet_btn = gr.Button("Greet")
    greet_btn.click(fn=greet, inputs=name, outputs=output)
    name.submit(fn=greet, inputs=name, outputs=output)

if __name__ == "__main__":
    demo.css = "footer {visibility: hidden}"
    demo.launch()
