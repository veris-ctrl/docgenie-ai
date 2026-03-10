# ===============================
# IMPORTS
# ===============================
import gradio as gr
import ast
import os
import webbrowser
import requests
import autopep8
import black
import torch

from transformers import pipeline

from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4


# ===============================
# LOAD AI MODEL
# ===============================
generator = pipeline(
    "text-generation",
    model="ibm-granite/granite-3.3-2b-instruct",
    device=-1
)


# ===============================
# DOCGENIE ANALYZER
# ===============================
class DocGenieAnalyzer:

    @staticmethod
    def detect_return_type(node):

        for child in ast.walk(node):

            if isinstance(child, ast.Return):

                if isinstance(child.value, ast.List):
                    return "list"

                if isinstance(child.value, ast.Tuple):
                    return "tuple"

                if isinstance(child.value, ast.Constant):
                    return type(child.value.value).__name__

                if isinstance(child.value, ast.BinOp):
                    return "float"

        return "None"

    @staticmethod
    def extract_functions(code):

        tree = ast.parse(code)
        functions = []

        for node in tree.body:

            if isinstance(node, ast.FunctionDef):

                functions.append({
                    "name": node.name,
                    "args": [arg.arg for arg in node.args.args],
                    "returns": DocGenieAnalyzer.detect_return_type(node),
                    "node": node
                })

        return functions

    @staticmethod
    def analyze_function_logic(node):

        logic = {
            "condition": False,
            "loop": False,
            "math": False
        }

        for child in ast.walk(node):

            if isinstance(child, ast.If):
                logic["condition"] = True

            if isinstance(child, (ast.For, ast.While)):
                logic["loop"] = True

            if isinstance(child, ast.BinOp):
                logic["math"] = True

        return logic

    @staticmethod
    def generate_google_docstring(signature, analysis):

        doc = f'"""\n{signature["name"]} function.\n'

        if analysis["condition"]:
            doc += "\nIncludes conditional logic."

        if analysis["loop"]:
            doc += "\nUses loop operations."

        if analysis["math"]:
            doc += "\nPerforms mathematical operations."

        doc += "\n\nArgs:\n"

        for arg in signature["args"]:
            doc += f"    {arg} (type): Description.\n"

        doc += f"\nReturns:\n    {signature['returns']}: Description.\n"
        doc += '"""'

        return doc

    @staticmethod
    def generate_numpy_docstring(signature):

        doc = f'"""\n{signature["name"]} function.\n\n'

        doc += "Parameters\n----------\n"

        for arg in signature["args"]:
            doc += f"{arg} : type\n    Description.\n"

        doc += "\nReturns\n-------\n"
        doc += f"{signature['returns']}\n    Description.\n"

        doc += '"""'

        return doc


# ===============================
# AI DOCSTRING IMPROVER
# ===============================
def improve_docstring_ai(code):

    prompt = f"""
Improve the docstrings in this Python code.

Rules:
- Do NOT modify any code.
- Do NOT remove functions.
- Only improve the text inside the docstrings.

Python Code:
{code}
"""

    result = generator(prompt, max_new_tokens=150)

    return result[0]["generated_text"]


# ===============================
# CODE FORMATTER
# ===============================
def format_code(code):

    try:
        code = autopep8.fix_code(code)
        code = black.format_str(code, mode=black.FileMode())
        return code
    except:
        return code


# ===============================
# API CHECK
# ===============================
def api_status():

    try:
        r = requests.get("https://api.github.com")
        return f"API Status: {r.status_code}"
    except:
        return "API request failed"


# ===============================
# FILE LOADER
# ===============================
def load_py_file(file):

    if file is None:
        return ""

    with open(file.name, "r") as f:
        return f.read()


# ===============================
# PROCESS CODE
# ===============================
def process_code(code, style):
    try:

        functions = DocGenieAnalyzer.extract_functions(code)

        if not functions:
            return "No functions found.", None, None, "No functions detected"

        lines = code.split("\n")

        for func in functions:
            analysis = DocGenieAnalyzer.analyze_function_logic(func["node"])

            if style == "Google":
                docstring = DocGenieAnalyzer.generate_google_docstring(func, analysis)
            else:
                docstring = DocGenieAnalyzer.generate_numpy_docstring(func)

            for i, line in enumerate(lines):
                if line.strip().startswith(f"def {func['name']}"):
                    indent = " " * (len(line) - len(line.lstrip()) + 4)
                    formatted = indent + docstring.replace("\n", "\n" + indent)
                    lines.insert(i + 1, formatted)
                    break

        final_code = "\n".join(lines)

        # AI enhancement (optional)
        ai_output = improve_docstring_ai(final_code)
        if ai_output:
            # Keep your AST-generated code safe
            final_code = final_code

        # Format code
        final_code = format_code(final_code)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        txt_path = f"docgenie_{timestamp}.txt"
        pdf_path = f"docgenie_{timestamp}.pdf"

        with open(txt_path, "w") as f:
            f.write(final_code)

        styles = getSampleStyleSheet()
        code_style = ParagraphStyle(
            name="Code",
            fontName="Courier",
            fontSize=8
        )

        story = []
        story.append(Paragraph("DocGenie AI Generated Documentation", styles["Title"]))
        story.append(Spacer(1, 20))
        story.append(Preformatted(final_code, code_style))

        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        doc.build(story)

        status = api_status()
        return final_code, os.path.abspath(txt_path), os.path.abspath(pdf_path), status

    except Exception as e:
        return str(e), None, None, "Error occurred"


# ===============================
# UI
# ===============================
with gr.Blocks(theme=gr.themes.Soft(), title="DocGenie AI") as demo:

    gr.Markdown("# 🚀 DocGenie AI")
    gr.Markdown("### Python Code Documentation Generator")

    with gr.Row():

        with gr.Column(scale=1):

            code_input = gr.Code(
                label="Paste Python Code",
                language="python",
                lines=18
            )

            file_upload = gr.File(
                label="Upload Python File",
                file_types=[".py"]
            )

            style = gr.Radio(
                ["Google", "NumPy"],
                value="Google",
                label="Docstring Style"
            )

            generate_btn = gr.Button(
                "Generate Docstring",
                variant="primary"
            )

            status = gr.Textbox(label="Status")

        with gr.Column(scale=1):

            output_code = gr.Code(
                label="Generated Code",
                language="python",
                lines=20
            )

            gr.Markdown("### Download Files")

            txt_file = gr.File(label="TXT File")
            pdf_file = gr.File(label="PDF File")

            gr.Markdown("### Share")

            with gr.Row():

                whatsapp_btn = gr.Button("WhatsApp")
                facebook_btn = gr.Button("Facebook")


    file_upload.change(
        load_py_file,
        inputs=file_upload,
        outputs=code_input
    )

    generate_btn.click(
        process_code,
        inputs=[code_input, style],
        outputs=[output_code, txt_file, pdf_file, status]
    )

    whatsapp_btn.click(
        share_whatsapp,
        outputs=status
    )

    facebook_btn.click(
        share_facebook,
        outputs=status
    )


# ===============================
# LAUNCH
# ===============================
demo.launch(share=True)
