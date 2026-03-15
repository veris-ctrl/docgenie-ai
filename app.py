# ===============================
# IMPORTS
# ===============================
import ast
import os
from datetime import datetime
from typing import Optional

import gradio as gr
import autopep8
import black

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4


# ===============================
# DOCGENIE ANALYZER
# ===============================
class DocGenieAnalyzer:
    @staticmethod
    def _annotation_to_str(ann: Optional[ast.AST]) -> Optional[str]:
        if ann is None:
            return None
        try:
            return ast.unparse(ann)
        except Exception:
            if isinstance(ann, ast.Name):
                return ann.id
            return None

    @staticmethod
    def detect_return_type(node: ast.AST) -> str:
        # Prefer explicit type annotations on the function
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ann = DocGenieAnalyzer._annotation_to_str(node.returns)
            if ann:
                return ann

        # Conservative inference from return statements
        found = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Return):
                val = child.value
                if val is None:
                    found.add("None")
                elif isinstance(val, ast.Constant):
                    found.add(type(val.value).__name__)
                elif isinstance(val, ast.List):
                    found.add("list")
                elif isinstance(val, ast.Tuple):
                    found.add("tuple")
                elif isinstance(val, ast.Dict):
                    found.add("dict")
                elif isinstance(val, ast.Set):
                    found.add("set")
                else:
                    found.add("Any")

        if not found:
            return "None"
        if len(found) == 1:
            return next(iter(found))
        return " | ".join(sorted(found))

    @staticmethod
    def extract_functions(code: str):
        """Extract all (top-level and nested) function definitions, incl. async."""
        tree = ast.parse(code)
        functions = []

        class Visitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node: ast.FunctionDef):
                functions.append(
                    {
                        "name": node.name,
                        "args": [a.arg for a in node.args.args],
                        "returns": DocGenieAnalyzer.detect_return_type(node),
                        "node": node,
                        "lineno": getattr(node, "lineno", None),
                        "col_offset": getattr(node, "col_offset", None),
                    }
                )
                self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                functions.append(
                    {
                        "name": node.name,
                        "args": [a.arg for a in node.args.args],
                        "returns": DocGenieAnalyzer.detect_return_type(node),
                        "node": node,
                        "lineno": getattr(node, "lineno", None),
                        "col_offset": getattr(node, "col_offset", None),
                    }
                )
                self.generic_visit(node)

        Visitor().visit(tree)
        return functions

    @staticmethod
    def analyze_function_logic(node: ast.AST):
        logic = {"condition": False, "loop": False, "math": False}
        for c in ast.walk(node):
            if isinstance(c, ast.If):
                logic["condition"] = True
            if isinstance(c, (ast.For, ast.While)):
                logic["loop"] = True
            if isinstance(c, ast.BinOp):
                logic["math"] = True
        return logic

    @staticmethod
    def google_doc(signature, logic):
        lines = [f"{signature['name']} function.", "", "Args:"]
        if signature["args"]:
            for a in signature["args"]:
                lines.append(f"    {a} (Any): Description.")
        else:
            lines.append("    None")

        lines.append("")
        lines.append("Returns:")
        lines.append(f"    {signature['returns']}: Description.")
        return "\n".join(lines)

    @staticmethod
    def numpy_doc(signature, logic):
        lines = [
            f"{signature['name']} function.",
            "",
            "Parameters",
            "----------",
        ]
        if signature["args"]:
            for a in signature["args"]:
                lines.append(f"{a} : Any")
                lines.append("    Description.")
        else:
            lines.append("None")

        lines.extend(
            [
                "",
                "Returns",
                "-------",
                signature["returns"],
                "    Description.",
            ]
        )
        return "\n".join(lines)


# ===============================
# HELPERS
# ===============================
def sanitize_html_entities(text: str) -> str:
    """
    Fix common HTML entities that break Python when pasted from the web.
    We loop twice to handle double-encoded content (e.g., '&amp;gt;' -> '&gt;' -> '>').
    """
    patterns = [
        ("&amp;", "&"),
        ("&gt;", ">"),
        ("&lt;", "<"),
        ("-&gt;", "->"),
        ("−", "-"),  # minus variants from copy/paste
        ("–", "-"),
        ("—", "-"),
    ]
    for _ in range(2):
        for bad, good in patterns:
            text = text.replace(bad, good)
    return text


def replace_docstring(code: str, func: dict, doc: str) -> str:
    """
    Insert or REPLACE the docstring of a specific function using AST.
    Matches by name + lineno + col_offset; if a docstring exists, replace it.
    """
    tree = ast.parse(code)

    target = None
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == func["name"]
            and getattr(node, "lineno", None) == func["lineno"]
            and getattr(node, "col_offset", None) == func["col_offset"]
        ):
            target = node
            break

    if target is None:
        # Fallback: first function with the same name
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func["name"]:
                target = node
                break

    if target is None:
        return code  # nothing to do

    # Replace existing docstring or insert at top
    has_doc = (
        len(target.body) > 0
        and isinstance(target.body[0], ast.Expr)
        and isinstance(getattr(target.body[0], "value", None), ast.Constant)
        and isinstance(target.body[0].value.value, str)
    )
    new_doc_expr = ast.Expr(value=ast.Constant(value=doc))
    if has_doc:
        target.body[0] = new_doc_expr
    else:
        target.body.insert(0, new_doc_expr)

    ast.fix_missing_locations(tree)
    try:
        return ast.unparse(tree)
    except Exception:
        return code


