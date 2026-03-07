import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from utils.utilidades import aplicar_formato_fecha, aplicar_deseleccion_tabla

class VentanaCargarTorneo(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent # Guarda la referencia a PantallaInscripcion
        self.db = parent.db  # Hereda la conexión de la pantalla principal
        
        self.title("Búsqueda y Selección de Torneos")
        ancho, alto = 950, 500  
        x = (self.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.winfo_screenheight() // 2) - (alto // 2)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.transient(parent)
        self.grab_set()

        self.torneos_memoria_carga = []

        self.crear_interfaz()
        
        # Desplegar datos iniciales
        self.cargar_memoria_torneos()
        self.filtrar_tabla_torneos()

        # Iniciar el motor de actualización en vivo
        self.bucle_refrescar_busqueda_torneos()

    def crear_interfaz(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ================= PANEL IZQUIERDO (FILTROS) =================
        panel_filtros = ttk.LabelFrame(main_frame, text="Filtros de Búsqueda", padding=10)
        panel_filtros.pack(side="left", fill="y", padx=(0, 10))

        ttk.Label(panel_filtros, text="Buscar Nombre:").pack(anchor="w", pady=(0, 2))
        self.ent_filtro_nombre = ttk.Entry(panel_filtros, width=25)
        self.ent_filtro_nombre.pack(fill="x", pady=(0, 10))
        self.ent_filtro_nombre.bind("<KeyRelease>", lambda e: self.filtrar_tabla_torneos())

        ttk.Label(panel_filtros, text="Fecha Inicio (DD/MM/YYYY):").pack(anchor="w", pady=(0, 2))
        self.ent_filtro_fecha_ini = ttk.Entry(panel_filtros, width=25)
        self.ent_filtro_fecha_ini.pack(fill="x", pady=(0, 10))
        aplicar_formato_fecha(self.ent_filtro_fecha_ini)
        self.ent_filtro_fecha_ini.bind("<KeyRelease>", lambda e: self.filtrar_tabla_torneos())

        ttk.Label(panel_filtros, text="Fecha Fin (DD/MM/YYYY):").pack(anchor="w", pady=(0, 2))
        self.ent_filtro_fecha_fin = ttk.Entry(panel_filtros, width=25)
        self.ent_filtro_fecha_fin.pack(fill="x", pady=(0, 10))
        aplicar_formato_fecha(self.ent_filtro_fecha_fin)
        self.ent_filtro_fecha_fin.bind("<KeyRelease>", lambda e: self.filtrar_tabla_torneos())

        # --- FILTRO 1: CATEGORÍAS ---
        ttk.Label(panel_filtros, text="Categorías:").pack(anchor="w", pady=(0, 2))
        frame_cat_scroll = ttk.Frame(panel_filtros)
        frame_cat_scroll.pack(fill="x", pady=(0, 10))
        
        scroll_cat = ttk.Scrollbar(frame_cat_scroll, orient="vertical")
        self.listbox_filtro_cat = tk.Listbox(frame_cat_scroll, selectmode="multiple", height=4, yscrollcommand=scroll_cat.set, exportselection=False)
        scroll_cat.config(command=self.listbox_filtro_cat.yview)
        self.listbox_filtro_cat.pack(side="left", fill="both", expand=True)
        scroll_cat.pack(side="right", fill="y")
        self.listbox_filtro_cat.bind("<<ListboxSelect>>", lambda e: self.filtrar_tabla_torneos())

        # Leer las categorías desde la pantalla principal
        for cat in self.parent.categorias_db:
            self.listbox_filtro_cat.insert(tk.END, cat['nombre'])

        # --- NUEVO FILTRO 2: ESTADOS ---
        ttk.Label(panel_filtros, text="Estados:").pack(anchor="w", pady=(0, 2))
        frame_est_scroll = ttk.Frame(panel_filtros)
        frame_est_scroll.pack(fill="x", pady=(0, 10))
        
        scroll_est = ttk.Scrollbar(frame_est_scroll, orient="vertical")
        self.listbox_filtro_est = tk.Listbox(frame_est_scroll, selectmode="multiple", height=4, yscrollcommand=scroll_est.set, exportselection=False)
        scroll_est.config(command=self.listbox_filtro_est.yview)
        self.listbox_filtro_est.pack(side="left", fill="both", expand=True)
        scroll_est.pack(side="right", fill="y")
        self.listbox_filtro_est.bind("<<ListboxSelect>>", lambda e: self.filtrar_tabla_torneos())

        for est in ["En edición", "Iniciado", "En línea", "Terminado"]:
            self.listbox_filtro_est.insert(tk.END, est)

        ttk.Button(panel_filtros, text="Limpiar Filtros", command=self.limpiar_filtros_torneos).pack(fill="x", pady=(5, 0))

        # ================= PANEL DERECHO (TABLA Y BOTONES) =================
        panel_derecho = ttk.Frame(main_frame)
        panel_derecho.pack(side="right", fill="both", expand=True)

        columnas = ("id", "nombre", "fecha", "categoria", "estado")
        self.tabla_torneos = ttk.Treeview(panel_derecho, columns=columnas, show="headings")
        aplicar_deseleccion_tabla(self.tabla_torneos)
        
        self.tabla_torneos.tag_configure("st_terminado", foreground="#dc3545") 
        self.tabla_torneos.tag_configure("st_en_linea", foreground="#28a745")  
        self.tabla_torneos.tag_configure("st_iniciado", foreground="#d39e00")  
        self.tabla_torneos.tag_configure("st_edicion", foreground="#6c757d")   
        self.tabla_torneos.tag_configure("st_actual", background="#e9ecef")
        
        self.tabla_torneos.heading("id", text="ID"); self.tabla_torneos.column("id", width=40, anchor="center")
        self.tabla_torneos.heading("nombre", text="Nombre del Torneo"); self.tabla_torneos.column("nombre", width=250, anchor="w")
        self.tabla_torneos.heading("fecha", text="Fecha"); self.tabla_torneos.column("fecha", width=90, anchor="center")
        self.tabla_torneos.heading("categoria", text="Categoría"); self.tabla_torneos.column("categoria", width=120, anchor="center")
        self.tabla_torneos.heading("estado", text="Estado"); self.tabla_torneos.column("estado", width=120, anchor="w")
        self.tabla_torneos.pack(fill="both", expand=True, pady=(0, 10))

        # Controles inferiores
        btn_frame = ttk.Frame(panel_derecho)
        btn_frame.pack(fill="x")

        btn_cancelar = ttk.Button(btn_frame, text="Cancelar", command=self.destroy)
        btn_cancelar.pack(side="right", padx=(5, 0))

        btn_cargar = ttk.Button(btn_frame, text="Seleccionar Torneo", command=self.ejecutar_seleccion)
        btn_cargar.pack(side="right")

        self.tabla_torneos.bind("<Double-1>", lambda e: self.ejecutar_seleccion())

    def cargar_memoria_torneos(self):
        torneos_raw = self.db.obtener_lista_torneos_debug()
        self.torneos_memoria_carga = []

        for t in torneos_raw:
            if t.get('fecha_fin'):
                estado_puro = "Terminado"
                tag = "st_terminado"
            elif t.get('tiene_master'):
                estado_puro = "En línea"
                tag = "st_en_linea"
            else:
                bloqueadas = self.db.obtener_divisiones_bloqueadas(t['id'])
                if bloqueadas and len(bloqueadas) > 0:
                    estado_puro = "Iniciado"
                    tag = "st_iniciado"
                else:
                    estado_puro = "En edición"
                    tag = "st_edicion"

            t['estado_puro'] = estado_puro
            t['estado_str'] = f"● {estado_puro}"
            t['tag_estado'] = tag
            self.torneos_memoria_carga.append(t)

    def limpiar_filtros_torneos(self):
        self.ent_filtro_nombre.delete(0, tk.END)
        self.ent_filtro_fecha_ini.delete(0, tk.END)
        self.ent_filtro_fecha_fin.delete(0, tk.END)
        self.listbox_filtro_cat.selection_clear(0, tk.END)
        self.listbox_filtro_est.selection_clear(0, tk.END)
        self.filtrar_tabla_torneos()

    def filtrar_tabla_torneos(self):
        for item in self.tabla_torneos.get_children(): self.tabla_torneos.delete(item)

        term_nombre = self.ent_filtro_nombre.get().strip().lower()
        term_fini = self.ent_filtro_fecha_ini.get().strip()
        term_ffin = self.ent_filtro_fecha_fin.get().strip()
        sel_cats = [self.listbox_filtro_cat.get(i) for i in self.listbox_filtro_cat.curselection()]
        sel_ests = [self.listbox_filtro_est.get(i) for i in self.listbox_filtro_est.curselection()]

        dt_ini = dt_fin = None
        if len(term_fini) == 10:
            try: dt_ini = datetime.strptime(term_fini, "%d/%m/%Y").date()
            except: pass
        if len(term_ffin) == 10:
            try: dt_fin = datetime.strptime(term_ffin, "%d/%m/%Y").date()
            except: pass

        for t in self.torneos_memoria_carga:
            if term_nombre and term_nombre not in t['nombre'].lower(): continue
            if sel_cats and t['categoria'] not in sel_cats: continue
            if sel_ests and t['estado_puro'] not in sel_ests: continue

            if dt_ini or dt_fin:
                try:
                    t_fecha_str = str(t['fecha'])
                    t_date = datetime.strptime(t_fecha_str, "%d/%m/%Y").date()
                    if dt_ini and t_date < dt_ini: continue
                    if dt_fin and t_date > dt_fin: continue
                except: pass

            tags_fila = [t['tag_estado']]
            if getattr(self.parent, "torneo_debug_id", None) == t['id']:
                tags_fila.append("st_actual")
                t['estado_str'] = f"{t['estado_str']} (Actual)"
                
            self.tabla_torneos.insert("", "end", values=(t['id'], t['nombre'], t['fecha'], t['categoria'], t['estado_str']), tags=tuple(tags_fila))

    def bucle_refrescar_busqueda_torneos(self):
        if not self.winfo_exists(): return 
        
        seleccionados = [self.tabla_torneos.item(i, "values")[0] for i in self.tabla_torneos.selection()]
        
        self.cargar_memoria_torneos()
        self.filtrar_tabla_torneos()
        
        for item in self.tabla_torneos.get_children():
            id_item = self.tabla_torneos.item(item, "values")[0]
            if str(id_item) in [str(x) for x in seleccionados]:
                self.tabla_torneos.selection_add(item)
                
        self.after(2000, self.bucle_refrescar_busqueda_torneos)

    def ejecutar_seleccion(self):
        seleccion = self.tabla_torneos.selection()
        if not seleccion:
            return messagebox.showwarning("Aviso", "Seleccione un torneo de la lista.")

        id_torneo = int(self.tabla_torneos.item(seleccion[0], "values")[0])
        
        # Llama al método de la pantalla principal pasando el ID y cierra la ventana
        self.parent.ejecutar_carga_torneo(id_torneo)
        self.destroy()
