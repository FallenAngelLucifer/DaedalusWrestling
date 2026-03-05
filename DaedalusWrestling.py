import tkinter as tk
from tkinter import ttk, messagebox
import socket
import sys      # NUEVO
import atexit   # NUEVO
import signal   # NUEVO
from pantalla_inscripcion import PantallaInscripcion
from pantalla_pareo import PantallaPareo
from conexion_db import ConexionDB

class AplicacionPrincipal(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Daedalus Wrestling - Gestión de Torneos")
        
        ancho, alto = 1050, 700
        x = (self.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.winfo_screenheight() // 2) - (alto // 2)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.minsize(1050, 700)

        # --- VARIABLES DE RED Y SESIÓN ---
        self.db = ConexionDB()
        self.nombre_pc = socket.gethostname()
        self.id_operador = None
        
        # Inicializamos variables globales de conexión para toda la app
        self.id_conexion_red = None
        self.es_master = False
        self.tapiz_asignado = None

        # Atrapamos el evento de cerrar la ventana en la "X"
        self.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)

        # --- NUEVO: ATRAPAR CIERRES FORZOSOS Y CRASHES ---
        atexit.register(self.limpieza_emergencia)
        try:
            # Atrapa el "Stop" de VS Code o Ctrl+C en consola
            signal.signal(signal.SIGINT, self.manejador_senales)
            signal.signal(signal.SIGTERM, self.manejador_senales)
        except ValueError:
            pass # Ignorar si no está corriendo en el hilo principal

        # --- RECONFIGURACIÓN DE LA CUADRÍCULA (GRID) ---
        self.grid_rowconfigure(0, weight=0) # Fila 0 para la barra superior (altura fija)
        self.grid_rowconfigure(1, weight=1) # Fila 1 para el contenido principal (expansible)
        self.grid_columnconfigure(0, weight=1)

        # --- BARRA SUPERIOR DE SESIÓN ---
        self.header_frame = tk.Frame(self, bg="#212529", height=40)
        self.header_frame.grid_propagate(False)
        
        self.lbl_usuario_activo = tk.Label(self.header_frame, text="👤 Árbitro: --", bg="#212529", fg="white", font=("Helvetica", 10, "bold"))
        self.lbl_usuario_activo.pack(side="left", padx=15)
        
        # Nuevos botones alineados a la derecha
        self.btn_cambiar_arbitro = tk.Button(self.header_frame, text="Cambiar Árbitro", bg="#ffc107", fg="black", font=("Helvetica", 9, "bold"), relief="flat", padx=10, cursor="hand2", command=self.abrir_cambiar_arbitro)
        self.btn_cambiar_arbitro.pack(side="right", padx=(0, 15), pady=5)

        self.btn_cerrar_sesion = tk.Button(self.header_frame, text="Cerrar Sesión", bg="#dc3545", fg="white", font=("Helvetica", 9, "bold"), relief="flat", padx=10, cursor="hand2", command=self.cerrar_sesion)
        self.btn_cerrar_sesion.pack(side="right", padx=5, pady=5)

        # --- CONTENEDOR PRINCIPAL DE PANTALLAS ---
        self.contenedor = ttk.Frame(self)
        self.contenedor.grid_rowconfigure(0, weight=1)
        self.contenedor.grid_columnconfigure(0, weight=1)

        self.pantallas = {}

        # --- PANTALLA DE INICIO DE SESIÓN ---
        self.construir_pantalla_login()

        # CORRECCIÓN: El nombre debe ser ciclo_latido_global
        self.ciclo_latido_global()

    # ================= MÉTODOS DE LIMPIEZA Y CIERRE =================
    def limpieza_emergencia(self):
        """Se ejecuta si el programa se cierra forzosamente (X de la ventana o VS Code)."""
        if getattr(self, 'id_conexion_red', None):
            try: self.db.eliminar_conexion_instancia(self.id_conexion_red)
            except Exception: pass 
            
        # --- NUEVO: BORRAR PRESENCIA GLOBAL EN CRASHEO ---
        if getattr(self, 'id_operador', None):
            try: self.db.eliminar_sesion_app(self.id_operador)
            except Exception: pass

    def manejador_senales(self, sig, frame):
        self.cerrar_aplicacion()
        sys.exit(0)

    def cerrar_aplicacion(self):
        self.limpieza_emergencia() 
        self.destroy()

    # ================= GESTIÓN DE SESIONES =================
    def construir_pantalla_login(self):
        self.frame_login = tk.Frame(self, bg="#1e1e1e")
        self.frame_login.grid(row=0, column=0, rowspan=2, sticky="nsew") # Ocupa toda la ventana

        caja = tk.Frame(self.frame_login, bg="#2d2d2d", padx=40, pady=40, highlightbackground="#007bff", highlightthickness=2)
        caja.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(caja, text="DAEDALUS WRESTLING", font=("Helvetica", 18, "bold"), fg="white", bg="#2d2d2d").pack(pady=(0, 20))
        tk.Label(caja, text=f"💻 Dispositivo Local: {self.nombre_pc}", font=("Helvetica", 10), fg="#28a745", bg="#2d2d2d").pack(pady=(0, 20))

        tk.Label(caja, text="Seleccione al Operador (Árbitro) de este equipo:", font=("Helvetica", 10), fg="white", bg="#2d2d2d").pack(anchor="w")

        oficiales = self.db.obtener_oficiales()
        self.lista_oficiales = oficiales
        nombres = [f"{o['apellidos']}, {o['nombre']}" for o in oficiales]

        self.cmb_operador = ttk.Combobox(caja, values=nombres, state="readonly", width=40)
        self.cmb_operador.pack(fill="x", pady=10)

        tk.Button(caja, text="INGRESAR AL SISTEMA", font=("Helvetica", 11, "bold"), bg="#007bff", fg="white", cursor="hand2", command=self.iniciar_sesion).pack(fill="x", pady=(15, 0), ipady=5)

    def iniciar_sesion(self):
        idx = self.cmb_operador.current()
        if idx == -1:
            return messagebox.showwarning("Aviso", "Debe seleccionar un operador para continuar.")

        id_seleccionado = self.lista_oficiales[idx]['id']
        nombre_oficial = f"{self.lista_oficiales[idx]['nombre']} {self.lista_oficiales[idx]['apellidos']}"
        
        # --- NUEVO: TRIGGER DE LIMPIEZA INMEDIATA ---
        # Llamamos a la función con un ID inexistente (0) solo para que ejecute el DELETE por tiempo
        self.db.verificar_oficial_en_uso(0) 

        # Ahora sí, verificamos si el oficial sigue realmente activo tras la purga
        if self.db.verificar_oficial_en_uso(id_seleccionado):
            return messagebox.showerror("Acceso Denegado", f"El árbitro '{nombre_oficial}' ya tiene una sesión activa.")

        # --- NUEVO: REGISTRAR PRESENCIA GLOBAL ---
        import os
        nombre_unico = f"{self.nombre_pc}-{os.getpid()}"
        self.db.registrar_sesion_app(id_seleccionado, nombre_unico)

        self.id_operador = id_seleccionado

        # Iniciar el latido global (Ping de presencia)
        self.latido_global_activo = True
        self.ciclo_latido_global()

        # Actualizar la barra superior y mostrarla
        self.lbl_usuario_activo.config(text=f"👤 Árbitro: {nombre_oficial}   |   💻 {self.nombre_pc}")
        self.header_frame.grid(row=0, column=0, sticky="ew")

        self.frame_login.grid_forget()
        self.contenedor.grid(row=1, column=0, sticky="nsew")

        if not self.pantallas:
            pantalla_ins = PantallaInscripcion(self.contenedor, self)
            self.pantallas[PantallaInscripcion] = pantalla_ins
            pantalla_ins.grid(row=0, column=0, sticky="nsew")

            pantalla_par = PantallaPareo(self.contenedor, self)
            self.pantallas[PantallaPareo] = pantalla_par
            pantalla_par.grid(row=0, column=0, sticky="nsew")

        self.mostrar_pantalla(PantallaInscripcion)

    def ciclo_latido_global(self):
        """Mantiene la sesión de la aplicación viva en la Base de Datos."""
        # Solo actúa si el usuario ya se logueó
        if getattr(self, 'latido_global_activo', False) and getattr(self, 'id_operador', None):
            # Asegúrate de que 'ping_sesion_app' sea el nombre en conexion_db.py
            self.db.ping_sesion_app(self.id_operador) 
            
        # El bucle se mantiene corriendo cada 2 segundos esperando el login
        self.after(2000, self.ciclo_latido_global)

    def cerrar_sesion(self):
        """Maneja el cierre de sesión voluntario del usuario para salir al Login."""
        if messagebox.askyesno("Cerrar Sesión", "¿Está seguro de que desea cerrar sesión y abandonar la sala actual?"):
            if self.id_conexion_red:
                self.db.eliminar_conexion_instancia(self.id_conexion_red)
            
            # Apagar latido y liberar la presencia global
            self.latido_global_activo = False
            if self.id_operador:
                self.db.eliminar_sesion_app(self.id_operador)

            self.id_conexion_red = None
            self.es_master = False
            self.tapiz_asignado = None
            self.id_operador = None

            # Vaciar el torneo en la pantalla principal
            if PantallaInscripcion in self.pantallas:
                self.pantallas[PantallaInscripcion].resetear_torneo(forzar=True)

            # Ocultar la interfaz principal
            self.header_frame.grid_forget()
            self.contenedor.grid_forget()
            
            # Reciclar el Login
            oficiales = self.db.obtener_oficiales()
            self.lista_oficiales = oficiales
            nombres = [f"{o['apellidos']}, {o['nombre']}" for o in oficiales]
            
            self.cmb_operador.config(values=nombres)
            self.cmb_operador.set('')

            # Volver a colocar el Login en la pantalla y forzarlo al frente
            self.frame_login.grid(row=0, column=0, rowspan=2, sticky="nsew")
            self.frame_login.tkraise()

            # --- NUEVO: EL TRUCO DEL EMPUJÓN (NUDGE) PARA FORZAR REDIBUJADO ---
            # 1. Obtenemos el tamaño exacto en este momento
            ancho_actual = self.winfo_width()
            alto_actual = self.winfo_height()
            
            # 2. Engañamos a Windows cambiándola por 1 píxel para forzar el redibujado
            self.geometry(f"{ancho_actual}x{alto_actual + 1}")
            self.update()
            
            # 3. La regresamos a su tamaño original (es tan rápido que el ojo humano no lo nota)
            self.geometry(f"{ancho_actual}x{alto_actual}")

    def abrir_cambiar_arbitro(self):
        """Abre un pop-up para cambiar de árbitro sin salir de la sala de red."""
        ventana = tk.Toplevel(self)
        ventana.title("Cambiar de Árbitro")
        ventana.geometry("400x200")
        ventana.transient(self)
        ventana.grab_set()

        tk.Label(ventana, text="Seleccione el nuevo Árbitro:", font=("Helvetica", 10, "bold")).pack(pady=(20, 10))

        oficiales = self.db.obtener_oficiales()
        nombres = [f"{o['apellidos']}, {o['nombre']}" for o in oficiales]

        cmb = ttk.Combobox(ventana, values=nombres, state="readonly", width=40)
        cmb.pack(pady=10)

        def confirmar_cambio():
            idx = cmb.current()
            if idx == -1: return messagebox.showwarning("Aviso", "Seleccione un árbitro.", parent=ventana)
            
            nuevo_id = oficiales[idx]['id']
            if nuevo_id == self.id_operador:
                return messagebox.showinfo("Aviso", "Ya está operando con este árbitro.", parent=ventana)

            # --- NUEVO: Purga automática antes de validar ---
            if hasattr(self.db, 'verificar_oficial_en_uso'):
                self.db.verificar_oficial_en_uso(0)

            if self.db.verificar_oficial_en_uso(nuevo_id):
                return messagebox.showerror("Denegado", "Ese árbitro ya está activo en otro equipo.", parent=ventana)

            # --- NUEVO: GESTIÓN DE SESIONES GLOBALES AL CAMBIAR ---
            # 1. Liberamos al usuario viejo de la app global
            self.db.eliminar_sesion_app(self.id_operador)

            # 2. Actualizamos en la sala de torneo si es que estaba dentro de una
            if self.id_conexion_red:
                self.db.actualizar_oficial_conexion(self.id_conexion_red, nuevo_id)
            
            # 3. Registramos al usuario nuevo en la app global
            import os
            nombre_unico = f"{self.nombre_pc}-{os.getpid()}"
            self.db.registrar_sesion_app(nuevo_id, nombre_unico)

            self.id_operador = nuevo_id
            nombre_oficial = f"{oficiales[idx]['nombre']} {oficiales[idx]['apellidos']}"
            self.lbl_usuario_activo.config(text=f"👤 Árbitro: {nombre_oficial}   |   💻 {self.nombre_pc}")
            
            messagebox.showinfo("Éxito", f"Sesión cambiada a {nombre_oficial}.", parent=ventana)
            ventana.destroy()

        tk.Button(ventana, text="Confirmar Cambio", bg="#28a745", fg="white", cursor="hand2", command=confirmar_cambio).pack(pady=10)

    def mostrar_pantalla(self, cont):
        frame = self.pantallas[cont]
        frame.tkraise()

if __name__ == "__main__":
    app = AplicacionPrincipal()
    app.mainloop()