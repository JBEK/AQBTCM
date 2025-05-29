import tkinter as tk
from tkinter import font

root = tk.Tk()
fonts = list(font.families())
fonts.sort()

for f in fonts:
    if "Helvetica" in f or "Neue" in f:
        print(f)

root.destroy()
