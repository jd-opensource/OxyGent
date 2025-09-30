import os
import shutil

# import pandas as pd
from pydantic import Field

from oxygent.oxy import FunctionHub

file_tools = FunctionHub(name="file_tools")


@file_tools.tool(
    description="Create a new file or completely overwrite an existing file with new content. Use with caution as it will overwrite existing files without warning. Handles text content with proper encoding. Only works within allowed directories."
)
def write_file(
    path: str = Field(description=""), content: str = Field(description="")
) -> str:
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)
    return "Successfully wrote to " + path


@file_tools.tool(
    description="Read the content of a file. Returns an error message if the file does not exist."
)
def read_file(path: str = Field(description="Path to the file to read")) -> str:
    if not os.path.exists(path):
        return f"Error: The file at {path} does not exist."
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


@file_tools.tool(
    description="Delete a file or directory. Returns a success message if the item is deleted, or an error if the item does not exist. For directories, this will delete all contents recursively."
)
def delete_file(path: str = Field(description="Path to the file or directory to delete")) -> str:
    if not os.path.exists(path):
        return f"Error: The file or directory at {path} does not exist."

    try:
        if os.path.isfile(path):
            os.remove(path)
            return f"Successfully deleted the file at {path}"
        elif os.path.isdir(path):
            shutil.rmtree(path)
            return f"Successfully deleted the directory at {path} and all its contents"
    except PermissionError:
        return f"Error: Permission denied when trying to delete {path}"
    except Exception as e:
        return f"Error: Failed to delete {path}. Reason: {str(e)}"


# @file_tools.tool(
#     description="Read plain text from a Word document (.doc/.docx). "
#     "Returns the concatenated paragraph text. If python-docx is missing, "
#     "it fails gracefully and tells the user to install it."
# )
# def read_docx(path: str = Field(description="Path of .doc or .docx file")) -> str:
#     if not os.path.exists(path):
#         return f"Error: {path} does not exist."
#     try:
#         import docx
#     except ImportError:
#         return "Error: python-docx library not installed."
#     try:
#         doc = docx.Document(path)
#         return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
#     except Exception as e:
#         return f"Error reading docx file: {e}"


# @file_tools.tool(
#     description="Read an Excel file (.xlsx/.xls). "
#     "Returns the first 20 rows of the first sheet in CSV format."
# )
# def read_excel(path: str = Field(description="Excel file path")) -> str:
#     if not os.path.exists(path):
#         return f"Error: {path} does not exist."
#     try:
#         df = pd.read_excel(path, sheet_name=0)
#         return df.head(20).to_csv(index=False)
#     except Exception as e:
#         return f"Error reading Excel file: {e}"


# @file_tools.tool(
#     description="Read a CSV file. Returns the first 20 rows as CSV text."
# )
# def read_csv(path: str = Field(description="CSV file path")) -> str:
#     if not os.path.exists(path):
#         return f"Error: {path} does not exist."
#     try:
#         df = pd.read_csv(path, nrows=20)
#         return df.to_csv(index=False)
#     except Exception as e:
#         return f"Error reading CSV file: {e}"


# @file_tools.tool(
#     description="Read a JSON file and pretty-print its content (max 8 KB)."
# )
# def read_json_file(path: str = Field(description="JSON file path")) -> str:
#     if not os.path.exists(path):
#         return f"Error: {path} does not exist."
#     try:
#         with open(path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         text = json.dumps(data, indent=2, ensure_ascii=False)
#         return text[:8192] + ("…" if len(text) > 8192 else "")
#     except Exception as e:
#         return f"Error reading JSON file: {e}"


# @file_tools.tool(
#     description="Read a Markdown or plain-text code file (.md/.py/.txt). "
#     "Returns the first 400 lines."
# )
# def read_text_like_file(
#     path: str = Field(description="Path of .md/.py/.txt or similar file"),
#     max_lines: int = Field(default=400, description="Lines to read (default 400)"),
# ) -> str:
#     if not os.path.exists(path):
#         return f"Error: {path} does not exist."
#     try:
#         with open(path, "r", encoding="utf-8") as f:
#             lines = []
#             for i, line in enumerate(f):
#                 if i >= max_lines:
#                     lines.append("...\n")
#                     break
#                 lines.append(line)
#         return "".join(lines)
#     except Exception as e:
#         return f"Error reading text file: {e}"
