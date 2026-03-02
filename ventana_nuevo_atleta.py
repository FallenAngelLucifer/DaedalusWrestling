import tkinter as tk
from tkinter import ttk, messagebox
import calendar
from tkcalendar import Calendar
from datetime import datetime
from conexion_db import ConexionDB
from utilidades import ComboBuscador, aplicar_formato_fecha, aplicar_formato_cedula

class VentanaNuevoRegistro(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.db = ConexionDB()
        
        self.title("Gestión Completa de Catálogos y Atletas")

        # --- CENTRAR Y AMPLIAR VENTANA PARA LAS SUB-PESTAÑAS ---
        ancho, alto = 500, 450
        x = (self.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.winfo_screenheight() // 2) - (alto // 2)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.resizable(False, False)
        self.transient(parent)

        # Diccionarios de mapeo para ID's rápidos
        self.map_deptos = {}; self.map_ciudades = {}; self.map_clubes = {}
        self.map_colegios = {}; self.map_oficiales = {}; self.map_atletas = {}
        
        # Guardamos los registros completos para la edición
        self.db_deptos = []; self.db_ciudades = []; self.db_clubes = []
        self.db_colegios = []; self.db_oficiales = []; self.db_atletas = []

        self.crear_interfaz()
        self.cargar_datos_combos()

    # ================= FUNCIONES DE CONTROL DINÁMICO =================
    def set_estado_controles(self, controles, estado):
        """Bloquea o desbloquea una lista de controles."""
        for ctrl in controles:
            ctrl.config(state=estado)

    def limpiar_controles(self, controles):
        """Vacía el contenido de los controles sin afectar su estado bloqueado."""
        for ctrl in controles:
            if isinstance(ctrl, ttk.Button): continue
            est_previo = ctrl.cget("state")
            if est_previo == "disabled": ctrl.config(state="normal")
            
            if isinstance(ctrl, ComboBuscador) or isinstance(ctrl, ttk.Combobox):
                ctrl.set('')
            elif isinstance(ctrl, (ttk.Entry, tk.Entry)):
                ctrl.delete(0, tk.END)
                
            if est_previo == "disabled": ctrl.config(state="disabled")

    def evaluar_bloqueo_edicion(self, combo, lista_validos, controles, funcion_carga):
        """Vigila el buscador: Si el dato es válido, carga y desbloquea. Si no, limpia y bloquea."""
        texto = combo.get()
        if texto in lista_validos and texto != "":
            self.set_estado_controles(controles, "normal")
            funcion_carga(texto)
        else:
            self.limpiar_controles(controles)
            self.set_estado_controles(controles, "disabled")

    def crear_sub_tabs(self, parent_tab):
        """Generador rápido de sub-pestañas Añadir/Editar."""
        sub_nb = ttk.Notebook(parent_tab)
        sub_nb.pack(fill="both", expand=True, padx=10, pady=10)
        tab_add = ttk.Frame(sub_nb, padding=10)
        tab_edit = ttk.Frame(sub_nb, padding=10)
        sub_nb.add(tab_add, text="➕ Añadir Nuevo")
        sub_nb.add(tab_edit, text="✏️ Editar Existente")
        return tab_add, tab_edit

    # ================= INTERFAZ PRINCIPAL =================
    def crear_interfaz(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=5, pady=5)

        tab_atl = ttk.Frame(notebook); notebook.add(tab_atl, text="Atletas")
        tab_clu = ttk.Frame(notebook); notebook.add(tab_clu, text="Clubes")
        tab_col = ttk.Frame(notebook); notebook.add(tab_col, text="Colegios")
        tab_ciu = ttk.Frame(notebook); notebook.add(tab_ciu, text="Ciudades / Deptos")
        tab_arb = ttk.Frame(notebook); notebook.add(tab_arb, text="Oficiales de Arbitraje")

        self._construir_seccion_atleta(tab_atl)
        self._construir_seccion_club(tab_clu)
        self._construir_seccion_colegio(tab_col)
        self._construir_seccion_ciudad(tab_ciu)
        self._construir_seccion_arbitro(tab_arb)

    # ================= SECCIÓN: ATLETAS =================
    def _construir_seccion_atleta(self, parent_tab):
        tab_add, tab_edit = self.crear_sub_tabs(parent_tab)

        # --- AÑADIR ---
        ttk.Label(tab_add, text="Nombres:").grid(row=0, column=0, sticky="w", pady=5); self.ent_atl_nombres = ttk.Entry(tab_add, width=35); self.ent_atl_nombres.grid(row=0, column=1, pady=5)
        ttk.Label(tab_add, text="Apellidos:").grid(row=1, column=0, sticky="w", pady=5); self.ent_atl_apellidos = ttk.Entry(tab_add, width=35); self.ent_atl_apellidos.grid(row=1, column=1, pady=5)
        
        ttk.Label(tab_add, text="Fecha Nac.:").grid(row=2, column=0, sticky="w", pady=5)
        f_atl_frame = ttk.Frame(tab_add); f_atl_frame.grid(row=2, column=1, pady=5, sticky="w")
        self.ent_atl_fecha = ttk.Entry(f_atl_frame, width=25); self.ent_atl_fecha.pack(side="left", padx=(0, 5)); aplicar_formato_fecha(self.ent_atl_fecha)
        ttk.Button(f_atl_frame, text="📅", width=3, command=lambda: self.abrir_calendario(self.ent_atl_fecha)).pack(side="left")

        ttk.Label(tab_add, text="Sexo:").grid(row=3, column=0, sticky="w", pady=5); self.cmb_atl_sexo = ComboBuscador(tab_add, values=["M", "F"], state="readonly", width=33); self.cmb_atl_sexo.grid(row=3, column=1, pady=5)
        ttk.Label(tab_add, text="Club:").grid(row=4, column=0, sticky="w", pady=5); self.cmb_atl_club = ComboBuscador(tab_add, state="readonly", width=33); self.cmb_atl_club.grid(row=4, column=1, pady=5)
        ttk.Label(tab_add, text="Colegio:").grid(row=5, column=0, sticky="w", pady=5); self.cmb_atl_colegio = ComboBuscador(tab_add, state="readonly", width=33); self.cmb_atl_colegio.grid(row=5, column=1, pady=5)
        ttk.Button(tab_add, text="Guardar Atleta", command=self.guardar_atleta).grid(row=6, column=0, columnspan=2, pady=15)

        # --- EDITAR ---
        ttk.Label(tab_edit, text="Buscar Atleta:").grid(row=0, column=0, sticky="w", pady=5)
        self.cmb_ed_sel_atl = ComboBuscador(tab_edit, state="normal", width=33)
        self.cmb_ed_sel_atl.grid(row=0, column=1, pady=5)
        ttk.Separator(tab_edit, orient='horizontal').grid(row=1, column=0, columnspan=2, sticky='ew', pady=5)

        self.ent_ed_nombres = ttk.Entry(tab_edit, width=35); self.ent_ed_apellidos = ttk.Entry(tab_edit, width=35)
        f_ed_frame = ttk.Frame(tab_edit)
        self.ent_ed_fecha = ttk.Entry(f_ed_frame, width=25); self.ent_ed_fecha.pack(side="left", padx=(0, 5)); aplicar_formato_fecha(self.ent_ed_fecha)
        self.btn_cal_ed_atl = ttk.Button(f_ed_frame, text="📅", width=3, command=lambda: self.abrir_calendario(self.ent_ed_fecha)); self.btn_cal_ed_atl.pack(side="left")
        
        self.cmb_ed_sexo = ComboBuscador(tab_edit, values=["M", "F"], state="readonly", width=33)
        self.cmb_ed_club = ComboBuscador(tab_edit, state="readonly", width=33)
        self.cmb_ed_colegio = ComboBuscador(tab_edit, state="readonly", width=33)
        self.btn_ed_atl_guardar = ttk.Button(tab_edit, text="Actualizar Atleta", command=self.actualizar_atleta_db)

        ttk.Label(tab_edit, text="Nombres:").grid(row=2, column=0, sticky="w", pady=5); self.ent_ed_nombres.grid(row=2, column=1, pady=5)
        ttk.Label(tab_edit, text="Apellidos:").grid(row=3, column=0, sticky="w", pady=5); self.ent_ed_apellidos.grid(row=3, column=1, pady=5)
        ttk.Label(tab_edit, text="Fecha Nac.:").grid(row=4, column=0, sticky="w", pady=5); f_ed_frame.grid(row=4, column=1, pady=5, sticky="w")
        ttk.Label(tab_edit, text="Sexo:").grid(row=5, column=0, sticky="w", pady=5); self.cmb_ed_sexo.grid(row=5, column=1, pady=5)
        ttk.Label(tab_edit, text="Club:").grid(row=6, column=0, sticky="w", pady=5); self.cmb_ed_club.grid(row=6, column=1, pady=5)
        ttk.Label(tab_edit, text="Colegio:").grid(row=7, column=0, sticky="w", pady=5); self.cmb_ed_colegio.grid(row=7, column=1, pady=5)
        self.btn_ed_atl_guardar.grid(row=8, column=0, columnspan=2, pady=15)

        self.ctrls_ed_atl = [self.ent_ed_nombres, self.ent_ed_apellidos, self.ent_ed_fecha, self.cmb_ed_sexo, self.cmb_ed_club, self.cmb_ed_colegio, self.btn_ed_atl_guardar, self.btn_cal_ed_atl]
        self.cmb_ed_sel_atl.bind("<<ComboboxSelected>>", lambda e: self.evaluar_bloqueo_edicion(self.cmb_ed_sel_atl, list(self.map_atletas.keys()), self.ctrls_ed_atl, self.cargar_datos_edicion_atleta))
        self.cmb_ed_sel_atl.bind("<KeyRelease>", lambda e: self.evaluar_bloqueo_edicion(self.cmb_ed_sel_atl, list(self.map_atletas.keys()), self.ctrls_ed_atl, self.cargar_datos_edicion_atleta), add="+")
        self.set_estado_controles(self.ctrls_ed_atl, "disabled")

    # ================= SECCIÓN: CLUBES =================
    def _construir_seccion_club(self, parent_tab):
        tab_add, tab_edit = self.crear_sub_tabs(parent_tab)

        # Añadir
        ttk.Label(tab_add, text="Ciudad Base:").grid(row=0, column=0, sticky="w", pady=5); self.cmb_club_ciudad = ComboBuscador(tab_add, state="readonly", width=33); self.cmb_club_ciudad.grid(row=0, column=1, pady=5)
        ttk.Label(tab_add, text="Nombre del Club:").grid(row=1, column=0, sticky="w", pady=5); self.ent_club_nombre = ttk.Entry(tab_add, width=35); self.ent_club_nombre.grid(row=1, column=1, pady=5)
        ttk.Button(tab_add, text="Guardar Club", command=self.guardar_club).grid(row=2, column=0, columnspan=2, pady=20)

        # Editar
        ttk.Label(tab_edit, text="Buscar Club:").grid(row=0, column=0, sticky="w", pady=5)
        self.cmb_ed_sel_club = ComboBuscador(tab_edit, state="normal", width=33)
        self.cmb_ed_sel_club.grid(row=0, column=1, pady=5)
        ttk.Separator(tab_edit, orient='horizontal').grid(row=1, column=0, columnspan=2, sticky='ew', pady=5)

        self.cmb_ed_club_ciudad = ComboBuscador(tab_edit, state="readonly", width=33)
        self.ent_ed_club_nombre = ttk.Entry(tab_edit, width=35)
        self.btn_ed_club_guardar = ttk.Button(tab_edit, text="Actualizar Club", command=self.actualizar_club_db)

        ttk.Label(tab_edit, text="Ciudad Base:").grid(row=2, column=0, sticky="w", pady=5); self.cmb_ed_club_ciudad.grid(row=2, column=1, pady=5)
        ttk.Label(tab_edit, text="Nombre del Club:").grid(row=3, column=0, sticky="w", pady=5); self.ent_ed_club_nombre.grid(row=3, column=1, pady=5)
        self.btn_ed_club_guardar.grid(row=4, column=0, columnspan=2, pady=15)

        self.ctrls_ed_club = [self.cmb_ed_club_ciudad, self.ent_ed_club_nombre, self.btn_ed_club_guardar]
        self.cmb_ed_sel_club.bind("<<ComboboxSelected>>", lambda e: self.evaluar_bloqueo_edicion(self.cmb_ed_sel_club, list(self.map_clubes.keys()), self.ctrls_ed_club, self.cargar_datos_edicion_club))
        self.cmb_ed_sel_club.bind("<KeyRelease>", lambda e: self.evaluar_bloqueo_edicion(self.cmb_ed_sel_club, list(self.map_clubes.keys()), self.ctrls_ed_club, self.cargar_datos_edicion_club), add="+")
        self.set_estado_controles(self.ctrls_ed_club, "disabled")

    # ================= SECCIÓN: COLEGIOS =================
    def _construir_seccion_colegio(self, parent_tab):
        tab_add, tab_edit = self.crear_sub_tabs(parent_tab)

        # Añadir
        ttk.Label(tab_add, text="Nombre del Colegio:").grid(row=0, column=0, sticky="w", pady=5); self.ent_col_nombre = ttk.Entry(tab_add, width=40); self.ent_col_nombre.grid(row=0, column=1, pady=5)
        ttk.Button(tab_add, text="Guardar Colegio", command=self.guardar_colegio).grid(row=1, column=0, columnspan=2, pady=20)

        # Editar
        ttk.Label(tab_edit, text="Buscar Colegio:").grid(row=0, column=0, sticky="w", pady=5)
        self.cmb_ed_sel_col = ComboBuscador(tab_edit, state="normal", width=38)
        self.cmb_ed_sel_col.grid(row=0, column=1, pady=5)
        ttk.Separator(tab_edit, orient='horizontal').grid(row=1, column=0, columnspan=2, sticky='ew', pady=5)

        self.ent_ed_col_nombre = ttk.Entry(tab_edit, width=40)
        self.btn_ed_col_guardar = ttk.Button(tab_edit, text="Actualizar Colegio", command=self.actualizar_colegio_db)

        ttk.Label(tab_edit, text="Nombre del Colegio:").grid(row=2, column=0, sticky="w", pady=5); self.ent_ed_col_nombre.grid(row=2, column=1, pady=5)
        self.btn_ed_col_guardar.grid(row=3, column=0, columnspan=2, pady=15)

        self.ctrls_ed_col = [self.ent_ed_col_nombre, self.btn_ed_col_guardar]
        self.cmb_ed_sel_col.bind("<<ComboboxSelected>>", lambda e: self.evaluar_bloqueo_edicion(self.cmb_ed_sel_col, list(self.map_colegios.keys()), self.ctrls_ed_col, self.cargar_datos_edicion_col))
        self.cmb_ed_sel_col.bind("<KeyRelease>", lambda e: self.evaluar_bloqueo_edicion(self.cmb_ed_sel_col, list(self.map_colegios.keys()), self.ctrls_ed_col, self.cargar_datos_edicion_col), add="+")
        self.set_estado_controles(self.ctrls_ed_col, "disabled")

    # ================= SECCIÓN: CIUDADES Y DEPTOS =================
    def _construir_seccion_ciudad(self, parent_tab):
        tab_add, tab_edit = self.crear_sub_tabs(parent_tab)

        # Añadir
        ttk.Label(tab_add, text="Departamento:").grid(row=0, column=0, sticky="w", pady=5); self.cmb_ciu_depto = ComboBuscador(tab_add, state="readonly", width=33); self.cmb_ciu_depto.grid(row=0, column=1, pady=5)
        ttk.Label(tab_add, text="Nombre Ciudad:").grid(row=1, column=0, sticky="w", pady=5); self.ent_ciu_nombre = ttk.Entry(tab_add, width=35); self.ent_ciu_nombre.grid(row=1, column=1, pady=5)
        ttk.Button(tab_add, text="Guardar Ciudad", command=self.guardar_ciudad).grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Separator(tab_add, orient='horizontal').grid(row=3, column=0, columnspan=2, sticky='ew', pady=10)
        ttk.Label(tab_add, text="Nuevo Departamento:").grid(row=4, column=0, sticky="w", pady=5); self.ent_dep_nombre = ttk.Entry(tab_add, width=35); self.ent_dep_nombre.grid(row=4, column=1, pady=5)
        ttk.Button(tab_add, text="Guardar Depto", command=self.guardar_departamento).grid(row=5, column=0, columnspan=2, pady=5)

        # Editar (Solo Ciudades)
        ttk.Label(tab_edit, text="Buscar Ciudad:").grid(row=0, column=0, sticky="w", pady=5)
        self.cmb_ed_sel_ciu = ComboBuscador(tab_edit, state="normal", width=33)
        self.cmb_ed_sel_ciu.grid(row=0, column=1, pady=5)
        ttk.Separator(tab_edit, orient='horizontal').grid(row=1, column=0, columnspan=2, sticky='ew', pady=5)

        self.cmb_ed_ciu_depto = ComboBuscador(tab_edit, state="readonly", width=33)
        self.ent_ed_ciu_nombre = ttk.Entry(tab_edit, width=35)
        self.btn_ed_ciu_guardar = ttk.Button(tab_edit, text="Actualizar Ciudad", command=self.actualizar_ciudad_db)

        ttk.Label(tab_edit, text="Departamento:").grid(row=2, column=0, sticky="w", pady=5); self.cmb_ed_ciu_depto.grid(row=2, column=1, pady=5)
        ttk.Label(tab_edit, text="Nombre Ciudad:").grid(row=3, column=0, sticky="w", pady=5); self.ent_ed_ciu_nombre.grid(row=3, column=1, pady=5)
        self.btn_ed_ciu_guardar.grid(row=4, column=0, columnspan=2, pady=15)

        self.ctrls_ed_ciu = [self.cmb_ed_ciu_depto, self.ent_ed_ciu_nombre, self.btn_ed_ciu_guardar]
        self.cmb_ed_sel_ciu.bind("<<ComboboxSelected>>", lambda e: self.evaluar_bloqueo_edicion(self.cmb_ed_sel_ciu, list(self.map_ciudades.keys()), self.ctrls_ed_ciu, self.cargar_datos_edicion_ciu))
        self.cmb_ed_sel_ciu.bind("<KeyRelease>", lambda e: self.evaluar_bloqueo_edicion(self.cmb_ed_sel_ciu, list(self.map_ciudades.keys()), self.ctrls_ed_ciu, self.cargar_datos_edicion_ciu), add="+")
        self.set_estado_controles(self.ctrls_ed_ciu, "disabled")

    # ================= SECCIÓN: ÁRBITROS =================
    def _construir_seccion_arbitro(self, parent_tab):
        tab_add, tab_edit = self.crear_sub_tabs(parent_tab)

        # Añadir
        ttk.Label(tab_add, text="Nombres:").grid(row=0, column=0, sticky="w", pady=5); self.ent_arb_nombres = ttk.Entry(tab_add, width=35); self.ent_arb_nombres.grid(row=0, column=1, pady=5)
        ttk.Label(tab_add, text="Apellidos:").grid(row=1, column=0, sticky="w", pady=5); self.ent_arb_apellidos = ttk.Entry(tab_add, width=35); self.ent_arb_apellidos.grid(row=1, column=1, pady=5)
        ttk.Label(tab_add, text="Cédula:").grid(row=2, column=0, sticky="w", pady=5); self.ent_arb_cedula = ttk.Entry(tab_add, width=35); self.ent_arb_cedula.grid(row=2, column=1, pady=5); aplicar_formato_cedula(self.ent_arb_cedula)
        ttk.Label(tab_add, text="Correo:").grid(row=3, column=0, sticky="w", pady=5); self.ent_arb_correo = ttk.Entry(tab_add, width=35); self.ent_arb_correo.grid(row=3, column=1, pady=5)
        ttk.Label(tab_add, text="Celular:").grid(row=4, column=0, sticky="w", pady=5); self.ent_arb_celular = ttk.Entry(tab_add, width=35); self.ent_arb_celular.grid(row=4, column=1, pady=5)
        ttk.Button(tab_add, text="Guardar Oficial / Árbitro", command=self.guardar_arbitro).grid(row=5, column=0, columnspan=2, pady=15)

        # Editar
        ttk.Label(tab_edit, text="Buscar Árbitro:").grid(row=0, column=0, sticky="w", pady=5)
        self.cmb_ed_sel_arb = ComboBuscador(tab_edit, state="normal", width=33)
        self.cmb_ed_sel_arb.grid(row=0, column=1, pady=5)
        ttk.Separator(tab_edit, orient='horizontal').grid(row=1, column=0, columnspan=2, sticky='ew', pady=5)

        self.ent_ed_arb_nombres = ttk.Entry(tab_edit, width=35)
        self.ent_ed_arb_apellidos = ttk.Entry(tab_edit, width=35)
        self.ent_ed_arb_ced = ttk.Entry(tab_edit, width=35); aplicar_formato_cedula(self.ent_ed_arb_ced)
        self.ent_ed_arb_cor = ttk.Entry(tab_edit, width=35)
        self.ent_ed_arb_cel = ttk.Entry(tab_edit, width=35)
        self.btn_ed_arb_guardar = ttk.Button(tab_edit, text="Actualizar Árbitro", command=self.actualizar_arbitro_db)

        ttk.Label(tab_edit, text="Nombres:").grid(row=2, column=0, sticky="w", pady=5); self.ent_ed_arb_nombres.grid(row=2, column=1, pady=5)
        ttk.Label(tab_edit, text="Apellidos:").grid(row=3, column=0, sticky="w", pady=5); self.ent_ed_arb_apellidos.grid(row=3, column=1, pady=5)
        ttk.Label(tab_edit, text="Cédula:").grid(row=4, column=0, sticky="w", pady=5); self.ent_ed_arb_ced.grid(row=4, column=1, pady=5)
        ttk.Label(tab_edit, text="Correo:").grid(row=5, column=0, sticky="w", pady=5); self.ent_ed_arb_cor.grid(row=5, column=1, pady=5)
        ttk.Label(tab_edit, text="Celular:").grid(row=6, column=0, sticky="w", pady=5); self.ent_ed_arb_cel.grid(row=6, column=1, pady=5)
        self.btn_ed_arb_guardar.grid(row=7, column=0, columnspan=2, pady=15)

        self.ctrls_ed_arb = [self.ent_ed_arb_nombres, self.ent_ed_arb_apellidos, self.ent_ed_arb_ced, self.ent_ed_arb_cor, self.ent_ed_arb_cel, self.btn_ed_arb_guardar]
        self.cmb_ed_sel_arb.bind("<<ComboboxSelected>>", lambda e: self.evaluar_bloqueo_edicion(self.cmb_ed_sel_arb, list(self.map_oficiales.keys()), self.ctrls_ed_arb, self.cargar_datos_edicion_arb))
        self.cmb_ed_sel_arb.bind("<KeyRelease>", lambda e: self.evaluar_bloqueo_edicion(self.cmb_ed_sel_arb, list(self.map_oficiales.keys()), self.ctrls_ed_arb, self.cargar_datos_edicion_arb), add="+")
        self.set_estado_controles(self.ctrls_ed_arb, "disabled")

    # ================= CALENDARIO =================
    def abrir_calendario(self, entry_objetivo):
        top_cal = tk.Toplevel(self)
        top_cal.title("Calendario")
        ancho, alto = 260, 260
        x = (self.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.winfo_screenheight() // 2) - (alto // 2)
        top_cal.geometry(f"{ancho}x{alto}+{x}+{y}")
        top_cal.resizable(False, False)
        top_cal.transient(self)
        top_cal.grab_set() 

        texto_fecha = entry_objetivo.get().strip()
        sel_year, sel_month, sel_day = 2006, 1, 1 

        if texto_fecha:
            try:
                fecha_obj = datetime.strptime(texto_fecha, "%d/%m/%Y")
                sel_year, sel_month, sel_day = fecha_obj.year, fecha_obj.month, fecha_obj.day
            except ValueError:
                partes = texto_fecha.split('/')
                if len(partes) == 3:
                    try:
                        y = int(partes[2]); sel_year = max(1900, min(y, 2100)) 
                        m = int(partes[1]); sel_month = max(1, min(m, 12))     
                        d = int(partes[0]); max_day = calendar.monthrange(sel_year, sel_month)[1]; sel_day = max(1, min(d, max_day))  
                    except ValueError: pass 

        cal = Calendar(top_cal, selectmode='day', date_pattern='dd/mm/yyyy', year=sel_year, month=sel_month, day=sel_day)
        cal.pack(pady=10, padx=10, fill="both", expand=True)
        
        def confirmar_fecha():
            entry_objetivo.delete(0, tk.END)
            entry_objetivo.insert(0, cal.get_date())
            entry_objetivo.icursor(tk.END) 
            top_cal.destroy()
            
        ttk.Button(top_cal, text="Confirmar Fecha", command=confirmar_fecha).pack(pady=5)

    # ================= CARGA DE DATOS GENERALES =================
    def cargar_datos_combos(self):
        self.db_deptos = self.db.obtener_departamentos()
        self.map_deptos = {d['nombre']: d['id'] for d in self.db_deptos}
        
        self.db_ciudades = self.db.obtener_ciudades()
        self.map_ciudades = {f"{c['nombre']} ({c['departamento']})": c['id'] for c in self.db_ciudades}

        self.db_clubes = self.db.obtener_clubes()
        self.map_clubes = {c['nombre']: c['id'] for c in self.db_clubes}

        self.db_colegios = self.db.obtener_colegios()
        self.map_colegios = {c['nombre']: c['id'] for c in self.db_colegios}

        self.db_oficiales = self.db.obtener_oficiales()
        self.map_oficiales = {f"{o['apellidos']}, {o['nombre']} ({o['cedula']})": o['id'] for o in self.db_oficiales}

        self.db_atletas = self.db.obtener_atletas()
        self.map_atletas = {f"{a['apellidos']}, {a['nombre']} (ID: {a['id']})": a['id'] for a in self.db_atletas}

        # Actualizar opciones de los combobox en UI
        self.cmb_ciu_depto.config(values=list(self.map_deptos.keys()))
        self.cmb_ed_ciu_depto.config(values=list(self.map_deptos.keys()))

        self.cmb_club_ciudad.config(values=list(self.map_ciudades.keys()))
        self.cmb_ed_sel_ciu.config(values=list(self.map_ciudades.keys()))

        self.cmb_atl_club.config(values=list(self.map_clubes.keys()))
        self.cmb_ed_club.config(values=list(self.map_clubes.keys()))
        self.cmb_ed_sel_club.config(values=list(self.map_clubes.keys()))

        self.cmb_atl_colegio.config(values=list(self.map_colegios.keys()))
        self.cmb_ed_colegio.config(values=list(self.map_colegios.keys()))
        self.cmb_ed_sel_col.config(values=list(self.map_colegios.keys()))

        self.cmb_ed_sel_arb.config(values=list(self.map_oficiales.keys()))
        self.cmb_ed_sel_atl.config(values=list(self.map_atletas.keys()))

    # ================= CARGA INDIVIDUAL PARA EDICIÓN =================
    def cargar_datos_edicion_atleta(self, texto_buscado):
        id_obj = self.map_atletas[texto_buscado]
        atleta = next(a for a in self.db_atletas if a['id'] == id_obj)
        self.ent_ed_nombres.delete(0, tk.END); self.ent_ed_nombres.insert(0, atleta['nombre'])
        self.ent_ed_apellidos.delete(0, tk.END); self.ent_ed_apellidos.insert(0, atleta['apellidos'])
        self.ent_ed_fecha.delete(0, tk.END); self.ent_ed_fecha.insert(0, atleta['fecha_nacimiento'].strftime("%d/%m/%Y"))
        self.cmb_ed_sexo.set(atleta['sexo'])
        self.cmb_ed_club.set(atleta['club'] if atleta['club'] else '')
        self.cmb_ed_colegio.set(atleta['colegio'] if atleta['colegio'] else '')

    def cargar_datos_edicion_club(self, texto_buscado):
        id_obj = self.map_clubes[texto_buscado]
        club = next(c for c in self.db_clubes if c['id'] == id_obj)
        self.ent_ed_club_nombre.delete(0, tk.END); self.ent_ed_club_nombre.insert(0, club['nombre'])
        ciudad_formato = f"{club['ciudad']} ({club['departamento']})"
        self.cmb_ed_club_ciudad.set(ciudad_formato)

    def cargar_datos_edicion_col(self, texto_buscado):
        self.ent_ed_col_nombre.delete(0, tk.END); self.ent_ed_col_nombre.insert(0, texto_buscado)

    def cargar_datos_edicion_ciu(self, texto_buscado):
        id_obj = self.map_ciudades[texto_buscado]
        ciudad = next(c for c in self.db_ciudades if c['id'] == id_obj)
        self.ent_ed_ciu_nombre.delete(0, tk.END); self.ent_ed_ciu_nombre.insert(0, ciudad['nombre'])
        self.cmb_ed_ciu_depto.set(ciudad['departamento'])

    def cargar_datos_edicion_arb(self, texto_buscado):
        id_obj = self.map_oficiales[texto_buscado]
        oficial = next(o for o in self.db_oficiales if o['id'] == id_obj)
        self.ent_ed_arb_nombres.delete(0, tk.END); self.ent_ed_arb_nombres.insert(0, oficial['nombre'])
        self.ent_ed_arb_apellidos.delete(0, tk.END); self.ent_ed_arb_apellidos.insert(0, oficial['apellidos'])
        self.ent_ed_arb_ced.delete(0, tk.END); self.ent_ed_arb_ced.insert(0, oficial['cedula'])
        self.ent_ed_arb_cor.delete(0, tk.END); self.ent_ed_arb_cor.insert(0, oficial['correo'] if oficial['correo'] else "")
        self.ent_ed_arb_cel.delete(0, tk.END); self.ent_ed_arb_cel.insert(0, oficial['celular'] if oficial['celular'] else "")

    # ================= GUARDADO NUEVO =================
    def guardar_atleta(self):
        nombres = self.ent_atl_nombres.get().strip().title(); apellidos = self.ent_atl_apellidos.get().strip().title()
        sexo = self.cmb_atl_sexo.get(); club_sel = self.cmb_atl_club.get(); colegio_sel = self.cmb_atl_colegio.get()
        try: fecha_db = datetime.strptime(self.ent_atl_fecha.get().strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
        except: return messagebox.showerror("Error", "Formato de fecha inválido.", parent=self)

        if not all([nombres, apellidos, sexo, club_sel, fecha_db]): return messagebox.showwarning("Error", "Complete todos los campos obligatorios.", parent=self)
        if self.db.insertar_peleador(nombres, apellidos, fecha_db, sexo, self.map_clubes.get(club_sel), self.map_colegios.get(colegio_sel)):
            messagebox.showinfo("Éxito", "Atleta guardado.", parent=self)
            self.cargar_datos_combos(); self.ent_atl_nombres.delete(0, tk.END); self.ent_atl_apellidos.delete(0, tk.END); self.cmb_atl_colegio.set('')
            if hasattr(self.parent, 'cargar_datos_bd'): self.parent.cargar_datos_bd()

    def guardar_colegio(self):
        nombre = self.ent_col_nombre.get().strip().title()
        if not nombre: return
        if self.db.insertar_colegio(nombre):
            messagebox.showinfo("Éxito", "Colegio guardado.", parent=self); self.ent_col_nombre.delete(0, tk.END); self.cargar_datos_combos()
            
    def guardar_arbitro(self):
        nom = self.ent_arb_nombres.get().strip().title(); ape = self.ent_arb_apellidos.get().strip().title(); ced = self.ent_arb_cedula.get().strip()
        cor = self.ent_arb_correo.get().strip() or None; cel = self.ent_arb_celular.get().strip() or None
        if not nom or not ape or not ced: return messagebox.showwarning("Error", "Faltan datos obligatorios.", parent=self)
        if self.db.insertar_oficial(nom, ape, ced, cor, cel):
            messagebox.showinfo("Éxito", "Oficial / Árbitro guardado.", parent=self)
            self.limpiar_controles([self.ent_arb_nombres, self.ent_arb_apellidos, self.ent_arb_cedula, self.ent_arb_correo, self.ent_arb_celular]); self.cargar_datos_combos()

    def guardar_club(self):
        ciu = self.cmb_club_ciudad.get(); nom = self.ent_club_nombre.get().strip().title()
        if not ciu or not nom: return
        if self.db.insertar_club(self.map_ciudades[ciu], nom):
            messagebox.showinfo("Éxito", "Club guardado.", parent=self); self.ent_club_nombre.delete(0, tk.END); self.cargar_datos_combos()

    def guardar_ciudad(self):
        dep = self.cmb_ciu_depto.get(); nom = self.ent_ciu_nombre.get().strip().title()
        if not dep or not nom: return
        if self.db.insertar_ciudad(self.map_deptos[dep], nom):
            messagebox.showinfo("Éxito", "Ciudad guardada.", parent=self); self.ent_ciu_nombre.delete(0, tk.END); self.cargar_datos_combos()

    def guardar_departamento(self):
        nom = self.ent_dep_nombre.get().strip().title()
        if not nom: return
        if self.db.insertar_departamento(nom):
            messagebox.showinfo("Éxito", "Depto guardado.", parent=self); self.ent_dep_nombre.delete(0, tk.END); self.cargar_datos_combos()

    # ================= ACTUALIZACIONES EN BD =================
    def actualizar_atleta_db(self):
        id_obj = self.map_atletas[self.cmb_ed_sel_atl.get()]
        nombres = self.ent_ed_nombres.get().strip().title(); apellidos = self.ent_ed_apellidos.get().strip().title()
        sexo = self.cmb_ed_sexo.get(); club_sel = self.cmb_ed_club.get(); colegio_sel = self.cmb_ed_colegio.get()
        try: fecha_db = datetime.strptime(self.ent_ed_fecha.get().strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
        except: return messagebox.showerror("Error", "Formato de fecha inválido.", parent=self)
        
        if self.db.actualizar_peleador(id_obj, nombres, apellidos, fecha_db, sexo, self.map_clubes.get(club_sel), self.map_colegios.get(colegio_sel)):
            messagebox.showinfo("Éxito", "Atleta actualizado.", parent=self)
            self.cargar_datos_combos(); self.cmb_ed_sel_atl.set(''); self.limpiar_controles(self.ctrls_ed_atl); self.set_estado_controles(self.ctrls_ed_atl, "disabled")
            if hasattr(self.parent, 'cargar_datos_bd'): self.parent.cargar_datos_bd()

    def actualizar_club_db(self):
        id_obj = self.map_clubes[self.cmb_ed_sel_club.get()]
        nom = self.ent_ed_club_nombre.get().strip().title()
        id_ciu = self.map_ciudades.get(self.cmb_ed_club_ciudad.get())
        if self.db.actualizar_club(id_obj, id_ciu, nom):
            messagebox.showinfo("Éxito", "Club actualizado.", parent=self)
            self.cargar_datos_combos(); self.cmb_ed_sel_club.set(''); self.limpiar_controles(self.ctrls_ed_club); self.set_estado_controles(self.ctrls_ed_club, "disabled")

    def actualizar_colegio_db(self):
        id_obj = self.map_colegios[self.cmb_ed_sel_col.get()]
        nom = self.ent_ed_col_nombre.get().strip().title()
        if self.db.actualizar_colegio(id_obj, nom):
            messagebox.showinfo("Éxito", "Colegio actualizado.", parent=self)
            self.cargar_datos_combos(); self.cmb_ed_sel_col.set(''); self.limpiar_controles(self.ctrls_ed_col); self.set_estado_controles(self.ctrls_ed_col, "disabled")

    def actualizar_ciudad_db(self):
        id_obj = self.map_ciudades[self.cmb_ed_sel_ciu.get()]
        nom = self.ent_ed_ciu_nombre.get().strip().title()
        id_dep = self.map_deptos.get(self.cmb_ed_ciu_depto.get())
        if self.db.actualizar_ciudad(id_obj, id_dep, nom):
            messagebox.showinfo("Éxito", "Ciudad actualizada.", parent=self)
            self.cargar_datos_combos(); self.cmb_ed_sel_ciu.set(''); self.limpiar_controles(self.ctrls_ed_ciu); self.set_estado_controles(self.ctrls_ed_ciu, "disabled")

    def actualizar_arbitro_db(self):
        id_obj = self.map_oficiales[self.cmb_ed_sel_arb.get()]
        nom = self.ent_ed_arb_nombres.get().strip().title(); ape = self.ent_ed_arb_apellidos.get().strip().title()
        ced = self.ent_ed_arb_ced.get().strip(); cor = self.ent_ed_arb_cor.get().strip(); cel = self.ent_ed_arb_cel.get().strip()
        if self.db.actualizar_oficial(id_obj, nom, ape, ced, cor, cel):
            messagebox.showinfo("Éxito", "Árbitro actualizado.", parent=self)
            self.cargar_datos_combos(); self.cmb_ed_sel_arb.set(''); self.limpiar_controles(self.ctrls_ed_arb); self.set_estado_controles(self.ctrls_ed_arb, "disabled")