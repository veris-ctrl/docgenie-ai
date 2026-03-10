
# ===============================
# IMPORTS
# ===============================
import gradio as gr
import ast
import os
import webbrowser
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4


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

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        txt_path = f"docgenie_{timestamp}.txt"
        pdf_path = f"docgenie_{timestamp}.pdf"

        # Save TXT
        with open(txt_path, "w") as f:
            f.write(final_code)

        # Create PDF
        styles = getSampleStyleSheet()

        code_style = ParagraphStyle(
            name="Code",
            fontName="Courier",
            fontSize=8
        )

        story = []

        story.append(Paragraph("DocGenie AI Generated Docstrings", styles["Title"]))
        story.append(Spacer(1, 20))
        story.append(Preformatted(final_code, code_style))

        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        doc.build(story)

        status = "Docstring Generated Successfully"

        return final_code, os.path.abspath(txt_path), os.path.abspath(pdf_path), status

    except Exception as e:

        return str(e), None, None, "Error occurred"


# ===============================
# SHARE FUNCTIONS
# ===============================

def share_whatsapp():

    url = "https://wa.me/?text=Check%20out%20DocGenie%20AI%20-%20Python%20Docstring%20Generator"
    webbrowser.open(url)

    return "Opening WhatsApp..."


def share_facebook():

    url = "https://www.facebook.com/sharer/sharer.php?u=https://example.com"
    webbrowser.open(url)

    return "Opening Facebook..."


# ===============================
# UI
# ===============================

with gr.Blocks(theme=gr.themes.Soft(), title="DocGenie AI") as demo:

    gr.Markdown("# 🚀 DocGenie AI")
    gr.Markdown("### Python Code Documentation Generator")

    with gr.Row():

        # LEFT PANEL
        with gr.Column(scale=1):

            code_input = gr.Code(
                label="Paste Python Code",
                language="python",
                lines=18
            )

            file_upload = gr.File(
                label="Drag & Drop Python File",
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

        # RIGHT PANEL
        with gr.Column(scale=1):

            output_code = gr.Code(
                label="Generated Code",
                language="python",
                lines=20
            )

            gr.Markdown("### Download Files")

            txt_file = gr.File(label="TXT File")
            pdf_file = gr.File(label="PDF File")

            gr.Markdown("### Share on Social Media")

            with gr.Row():

                whatsapp_btn = gr.Button(
                    "WhatsApp",
                    variant="secondary"
                )

                facebook_btn = gr.Button(
                    "Facebook",
                    variant="secondary"
                )


    # EVENTS

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