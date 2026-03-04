import tkinter as tk
from tkinter import ttk, messagebox
import socket
from conexion_db import ConexionDB

class VentanaLoginRed(tk.Toplevel):
    def __init__(self, parent, id_torneo, callback_acceso):
        super().__init__(parent)
        self.db = ConexionDB()
        self.id_torneo = id_torneo
        self.callback_acceso = callback_acceso # Función a ejecutar si entra con éxito
        self.nombre_pc = socket.gethostname() # Captura el nombre de la computadora en la red
        
        self.title("Conexión Segura al Torneo")
        
        # Centrar la ventana
        ancho, alto = 400, 250
        x = (self.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.winfo_screenheight() // 2) - (alto // 2)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()

        # Cargar oficiales para el combobox
        self.oficiales = self.db.obtener_oficiales()
        self.nombres_oficiales = [f"{o['apellidos']}, {o['nombre']}" for o in self.oficiales]

        self.crear_interfaz()

    def crear_interfaz(self):
        f_header = tk.Frame(self, bg="#004085")
        f_header.pack(fill="x")
        tk.Label(f_header, text="SISTEMA DE RED - UWW", bg="#004085", fg="white", font=("Helvetica", 12, "bold")).pack(pady=10)

        f_body = tk.Frame(self, padx=20, pady=10)
        f_body.pack(fill="both", expand=True)

        tk.Label(f_body, text=f"💻 Equipo detectado: {self.nombre_pc}", font=("Helvetica", 10, "bold"), fg="#28a745").pack(pady=(0, 15))

        tk.Label(f_body, text="Seleccione al Operador del Software:", font=("Helvetica", 10)).pack(anchor="w")
        self.cmb_oficial = ttk.Combobox(f_body, values=self.nombres_oficiales, state="readonly", width=40)
        self.cmb_oficial.pack(fill="x", pady=5)

        btn_conectar = tk.Button(f_body, text="🌐 Conectar al Torneo", bg="#007bff", fg="white", font=("Helvetica", 11, "bold"), command=self.intentar_conexion)
        btn_conectar.pack(pady=(20, 0), fill="x", ipady=5)

    def intentar_conexion(self):
        idx = self.cmb_oficial.current()
        if idx == -1:
            return messagebox.showwarning("Aviso", "Por favor seleccione su nombre en la lista de oficiales.")
        
        id_oficial = self.oficiales[idx]['id']
        master_actual = self.db.verificar_master_existente(self.id_torneo)
        
        es_master = False
        if not master_actual:
            resp = messagebox.askyesno("Crear Sala", "No hay ningún operador gestionando este torneo actualmente.\n\n¿Deseas abrir la sala y ser el MASTER (Control Total)?")
            if not resp: return
            es_master = True
        else:
            nombre_master = master_actual['nombre_dispositivo']
            resp = messagebox.askyesno("Unirse a Sala", f"El torneo está siendo gestionado por el equipo: {nombre_master}.\n\n¿Deseas solicitar acceso como Cliente / Tapiz Secundario?")
            if not resp: return

        id_conexion = self.db.registrar_conexion_instancia(self.id_torneo, id_oficial, self.nombre_pc, es_master)
        
        if id_conexion:
            tapiz = "Tapiz A" if es_master else "Pendiente"
            self.callback_acceso(id_conexion, es_master, tapiz, id_oficial)
            self.destroy()
        else:
            messagebox.showerror("Error", "No se pudo conectar a la base de datos de red.")