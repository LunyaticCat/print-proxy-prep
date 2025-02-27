"""
Utility module for PDF generation and helper functions.
"""

import os
import re
import subprocess
import tkinter as tk
from reportlab.pdfgen import canvas


def show_popup(message: str) -> None:
    """
    Display a modal popup window with a given message.
    """
    popup = tk.Toplevel()
    popup.title("Info")
    tk.Label(popup, text=message, padx=20, pady=20).pack()
    popup.grab_set()
    popup.wait_window()


def draw_cross(can: canvas.Canvas, x: float, y: float, c: int = 6, s: int = 1) -> None:
    """
    Draw a cross marker at the specified coordinates on a canvas.
    """
    dash = [s, s]
    can.setLineWidth(s)
    can.setDash(dash)
    can.setStrokeColorRGB(255, 255, 255)
    can.line(x, y - c, x, y + c)
    can.setStrokeColorRGB(0, 0, 0)
    can.line(x - c, y, x + c, y)
    can.setDash(dash, s)
    can.setStrokeColorRGB(255, 255, 255)
    can.line(x - c, y, x + c, y)
    can.setStrokeColorRGB(0, 0, 0)
    can.line(x, y - c, x, y + c)


def pdf_gen(p_dict: dict, size: tuple) -> None:
    """
    Generate a PDF document from the project dictionary and specified page size.
    """
    rgx = re.compile(r"\W")
    img_dict = p_dict["cards"]
    w, h = 2.48 * 72, 3.46 * 72
    rotate = (p_dict["orient"] == "Landscape")
    size = tuple(size[::-1]) if rotate else size
    pw, ph = size
    pdf_fp = os.path.join(
        os.path.dirname(__file__),
        f"{re.sub(rgx, '', p_dict['filename'])}.pdf" if len(p_dict["filename"]) > 0 else "_printme.pdf",
    )
    pages = canvas.Canvas(pdf_fp, pagesize=size)
    cols, rows = int(pw // w), int(ph // h)
    rx, ry = round((pw - (w * cols)) / 2), round((ph - (h * rows)) / 2)
    total_cards = sum(img_dict.values())
    pbreak = cols * rows
    i = 0

    for img in img_dict.keys():
        img_path = os.path.join(os.path.dirname(__file__), "images", "crop", img)
        for _ in range(img_dict[img]):
            p, j = divmod(i, pbreak)
            y_idx, x_idx = divmod(j, cols)
            if j == 0 and i > 0:
                pages.showPage()
            pages.drawImage(
                img_path,
                x_idx * w + rx,
                y_idx * h + ry,
                w,
                h,
            )
            if j == pbreak - 1 or i == total_cards - 1:
                for cy in range(rows + 1):
                    for cx in range(cols + 1):
                        draw_cross(pages, rx + w * cx, ry + h * cy)
            i += 1

    show_popup("Saving PDF...")
    pages.save()
    try:
        subprocess.Popen([pdf_fp], shell=True)
    except Exception as e:
        print(e)
