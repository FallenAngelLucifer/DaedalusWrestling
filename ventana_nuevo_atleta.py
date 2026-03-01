import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import Calendar
from datetime import datetime
from conexion_db import ConexionDB
from utilidades import aplicar_autocompletado
from utilidades import ComboBuscador
from utilidades import aplicar_formato_fecha
from utilidades import aplicar_formato_cedula

class VentanaNuevoRegistro(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.db = ConexionDB()
        
        self.title("Gestión de Catálogos y Atletas")

        # --- CENTRAR VENTANA ---
        ancho, alto = 530, 350
        x = (self.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.winfo_screenheight() // 2) - (alto // 2)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")

        self.resizable(False, False)

        self.transient(parent)

        self.map_departamentos = {}
        self.map_ciudades = {}
        self.map_clubes = {}
        self.map_colegios = {} # <-- NUEVO
        self.atletas_db_local = [] 

        self.crear_interfaz()
        self.cargar_datos_combos()

    def crear_interfaz(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_atleta = ttk.Frame(notebook, padding=15)
        self.tab_editar = ttk.Frame(notebook, padding=15) 
        self.tab_club = ttk.Frame(notebook, padding=15)
        self.tab_colegio = ttk.Frame(notebook, padding=15) # <-- NUEVO
        self.tab_ciudad = ttk.Frame(notebook, padding=15)
        self.tab_depto = ttk.Frame(notebook, padding=15) 
        self.tab_arbitro = ttk.Frame(notebook, padding=15) # <-- NUEVO

        notebook.add(self.tab_atleta, text="Nuevo Atleta")
        notebook.add(self.tab_editar, text="Editar Atleta")
        notebook.add(self.tab_club, text="Nuevo Club")
        notebook.add(self.tab_colegio, text="Nuevo Colegio")
        notebook.add(self.tab_ciudad, text="Nueva Ciudad")
        notebook.add(self.tab_depto, text="Nuevo Depto") 
        notebook.add(self.tab_arbitro, text="Nuevo Árbitro") 

        self._construir_tab_atleta()
        self._construir_tab_editar()
        self._construir_tab_club()
        self._construir_tab_colegio()
        self._construir_tab_ciudad()
        self._construir_tab_depto() 
        self._construir_tab_arbitro()

    # ================= CONSTRUCTORES DE PESTAÑAS =================
    def _construir_tab_depto(self):
        ttk.Label(self.tab_depto, text="Nombre del Depto:").grid(row=0, column=0, sticky="w", pady=5)
        self.ent_dep_nombre = ttk.Entry(self.tab_depto, width=33)
        self.ent_dep_nombre.grid(row=0, column=1, pady=5)
        ttk.Button(self.tab_depto, text="Guardar Departamento", command=self.guardar_departamento).grid(row=1, column=0, columnspan=2, pady=20)

    def _construir_tab_ciudad(self):
        ttk.Label(self.tab_ciudad, text="Departamento:").grid(row=0, column=0, sticky="w", pady=5)
        self.cmb_ciu_depto = ComboBuscador(self.tab_ciudad, state="readonly", width=30)
        self.cmb_ciu_depto.grid(row=0, column=1, pady=5)
        ttk.Label(self.tab_ciudad, text="Nombre de la Ciudad:").grid(row=1, column=0, sticky="w", pady=5)
        self.ent_ciu_nombre = ttk.Entry(self.tab_ciudad, width=33)
        self.ent_ciu_nombre.grid(row=1, column=1, pady=5)
        ttk.Button(self.tab_ciudad, text="Guardar Ciudad", command=self.guardar_ciudad).grid(row=2, column=0, columnspan=2, pady=20)

    def _construir_tab_club(self):
        ttk.Label(self.tab_club, text="Ciudad:").grid(row=0, column=0, sticky="w", pady=5)
        self.cmb_club_ciudad = ComboBuscador(self.tab_club, state="readonly", width=30)
        self.cmb_club_ciudad.grid(row=0, column=1, pady=5)
        ttk.Label(self.tab_club, text="Nombre del Club:").grid(row=1, column=0, sticky="w", pady=5)
        self.ent_club_nombre = ttk.Entry(self.tab_club, width=33)
        self.ent_club_nombre.grid(row=1, column=1, pady=5)
        ttk.Button(self.tab_club, text="Guardar Club", command=self.guardar_club).grid(row=2, column=0, columnspan=2, pady=20)

    def _construir_tab_colegio(self):
        ttk.Label(self.tab_colegio, text="Nombre del Colegio:").grid(row=0, column=0, sticky="w", pady=5)
        self.ent_col_nombre = ttk.Entry(self.tab_colegio, width=40)
        self.ent_col_nombre.grid(row=0, column=1, pady=5)
        ttk.Button(self.tab_colegio, text="Guardar Colegio", command=self.guardar_colegio).grid(row=1, column=0, columnspan=2, pady=20)

    def _construir_tab_arbitro(self):
        ttk.Label(self.tab_arbitro, text="Nombres:").grid(row=0, column=0, sticky="w", pady=5)
        self.ent_arb_nombres = ttk.Entry(self.tab_arbitro, width=30)
        self.ent_arb_nombres.grid(row=0, column=1, pady=5)

        ttk.Label(self.tab_arbitro, text="Apellidos:").grid(row=1, column=0, sticky="w", pady=5)
        self.ent_arb_apellidos = ttk.Entry(self.tab_arbitro, width=30)
        self.ent_arb_apellidos.grid(row=1, column=1, pady=5)

        ttk.Label(self.tab_arbitro, text="Cédula:").grid(row=2, column=0, sticky="w", pady=5)
        self.ent_arb_cedula = ttk.Entry(self.tab_arbitro, width=30)
        self.ent_arb_cedula.grid(row=2, column=1, pady=5)

        ttk.Label(self.tab_arbitro, text="Correo Electrónico:").grid(row=3, column=0, sticky="w", pady=5)
        self.ent_arb_correo = ttk.Entry(self.tab_arbitro, width=30)
        self.ent_arb_correo.grid(row=3, column=1, pady=5)

        ttk.Label(self.tab_arbitro, text="Celular:").grid(row=4, column=0, sticky="w", pady=5)
        self.ent_arb_celular = ttk.Entry(self.tab_arbitro, width=30)
        self.ent_arb_celular.grid(row=4, column=1, pady=5)
        aplicar_formato_cedula(self.ent_arb_cedula)

        ttk.Button(self.tab_arbitro, text="Guardar Oficial / Árbitro", command=self.guardar_arbitro).grid(row=5, column=0, columnspan=2, pady=20)

    def _construir_tab_atleta(self):
        ttk.Label(self.tab_atleta, text="Nombres:").grid(row=0, column=0, sticky="w", pady=5)
        self.ent_atl_nombres = ttk.Entry(self.tab_atleta, width=30)
        self.ent_atl_nombres.grid(row=0, column=1, pady=5)

        ttk.Label(self.tab_atleta, text="Apellidos:").grid(row=1, column=0, sticky="w", pady=5)
        self.ent_atl_apellidos = ttk.Entry(self.tab_atleta, width=30)
        self.ent_atl_apellidos.grid(row=1, column=1, pady=5)

        ttk.Label(self.tab_atleta, text="Fecha Nac.:").grid(row=2, column=0, sticky="w", pady=5)
        fecha_atl_frame = ttk.Frame(self.tab_atleta)
        fecha_atl_frame.grid(row=2, column=1, pady=5, sticky="w")
        
        self.ent_atl_fecha = ttk.Entry(fecha_atl_frame, width=22)
        self.ent_atl_fecha.pack(side="left", padx=(0, 5))
        aplicar_formato_fecha(self.ent_atl_fecha)
        ttk.Button(fecha_atl_frame, text="📅", width=3, command=lambda: self.abrir_calendario(self.ent_atl_fecha)).pack(side="left")

        ttk.Label(self.tab_atleta, text="Sexo:").grid(row=3, column=0, sticky="w", pady=5)
        self.cmb_atl_sexo = ComboBuscador(self.tab_atleta, values=["M", "F"], state="readonly", width=27)
        self.cmb_atl_sexo.grid(row=3, column=1, pady=5)

        ttk.Label(self.tab_atleta, text="Club:").grid(row=4, column=0, sticky="w", pady=5)
        self.cmb_atl_club = ComboBuscador(self.tab_atleta, state="readonly", width=27)
        self.cmb_atl_club.grid(row=4, column=1, pady=5)

        # Ahora es un Combobox para Colegios
        ttk.Label(self.tab_atleta, text="Colegio:").grid(row=5, column=0, sticky="w", pady=5)
        self.cmb_atl_colegio = ComboBuscador(self.tab_atleta, state="readonly", width=27)
        self.cmb_atl_colegio.grid(row=5, column=1, pady=5)

        ttk.Button(self.tab_atleta, text="Guardar Atleta", command=self.guardar_atleta).grid(row=6, column=0, columnspan=2, pady=20)

    def _construir_tab_editar(self):
        ttk.Label(self.tab_editar, text="Seleccionar Atleta:").grid(row=0, column=0, sticky="w", pady=5)
        self.cmb_edit_sel = ComboBuscador(self.tab_editar, state="readonly", width=40)
        self.cmb_edit_sel.grid(row=0, column=1, pady=5)
        self.cmb_edit_sel.bind("<<ComboboxSelected>>", self.cargar_datos_edicion)

        ttk.Separator(self.tab_editar, orient='horizontal').grid(row=1, column=0, columnspan=2, sticky='ew', pady=10)

        ttk.Label(self.tab_editar, text="Nombres:").grid(row=2, column=0, sticky="w", pady=5)
        self.ent_ed_nombres = ttk.Entry(self.tab_editar, width=30)
        self.ent_ed_nombres.grid(row=2, column=1, pady=5)

        ttk.Label(self.tab_editar, text="Apellidos:").grid(row=3, column=0, sticky="w", pady=5)
        self.ent_ed_apellidos = ttk.Entry(self.tab_editar, width=30)
        self.ent_ed_apellidos.grid(row=3, column=1, pady=5)

        ttk.Label(self.tab_editar, text="Fecha Nac.:").grid(row=4, column=0, sticky="w", pady=5)
        fecha_ed_frame = ttk.Frame(self.tab_editar)
        fecha_ed_frame.grid(row=4, column=1, pady=5, sticky="w")
        self.ent_ed_fecha = ttk.Entry(fecha_ed_frame, width=22)
        self.ent_ed_fecha.pack(side="left", padx=(0, 5))
        aplicar_formato_fecha(self.ent_ed_fecha)
        ttk.Button(fecha_ed_frame, text="📅", width=3, command=lambda: self.abrir_calendario(self.ent_ed_fecha)).pack(side="left")

        ttk.Label(self.tab_editar, text="Sexo:").grid(row=5, column=0, sticky="w", pady=5)
        self.cmb_ed_sexo = ComboBuscador(self.tab_editar, values=["M", "F"], state="readonly", width=27)
        self.cmb_ed_sexo.grid(row=5, column=1, pady=5)

        ttk.Label(self.tab_editar, text="Club:").grid(row=6, column=0, sticky="w", pady=5)
        self.cmb_ed_club = ComboBuscador(self.tab_editar, state="readonly", width=27)
        self.cmb_ed_club.grid(row=6, column=1, pady=5)

        # Ahora es un Combobox para Colegios
        ttk.Label(self.tab_editar, text="Colegio:").grid(row=7, column=0, sticky="w", pady=5)
        self.cmb_ed_colegio = ComboBuscador(self.tab_editar, state="readonly", width=27)
        self.cmb_ed_colegio.grid(row=7, column=1, pady=5)

        ttk.Button(self.tab_editar, text="Actualizar BD", command=self.actualizar_atleta_db).grid(row=8, column=0, columnspan=2, pady=15)

    def abrir_calendario(self, entry_objetivo):
        import calendar # Importación nativa para calcular días del mes
        
        top_cal = tk.Toplevel(self)
        top_cal.title("Calendario")
        
        # --- CENTRAR VENTANA ---
        ancho, alto = 260, 260
        x = (self.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.winfo_screenheight() // 2) - (alto // 2)
        top_cal.geometry(f"{ancho}x{alto}+{x}+{y}")

        top_cal.resizable(False, False)
        top_cal.transient(self)
        top_cal.grab_set() 

        # --- NUEVO: LÓGICA DE AUTO-SELECCIÓN Y CORRECCIÓN DE FECHA ---
        texto_fecha = entry_objetivo.get().strip()
        sel_year, sel_month, sel_day = 2006, 1, 1 # Valores por defecto

        if texto_fecha:
            try:
                # Intento 1: Fecha perfecta (ej: 15/08/2006)
                fecha_obj = datetime.strptime(texto_fecha, "%d/%m/%Y")
                sel_year, sel_month, sel_day = fecha_obj.year, fecha_obj.month, fecha_obj.day
            except ValueError:
                # Intento 2: Fecha aproximada o mal escrita (ej: 31/02/2006)
                partes = texto_fecha.split('/')
                if len(partes) == 3:
                    try:
                        # Corregir año
                        y = int(partes[2])
                        sel_year = max(1900, min(y, 2100)) 
                        
                        # Corregir mes (entre 1 y 12)
                        m = int(partes[1])
                        sel_month = max(1, min(m, 12))     
                        
                        # Corregir día (basado en el mes y año real, detecta años bisiestos)
                        d = int(partes[0])
                        max_day = calendar.monthrange(sel_year, sel_month)[1]
                        sel_day = max(1, min(d, max_day))  
                    except ValueError:
                        pass # Si tiene letras extrañas, usa el año 2006 por defecto

        cal = Calendar(top_cal, selectmode='day', date_pattern='dd/mm/yyyy', 
                       year=sel_year, month=sel_month, day=sel_day)
        cal.pack(pady=10, padx=10, fill="both", expand=True)
        
        def confirmar_fecha():
            entry_objetivo.delete(0, tk.END)
            entry_objetivo.insert(0, cal.get_date())
            # Esto corrige también la posición del cursor de tu máscara de fecha
            entry_objetivo.icursor(tk.END) 
            top_cal.destroy()
            
        ttk.Button(top_cal, text="Confirmar Fecha", command=confirmar_fecha).pack(pady=5)

    # ================= CARGA DE DATOS =================
    def cargar_datos_combos(self):
        deptos = self.db.obtener_departamentos()
        self.map_departamentos = {d['nombre']: d['id'] for d in deptos}
        aplicar_autocompletado(self.cmb_ciu_depto, list(self.map_departamentos.keys()))

        ciudades = self.db.obtener_ciudades()
        self.map_ciudades = {f"{c['nombre']} ({c['departamento']})": c['id'] for c in ciudades}
        aplicar_autocompletado(self.cmb_club_ciudad, list(self.map_ciudades.keys()))

        clubes = self.db.obtener_clubes()
        self.map_clubes = {c['nombre']: c['id'] for c in clubes}
        nombres_clubes = list(self.map_clubes.keys())
        aplicar_autocompletado(self.cmb_atl_club, nombres_clubes)
        aplicar_autocompletado(self.cmb_ed_club, nombres_clubes)

        colegios = self.db.obtener_colegios()
        self.map_colegios = {c['nombre']: c['id'] for c in colegios}
        nombres_colegios = list(self.map_colegios.keys())
        aplicar_autocompletado(self.cmb_atl_colegio, nombres_colegios)
        aplicar_autocompletado(self.cmb_ed_colegio, nombres_colegios)

        self.atletas_db_local = self.db.obtener_atletas()
        if self.atletas_db_local:
            aplicar_autocompletado(self.cmb_edit_sel, [f"{a['apellidos']}, {a['nombre']} (ID: {a['id']})" for a in self.atletas_db_local])

    def cargar_datos_edicion(self, event):
        idx = self.cmb_edit_sel.current()
        if idx == -1: return
        atleta = self.atletas_db_local[idx]

        self.ent_ed_nombres.delete(0, tk.END)
        self.ent_ed_nombres.insert(0, atleta['nombre'])
        
        self.ent_ed_apellidos.delete(0, tk.END)
        self.ent_ed_apellidos.insert(0, atleta['apellidos'])
        
        self.ent_ed_fecha.delete(0, tk.END)
        self.ent_ed_fecha.insert(0, atleta['fecha_nacimiento'].strftime("%d/%m/%Y"))
        
        self.cmb_ed_sexo.set(atleta['sexo'])
        self.cmb_ed_club.set(atleta['club'] if atleta['club'] else '')
        self.cmb_ed_colegio.set(atleta['colegio'] if atleta['colegio'] else '')

    # ================= GUARDADO EN BASE DE DATOS =================
    def actualizar_atleta_db(self):
        idx = self.cmb_edit_sel.current()
        if idx == -1: return messagebox.showwarning("Error", "Seleccione un atleta.", parent=self)
        
        id_peleador = self.atletas_db_local[idx]['id']
        nombres = self.ent_ed_nombres.get().strip()
        apellidos = self.ent_ed_apellidos.get().strip()
        sexo = self.cmb_ed_sexo.get()
        club_sel = self.cmb_ed_club.get()
        colegio_sel = self.cmb_ed_colegio.get()
        
        fecha_str = self.ent_ed_fecha.get().strip()
        try:
            fecha_db = datetime.strptime(fecha_str, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            return messagebox.showerror("Error", "Formato de fecha inválido. Use el calendario o escriba DD/MM/YYYY.", parent=self)
        
        if not all([nombres, apellidos, sexo, club_sel, fecha_db]):
            return messagebox.showwarning("Error", "Complete todos los campos (Colegio es opcional).", parent=self)

        id_club = self.map_clubes.get(club_sel)
        id_colegio = self.map_colegios.get(colegio_sel)
        
        if self.db.actualizar_peleador(id_peleador, nombres, apellidos, fecha_db, sexo, id_club, id_colegio):
            messagebox.showinfo("Éxito", "Atleta actualizado en la Base de Datos.", parent=self)
            self.cargar_datos_combos()
            self.ent_ed_nombres.delete(0, tk.END)
            self.ent_ed_apellidos.delete(0, tk.END)
            self.ent_ed_fecha.delete(0, tk.END)
            self.cmb_ed_colegio.set('')
            self.cmb_edit_sel.set('')
            if hasattr(self.parent, 'cargar_datos_bd'): self.parent.cargar_datos_bd()

    def guardar_atleta(self):
        nombres = self.ent_atl_nombres.get().strip()
        apellidos = self.ent_atl_apellidos.get().strip()
        sexo = self.cmb_atl_sexo.get()
        club_sel = self.cmb_atl_club.get()
        colegio_sel = self.cmb_atl_colegio.get()

        fecha_str = self.ent_atl_fecha.get().strip()
        try:
            fecha_db = datetime.strptime(fecha_str, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            return messagebox.showerror("Error", "Formato de fecha inválido. Use el calendario o escriba DD/MM/YYYY.", parent=self)

        if not all([nombres, apellidos, sexo, club_sel, fecha_db]):
            return messagebox.showwarning("Error", "Complete todos los campos obligatorios.", parent=self)

        id_club = self.map_clubes.get(club_sel)
        id_colegio = self.map_colegios.get(colegio_sel)

        if self.db.insertar_peleador(nombres, apellidos, fecha_db, sexo, id_club, id_colegio):
            messagebox.showinfo("Éxito", "Atleta guardado exitosamente.", parent=self)
            self.cargar_datos_combos() 
            if hasattr(self.parent, 'cargar_datos_bd'): self.parent.cargar_datos_bd()
            self.ent_atl_nombres.delete(0, tk.END)
            self.ent_atl_apellidos.delete(0, tk.END)
            self.cmb_atl_colegio.set('')

    def guardar_colegio(self):
        nombre = self.ent_col_nombre.get().strip()
        if not nombre: return messagebox.showwarning("Error", "Ingrese el nombre del colegio.", parent=self)
        
        if self.db.insertar_colegio(nombre):
            messagebox.showinfo("Éxito", "Colegio guardado en la base de datos.", parent=self)
            self.ent_col_nombre.delete(0, tk.END)
            self.cargar_datos_combos()
        else:
            messagebox.showerror("Error", "No se pudo guardar el colegio. ¿Quizás ya existe?", parent=self)

    def guardar_arbitro(self):
        nom = self.ent_arb_nombres.get().strip()
        ape = self.ent_arb_apellidos.get().strip()
        ced = self.ent_arb_cedula.get().strip()
        cor = self.ent_arb_correo.get().strip() or None
        cel = self.ent_arb_celular.get().strip() or None
        
        if not nom or not ape or not ced:
            return messagebox.showwarning("Error", "Nombres, Apellidos y Cédula son obligatorios.", parent=self)
            
        if self.db.insertar_oficial(nom, ape, ced, cor, cel):
            messagebox.showinfo("Éxito", "Oficial / Árbitro guardado.", parent=self)
            self.ent_arb_nombres.delete(0, tk.END)
            self.ent_arb_apellidos.delete(0, tk.END)
            self.ent_arb_cedula.delete(0, tk.END)
            self.ent_arb_correo.delete(0, tk.END)
            self.ent_arb_celular.delete(0, tk.END)
        else:
            messagebox.showerror("Error", "No se pudo guardar el árbitro. Verifique si la cédula ya existe.", parent=self)

    def guardar_club(self):
        ciudad_sel = self.cmb_club_ciudad.get()
        nombre = self.ent_club_nombre.get().strip()
        if not ciudad_sel or not nombre: return messagebox.showwarning("Error", "Complete campos.", parent=self)
        if self.db.insertar_club(self.map_ciudades[ciudad_sel], nombre):
            messagebox.showinfo("Éxito", "Club guardado.", parent=self)
            self.cargar_datos_combos()

    def guardar_ciudad(self):
        depto_sel = self.cmb_ciu_depto.get()
        nombre = self.ent_ciu_nombre.get().strip()
        if not depto_sel or not nombre: return messagebox.showwarning("Error", "Complete campos.", parent=self)
        if self.db.insertar_ciudad(self.map_departamentos[depto_sel], nombre):
            messagebox.showinfo("Éxito", "Ciudad guardada.", parent=self)
            self.cargar_datos_combos()

    def guardar_departamento(self):
        nombre = self.ent_dep_nombre.get().strip()
        if not nombre: return messagebox.showwarning("Error", "Ingrese el nombre del departamento.", parent=self)
        
        if self.db.insertar_departamento(nombre):
            messagebox.showinfo("Éxito", "Departamento guardado.", parent=self)
            self.ent_dep_nombre.delete(0, tk.END)
            self.cargar_datos_combos()
        else:
            messagebox.showerror("Error", "No se pudo guardar el departamento. ¿Quizás ya existe?", parent=self)