def format_code(code: str) -> str:
    try:
        code = autopep8.fix_code(code)
        return black.format_str(code, mode=black.FileMode())
    except Exception:
        return code


def load_py_file(file):
    if file is None:
        return ""
    with open(file.name, "r", encoding="utf-8") as f:
        return f.read()


def clear_all():
    """Return empty values for: code_input, file_upload, output_code, txt_file, pdf_file, status."""
    return "", None, "", None, None, ""


# ===============================
# PROCESS CODE
# ===============================
def process_code(code: str, style: str):
    # Sanitize pasted code (fix HTML entities)
    code = sanitize_html_entities(code)

    if not code.strip():
        return "", None, None, "Paste Python code first."

    try:
        functions = DocGenieAnalyzer.extract_functions(code)
    except SyntaxError as e:
        return "", None, None, f"❌ SyntaxError while parsing your code: {e}"

    if not functions:
        return "", None, None, "No functions found."

    updated = code

    for f in functions:
        logic = DocGenieAnalyzer.analyze_function_logic(f["node"])
        doc = (
            DocGenieAnalyzer.numpy_doc(f, logic)
            if style == "NumPy"
            else DocGenieAnalyzer.google_doc(f, logic)
        )
        updated = replace_docstring(updated, f, doc)

    updated = format_code(updated)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    txt_path = f"docgenie_{ts}.txt"
    pdf_path = f"docgenie_{ts}.pdf"

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(updated)

    styles = getSampleStyleSheet()
    story = [
        Paragraph("DocGenie Documentation", styles["Title"]),
        Spacer(1, 16),
        Preformatted(updated, ParagraphStyle("Code", fontName="Courier", fontSize=9)),
    ]
    SimpleDocTemplate(pdf_path, pagesize=A4).build(story)

    return updated, os.path.abspath(txt_path), os.path.abspath(pdf_path), "✅ Done"


# ===============================
# UI
# ===============================
CSS = """
.gradio-container {max-width: 1100px !important; margin: 0 auto;}
.share-bar {display:flex; gap:12px; margin-top:8px; flex-wrap:wrap;}
.share-btn {
  display:inline-block; padding:8px 14px; border-radius:8px;
  background:#2563eb; color:white; text-decoration:none; font-weight:600;
}
.share-btn.secondary { background:#10b981; }
"""

with gr.Blocks(title="DocGenie AI", theme=gr.themes.Soft(), css=CSS) as demo:
    gr.Markdown("## 🚀 DocGenie AI")
    gr.Markdown("**Professional Python Docstring Generator (Google / NumPy) using AST analysis**")

    with gr.Tabs():
        # INPUT TAB
        with gr.Tab("🧾 Input"):
            code_input = gr.Code(language="python", lines=22, label="Paste Python Code")
            file_upload = gr.File(label="Upload Python File", file_types=[".py"])
            style = gr.Radio(["Google", "NumPy"], value="Google", label="Docstring Style")

            with gr.Row():
                generate_btn = gr.Button("Generate Docstrings", variant="primary")
                clear_btn = gr.Button("Clear")

            status = gr.Textbox(label="Status")

        # OUTPUT TAB
        with gr.Tab("🧩 Output"):
            output_code = gr.Code(language="python", lines=22, label="Generated Code")
            with gr.Row():
                txt_file = gr.File(label="TXT File")
                pdf_file = gr.File(label="PDF File")

            # Share as clickable, button-styled links (no raw URL text)
            gr.HTML(
                """
                <div class="share-bar">
                  <a class="share-btn" href="https://wa.me/?text=Check%20out%20DocGenie%20AI" target="_blank" rel="noopener noreferrer">
                    📲 Share on WhatsApp
                  </a>
                  <a class="share-btn secondary" href="https://www.facebook.com/sharer/sharer.php?u=https://github.com/veris-ctrl/docgenie-ai" target="_blank" rel="noopener noreferrer">
                    📘 Share on Facebook
                  </a>
                </div>
                """
            )

    # Wiring
    file_upload.change(load_py_file, inputs=file_upload, outputs=code_input)

    generate_btn.click(
        process_code,
        inputs=[code_input, style],
        outputs=[output_code, txt_file, pdf_file, status],
    )

    clear_btn.click(
        clear_all,
        outputs=[code_input, file_upload, output_code, txt_file, pdf_file, status],
    )


if __name__ == "__main__":
    demo.launch(share=True)
