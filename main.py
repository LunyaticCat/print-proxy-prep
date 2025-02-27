import os
import math
import json
import time
import base64
import subprocess
import configparser
import io
import re
from PIL import Image, ImageFilter, ImageTk
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4, legal
import tkinter as tk
from tkinter import messagebox

# -----------------------
# Helper functions
# -----------------------
def show_popup(message):
    """A simple modal popup that shows a message."""
    popup = tk.Toplevel()
    popup.title("Info")
    tk.Label(popup, text=message, padx=20, pady=20).pack()
    popup.grab_set()
    popup.wait_window()

def draw_cross(can, x, y, c=6, s=1):
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

def pdf_gen(p_dict, size):
    rgx = re.compile(r"\W")
    img_dict = p_dict["cards"]
    w, h = 2.48 * 72, 3.46 * 72
    rotate = (p_dict["orient"] == "Landscape")
    size = tuple(size[::-1]) if rotate else size
    pw, ph = size
    pdf_fp = os.path.join(
        os.path.dirname(__file__),
        f"{re.sub(rgx, '', p_dict['filename'])}.pdf"
        if len(p_dict["filename"]) > 0
        else "_printme.pdf",
    )
    pages = canvas.Canvas(pdf_fp, pagesize=size)
    cols, rows = int(pw // w), int(ph // h)
    rx, ry = round((pw - (w * cols)) / 2), round((ph - (h * rows)) / 2)
    total_cards = sum(img_dict.values())
    pbreak = cols * rows
    i = 0
    for img in img_dict.keys():
        img_path = os.path.join(os.path.dirname(__file__), "images", "crop", img)
        for n in range(img_dict[img]):
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

# -----------------------
# Main Application Class
# -----------------------
class PDFProxyPrinter:
    def __init__(self, master):
        self.master = master
        self.cwd = os.path.dirname(__file__)
        self.image_dir = os.path.join(self.cwd, "images")
        self.crop_dir = os.path.join(self.image_dir, "crop")
        self.print_json = os.path.join(self.cwd, "print.json")
        self.img_cache = os.path.join(self.cwd, "img.cache")
        for folder in [self.image_dir, self.crop_dir]:
            if not os.path.exists(folder):
                os.mkdir(folder)

        # Load config.ini
        self.config = configparser.ConfigParser()
        subprocess.Popen(["xdg-open", os.path.join(self.cwd, "config.ini")])
        self.cfg = self.config["DEFAULT"]

        # Load image preview cache if needed (not used to create PhotoImages here)
        self.img_dict = {}

        # Load or initialize the print project configuration
        if os.path.exists(self.print_json):
            with open(self.print_json, "r") as fp:
                self.print_dict = json.load(fp)
            # Add any new images from crop_dir to project
            for img in os.listdir(self.crop_dir):
                if img not in self.print_dict["cards"]:
                    self.print_dict["cards"][img] = 1
        else:
            self.print_dict = {
                "cards": {},
                "size": (1480, 920),
                "columns": 5,
                "pagesize": "Letter",
                "page_sizes": ["Letter", "A4", "Legal"],
                "orient": "Portrait",
                "filename": "_printme",
            }
            for img in os.listdir(self.crop_dir):
                self.print_dict["cards"][img] = 1

        self.card_vars = {}  # To hold IntVar for each card's count

        self.setup_ui()

    def setup_ui(self):
        # Top configuration frame
        top_frame = tk.Frame(self.master)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        btn_config = tk.Button(top_frame, text="Config", command=self.open_config)
        btn_config.pack(side=tk.LEFT, padx=5)

        # Paper Size radios
        tk.Label(top_frame, text="Paper Size:").pack(side=tk.LEFT, padx=5)
        self.paper_var = tk.StringVar(value=self.print_dict.get("pagesize", "Letter"))
        for size in self.print_dict.get("page_sizes", ["Letter", "A4", "Legal"]):
            rb = tk.Radiobutton(top_frame, text=size, variable=self.paper_var,
                                value=size, command=self.update_paper_size)
            rb.pack(side=tk.LEFT, padx=2)

        # Orientation radios
        tk.Label(top_frame, text="Orientation:").pack(side=tk.LEFT, padx=5)
        self.orient_var = tk.StringVar(value=self.print_dict.get("orient", "Portrait"))
        rb_portrait = tk.Radiobutton(top_frame, text="Portrait", variable=self.orient_var,
                                     value="Portrait", command=self.update_orientation)
        rb_landscape = tk.Radiobutton(top_frame, text="Landscape", variable=self.orient_var,
                                      value="Landscape", command=self.update_orientation)
        rb_portrait.pack(side=tk.LEFT, padx=2)
        rb_landscape.pack(side=tk.LEFT, padx=2)

        # PDF Filename
        tk.Label(top_frame, text="PDF Filename:").pack(side=tk.LEFT, padx=5)
        self.filename_var = tk.StringVar(value=self.print_dict.get("filename", "_printme"))
        entry_filename = tk.Entry(top_frame, textvariable=self.filename_var, width=20)
        entry_filename.pack(side=tk.LEFT, padx=5)
        entry_filename.bind("<FocusOut>", lambda e: self.update_filename())

        # Action buttons
        btn_crop = tk.Button(top_frame, text="Run Cropper", command=self.run_cropper)
        btn_crop.pack(side=tk.LEFT, padx=5)
        btn_save = tk.Button(top_frame, text="Save Project", command=self.save_project)
        btn_save.pack(side=tk.LEFT, padx=5)
        btn_render = tk.Button(top_frame, text="Render PDF", command=self.render_pdf)
        btn_render.pack(side=tk.LEFT, padx=5)

        # Scrollable frame for card images
        self.scroll_canvas = tk.Canvas(self.master, borderwidth=0)
        self.frame_cards = tk.Frame(self.scroll_canvas)
        vsb = tk.Scrollbar(self.master, orient="vertical", command=self.scroll_canvas.yview)
        self.scroll_canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.scroll_canvas.create_window((4, 4), window=self.frame_cards, anchor="nw",
                                         tags="self.frame_cards")
        self.frame_cards.bind("<Configure>", self.on_frame_configure)

        self.refresh_cards()

    def on_frame_configure(self, event):
        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))

    def refresh_cards(self):
        # Clear the current card frames
        for widget in self.frame_cards.winfo_children():
            widget.destroy()
        self.card_vars.clear()

        col_count = self.print_dict.get("columns", 5)
        row = 0
        col = 0
        for card, count in self.print_dict.get("cards", {}).items():
            card_path = os.path.join(self.crop_dir, card)
            if not os.path.exists(card_path):
                continue

            card_frame = tk.Frame(self.frame_cards, bd=2, relief=tk.RIDGE, padx=5, pady=5)
            card_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

            # Load and display preview image
            try:
                img = Image.open(card_path)
                # Resize for preview (width = 150 pixels)
                w, h = img.size
                new_w = 150
                new_h = int(h * (150 / w))
                img = img.resize((new_w, new_h), Image.ANTIALIAS)
                photo = ImageTk.PhotoImage(img)
            except Exception as e:
                photo = None

            if photo:
                label_img = tk.Label(card_frame, image=photo)
                label_img.image = photo  # keep a reference
                label_img.pack()

            # Card name (truncated if too long)
            display_name = card if len(card) < 35 else card[:28] + "..." + card[card.rfind('.')-1:]
            tk.Label(card_frame, text=display_name).pack()

            # Count controls: minus, entry, plus
            var = tk.IntVar(value=count)
            self.card_vars[card] = var
            btn_sub = tk.Button(card_frame, text="-",
                                command=lambda c=card: self.update_card_count(c, -1))
            btn_sub.pack(side=tk.LEFT, padx=2)
            entry_count = tk.Entry(card_frame, textvariable=var, width=3, justify='center')
            entry_count.pack(side=tk.LEFT, padx=2)
            btn_add = tk.Button(card_frame, text="+",
                                command=lambda c=card: self.update_card_count(c, 1))
            btn_add.pack(side=tk.LEFT, padx=2)

            col += 1
            if col >= col_count:
                col = 0
                row += 1

    def update_card_count(self, card, delta):
        current = self.card_vars[card].get()
        new_val = max(0, current + delta)
        self.card_vars[card].set(new_val)
        self.print_dict["cards"][card] = new_val

    def update_paper_size(self):
        self.print_dict["pagesize"] = self.paper_var.get()

    def update_orientation(self):
        self.print_dict["orient"] = self.orient_var.get()

    def update_filename(self):
        self.print_dict["filename"] = self.filename_var.get()

    def open_config(self):
        try:
            subprocess.Popen([os.path.join(self.cwd, "config.ini")], shell=True)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_project(self):
        with open(self.print_json, "w") as fp:
            json.dump(self.print_dict, fp)
        messagebox.showinfo("Info", "Project saved.")

    def run_cropper(self):
        # Show a modal wait window
        wait_win = tk.Toplevel(self.master)
        wait_win.title("Please Wait")
        tk.Label(wait_win, text="Cropping...").pack(padx=20, pady=20)
        self.master.update()
        # Run cropper (which also applies vibrance if configured)
        self.cropper(self.image_dir, self.print_dict["cards"])
        # Add any new images from crop_dir to project list
        for img in os.listdir(self.crop_dir):
            if img not in self.print_dict["cards"]:
                self.print_dict["cards"][img] = 1
        wait_win.destroy()
        self.refresh_cards()

    def render_pdf(self):
        wait_win = tk.Toplevel(self.master)
        wait_win.title("Please Wait")
        tk.Label(wait_win, text="Rendering PDF...").pack(padx=20, pady=20)
        self.master.update()
        size_map = {"Letter": letter, "A4": A4, "Legal": legal}
        pdf_gen(self.print_dict, size_map[self.print_dict["pagesize"]])
        wait_win.destroy()

    def cropper(self, folder, img_dict):
        # Apply vibrance filter if enabled in config
        if self.cfg.getboolean("Vibrance.Bump", fallback=False):
            try:
                with open(os.path.join(self.cwd, "vibrance.CUBE")) as f:
                    lut_raw = f.read().splitlines()[11:]
                lsize = round(len(lut_raw) ** (1/3))
                def row2val(row):
                    return tuple(float(val) for val in row.split())
                lut_table = [row2val(row) for row in lut_raw]
                lut = ImageFilter.Color3DLUT(lsize, lut_table)
            except Exception as e:
                lut = None
        else:
            lut = None
        if not os.path.exists(self.crop_dir):
            os.mkdir(self.crop_dir)
        for img_file in os.listdir(folder):
            ext = os.path.splitext(img_file)[1].lower()
            if ext not in [".gif", ".jpg", ".jpeg", ".png"]:
                continue
            target_path = os.path.join(self.crop_dir, img_file)
            if os.path.exists(target_path):
                continue
            try:
                with Image.open(os.path.join(folder, img_file)) as im:
                    w, h = im.size
                    c = round(0.12 * min(w / 2.72, h / 3.7))
                    dpi = c * (1 / 0.12)
                    crop_im = im.crop((c, c, w - c, h - c))
                    if dpi > self.cfg.getint("Max.DPI", fallback=300):
                        new_w = int(round(crop_im.size[0] * self.cfg.getint("Max.DPI", fallback=300) / dpi))
                        new_h = int(round(crop_im.size[1] * self.cfg.getint("Max.DPI", fallback=300) / dpi))
                        crop_im = crop_im.resize((new_w, new_h), Image.Resampling.BICUBIC)
                        crop_im = crop_im.filter(ImageFilter.UnsharpMask(1, 20, 8))
                    if lut:
                        crop_im = crop_im.filter(lut)
                    crop_im.save(target_path, quality=98)
            except Exception as e:
                print(f"Error processing {img_file}: {e}")
        return img_dict

# -----------------------
# Run the Application
# -----------------------
if __name__ == "__main__":
    root = tk.Tk()
    root.title("PDF Proxy Printer")
    app = PDFProxyPrinter(root)
    root.mainloop()
