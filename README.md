# 🚀 DocGenie AI

DocGenie AI automatically generates Python docstrings using AST analysis.

## Features

* Google style docstrings
* NumPy style docstrings
* Upload Python files
* Download documentation as TXT and PDF
* Simple Gradio interface

## Installation

```bash
pip install -r requirements.txt
```

## Run the Application

```bash
python app.py
```

After running the command, the **Gradio interface** will start in your browser.

## Usage

1. Paste your Python code or upload a `.py` file.
2. Select the docstring style (Google or NumPy).
3. Click **Generate Docstring**.
4. Download the generated documentation as **TXT or PDF**.

## Tech Stack

* Python
* Gradio
* AST (Abstract Syntax Tree)
* ReportLab

## Project Structure

```
docgenie-ai
│
├── app.py
├── requirements.txt
├── README.md
└── .gitignore
```

MIT License
