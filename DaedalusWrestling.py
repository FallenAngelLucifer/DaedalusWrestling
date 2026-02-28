import tkinter as tk
from tkinter import ttk
from pantalla_inscripcion import PantallaInscripcion
from pantalla_pareo import PantallaPareo

class AplicacionPrincipal(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # Configuración básica de la ventana
        self.title("Daedalus Wrestling - Gestión de Torneos")
        self.geometry("950x650")
        self.minsize(950, 650)

        # Configurar el grid para que el contenedor principal se expanda
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Contenedor donde se cargarán las diferentes pantallas
        self.contenedor = ttk.Frame(self)
        self.contenedor.grid(row=0, column=0, sticky="nsew")
        self.contenedor.grid_rowconfigure(0, weight=1)
        self.contenedor.grid_columnconfigure(0, weight=1)

        # Diccionario para almacenar las pantallas instanciadas
        self.pantallas = {}

        # Inicializar y guardar la pantalla de inscripción
        pantalla = PantallaInscripcion(self.contenedor, self)
        self.pantallas[PantallaInscripcion] = pantalla
        pantalla.grid(row=0, column=0, sticky="nsew")

        p_pareo = PantallaPareo(self.contenedor, self)
        self.pantallas[PantallaPareo] = p_pareo
        p_pareo.grid(row=0, column=0, sticky="nsew")

        # Mostrar la primera fase por defecto
        self.mostrar_pantalla(PantallaInscripcion)

    def mostrar_pantalla(self, clase_pantalla):
        """Eleva la pantalla solicitada al frente del contenedor"""
        pantalla = self.pantallas[clase_pantalla]
        pantalla.tkraise()

if __name__ == "__main__":
    app = AplicacionPrincipal()
    app.mainloop()
