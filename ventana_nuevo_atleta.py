import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import Calendar
from datetime import datetime # <-- ¡NUEVO! Necesario para las fechas
from conexion_db import ConexionDB

class VentanaNuevoRegistro(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.db = ConexionDB()
        
        self.title("Gestión de Catálogos y Atletas")
        self.geometry("550x500")
        self.resizable(False, False)
        #self.transient(parent)
        #self.grab_set()

        self.map_departamentos = {}
        self.map_ciudades = {}
        self.map_clubes = {}
        self.atletas_db_local = [] # Para la pestaña de edición

        self.crear_interfaz()
        self.cargar_datos_combos()

    def crear_interfaz(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_atleta = ttk.Frame(notebook, padding=15)
        self.tab_editar = ttk.Frame(notebook, padding=15) 
        self.tab_club = ttk.Frame(notebook, padding=15)
        self.tab_ciudad = ttk.Frame(notebook, padding=15)
        self.tab_depto = ttk.Frame(notebook, padding=15) 

        notebook.add(self.tab_atleta, text="Nuevo Atleta")
        notebook.add(self.tab_editar, text="Editar Atleta")
        notebook.add(self.tab_club, text="Nuevo Club")
        notebook.add(self.tab_ciudad, text="Nueva Ciudad")
        notebook.add(self.tab_depto, text="Nuevo Departamento") 

        self._construir_tab_atleta()
        self._construir_tab_editar()
        self._construir_tab_club()
        self._construir_tab_ciudad()
        self._construir_tab_depto() 

    def _construir_tab_depto(self):
        ttk.Label(self.tab_depto, text="Nombre del Depto:").grid(row=0, column=0, sticky="w", pady=5)
        self.ent_dep_nombre = ttk.Entry(self.tab_depto, width=33)
        self.ent_dep_nombre.grid(row=0, column=1, pady=5)

        ttk.Button(self.tab_depto, text="Guardar Departamento", command=self.guardar_departamento).grid(row=1, column=0, columnspan=2, pady=20)

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
        
        btn_cal_atl = ttk.Button(fecha_atl_frame, text="📅", width=3, command=lambda: self.abrir_calendario(self.ent_atl_fecha))
        btn_cal_atl.pack(side="left")

        ttk.Label(self.tab_atleta, text="Sexo:").grid(row=3, column=0, sticky="w", pady=5)
        self.cmb_atl_sexo = ttk.Combobox(self.tab_atleta, values=["M", "F"], state="readonly", width=27)
        self.cmb_atl_sexo.grid(row=3, column=1, pady=5)

        ttk.Label(self.tab_atleta, text="Club:").grid(row=4, column=0, sticky="w", pady=5)
        self.cmb_atl_club = ttk.Combobox(self.tab_atleta, state="readonly", width=27)
        self.cmb_atl_club.grid(row=4, column=1, pady=5)

        ttk.Label(self.tab_atleta, text="Colegio:").grid(row=5, column=0, sticky="w", pady=5)
        self.ent_atl_colegio = ttk.Entry(self.tab_atleta, width=30)
        self.ent_atl_colegio.grid(row=5, column=1, pady=5)

        ttk.Button(self.tab_atleta, text="Guardar Atleta", command=self.guardar_atleta).grid(row=6, column=0, columnspan=2, pady=20)

    def _construir_tab_editar(self):
        ttk.Label(self.tab_editar, text="Seleccionar Atleta:").grid(row=0, column=0, sticky="w", pady=5)
        self.cmb_edit_sel = ttk.Combobox(self.tab_editar, state="readonly", width=40)
        self.cmb_edit_sel.grid(row=0, column=1, pady=5)
        self.cmb_edit_sel.bind("<<ComboboxSelected>>", self.cargar_datos_edicion)

        ttk.Separator(self.tab_editar, orient='horizontal').grid(row=1, column=0, columnspan=2, sticky='ew', pady=10)

        ttk.Label(self.tab_editar, text="Nombres:").grid(row=2, column=0, sticky="w", pady=5)
        self.ent_ed_nombres = ttk.Entry(self.tab_editar, width=30)
        self.ent_ed_nombres.grid(row=2, column=1, pady=5)

        ttk.Label(self.tab_editar, text="Apellidos:").grid(row=3, column=0, sticky="w", pady=5)
        self.ent_ed_apellidos = ttk.Entry(self.tab_editar, width=30)
        self.ent_ed_apellidos.grid(row=3, column=1, pady=5)

        # CORRECCIÓN: Aplicamos el mismo calendario seguro a la pestaña de edición
        ttk.Label(self.tab_editar, text="Fecha Nac.:").grid(row=4, column=0, sticky="w", pady=5)
        fecha_ed_frame = ttk.Frame(self.tab_editar)
        fecha_ed_frame.grid(row=4, column=1, pady=5, sticky="w")
        
        self.ent_ed_fecha = ttk.Entry(fecha_ed_frame, width=22)
        self.ent_ed_fecha.pack(side="left", padx=(0, 5))
        
        btn_cal_ed = ttk.Button(fecha_ed_frame, text="📅", width=3, command=lambda: self.abrir_calendario(self.ent_ed_fecha))
        btn_cal_ed.pack(side="left")

        ttk.Label(self.tab_editar, text="Sexo:").grid(row=5, column=0, sticky="w", pady=5)
        self.cmb_ed_sexo = ttk.Combobox(self.tab_editar, values=["M", "F"], state="readonly", width=27)
        self.cmb_ed_sexo.grid(row=5, column=1, pady=5)

        ttk.Label(self.tab_editar, text="Club:").grid(row=6, column=0, sticky="w", pady=5)
        self.cmb_ed_club = ttk.Combobox(self.tab_editar, state="readonly", width=27)
        self.cmb_ed_club.grid(row=6, column=1, pady=5)

        ttk.Button(self.tab_editar, text="Actualizar BD", command=self.actualizar_atleta_db).grid(row=7, column=0, columnspan=2, pady=15)

    def _construir_tab_club(self):
        ttk.Label(self.tab_club, text="Ciudad:").grid(row=0, column=0, sticky="w", pady=5)
        self.cmb_club_ciudad = ttk.Combobox(self.tab_club, state="readonly", width=30)
        self.cmb_club_ciudad.grid(row=0, column=1, pady=5)

        ttk.Label(self.tab_club, text="Nombre del Club:").grid(row=1, column=0, sticky="w", pady=5)
        self.ent_club_nombre = ttk.Entry(self.tab_club, width=33)
        self.ent_club_nombre.grid(row=1, column=1, pady=5)

        ttk.Button(self.tab_club, text="Guardar Club", command=self.guardar_club).grid(row=2, column=0, columnspan=2, pady=20)

    def _construir_tab_ciudad(self):
        ttk.Label(self.tab_ciudad, text="Departamento:").grid(row=0, column=0, sticky="w", pady=5)
        self.cmb_ciu_depto = ttk.Combobox(self.tab_ciudad, state="readonly", width=30)
        self.cmb_ciu_depto.grid(row=0, column=1, pady=5)

        ttk.Label(self.tab_ciudad, text="Nombre de la Ciudad:").grid(row=1, column=0, sticky="w", pady=5)
        self.ent_ciu_nombre = ttk.Entry(self.tab_ciudad, width=33)
        self.ent_ciu_nombre.grid(row=1, column=1, pady=5)

        ttk.Button(self.tab_ciudad, text="Guardar Ciudad", command=self.guardar_ciudad).grid(row=2, column=0, columnspan=2, pady=20)

    def abrir_calendario(self, entry_objetivo):
        top_cal = tk.Toplevel(self)
        top_cal.title("Calendario")
        top_cal.geometry("260x260")
        top_cal.resizable(False, False)
        top_cal.transient(self)
        top_cal.grab_set() 

        cal = Calendar(top_cal, selectmode='day', date_pattern='dd/mm/yyyy', year=2006)
        cal.pack(pady=10, padx=10, fill="both", expand=True)
        
        def confirmar_fecha():
            entry_objetivo.delete(0, tk.END)
            entry_objetivo.insert(0, cal.get_date())
            top_cal.destroy()
            
        ttk.Button(top_cal, text="Confirmar Fecha", command=confirmar_fecha).pack(pady=5)

    def cargar_datos_combos(self):
        deptos = self.db.obtener_departamentos()
        self.map_departamentos = {d['nombre']: d['id'] for d in deptos}
        self.cmb_ciu_depto['values'] = list(self.map_departamentos.keys())

        ciudades = self.db.obtener_ciudades()
        self.map_ciudades = {f"{c['nombre']} ({c['departamento']})": c['id'] for c in ciudades}
        self.cmb_club_ciudad['values'] = list(self.map_ciudades.keys())

        clubes = self.db.obtener_clubes()
        self.map_clubes = {c['nombre']: c['id'] for c in clubes}
        nombres_clubes = list(self.map_clubes.keys())
        self.cmb_atl_club['values'] = nombres_clubes
        self.cmb_ed_club['values'] = nombres_clubes

        self.atletas_db_local = self.db.obtener_atletas()
        if self.atletas_db_local:
            self.cmb_edit_sel['values'] = [f"{a['apellidos']}, {a['nombre']} (ID: {a['id']})" for a in self.atletas_db_local]

    def cargar_datos_edicion(self, event):
        idx = self.cmb_edit_sel.current()
        if idx == -1: return
        atleta = self.atletas_db_local[idx]

        self.ent_ed_nombres.delete(0, tk.END)
        self.ent_ed_nombres.insert(0, atleta['nombre'])
        
        self.ent_ed_apellidos.delete(0, tk.END)
        self.ent_ed_apellidos.insert(0, atleta['apellidos'])
        
        # CORRECCIÓN: Convertir la fecha de la base de datos a formato DD/MM/YYYY para el Entry
        self.ent_ed_fecha.delete(0, tk.END)
        self.ent_ed_fecha.insert(0, atleta['fecha_nacimiento'].strftime("%d/%m/%Y"))
        
        self.cmb_ed_sexo.set(atleta['sexo'])
        self.cmb_ed_club.set(atleta['club'])

    def actualizar_atleta_db(self):
        idx = self.cmb_edit_sel.current()
        if idx == -1: return messagebox.showwarning("Error", "Seleccione un atleta.")
        
        id_peleador = self.atletas_db_local[idx]['id']
        nombres = self.ent_ed_nombres.get().strip()
        apellidos = self.ent_ed_apellidos.get().strip()
        sexo = self.cmb_ed_sexo.get()
        club_sel = self.cmb_ed_club.get()
        
        # CORRECCIÓN: Validación y formateo de la fecha (de DD/MM/YYYY a YYYY-MM-DD)
        fecha_str = self.ent_ed_fecha.get().strip()
        try:
            fecha_db = datetime.strptime(fecha_str, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            return messagebox.showerror("Error", "Formato de fecha inválido. Use el calendario o escriba DD/MM/YYYY.")
        
        if not all([nombres, apellidos, sexo, club_sel, fecha_db]):
            return messagebox.showwarning("Error", "Complete todos los campos.")

        id_club = self.map_clubes[club_sel]
        
        if self.db.actualizar_peleador(id_peleador, nombres, apellidos, fecha_db, sexo, id_club, None):
            messagebox.showinfo("Éxito", "Atleta actualizado en la Base de Datos.")
            self.cargar_datos_combos()
            self.ent_ed_nombres.delete(0, tk.END)
            self.ent_ed_apellidos.delete(0, tk.END)
            self.ent_ed_fecha.delete(0, tk.END)
            self.cmb_edit_sel.set('')
            if hasattr(self.parent, 'cargar_datos_bd'): self.parent.cargar_datos_bd()

    def guardar_atleta(self):
        nombres = self.ent_atl_nombres.get().strip()
        apellidos = self.ent_atl_apellidos.get().strip()
        sexo = self.cmb_atl_sexo.get()
        club_sel = self.cmb_atl_club.get()
        colegio = self.ent_atl_colegio.get().strip() or None

        # CORRECCIÓN: Validación y formateo de la fecha (de DD/MM/YYYY a YYYY-MM-DD)
        fecha_str = self.ent_atl_fecha.get().strip()
        try:
            fecha_db = datetime.strptime(fecha_str, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            return messagebox.showerror("Error", "Formato de fecha inválido. Use el calendario o escriba DD/MM/YYYY.")

        if not all([nombres, apellidos, sexo, club_sel, fecha_db]):
            return messagebox.showwarning("Error", "Complete todos los campos obligatorios.")

        id_club = self.map_clubes[club_sel]
        if self.db.insertar_peleador(nombres, apellidos, fecha_db, sexo, id_club, colegio):
            messagebox.showinfo("Éxito", "Atleta guardado exitosamente.")
            self.cargar_datos_combos() 
            if hasattr(self.parent, 'cargar_datos_bd'): self.parent.cargar_datos_bd()
            self.ent_atl_nombres.delete(0, tk.END)
            self.ent_atl_apellidos.delete(0, tk.END)
            self.ent_atl_fecha.delete(0, tk.END)

    def guardar_club(self):
        ciudad_sel = self.cmb_club_ciudad.get()
        nombre = self.ent_club_nombre.get().strip()
        if not ciudad_sel or not nombre: return messagebox.showwarning("Error", "Complete campos.")
        if self.db.insertar_club(self.map_ciudades[ciudad_sel], nombre):
            messagebox.showinfo("Éxito", "Club guardado."); self.cargar_datos_combos()

    def guardar_ciudad(self):
        depto_sel = self.cmb_ciu_depto.get()
        nombre = self.ent_ciu_nombre.get().strip()
        if not depto_sel or not nombre: return messagebox.showwarning("Error", "Complete campos.")
        if self.db.insertar_ciudad(self.map_departamentos[depto_sel], nombre):
            messagebox.showinfo("Éxito", "Ciudad guardada."); self.cargar_datos_combos()

    def guardar_departamento(self):
        nombre = self.ent_dep_nombre.get().strip()
        if not nombre: return messagebox.showwarning("Error", "Ingrese el nombre del departamento.")
        
        if self.db.insertar_departamento(nombre):
            messagebox.showinfo("Éxito", "Departamento guardado.")
            self.ent_dep_nombre.delete(0, tk.END)
            self.cargar_datos_combos()
        else:
            messagebox.showerror("Error", "No se pudo guardar el departamento. ¿Quizás ya existe un departamento con ese nombre?")