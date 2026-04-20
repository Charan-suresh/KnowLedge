import json
import gradio as gr
from inference import generate_text, generate_with_image, health_check

def api_generate(payload_str: str) -> str:
    try:
        data = json.loads(payload_str)
        model = data.get("model", "")
        model_name = "e2b" if "e2b" in model.lower() else "e4b"
        prompt = data.get("prompt", "")
        max_tokens = data.get("max_tokens", 512)
        response = generate_text(model_name, prompt, max_tokens)
        return json.dumps({"response": response})
    except Exception as e:
        return json.dumps({"error": str(e)})

def api_generate_vision(payload_str: str) -> str:
    try:
        data = json.loads(payload_str)
        prompt = data.get("prompt", "")
        image_base64 = data.get("image_base64", "")
        max_tokens = data.get("max_tokens", 512)
        response = generate_with_image(prompt, image_base64, max_tokens)
        return json.dumps({"response": response})
    except Exception as e:
        return json.dumps({"error": str(e)})

def api_health() -> str:
    try:
        status = health_check()
        return json.dumps(status)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})

with gr.Blocks() as demo:
    gr.Markdown("# KnowLedge Inference API\nThis Space serves as the LLM backend for the KnowLedge platform.")
    
    # Expose APIs (hidden in UI)
    gen_in = gr.Textbox(visible=False)
    gen_out = gr.Textbox(visible=False)
    gr.Button("Generate", visible=False).click(api_generate, inputs=[gen_in], outputs=[gen_out], api_name="generate")
    
    vis_in = gr.Textbox(visible=False)
    vis_out = gr.Textbox(visible=False)
    gr.Button("Generate Vision", visible=False).click(api_generate_vision, inputs=[vis_in], outputs=[vis_out], api_name="generate_vision")
    
    health_out = gr.Textbox(visible=False)
    gr.Button("Health", visible=False).click(api_health, inputs=[], outputs=[health_out], api_name="health")

if __name__ == "__main__":
    demo.launch()
