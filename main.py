#!/usr/bin/env python3
"""
Main entry point for the PDF Proxy Printer application.
"""

import tkinter as tk
from gui import PDFProxyPrinter

def main() -> None:
    root = tk.Tk()
    root.title("PDF Proxy Printer")
    PDFProxyPrinter(root)
    root.mainloop()

if __name__ == "__main__":
    main()
