"""
GUI module for the PDF Proxy Printer.

This module contains the PDFProxyPrinter class, which handles the Tkinter
user interface, configuration management, and calls to image cropping and PDF generation.
"""

import os
import json
import configparser
import subprocess
import re
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageFilter
from reportlab.lib.pagesizes import letter, A4, legal
from pdf_utils import pdf_gen, show_popup
from cropper import crop_images


class PDFProxyPrinter:
    """
    A GUI application to manage and print PDFs from card images.
    """

    def __init__(self, master: tk.Tk) -> None:
        self.master = master
        self.cwd = os.path.dirname(__file__)
        self.image_dir = os.path.join(self.cwd, "images")
        self.crop_dir = os.path.join(self.image_dir, "crop")
        self.print_json = os.path.join(self.cwd, "print.json")
        self.img_cache = os.path.join(self.cwd, "img.cache")

        self.ensure_directories([self.image_dir, self.crop_dir])
        self.config = configparser.ConfigParser()
        self.open_config_file(os.path.join(self.cwd, "config.ini"))
        self.cfg = self.config["DEFAULT"]

        self.img_dict = {}
        self.print_dict = self.load_project_configuration()
        self.card_vars = {}

        self.setup_ui()

    def ensure_directories(self, directories: list) -> None:
        """
        Ensure that all required directories exist.
        """
        for folder in directories:
            if not os.path.exists(folder):
                os.mkdir(folder)

    def open_config_file(self, filepath: str) -> None:
        """
        Open the configuration file with the system's default editor.
        """
        subprocess.Popen(["xdg-open", filepath])

    def load_project_configuration(self) -> dict:
        """
        Load the project configuration from a JSON file or initialize a new project.
        """
        if os.path.exists(self.print_json):
            with open(self.print_json, "r") as fp:
                print_dict = json.load(fp)
            # Add new images from the crop directory to the project
            for img in os.listdir(self.crop_dir):
                if img not in print_dict["cards"]:
                    print_dict["cards"][img] = 1
        else:
            print_dict = {
                "cards": {},
                "size": (1480, 920),
                "columns": 5,
                "pagesize": "Letter",
                "page_sizes": ["Letter", "A4", "Legal"],
                "orient": "Portrait",
                "filename": "_printme",
            }
            for img in os.listdir(self.crop_dir):
                print_dict["cards"][img] = 1
        return print_dict

    def setup_ui(self) -> None:
        """
        Set up the user interface components.
        """
        top_frame = tk.Frame(self.master)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        btn_config = tk.Button(top_frame, text="Config", command=self.open_config)
        btn_config.pack(side=tk.LEFT, padx=5)

        tk.Label(top_frame, text="Paper Size:").pack(side=tk.LEFT, padx=5)
        self.paper_var = tk.StringVar(value=self.print_dict.get("pagesize", "Letter"))
        for size in self.print_dict.get("page_sizes", ["Letter", "A4", "Legal"]):
            rb = tk.Radiobutton(top_frame, text=size, variable=self.paper_var,
                                value=size, command=self.update_paper_size)
            rb.pack(side=tk.LEFT, padx=2)

        tk.Label(top_frame, text="Orientation:").pack(side=tk.LEFT, padx=5)
        self.orient_var = tk.StringVar(value=self.print_dict.get("orient", "Portrait"))
        rb_portrait = tk.Radiobutton(top_frame, text="Portrait", variable=self.orient_var,
                                     value="Portrait", command=self.update_orientation)
        rb_landscape = tk.Radiobutton(top_frame, text="Landscape", variable=self.orient_var,
                                      value="Landscape", command=self.update_orientation)
        rb_portrait.pack(side=tk.LEFT, padx=2)
        rb_landscape.pack(side=tk.LEFT, padx=2)

        tk.Label(top_frame, text="PDF Filename:").pack(side=tk.LEFT, padx=5)
        self.filename_var = tk.StringVar(value=self.print_dict.get("filename", "_printme"))
        entry_filename = tk.Entry(top_frame, textvariable=self.filename_var, width=20)
        entry_filename.pack(side=tk.LEFT, padx=5)
        entry_filename.bind("<FocusOut>", lambda e: self.update_filename())

        btn_crop = tk.Button(top_frame, text="Run Cropper", command=self.run_cropper)
        btn_crop.pack(side=tk.LEFT, padx=5)
        btn_save = tk.Button(top_frame, text="Save Project", command=self.save_project)
        btn_save.pack(side=tk.LEFT, padx=5)
        btn_render = tk.Button(top_frame, text="Render PDF", command=self.render_pdf)
        btn_render.pack(side=tk.LEFT, padx=5)

        self.setup_scrollable_frame()

    def setup_scrollable_frame(self) -> None:
        """
        Set up the scrollable frame used to display card previews.
        """
        self.scroll_canvas = tk.Canvas(self.master, borderwidth=0)
        self.frame_cards = tk.Frame(self.scroll_canvas)
        vsb = tk.Scrollbar(self.master, orient="vertical", command=self.scroll_canvas.yview)
        self.scroll_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.scroll_canvas.create_window((4, 4), window=self.frame_cards, anchor="nw", tags="self.frame_cards")
        self.frame_cards.bind("<Configure>", self.on_frame_configure)
        self.refresh_cards()

    def on_frame_configure(self, event: tk.Event) -> None:
        """
        Reset the scroll region of the canvas to encompass the inner frame.
        """
        self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))

    def refresh_cards(self) -> None:
        """
        Refresh the card preview area by recreating the card widgets.
        """
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

            try:
                img = Image.open(card_path)
                w, h = img.size
                new_w = 150
                new_h = int(h * (150 / w))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
            except Exception:
                photo = None

            if photo:
                label_img = tk.Label(card_frame, image=photo)
                label_img.image = photo
                label_img.pack()

            display_name = card if len(card) < 35 else card[:28] + "..." + card[card.rfind('.')-1:]
            tk.Label(card_frame, text=display_name).pack()

            var = tk.IntVar(value=count)
            self.card_vars[card] = var
            btn_sub = tk.Button(card_frame, text="-", command=lambda c=card: self.update_card_count(c, -1))
            btn_sub.pack(side=tk.LEFT, padx=2)
            entry_count = tk.Entry(card_frame, textvariable=var, width=3, justify='center')
            entry_count.pack(side=tk.LEFT, padx=2)
            btn_add = tk.Button(card_frame, text="+", command=lambda c=card: self.update_card_count(c, 1))
            btn_add.pack(side=tk.LEFT, padx=2)

            col += 1
            if col >= col_count:
                col = 0
                row += 1

    def update_card_count(self, card: str, delta: int) -> None:
        """
        Update the count of a specified card.
        """
        current = self.card_vars[card].get()
        new_val = max(0, current + delta)
        self.card_vars[card].set(new_val)
        self.print_dict["cards"][card] = new_val

    def update_paper_size(self) -> None:
        """
        Update the paper size in the project configuration.
        """
        self.print_dict["pagesize"] = self.paper_var.get()

    def update_orientation(self) -> None:
        """
        Update the orientation in the project configuration.
        """
        self.print_dict["orient"] = self.orient_var.get()

    def update_filename(self) -> None:
        """
        Update the PDF filename in the project configuration.
        """
        self.print_dict["filename"] = self.filename_var.get()

    def open_config(self) -> None:
        """
        Open the configuration file for editing.
        """
        try:
            subprocess.Popen([os.path.join(self.cwd, "config.ini")], shell=True)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_project(self) -> None:
        """
        Save the current project configuration to a JSON file.
        """
        with open(self.print_json, "w") as fp:
            json.dump(self.print_dict, fp)
        messagebox.showinfo("Info", "Project saved.")

    def run_cropper(self) -> None:
        """
        Run the cropper to process images.
        """
        wait_win = tk.Toplevel(self.master)
        wait_win.title("Please Wait")
        tk.Label(wait_win, text="Cropping...").pack(padx=20, pady=20)
        self.master.update()
        crop_images(self.image_dir, self.crop_dir, self.cfg)
        # Add any new images to the project configuration.
        for img in os.listdir(self.crop_dir):
            if img not in self.print_dict["cards"]:
                self.print_dict["cards"][img] = 1
        wait_win.destroy()
        self.refresh_cards()

    def render_pdf(self) -> None:
        """
        Render the final PDF document using the current project configuration.
        """
        wait_win = tk.Toplevel(self.master)
        wait_win.title("Please Wait")
        tk.Label(wait_win, text="Rendering PDF...").pack(padx=20, pady=20)
        self.master.update()
        size_map = {"Letter": letter, "A4": A4, "Legal": legal}
        pdf_gen(self.print_dict, size_map[self.print_dict["pagesize"]])
        wait_win.destroy()
