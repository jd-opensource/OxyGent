import os, sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.append('..')

from pydantic import Field
from PIL import Image, ImageDraw, ImageFont
import openpyxl
import logging
logger = logging.getLogger(__name__)

from oxygent import oxy
ep = oxy.FunctionHub(name="excel2png_tool", timeout=900)


def excel_range_to_image(
        excel_path,
        sheet_name,
        cell_range,
        output_path,
        dpi=150
):
    """
    Convert specified range of Excel to image (without using LibreOffice)

    Parameters:
    excel_path: Path to Excel file
    sheet_name: Worksheet name
    cell_range: Cell range (e.g., "A1:D10")
    output_path: Output image path
    dpi: Image resolution
    """
    # Load workbook
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    sheet = wb[sheet_name]

    # Parse cell range
    start_col, start_row, end_col, end_row = parse_cell_range(cell_range)

    # Calculate range dimensions
    num_cols = end_col - start_col + 1
    num_rows = end_row - start_row + 1

    # Create image
    cell_width = 100  # pixels
    cell_height = 30  # pixels
    img_width = num_cols * cell_width + 20
    img_height = num_rows * cell_height + 20
    img = Image.new('RGB', (img_width, img_height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Load font
    try:
        font = ImageFont.truetype("Arial.ttf", 12)
    except:
        # Fallback to default font
        font = ImageFont.load_default()

    # Draw cells
    for row_idx in range(num_rows):
        for col_idx in range(num_cols):
            # Calculate cell position
            x1 = 10 + col_idx * cell_width
            y1 = 10 + row_idx * cell_height
            x2 = x1 + cell_width
            y2 = y1 + cell_height

            # Get cell
            cell = sheet.cell(
                row=start_row + row_idx,
                column=start_col + col_idx
            )

            # Draw cell background
            bg_color = (255, 255, 255)
            if cell.fill and cell.fill.patternType != 'none':
                if cell.fill.fgColor and cell.fill.fgColor.rgb:
                    try:
                        hex_color = cell.fill.fgColor.rgb
                        if hex_color.startswith('FF'):
                            hex_color = hex_color[2:]
                        r = int(hex_color[0:2], 16)
                        g = int(hex_color[2:4], 16)
                        b = int(hex_color[4:6], 16)
                        bg_color = (r, g, b)
                    except:
                        pass

            draw.rectangle([(x1, y1), (x2, y2)], fill=bg_color, outline=(0, 0, 0))

            # Add text
            if cell.value is not None:
                text = str(cell.value)
                text_width, text_height = draw.textsize(text, font=font)
                text_x = x1 + (cell_width - text_width) / 2
                text_y = y1 + (cell_height - text_height) / 2

                # Text color
                text_color = (0, 0, 0)
                if cell.font and cell.font.color and cell.font.color.rgb:
                    try:
                        hex_color = cell.font.color.rgb
                        if hex_color.startswith('FF'):
                            hex_color = hex_color[2:]
                        r = int(hex_color[0:2], 16)
                        g = int(hex_color[2:4], 16)
                        b = int(hex_color[4:6], 16)
                        text_color = (r, g, b)
                    except:
                        pass

                draw.text((text_x, text_y), text, font=font, fill=text_color)

    # Save image
    img.save(output_path, dpi=(dpi, dpi))
    print(f"✅ Image saved: {output_path}")
    return output_path


def parse_cell_range(cell_range):
    """Parse cell range (e.g., 'A1:D10')"""
    # Split start and end positions
    parts = cell_range.split(':')
    if len(parts) != 2:
        raise ValueError("Invalid cell range format")

    start_cell = parts[0]
    end_cell = parts[1]

    # Parse start position
    col_str = ''
    row_str = ''
    for char in start_cell:
        if char.isalpha():
            col_str += char
        else:
            row_str += char

    start_col = column_index_from_string(col_str)
    start_row = int(row_str)

    # Parse end position
    col_str = ''
    row_str = ''
    for char in end_cell:
        if char.isalpha():
            col_str += char
        else:
            row_str += char

    end_col = column_index_from_string(col_str)
    end_row = int(row_str)

    return start_col, start_row, end_col, end_row


def column_index_from_string(col_str):
    """Convert column letters to numeric index (A=1, B=2, ..., Z=26, AA=27, etc.)"""
    col_str = col_str.upper()
    num = 0
    for c in col_str:
        num = num * 26 + (ord(c) - ord('A') + 1)
    return num


@ep.tool(description="convert excel to png.")
async def excel2png_api(
    excel_path: str = Field(description="The file name to convert")
) -> str:
    sheet_name = "Sheet1"
    cell_range = "A1:Z100"
    output_path = (os.getenv('LOCAL_CACHE_DIR') +
                   excel_path.split("test/")[1].split('.')[0] + ".png")
    excel_range_to_image(excel_path, sheet_name, cell_range, output_path, dpi=200)
    return output_path

if __name__ == '__main__':
    from dotenv import load_dotenv
    from pathlib import Path
    import asyncio
    env_path = Path('../examples/gaia/') / '.env'
    load_dotenv(dotenv_path=env_path, verbose=True)
    print(asyncio.run(excel2png_api(".xlsx")))
    print("running")
