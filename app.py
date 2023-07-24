from tkinter import *
from tkinter import filedialog

def fonction_open():
    filedialog.askopenfilename()

############################################################################
##################################  TKINTER  ###############################
############################################################################
window = Tk ()
window.title("AQBTCM PROGRAM")
window.geometry("720x480")
window.config(background='cyan')

frame=Frame(window, bg='cyan')
# interface = Interface(fenetre)
champ_label = Label(frame, text= "Que voulez-faire ?")
champ_label.pack()


start_button = Button(frame, text="Start", command =window.quit)
start_button.pack(pady=10, fill=X)

pause_button = Button(frame, text="Pause", command =window.quit)
pause_button.pack(pady=10, fill=X)

quit_button = Button(frame, text="Quit", command=window.quit)
quit_button.pack(pady=10, fill=X)


frame.pack (expand=YES)

window.mainloop()
window.destroy()
