import tkinter as tk
from tkinter import ttk, messagebox
import re
from datetime import datetime
from conexion_db import ConexionDB
from ventana_nuevo_atleta import VentanaNuevoRegistro
from utilidades import aplicar_autocompletado
from utilidades import ComboBuscador

class PantallaInscripcion(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = ConexionDB()
        
        self.categorias_db = []
        self.atletas_db = [] 
        self.pesos_oficiales_db = [] # <- NUEVO: Almacena las reglas de la UWW
        self.inscripciones_memoria = []
        self.map_ciudades_torneo = {} # Para vincular nombre con ID
        
        self.categoria_confirmada = None
        self.torneo_nombre_conf = ""
        self.torneo_lugar_conf = ""

        self.id_atleta_editando = None 
        self.item_tree_editando = None 

        self.var_estilo_libre = tk.BooleanVar()
        self.var_estilo_greco = tk.BooleanVar()
        self.var_estilo_femenina = tk.BooleanVar()

        self.crear_interfaz()
        self.cargar_datos_bd()

        self.pesos_bloqueados_ids = set()
        self.todo_bloqueado = False

    def crear_interfaz(self):
        lbl_titulo = ttk.Label(self, text="Fase 1: Configuración de Torneo e Inscripciones", font=("Helvetica", 16, "bold"))
        lbl_titulo.pack(pady=10)

        # ================= FRAME 1: DATOS DEL TORNEO =================
        self.torneo_frame = ttk.LabelFrame(self, text="1. Datos Generales del Torneo", padding=10)
        self.torneo_frame.pack(fill="x", padx=20, pady=5)

        ttk.Label(self.torneo_frame, text="Nombre:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
        self.ent_tor_nombre = ttk.Entry(self.torneo_frame, width=40)
        # CAMBIO: columnspan=3 para que abarque hasta el final
        self.ent_tor_nombre.grid(row=0, column=1, columnspan=3, sticky="we", pady=5, padx=5)

        ttk.Label(self.torneo_frame, text="Lugar:").grid(row=1, column=0, sticky="w", pady=5, padx=5)
        self.ent_tor_lugar = ttk.Entry(self.torneo_frame, width=40)
        # CAMBIO: Eliminado columnspan=2 para que no choque con Ciudad
        self.ent_tor_lugar.grid(row=1, column=1, sticky="w", pady=5, padx=5)

        ttk.Label(self.torneo_frame, text="Ciudad:").grid(row=1, column=2, sticky="e", pady=5, padx=5)
        self.cmb_tor_ciudad = ComboBuscador(self.torneo_frame, state="readonly", width=25)
        self.cmb_tor_ciudad.grid(row=1, column=3, sticky="w", pady=5, padx=5)

        ttk.Label(self.torneo_frame, text="Fecha Realización:").grid(row=2, column=0, sticky="w", pady=5, padx=5)
        self.ent_tor_fecha = ttk.Entry(self.torneo_frame, width=15)
        self.ent_tor_fecha.grid(row=2, column=1, sticky="w", pady=5, padx=5)
        self.ent_tor_fecha.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.ent_tor_fecha.config(state="readonly") 

        ttk.Label(self.torneo_frame, text="Categoría Edad:").grid(row=2, column=2, sticky="e", pady=5, padx=5)
        self.cmb_categoria = ComboBuscador(self.torneo_frame, state="readonly", width=25)
        self.cmb_categoria.grid(row=2, column=3, sticky="w", pady=5, padx=5)
        self.cmb_categoria.bind("<<ComboboxSelected>>", lambda e: self.actualizar_btn_nuevo_limpiar())

        btn_torneo_box = ttk.Frame(self.torneo_frame)
        btn_torneo_box.grid(row=3, column=0, columnspan=4, pady=10)

        self.btn_confirmar_torneo = ttk.Button(btn_torneo_box, text="Confirmar Datos de Torneo", command=self.gestionar_bloqueo_torneo)
        self.btn_confirmar_torneo.pack(side="left", padx=5)

        self.btn_cancelar_torneo = ttk.Button(btn_torneo_box, text="Cancelar Edición", command=self.cancelar_edicion_torneo)

        # --- NUEVO: BOTÓN DINÁMICO ---
        self.btn_nuevo_limpiar = ttk.Button(btn_torneo_box, text="", command=self.resetear_torneo)

        # --- NUEVO BOTÓN DE DEBUG ---
        self.btn_cargar_torneo = ttk.Button(btn_torneo_box, text="Cargar Torneo (Debug)", command=self.abrir_ventana_cargar_torneo)
        self.btn_cargar_torneo.pack(side="right", padx=5)
        
        self.torneo_debug_id = None # Variable para controlar si estamos en modo debug

        # ================= CONTENEDOR CENTRAL (Formulario Izquierda / Búsqueda Derecha) =================
        middle_container = ttk.Frame(self)
        middle_container.pack(fill="x", padx=20, pady=5)

        # --- FRAME 2: INSCRIPCIÓN (Izquierda) ---
        self.form_frame = ttk.LabelFrame(middle_container, text="2. Inscripción y Pesaje (Confirmar torneo para habilitar)", padding=10)
        self.form_frame.pack(side="left", fill="both", padx=(0, 10))

        ttk.Label(self.form_frame, text="Atleta:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
        # REDUCCIÓN DE ANCHO AQUÍ (De 40 a 28 para ahorrar espacio)
        self.cmb_atleta = ComboBuscador(self.form_frame, state="readonly", width=28)
        self.cmb_atleta.grid(row=0, column=1, sticky="w", pady=5, padx=5)
        self.cmb_atleta.bind("<<ComboboxSelected>>", self.al_seleccionar_atleta)
        self.cmb_atleta.bind("<KeyRelease>", self.al_seleccionar_atleta, add="+")

        self.btn_nuevo_atleta = ttk.Button(self.form_frame, text="+ Gestión BD Atletas", command=self.abrir_ventana_nuevo)
        self.btn_nuevo_atleta.grid(row=0, column=2, sticky="w", padx=5)

        # --- SUSTITUIR EL ENTRY ANTIGUO POR ESTO ---
        vcmd_peso = (self.register(self.validar_peso), '%P')
        ttk.Label(self.form_frame, text="Peso Exacto (kg):").grid(row=1, column=0, sticky="w", pady=5, padx=5)
        
        # Frame para agrupar el Spinner y la Etiqueta Dinámica
        frame_peso_dinamico = ttk.Frame(self.form_frame)
        frame_peso_dinamico.grid(row=1, column=1, columnspan=2, sticky="w", pady=5, padx=5)
        
        self.var_peso = tk.StringVar()
        # Escucha cada tecla que se presiona para actualizar la etiqueta en vivo
        self.var_peso.trace_add("write", lambda *args: self.actualizar_categoria_dinamica())
        
        self.ent_peso = ttk.Spinbox(frame_peso_dinamico, from_=20.0, to=150.0, increment=0.1, width=10, 
                                    validate='key', validatecommand=vcmd_peso, textvariable=self.var_peso)
        self.ent_peso.pack(side="left")
        
        self.lbl_cat_dinamica = ttk.Label(frame_peso_dinamico, text="Categoría: --", foreground="gray", font=("Helvetica", 9, "italic"))
        self.lbl_cat_dinamica.pack(side="left", padx=10)

        # --- AÑADIR COMMAND A LOS CHECKBUTTONS PARA QUE REACCIONEN ---
        estilos_frame = ttk.Frame(self.form_frame)
        estilos_frame.grid(row=2, column=0, columnspan=3, sticky="w", pady=5, padx=5)
        self.chk_libre = ttk.Checkbutton(estilos_frame, text="Estilo Libre", variable=self.var_estilo_libre, command=self.actualizar_categoria_dinamica)
        self.chk_libre.pack(side="left", padx=(0, 10))
        self.chk_greco = ttk.Checkbutton(estilos_frame, text="Grecorromana", variable=self.var_estilo_greco, command=self.actualizar_categoria_dinamica)
        self.chk_greco.pack(side="left", padx=10)
        self.chk_femenina = ttk.Checkbutton(estilos_frame, text="Femenina", variable=self.var_estilo_femenina, command=self.actualizar_categoria_dinamica)
        self.chk_femenina.pack(side="left", padx=10)

        botones_form_frame = ttk.Frame(self.form_frame)
        botones_form_frame.grid(row=3, column=0, columnspan=3, pady=(10, 0), sticky="w", padx=5)

        self.btn_agregar = ttk.Button(botones_form_frame, text="Añadir a Memoria", command=self.agregar_a_memoria)
        self.btn_agregar.pack(side="left", padx=(0, 5))
        self.btn_cancelar_edicion = ttk.Button(botones_form_frame, text="Cancelar Edición", command=self.cancelar_edicion)

        # --- NUEVO PANEL DE BÚSQUEDA Y FILTROS OPTIMIZADO (Derecha) ---
        self.panel_busqueda = ttk.LabelFrame(middle_container, text="Filtros y Búsqueda Avanzada", padding=10)
        self.panel_busqueda.pack(side="left", fill="both", expand=True)
        
        # Sub-contenedor Izquierdo (Inputs y Sexo)
        frame_busq_izq = ttk.Frame(self.panel_busqueda)
        frame_busq_izq.pack(side="left", fill="y", padx=(0, 15))
        
        ttk.Label(frame_busq_izq, text="Buscar por:").grid(row=0, column=0, sticky="w", pady=2)
        self.cmb_tipo_busqueda = ComboBuscador(frame_busq_izq, values=["ID", "Nombre", "Club", "Ciudad"], state="readonly", width=10)
        self.cmb_tipo_busqueda.set("Nombre")
        self.cmb_tipo_busqueda.grid(row=0, column=1, sticky="w", pady=2, padx=(5, 0))
        self.cmb_tipo_busqueda.bind("<<ComboboxSelected>>", self.cambiar_tipo_busqueda)
        
        self.frame_inputs_busqueda = ttk.Frame(frame_busq_izq)
        self.frame_inputs_busqueda.grid(row=1, column=0, columnspan=2, sticky="we", pady=5)
        
        vcmd_id = (self.register(self.validar_solo_numeros), '%P')
        self.ent_busqueda_id = ttk.Entry(self.frame_inputs_busqueda, validate='key', validatecommand=vcmd_id, width=18)
        self.ent_busqueda_id.bind("<KeyRelease>", self.actualizar_tabla_visual)
        
        self.ent_busqueda_nombre = ttk.Entry(self.frame_inputs_busqueda, width=18)
        self.ent_busqueda_nombre.bind("<KeyRelease>", self.actualizar_tabla_visual)
        
        self.cmb_busqueda_club = ComboBuscador(self.frame_inputs_busqueda, state="readonly", width=18)
        self.cmb_busqueda_club.bind("<<ComboboxSelected>>", self.actualizar_tabla_visual)
        self.cmb_busqueda_ciudad = ComboBuscador(self.frame_inputs_busqueda, state="readonly", width=18)
        self.cmb_busqueda_ciudad.bind("<<ComboboxSelected>>", self.actualizar_tabla_visual)

        self.cambiar_tipo_busqueda() 
        
        frame_sexo = ttk.Frame(frame_busq_izq)
        frame_sexo.grid(row=2, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Label(frame_sexo, text="Sexo:").pack(side="left", padx=(0,5))
        self.var_filtro_m = tk.BooleanVar(value=True)
        self.var_filtro_f = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame_sexo, text="M", variable=self.var_filtro_m, command=self.actualizar_tabla_visual).pack(side="left", padx=2)
        ttk.Checkbutton(frame_sexo, text="F", variable=self.var_filtro_f, command=self.actualizar_tabla_visual).pack(side="left", padx=2)
        
        ttk.Button(frame_busq_izq, text="Limpiar Filtros", command=self.limpiar_filtros).grid(row=3, column=0, columnspan=2, pady=(5, 0), sticky="we")

        # Sub-contenedor Derecho (Listboxes en Paralelo)
        frame_listas = ttk.Frame(self.panel_busqueda)
        frame_listas.pack(side="left", fill="both", expand=True)

        # --- LISTA DE PESOS CON BUSCADOR ---
        frame_peso = ttk.Frame(frame_listas)
        frame_peso.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        lbl_peso_box = ttk.Frame(frame_peso)
        lbl_peso_box.pack(fill="x")
        ttk.Label(lbl_peso_box, text="Categoría / Peso:").pack(side="left")
        ttk.Button(lbl_peso_box, text="Ninguno", width=8, command=lambda: self.limpiar_listbox(self.listbox_pesos)).pack(side="right")
        
        # Buscador de Pesos COMPACTO (Entry + Botón X)
        search_peso_frame = ttk.Frame(frame_peso)
        search_peso_frame.pack(fill="x", pady=(2, 2))
        self.ent_buscar_peso = ttk.Entry(search_peso_frame, width=15)
        self.ent_buscar_peso.pack(side="left", fill="x", expand=True)
        # Etiqueta que simula un botón pequeño
        btn_clear_peso = tk.Label(search_peso_frame, text="✕", fg="gray", cursor="hand2", font=("Helvetica", 9, "bold"))
        btn_clear_peso.pack(side="right", padx=3)
        
        self.ent_buscar_peso.bind("<KeyRelease>", lambda e: self.filtrar_listbox(self.listbox_pesos, self.ent_buscar_peso, self.pesos_memoria_completa))
        btn_clear_peso.bind("<Button-1>", lambda e: self.limpiar_buscador(self.ent_buscar_peso, self.listbox_pesos, self.pesos_memoria_completa))

        frame_peso_scroll = ttk.Frame(frame_peso)
        frame_peso_scroll.pack(fill="both", expand=True)
        scroll_peso = ttk.Scrollbar(frame_peso_scroll, orient="vertical")
        self.listbox_pesos = tk.Listbox(frame_peso_scroll, selectmode="multiple", height=5, width=14, yscrollcommand=scroll_peso.set, exportselection=False)
        scroll_peso.config(command=self.listbox_pesos.yview)
        self.listbox_pesos.pack(side="left", fill="both", expand=True)
        scroll_peso.pack(side="right", fill="y")
        self.listbox_pesos.bind("<<ListboxSelect>>", self.actualizar_tabla_visual)
        
        # --- LISTA DE ESTILOS CON BUSCADOR ---
        frame_estilo = ttk.Frame(frame_listas)
        frame_estilo.pack(side="left", fill="both", expand=True)
        
        lbl_estilo_box = ttk.Frame(frame_estilo)
        lbl_estilo_box.pack(fill="x")
        ttk.Label(lbl_estilo_box, text="Estilos:").pack(side="left")
        ttk.Button(lbl_estilo_box, text="Ninguno", width=8, command=lambda: self.limpiar_listbox(self.listbox_estilos)).pack(side="right")
        
        # Buscador de Estilos COMPACTO (Entry + Botón X)
        search_estilo_frame = ttk.Frame(frame_estilo)
        search_estilo_frame.pack(fill="x", pady=(2, 2))
        self.ent_buscar_estilo = ttk.Entry(search_estilo_frame, width=15)
        self.ent_buscar_estilo.pack(side="left", fill="x", expand=True)
        # Etiqueta que simula un botón pequeño
        btn_clear_estilo = tk.Label(search_estilo_frame, text="✕", fg="gray", cursor="hand2", font=("Helvetica", 9, "bold"))
        btn_clear_estilo.pack(side="right", padx=3)
        
        self.ent_buscar_estilo.bind("<KeyRelease>", lambda e: self.filtrar_listbox(self.listbox_estilos, self.ent_buscar_estilo, self.estilos_memoria_completa))
        btn_clear_estilo.bind("<Button-1>", lambda e: self.limpiar_buscador(self.ent_buscar_estilo, self.listbox_estilos, self.estilos_memoria_completa))

        frame_estilo_scroll = ttk.Frame(frame_estilo)
        frame_estilo_scroll.pack(fill="both", expand=True)
        scroll_estilo = ttk.Scrollbar(frame_estilo_scroll, orient="vertical")
        self.listbox_estilos = tk.Listbox(frame_estilo_scroll, selectmode="multiple", height=5, width=14, yscrollcommand=scroll_estilo.set, exportselection=False)
        scroll_estilo.config(command=self.listbox_estilos.yview)
        self.listbox_estilos.pack(side="left", fill="both", expand=True)
        scroll_estilo.pack(side="right", fill="y")
        self.listbox_estilos.bind("<<ListboxSelect>>", self.al_cambiar_filtro_estilo)

        # Listas en memoria para no perder datos al buscar
        self.pesos_memoria_completa = []
        self.estilos_memoria_completa = []

        # ================= FRAME 3: TABLA DE MEMORIA OPTIMIZADA =================
        tabla_frame = ttk.LabelFrame(self, text="3. Atletas en Memoria (Pendientes de Subir)", padding=10)
        tabla_frame.pack(fill="both", expand=True, padx=20, pady=5)

        columnas = ("id", "idx_local", "atleta", "sexo", "club", "ciudad", "peso", "peso_oficial", "estilos")
        self.tabla = ttk.Treeview(tabla_frame, columns=columnas, show="headings", height=6)
        
        self.tabla.heading("id", text="ID BD")
        self.tabla.heading("idx_local", text="Idx") 
        self.tabla.heading("atleta", text="Atleta")
        self.tabla.heading("sexo", text="Sexo")
        self.tabla.heading("club", text="Club")
        self.tabla.heading("ciudad", text="Ciudad")
        self.tabla.heading("peso", text="Peso Dado")
        self.tabla.heading("peso_oficial", text="Peso Oficial")
        self.tabla.heading("estilos", text="Estilos")
        
        self.tabla.column("id", width=45, anchor="center") 
        self.tabla.column("idx_local", width=0, stretch=tk.NO) 
        self.tabla.column("atleta", width=180, anchor="w")
        self.tabla.column("sexo", width=40, anchor="center")
        self.tabla.column("club", width=120, anchor="w")
        self.tabla.column("ciudad", width=90, anchor="w")
        self.tabla.column("peso", width=70, anchor="center")
        self.tabla.column("peso_oficial", width=110, anchor="center")
        self.tabla.column("estilos", width=140, anchor="w")
        
        self.tabla.pack(side="top", fill="both", expand=True)

        btn_box = ttk.Frame(tabla_frame)
        btn_box.pack(fill="x", pady=5)
        
        # --- REEMPLAZO DE BOTONES PARA PODER CONTROLARLOS ---
        self.btn_eliminar_memoria = ttk.Button(btn_box, text="Eliminar Seleccionado", command=self.eliminar_de_memoria)
        self.btn_eliminar_memoria.pack(side="left", padx=5)
        
        self.btn_editar_memoria = ttk.Button(btn_box, text="Editar Seleccionado", command=self.cargar_para_editar)
        self.btn_editar_memoria.pack(side="left", padx=5)
        
        ttk.Button(btn_box, text="Confirmar y Subir a Base de Datos", command=self.subir_inscripciones_bd).pack(side="right")
        ttk.Button(btn_box, text="💾 Guardar Progreso", command=self.guardar_progreso).pack(side="right", padx=10)

        self.cambiar_estado_inscripcion("disabled")
        
        # --- NUEVO EVENTO: Escuchar selección de tabla ---
        self.tabla.bind("<<TreeviewSelect>>", self.al_seleccionar_tabla)

    

    def limpiar_buscador(self, entry, listbox, lista_completa):
        """Borra el texto del buscador y restaura la lista visual original."""
        entry.delete(0, tk.END)
        self.filtrar_listbox(listbox, entry, lista_completa)
        # Retorna el foco a la tabla para evitar que el cursor se quede en el buscador
        self.tabla.focus_set()

    def actualizar_categoria_dinamica(self, *args):
        # --- NUEVO: REGLA DE NO DESELECCIONAR TODOS ---
        if hasattr(self, 'cmb_atleta'):
            idx = self.cmb_atleta.current()
            if idx != -1:
                atleta = self.atletas_filtrados_objetos[idx]
                # Si el usuario intentó desmarcar el último estilo activo:
                if not (self.var_estilo_libre.get() or self.var_estilo_greco.get() or self.var_estilo_femenina.get()):
                    # Forzamos la reactivación del estilo principal según su sexo
                    if atleta['sexo'] == 'M': self.var_estilo_libre.set(True)
                    else: self.var_estilo_femenina.set(True)

        peso_str = self.var_peso.get().strip()
        if not peso_str:
            self.lbl_cat_dinamica.config(text="Categoría: --", foreground="gray")
            return
            
        try: peso_dado = float(peso_str)
        except ValueError:
            self.lbl_cat_dinamica.config(text="Categoría: Error", foreground="red")
            return
            
        if peso_dado <= 20: # Validar pesos irreales (0 o negativos)
            self.lbl_cat_dinamica.config(text="Peso irreal", foreground="red")
            return

        if not self.categoria_confirmada:
            self.lbl_cat_dinamica.config(text="Confirme torneo primero", foreground="orange")
            return

        estilos_sel = []
        if self.var_estilo_libre.get(): estilos_sel.append(("Libre", 1))
        if self.var_estilo_greco.get(): estilos_sel.append(("Greco", 2))
        if self.var_estilo_femenina.get(): estilos_sel.append(("Fem", 3))

        if not estilos_sel:
            self.lbl_cat_dinamica.config(text="Seleccione un estilo", foreground="gray")
            return

        id_cat_torneo = next((c['id'] for c in self.categorias_db if c['nombre'] == self.categoria_confirmada), None)
        
        cats_encontradas = []
        for nombre_estilo, id_estilo in estilos_sel:
            bracket_encontrado = None
            for p in self.pesos_oficiales_db:
                if p['id_categoria_edad'] == id_cat_torneo and p['id_estilo_lucha'] == id_estilo:
                    if p['peso_minimo'] <= peso_dado <= p['peso_maximo']:
                        bracket_encontrado = p
                        break
            if bracket_encontrado:
                cats_encontradas.append(f"{nombre_estilo[:3]}: {bracket_encontrado['peso_maximo']}kg")
            else:
                cats_encontradas.append(f"{nombre_estilo[:3]}: Fuera de Rango")
        
        texto_final = " | ".join(cats_encontradas)
        color = "red" if "Fuera" in texto_final else "#17a2b8"
        self.lbl_cat_dinamica.config(text=f"Asignación: {texto_final}", foreground=color)

    def al_cambiar_filtro_estilo(self, event=None):
        """Manejador para cuando el usuario cambia la selección de estilos."""
        self.actualizar_opciones_filtros()
        self.actualizar_tabla_visual()

    def al_seleccionar_tabla(self, event):
        # 1. Bloqueo total: Ni siquiera permite hacer clic
        if getattr(self, "todo_bloqueado", False):
            if self.tabla.selection():
                self.tabla.selection_remove(self.tabla.selection()[0])
            return
            
        item_sel = self.tabla.selection()
        if not item_sel: return
        
        # 2. Bloqueo parcial: Evalúa la categoría del atleta seleccionado
        id_atleta = int(self.tabla.item(item_sel[0], "values")[0])
        ins_data = next((i for i in self.inscripciones_memoria if i['id_atleta'] == id_atleta), None)
        if not ins_data: return
        
        is_locked = any(div_id in getattr(self, "pesos_bloqueados_ids", set()) for div_id in ins_data['ids_divisiones'])
        
        if is_locked:
            self.btn_editar_memoria.config(state="disabled")
            self.btn_eliminar_memoria.config(state="disabled")
        else:
            self.btn_editar_memoria.config(state="normal")
            self.btn_eliminar_memoria.config(state="normal")

    def actualizar_btn_nuevo_limpiar(self):
        """Evalúa el estado del formulario para mostrar, ocultar o cambiar el botón inteligente."""
        # 1. Si hay un torneo cargado de la BD
        if getattr(self, "torneo_debug_id", None) is not None:
            self.btn_nuevo_limpiar.config(text="Nuevo Torneo")
            self.btn_nuevo_limpiar.pack(side="left", padx=5)
            return
            
        # 2. Si es personalizado pero tiene datos escritos o confirmados
        nombre = self.ent_tor_nombre.get().strip()
        lugar = self.ent_tor_lugar.get().strip()
        cat = self.cmb_categoria.get()
        
        if nombre or lugar or cat or self.categoria_confirmada:
            self.btn_nuevo_limpiar.config(text="Limpiar Torneo")
            self.btn_nuevo_limpiar.pack(side="left", padx=5)
        else:
            # 3. Está completamente vacío
            self.btn_nuevo_limpiar.pack_forget()

    def resetear_torneo(self):
        """Borra la memoria y resetea la pantalla a su estado inicial de fábrica."""
        respuesta = messagebox.askyesno("Confirmar", "¿Está seguro de limpiar todos los datos y empezar de cero? Se perderán las inscripciones no guardadas.")
        if not respuesta: return

        # 1. Resetear variables lógicas
        self.torneo_debug_id = None
        self.categoria_confirmada = None
        self.torneo_nombre_conf = ""
        self.torneo_lugar_conf = ""
        self.torneo_ciudad_conf = "" # <-- NUEVO
        self.todo_bloqueado = False
        self.pesos_bloqueados_ids = set()

        # 2. Resetear Campos de Texto
        self.ent_tor_nombre.config(state="normal")
        self.ent_tor_lugar.config(state="normal")
        self.cmb_categoria.config(state="normal")
        
        self.ent_tor_nombre.delete(0, tk.END)
        self.ent_tor_lugar.delete(0, tk.END)
        self.cmb_tor_ciudad.set('') # <-- NUEVO
        self.cmb_tor_ciudad.config(state="normal") # <-- NUEVO
        self.cmb_categoria.set('')
        
        self.ent_tor_fecha.config(state="normal")
        self.ent_tor_fecha.delete(0, tk.END)
        self.ent_tor_fecha.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.ent_tor_fecha.config(state="readonly")

        # 3. Resetear Botones
        self.btn_confirmar_torneo.config(text="Confirmar Datos de Torneo", state="normal")
        self.btn_cancelar_torneo.pack_forget()
        
        # Restaurar botones de la tabla por si estaban ocultos por un torneo cerrado
        if hasattr(self, 'btn_editar_memoria') and not self.btn_editar_memoria.winfo_ismapped():
            self.btn_editar_memoria.pack(side="left", padx=5)
            self.btn_eliminar_memoria.pack(side="left", padx=5)
        
        # 4. Limpiar Inscripciones
        self.inscripciones_memoria.clear()
        
        # --- NUEVO: LIMPIAR FORMULARIO DE PESAJE ---
        self.cmb_atleta.set('')
        self.al_seleccionar_atleta()
        if hasattr(self, 'var_peso'): 
            self.var_peso.set('')
        self.al_seleccionar_atleta()
        if hasattr(self, 'lbl_cat_dinamica'):
            self.lbl_cat_dinamica.config(text="Categoría: --", foreground="gray")

        # --- NUEVO: LIMPIAR LISTBOX Y BUSCADORES DE FILTROS ---
        if hasattr(self, 'listbox_pesos'):
            self.listbox_pesos.delete(0, tk.END)
            self.listbox_estilos.delete(0, tk.END)
            self.ent_buscar_peso.delete(0, tk.END)
            self.ent_buscar_estilo.delete(0, tk.END)
            self.pesos_memoria_completa = []
            self.estilos_memoria_completa = []
        
        # --- CORRECCIÓN: Resetear el nuevo panel de búsqueda ---
        if hasattr(self, 'ent_busqueda_nombre'):
            self.limpiar_filtros()
        else:
            self.actualizar_opciones_filtros()
            self.actualizar_tabla_visual()
        
        self.cambiar_estado_inscripcion("disabled")
        self.form_frame.config(text="2. Inscripción y Pesaje (Confirmar torneo para habilitar)")
        
        # --- NUEVO: Ocultar el botón tras limpiar ---
        self.actualizar_btn_nuevo_limpiar()
        
        # --- NUEVO: Ocultar el botón tras limpiar ---
        self.actualizar_btn_nuevo_limpiar()

    def al_seleccionar_tabla(self, event):
        # Si el torneo entero está cerrado, no dejamos seleccionar nada
        if getattr(self, "todo_bloqueado", False):
            if self.tabla.selection():
                self.tabla.selection_remove(self.tabla.selection()[0])
            return
            
        item_sel = self.tabla.selection()
        if not item_sel: return
        valores = self.tabla.item(item_sel[0], "values")
        id_atleta = int(valores[0])
        
        ins_data = next((i for i in self.inscripciones_memoria if i['id_atleta'] == id_atleta), None)
        if not ins_data: return
        
        # Si alguna división de este atleta está bloqueada, bloqueamos los botones
        is_locked = any(div_id in getattr(self, "pesos_bloqueados_ids", set()) for div_id in ins_data['ids_divisiones'])
        
        if is_locked:
            self.btn_editar_memoria.config(state="disabled")
            self.btn_eliminar_memoria.config(state="disabled")
        else:
            self.btn_editar_memoria.config(state="normal")
            self.btn_eliminar_memoria.config(state="normal")

    # ================= VALIDACIONES =================
    def validar_peso(self, P):
        """Permite borrar y admite números con hasta 2 decimales (ej. 74 o 74.55)."""
        if P == "": return True
        # RegEx: Máximo 3 enteros, un punto opcional, y máximo 2 decimales
        match = re.match(r'^\d{0,3}(\.\d{0,2})?$', P)
        return match is not None

    def validar_solo_numeros(self, P):
        if P == "": return True
        return P.isdigit()

    def cambiar_tipo_busqueda(self, event=None):
        tipo = self.cmb_tipo_busqueda.get()
        self.ent_busqueda_id.pack_forget()
        self.ent_busqueda_nombre.pack_forget()
        self.cmb_busqueda_club.pack_forget()
        self.cmb_busqueda_ciudad.pack_forget()
        
        self.ent_busqueda_id.delete(0, tk.END)
        self.ent_busqueda_nombre.delete(0, tk.END)
        self.cmb_busqueda_club.set('')
        self.cmb_busqueda_ciudad.set('')
        
        if tipo == "ID": self.ent_busqueda_id.pack(fill="x")
        elif tipo == "Nombre": self.ent_busqueda_nombre.pack(fill="x")
        elif tipo == "Club": self.cmb_busqueda_club.pack(fill="x")
        elif tipo == "Ciudad": self.cmb_busqueda_ciudad.pack(fill="x")
        
        self.actualizar_tabla_visual()

    def limpiar_filtros(self):
        """Restablece todos los parámetros de búsqueda a su estado inicial."""
        self.ent_busqueda_id.delete(0, tk.END)
        self.ent_busqueda_nombre.delete(0, tk.END)
        self.cmb_busqueda_club.set('Todos')
        self.cmb_busqueda_ciudad.set('Todas')
        
        self.var_filtro_m.set(True)
        self.var_filtro_f.set(True)
        
        self.listbox_pesos.selection_clear(0, tk.END)
        self.listbox_estilos.selection_clear(0, tk.END)
        
        # IMPORTANTE: Forzar actualización de opciones tras limpiar
        self.actualizar_opciones_filtros()
        self.actualizar_tabla_visual()

    def limpiar_listbox(self, listbox):
        """Desmarca todas las opciones de un listbox y actualiza la tabla."""
        listbox.selection_clear(0, tk.END)
        # Si borramos estilos, debemos actualizar los pesos compatibles
        if listbox == getattr(self, 'listbox_estilos', None):
            self.actualizar_opciones_filtros()
        self.actualizar_tabla_visual()

    def filtrar_listbox(self, listbox, entry, lista_completa):
        """Filtra visualmente los elementos del Listbox según lo escrito."""
        texto = entry.get().lower()
        
        # Guardar qué estaba seleccionado antes de filtrar
        seleccionados_nombres = [listbox.get(i) for i in listbox.curselection()]
        
        listbox.delete(0, tk.END)
        for item in lista_completa:
            if texto in item.lower():
                listbox.insert(tk.END, item)
                # Volver a marcar si estaba seleccionado
                if item in seleccionados_nombres:
                    listbox.selection_set(listbox.size() - 1)

    def actualizar_opciones_filtros(self):
        """Actualiza las categorías de peso según los estilos seleccionados."""
        if not hasattr(self, 'listbox_pesos'): return

        sel_pesos = [self.listbox_pesos.get(i) for i in self.listbox_pesos.curselection()]
        sel_estilos = [self.listbox_estilos.get(i) for i in self.listbox_estilos.curselection()]
        
        pesos_compatibles = set()
        estilos_existentes = set()
        mapping = {"Est": "Estilo Libre", "Gre": "Grecorromana", "Fem": "Femenina"}

        for ins in self.inscripciones_memoria:
            for est in ins['estilos']: estilos_existentes.add(est)
            
            individuales = ins['peso_oficial'].split(" | ")
            for w_str in individuales:
                prefijo = w_str.split(":")[0].strip()
                estilo_del_peso = mapping.get(prefijo)
                
                if not sel_estilos or estilo_del_peso in sel_estilos:
                    pesos_compatibles.add(w_str)

        # 1. Actualizar memoria y Listbox de Pesos
        self.pesos_memoria_completa = sorted(pesos_compatibles)
        self.listbox_pesos.delete(0, tk.END)
        for idx, p in enumerate(self.pesos_memoria_completa):
            self.listbox_pesos.insert(tk.END, p)
            if p in sel_pesos: self.listbox_pesos.selection_set(idx)

        # 2. Actualizar memoria y Listbox de Estilos (Solo crece, no se borra si quitas selección)
        self.estilos_memoria_completa = sorted(estilos_existentes)
        # Solo rellenar si está vacío o difiere, para no borrar la selección actual del usuario
        actuales = [self.listbox_estilos.get(i) for i in range(self.listbox_estilos.size())]
        if set(actuales) != estilos_existentes:
            self.listbox_estilos.delete(0, tk.END)
            for e in self.estilos_memoria_completa:
                self.listbox_estilos.insert(tk.END, e)
                # Restaurar selección
                if e in sel_estilos: 
                    self.listbox_estilos.selection_set(self.listbox_estilos.size() - 1)

    # ================= LÓGICA DE TORNEO =================
    def cambiar_estado_inscripcion(self, estado):
        estado_cmb = "normal" if estado == "normal" else "disabled"
        self.cmb_atleta.config(state=estado_cmb)
        self.btn_nuevo_atleta.config(state=estado)
        self.ent_peso.config(state=estado)
        self.btn_agregar.config(state=estado)
        
        if estado == "disabled":
            self.chk_libre.config(state="disabled")
            self.chk_greco.config(state="disabled")
            self.chk_femenina.config(state="disabled")

    def gestionar_bloqueo_torneo(self):
        if self.btn_confirmar_torneo.cget("text") == "Modificar Torneo":
            self.ent_tor_nombre.config(state="normal")
            self.ent_tor_lugar.config(state="normal")
            self.cmb_tor_ciudad.config(state="normal") # <-- NUEVO
            self.cmb_categoria.config(state="normal")
            self.btn_confirmar_torneo.config(text="Guardar Cambios")
            self.btn_cancelar_torneo.pack(side="left", padx=5)
            self.cambiar_estado_inscripcion("disabled")
            self.form_frame.config(text="2. Inscripción y Pesaje (Confirmar torneo para habilitar)")
            return

        nombre = self.ent_tor_nombre.get().strip()
        lugar = self.ent_tor_lugar.get().strip()
        cat = self.cmb_categoria.get()
        ciu = self.cmb_tor_ciudad.get() # <-- NUEVO

        if not nombre or not lugar or not ciu or not cat: # <-- Actualizado
            return messagebox.showwarning("Incompleto", "Llene nombre, lugar, ciudad y categoría.")

        if self.categoria_confirmada is not None and self.categoria_confirmada != cat:
            if self.inscripciones_memoria:
                respuesta = messagebox.askyesno("Cambio de Categoría", "Cambiar la categoría borrará las inscripciones actuales. ¿Desea continuar?")
                if not respuesta:
                    self.cmb_categoria.set(self.categoria_confirmada)
                    return
                else:
                    self.inscripciones_memoria.clear()
                    for item in self.tabla.get_children(): self.tabla.delete(item)

        self.torneo_nombre_conf = nombre
        self.torneo_lugar_conf = lugar
        self.categoria_confirmada = cat
        self.torneo_ciudad_conf = ciu # <-- NUEVO

        self.ent_tor_nombre.config(state="disabled")
        self.ent_tor_lugar.config(state="disabled")
        self.cmb_categoria.config(state="disabled")
        self.cmb_tor_ciudad.config(state="disabled") # <-- NUEVO
        
        self.btn_confirmar_torneo.config(text="Modificar Torneo")
        self.btn_cancelar_torneo.pack_forget()

        self.form_frame.config(text="2. Inscripción y Pesaje (Habilitado)")
        self.filtrar_atletas_por_edad()
        self.cambiar_estado_inscripcion("normal")

        self.actualizar_btn_nuevo_limpiar()

    def cancelar_edicion_torneo(self):
        self.ent_tor_nombre.delete(0, tk.END); self.ent_tor_nombre.insert(0, self.torneo_nombre_conf)
        self.ent_tor_lugar.delete(0, tk.END); self.ent_tor_lugar.insert(0, self.torneo_lugar_conf)
        self.cmb_tor_ciudad.set(getattr(self, 'torneo_ciudad_conf', '')) # <-- NUEVO
        self.cmb_categoria.set(self.categoria_confirmada)

        self.ent_tor_nombre.config(state="disabled"); self.ent_tor_lugar.config(state="disabled"); self.cmb_categoria.config(state="disabled")
        self.btn_confirmar_torneo.config(text="Modificar Torneo")
        self.btn_cancelar_torneo.pack_forget()
        self.form_frame.config(text="2. Inscripción y Pesaje (Habilitado)")
        self.cambiar_estado_inscripcion("normal")
        self.cmb_tor_ciudad.config(state="disabled") # <-- NUEVO

        self.actualizar_btn_nuevo_limpiar()

    # ================= LÓGICA DE INSCRIPCIONES Y PESOS OFICIALES =================
    def cargar_para_editar(self):
        item_sel = self.tabla.selection()
        if not item_sel: return messagebox.showwarning("Selección", "Seleccione un atleta de la tabla.")
        
        valores = self.tabla.item(item_sel[0], "values")
        self.id_atleta_editando = int(valores[0])

        # Buscar el índice del atleta en el combobox original
        atleta_str = f"{valores[2]} (ID: {self.id_atleta_editando})"
        try:
            idx = list(self.cmb_atleta['values']).index(atleta_str)
            self.cmb_atleta.current(idx)
            self.al_seleccionar_atleta(None)
        except ValueError:
            pass
        
        self.var_peso.set(valores[6])

        self.var_estilo_libre.set(True if "Libre" in valores[8] else False) 
        self.var_estilo_greco.set(True if "Grecorromana" in valores[8] else False)
        self.var_estilo_femenina.set(True if "Femenina" in valores[8] else False)

        self.btn_agregar.config(text="Actualizar Inscripción")
        self.btn_cancelar_edicion.pack(side="left", padx=5)
        self.cmb_atleta.config(state="disabled")

    def cancelar_edicion(self):
        self.id_atleta_editando = None
        self.item_tree_editando = None
        self.btn_agregar.config(text="Añadir a Memoria")
        self.btn_cancelar_edicion.pack_forget()
        self.cmb_atleta.config(state="normal")
        self.cmb_atleta.set('')
        self.al_seleccionar_atleta()

    def agregar_a_memoria(self):
        idx = self.cmb_atleta.current()
        peso_str = self.ent_peso.get().strip()
        if idx == -1 or not peso_str: return messagebox.showwarning("Incompleto", "Seleccione atleta y peso.")
        try: peso_dado = float(peso_str)
        except ValueError: return messagebox.showwarning("Error", "Peso con formato inválido.")

        if peso_dado <= 20:
            return messagebox.showwarning("Error de Peso", "El peso debe ser mayor a 20 kg.")

        atleta = self.atletas_filtrados_objetos[idx]
        estilos_sel = []
        if self.var_estilo_libre.get(): estilos_sel.append(("Libre", 1))
        if self.var_estilo_greco.get(): estilos_sel.append(("Grecorromana", 2))
        if self.var_estilo_femenina.get(): estilos_sel.append(("Femenina", 3))

        if not estilos_sel: return messagebox.showwarning("Estilo Requerido", "Debe seleccionar al menos un estilo.")

        id_cat_torneo = next((c['id'] for c in self.categorias_db if c['nombre'] == self.categoria_confirmada), None)
        pesos_oficiales_text, estilos_memoria, ids_divisiones = [], [], [] # <- Modificado aquí

        for nombre_estilo, id_estilo in estilos_sel:
            bracket_encontrado = None
            for p in self.pesos_oficiales_db:
                if p['id_categoria_edad'] == id_cat_torneo and p['id_estilo_lucha'] == id_estilo:
                    if p['peso_minimo'] <= peso_dado <= p['peso_maximo']:
                        bracket_encontrado = p
                        break
            if not bracket_encontrado: return messagebox.showwarning("Fuera de Rango", f"Peso inválido para {nombre_estilo}.")
            
            # --- NUEVO: Validar si la categoría ya fue confirmada ---
            if bracket_encontrado['id'] in getattr(self, "pesos_bloqueados_ids", set()):
                return messagebox.showwarning("División Bloqueada", f"La llave para {nombre_estilo} - {bracket_encontrado['peso_maximo']}kg ya fue confirmada y generada.\n\nNo puede inscribir más atletas en esta división.")            
            
            pesos_oficiales_text.append(f"{nombre_estilo[:3]}: {bracket_encontrado['peso_maximo']}kg")
            estilos_memoria.append(nombre_estilo)
            ids_divisiones.append(bracket_encontrado['id'])

        texto_peso_oficial = " | ".join(pesos_oficiales_text)
        fila_valores = (atleta['id'], idx, f"{atleta['apellidos']}, {atleta['nombre']}", atleta['sexo'], atleta['club'], atleta['ciudad'], peso_str, texto_peso_oficial, " + ".join(estilos_memoria))

        if self.id_atleta_editando is not None:
            for ins in self.inscripciones_memoria:
                if ins['id_atleta'] == self.id_atleta_editando:
                    ins['peso'] = peso_str; ins['peso_oficial'] = texto_peso_oficial; ins['estilos'] = estilos_memoria; ins['ids_divisiones'] = ids_divisiones
                    break
            self.actualizar_tabla_visual()
            self.cancelar_edicion()
            return messagebox.showinfo("Actualizado", "Inscripción actualizada.")

        for ins in self.inscripciones_memoria:
            if ins['id_atleta'] == atleta['id']: return messagebox.showwarning("Duplicado", "Este atleta ya está en la lista.")

        self.inscripciones_memoria.append({"id_atleta": atleta['id'], "peso": peso_str, "peso_oficial": texto_peso_oficial, "estilos": estilos_memoria, "ids_divisiones": ids_divisiones})
        self.actualizar_opciones_filtros()
        self.actualizar_tabla_visual()
        
        self.cmb_atleta.set('')
        self.al_seleccionar_atleta()
        self.actualizar_categoria_dinamica()

    def eliminar_de_memoria(self):
        item_sel = self.tabla.selection()
        if not item_sel: return messagebox.showwarning("Selección", "Seleccione un atleta de la tabla.")
        
        valores = self.tabla.item(item_sel[0], "values")
        nombre_atleta = valores[2]
        id_atleta = int(valores[0])
        
        respuesta = messagebox.askyesno("Confirmar Eliminación", f"¿Seguro que desea eliminar a '{nombre_atleta}' de las inscripciones?")
        if not respuesta: return
            
        if self.id_atleta_editando == id_atleta: 
            self.cancelar_edicion() 
            
        self.inscripciones_memoria = [ins for ins in self.inscripciones_memoria if ins['id_atleta'] != id_atleta]
        self.actualizar_opciones_filtros()
        self.actualizar_tabla_visual()

    def actualizar_tabla_visual(self, event=None):
        # --- NUEVO: Seguro de inicialización ---
        if not hasattr(self, 'tabla'): return 
        
        for item in self.tabla.get_children(): self.tabla.delete(item)

        tipo_busq = getattr(self, 'cmb_tipo_busqueda', None)
        if not tipo_busq: return 
        tipo = tipo_busq.get()
        
        term = ""
        if tipo == "ID": term = self.ent_busqueda_id.get().strip()
        elif tipo == "Nombre": term = self.ent_busqueda_nombre.get().strip().lower()
        elif tipo == "Club": term = self.cmb_busqueda_club.get()
        elif tipo == "Ciudad": term = self.cmb_busqueda_ciudad.get()

        mostrar_m = self.var_filtro_m.get()
        mostrar_f = self.var_filtro_f.get()
        sel_pesos = [self.listbox_pesos.get(i) for i in self.listbox_pesos.curselection()]
        sel_estilos = [self.listbox_estilos.get(i) for i in self.listbox_estilos.curselection()]

        for ins in self.inscripciones_memoria:
            id_atl = ins['id_atleta']
            info = next((a for a in self.atletas_db if a['id'] == id_atl), None)
            if not info: continue

            # 1. Filtros Checkbox (Sexo)
            if info['sexo'] == 'M' and not mostrar_m: continue
            if info['sexo'] == 'F' and not mostrar_f: continue

            # 2. Filtros Listbox Múltiples (Validación por sub-cadena)
            if sel_pesos:
                pesos_atl = ins['peso_oficial'].split(" | ")
                if not any(p in sel_pesos for p in pesos_atl):
                    continue
            
            if sel_estilos and not any(e in sel_estilos for e in ins['estilos']): continue

            nombre_completo = f"{info['apellidos']}, {info['nombre']}"
            club = info['club'] or "Sin Club"
            ciudad = info['ciudad'] or "Sin Ciudad"
            
            # 3. Búsqueda por Texto o Combobox
            if term and term != "Todos" and term != "Todas":
                if tipo == "ID" and str(id_atl) != term: continue
                if tipo == "Nombre" and term not in nombre_completo.lower(): continue
                if tipo == "Club" and club != term: continue
                if tipo == "Ciudad" and ciudad != term: continue

            fila_valores = (id_atl, 0, nombre_completo, info['sexo'], club, ciudad, ins['peso'], ins['peso_oficial'], " + ".join(ins['estilos']))
            self.tabla.insert("", "end", values=fila_valores)

    # ================= CARGA DE DATOS =================
    def cargar_datos_bd(self):
        self.categorias_db = self.db.obtener_categorias()
        if self.categorias_db:
            aplicar_autocompletado(self.cmb_categoria, [cat['nombre'] for cat in self.categorias_db])
            
        self.pesos_oficiales_db = self.db.obtener_pesos_oficiales()
        self.atletas_db = self.db.obtener_atletas()
        
        if self.btn_confirmar_torneo.cget("text") == "Modificar Torneo":
            self.filtrar_atletas_por_edad()

        clubes = self.db.obtener_clubes()
        ciudades = self.db.obtener_ciudades()
        
        self.map_ciudades_torneo = {c['nombre']: c['id'] for c in ciudades}
        aplicar_autocompletado(self.cmb_tor_ciudad, sorted(list(self.map_ciudades_torneo.keys())))

        if hasattr(self, 'cmb_busqueda_club'):
            aplicar_autocompletado(self.cmb_busqueda_club, ["Todos"] + [c['nombre'] for c in clubes])
            aplicar_autocompletado(self.cmb_busqueda_ciudad, ["Todas"] + [c['nombre'] for c in ciudades])

    def filtrar_atletas_por_edad(self):
        idx_cat = self.cmb_categoria.current()
        if idx_cat == -1: return

        cat = self.categorias_db[idx_cat]
        anio_torneo = datetime.now().year
        self.atletas_filtrados_objetos = []
        atletas_permitidos = []

        # --- NUEVA REGLA DE BLOQUEO POR ESTILO (Inteligente) ---
        # 1. Obtenemos todas las divisiones que actualmente tienen al menos un atleta
        divs_con_atletas = set()
        for ins in self.inscripciones_memoria:
            for div_id in ins['ids_divisiones']:
                divs_con_atletas.add(div_id)

        estilos_abiertos = set()
        estilos_validos = set(p['id_estilo_lucha'] for p in self.pesos_oficiales_db if p['id_categoria_edad'] == cat['id'])

        # 2. Evaluamos el estado real de cada estilo
        for id_estilo in estilos_validos:
            divs_estilo = [p['id'] for p in self.pesos_oficiales_db if p['id_categoria_edad'] == cat['id'] and p['id_estilo_lucha'] == id_estilo]
            
            # Filtramos solo las divisiones de este estilo que tienen atletas
            divs_activas = [d for d in divs_estilo if d in divs_con_atletas]

            if not divs_activas:
                # Si el estilo está completamente vacío (0 atletas), lo dejamos abierto para nuevos ingresos
                estilos_abiertos.add(id_estilo)
            else:
                # Si el estilo ya tiene atletas, verificamos si queda ALGUNA llave sin confirmar/bloquear
                unblocked_activas = [d for d in divs_activas if d not in getattr(self, "pesos_bloqueados_ids", set())]
                if unblocked_activas:
                    estilos_abiertos.add(id_estilo)
                    
        # 3. Mapeo de validación: Libre (1), Greco (2), Femenina (3)
        allow_m = 1 in estilos_abiertos or 2 in estilos_abiertos
        allow_f = 3 in estilos_abiertos

        # 4. Filtrado final del Combobox
        for atleta in self.atletas_db:
            # Filtrar por sexo según la disponibilidad del estilo
            if atleta['sexo'] == 'M' and not allow_m: continue
            if atleta['sexo'] == 'F' and not allow_f: continue
            
            edad_uww = anio_torneo - atleta['fecha_nacimiento'].year
            if cat['edad_minima'] <= edad_uww <= cat['edad_maxima']:
                atletas_permitidos.append(f"{atleta['apellidos']}, {atleta['nombre']} (ID: {atleta['id']})")
                self.atletas_filtrados_objetos.append(atleta)

        aplicar_autocompletado(self.cmb_atleta, atletas_permitidos)
        self.cmb_atleta.set('')

    def al_seleccionar_atleta(self, event=None):
        if not hasattr(self, 'cmb_atleta'): return
        
        idx = self.cmb_atleta.current()
        
        # SI ESTÁ VACÍO O SE BORRÓ EL NOMBRE: Desmarcar y Bloquear Todo
        if idx == -1: 
            self.var_estilo_libre.set(False)
            self.var_estilo_greco.set(False)
            self.var_estilo_femenina.set(False)
            self.chk_libre.config(state="disabled")
            self.chk_greco.config(state="disabled")
            self.chk_femenina.config(state="disabled")
            self.actualizar_categoria_dinamica()
            return
            
        atleta = self.atletas_filtrados_objetos[idx]

        self.var_estilo_libre.set(False)
        self.var_estilo_greco.set(False)
        self.var_estilo_femenina.set(False)

        # SI HAY ALGUIEN SELECCIONADO: Habilitar según su sexo
        if atleta['sexo'] == 'M':
            self.chk_libre.config(state="normal")
            self.chk_greco.config(state="normal")
            self.chk_femenina.config(state="disabled")
            self.var_estilo_libre.set(True)
        else:
            self.chk_libre.config(state="disabled")
            self.chk_greco.config(state="disabled")
            self.chk_femenina.config(state="normal")
            self.var_estilo_femenina.set(True)

        self.actualizar_categoria_dinamica()

    def abrir_ventana_nuevo(self):
        VentanaNuevoRegistro(self)

    def guardar_progreso(self):
        """Guarda en la BD pero se queda en la pantalla actual."""
        self._ejecutar_guardado(ir_a_pareo=False)

    def subir_inscripciones_bd(self):
        """Guarda en la BD y avanza a la pantalla de pareos."""
        self._ejecutar_guardado(ir_a_pareo=True)

    def _ejecutar_guardado(self, ir_a_pareo=False):
        """Lógica central de validación, guardado y bloqueo."""
        if not self.inscripciones_memoria: 
            return messagebox.showwarning("Sin Atletas", "No hay atletas inscritos.")
        
        # --- SI YA SE GUARDÓ (MODO CARGADO) ---
        if getattr(self, "torneo_debug_id", None) is not None:
            if ir_a_pareo:
                from pantalla_pareo import PantallaPareo
                p_pareo = self.controller.pantallas.get(PantallaPareo)
                if p_pareo:
                    p_pareo.cargar_torneo(self.torneo_debug_id)
                    self.controller.mostrar_pantalla(PantallaPareo)
            else:
                messagebox.showinfo("Guardado", "El torneo ya se encuentra sincronizado con la Base de Datos.")
            return
            
        # 1. Agrupar inscripciones por división (estilo y peso) para contar parejas
        divisiones = {}
        for ins in self.inscripciones_memoria:
            id_atleta = ins['id_atleta']
            nombre_atleta = next((f"{a['apellidos']}, {a['nombre']}" for a in self.atletas_db if a['id'] == id_atleta), "Atleta Desconocido")
            
            for i, id_div in enumerate(ins['ids_divisiones']):
                estilo = ins['estilos'][i]
                peso_oficial_str = "Desconocido"
                for p in self.pesos_oficiales_db:
                    if p['id'] == id_div:
                        peso_oficial_str = f"{p['peso_maximo']}kg"
                        break
                        
                clave_div = (id_div, estilo, peso_oficial_str)
                if clave_div not in divisiones:
                    divisiones[clave_div] = []
                divisiones[clave_div].append(nombre_atleta)
                
        # 2. Validar si hay al menos una pareja y agrupar a los solitarios
        hay_pareja = False
        atletas_solitarios = {} 
        
        for (id_div, estilo, peso_str), atletas in divisiones.items():
            if len(atletas) >= 2:
                hay_pareja = True
            elif len(atletas) == 1:
                nombre = atletas[0]
                div_str = f"{estilo} - {peso_str}"
                if nombre not in atletas_solitarios:
                    atletas_solitarios[nombre] = []
                atletas_solitarios[nombre].append(div_str)
                
        # 3. Regla A: Debe haber al menos una pareja
        if not hay_pareja:
            return messagebox.showwarning("Parejas Insuficientes", "Debe haber al menos 2 atletas en una misma división de peso y estilo para poder generar un torneo válido.")
            
        # 4. Regla B: Avisar si hay atletas sin pareja antes de confirmar
        if atletas_solitarios:
            solitarios_lista = []
            for nombre, divs in atletas_solitarios.items():
                solitarios_lista.append(f"• {nombre} ({', '.join(divs)})")
                
            mensaje = "Los siguientes atletas están solos en su división (sin oponente):\n\n"
            mensaje += "\n".join(solitarios_lista[:15])
            if len(solitarios_lista) > 15:
                mensaje += f"\n... y {len(solitarios_lista) - 15} más."
            mensaje += "\n\n¿Desea continuar y guardar el torneo de todos modos?"
            
            respuesta = messagebox.askyesno("Atletas sin oponente", mensaje)
            if not respuesta:
                return 

        # --- Continuar con el guardado en BD ---
        id_cat = next((c['id'] for c in self.categorias_db if c['nombre'] == self.categoria_confirmada), None)
        try: fecha_db = datetime.strptime(self.ent_tor_fecha.get().strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
        except: fecha_db = datetime.now().strftime("%Y-%m-%d")

        id_ciu = self.map_ciudades_torneo.get(self.cmb_tor_ciudad.get())
        datos_torneo = {
            "nombre": self.torneo_nombre_conf, 
            "lugar": self.torneo_lugar_conf, 
            "id_ciudad": id_ciu, 
            "fecha": fecha_db, 
            "id_categoria": id_cat
        }
        
        id_torneo = self.db.guardar_torneo_completo(datos_torneo, self.inscripciones_memoria)
        
        if id_torneo:
            # --- ASIGNACIÓN CRÍTICA (Simula que fue cargado de la BD) ---
            self.torneo_debug_id = id_torneo
            
            # Bloquear edición de datos generales
            self.ent_tor_nombre.config(state="disabled")
            self.ent_tor_lugar.config(state="disabled")
            self.cmb_categoria.config(state="disabled")
            if hasattr(self, 'cmb_tor_ciudad'): 
                self.cmb_tor_ciudad.config(state="disabled")
            
            self.btn_confirmar_torneo.config(text="Modificar Torneo", state="disabled")
            self.btn_cancelar_torneo.pack_forget()
            
            self.actualizar_btn_nuevo_limpiar()
            
            # --- DECIDIR ACCIÓN FINAL ---
            if ir_a_pareo:
                messagebox.showinfo("Éxito", "Torneo guardado en la Base de Datos. Pasando a Fase de Pareos.")
                from pantalla_pareo import PantallaPareo
                p_pareo = self.controller.pantallas.get(PantallaPareo)
                if p_pareo:
                    p_pareo.cargar_torneo(id_torneo)
                    self.controller.mostrar_pantalla(PantallaPareo)
            else:
                messagebox.showinfo("Éxito", "Progreso guardado correctamente en la Base de Datos.")
        else:
            messagebox.showerror("Error", "Error al guardar en la base de datos.")

    def abrir_ventana_cargar_torneo(self):
        ventana = tk.Toplevel(self)
        ventana.title("Seleccionar Torneo (Debug)")

        # --- CENTRAR VENTANA ---
        ancho, alto = 600, 300  # Ajusta estos números si necesitas más o menos espacio
        x = (self.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.winfo_screenheight() // 2) - (alto // 2)
        ventana.geometry(f"{ancho}x{alto}+{x}+{y}")

        ventana.transient(self)
        ventana.grab_set()

        columnas = ("id", "nombre", "fecha", "categoria")
        tabla_torneos = ttk.Treeview(ventana, columns=columnas, show="headings")
        tabla_torneos.heading("id", text="ID"); tabla_torneos.column("id", width=50, anchor="center")
        tabla_torneos.heading("nombre", text="Nombre"); tabla_torneos.column("nombre", width=250, anchor="w")
        tabla_torneos.heading("fecha", text="Fecha"); tabla_torneos.column("fecha", width=100, anchor="center")
        tabla_torneos.heading("categoria", text="Categoría Edad"); tabla_torneos.column("categoria", width=150, anchor="center")
        tabla_torneos.pack(fill="both", expand=True, padx=10, pady=10)

        torneos = self.db.obtener_lista_torneos_debug()
        for t in torneos:
            tabla_torneos.insert("", "end", values=(t['id'], t['nombre'], t['fecha'], t['categoria']))

        btn_cargar = ttk.Button(ventana, text="Cargar en Pantalla", command=lambda: self.ejecutar_carga_torneo(tabla_torneos, ventana))
        btn_cargar.pack(pady=10)

    def ejecutar_carga_torneo(self, tabla, ventana):
        item_sel = tabla.selection()
        if not item_sel: return messagebox.showwarning("Selección", "Seleccione un torneo.")
        
        id_torneo = int(tabla.item(item_sel[0], "values")[0])
        ventana.destroy()

        datos_torneo, inscripciones = self.db.obtener_torneo_completo_debug(id_torneo)
        if not datos_torneo: return

        # 1. Llenar los campos de torneo
        self.ent_tor_nombre.config(state="normal"); self.ent_tor_nombre.delete(0, tk.END); self.ent_tor_nombre.insert(0, datos_torneo['nombre'])
        self.ent_tor_lugar.config(state="normal"); self.ent_tor_lugar.delete(0, tk.END); self.ent_tor_lugar.insert(0, datos_torneo['lugar'])
        self.ent_tor_fecha.config(state="normal"); self.ent_tor_fecha.delete(0, tk.END); self.ent_tor_fecha.insert(0, datos_torneo['fecha']); self.ent_tor_fecha.config(state="readonly")

        self.cmb_tor_ciudad.config(state="normal")
        self.cmb_tor_ciudad.set(datos_torneo.get('ciudad_nombre', ''))
        self.cmb_tor_ciudad.config(state="disabled")
        
        # Seleccionar índice correcto del combobox para evitar errores de filtrado
        self.cmb_categoria.config(state="normal")
        try:
            idx_cat = list(self.cmb_categoria['values']).index(datos_torneo['categoria'])
            self.cmb_categoria.current(idx_cat)
        except ValueError:
            self.cmb_categoria.set(datos_torneo['categoria'])

        # 2. Limpiar memoria y tabla
        self.inscripciones_memoria.clear()
        for item in self.tabla.get_children(): self.tabla.delete(item)

        # 3. Agrupar estilos por atleta (reconstrucción de memoria)
        atletas_agrupados = {}
        for ins in inscripciones:
            id_atl = ins['id_peleador']
            if id_atl not in atletas_agrupados:
                atletas_agrupados[id_atl] = {"datos_bd": ins, "estilos": [], "pesos_text": [], "ids_divisiones": []}
            atletas_agrupados[id_atl]["estilos"].append(ins['estilo'])
            atletas_agrupados[id_atl]["pesos_text"].append(f"{ins['estilo'][:3]}: {ins['peso_maximo']}kg")
            atletas_agrupados[id_atl]["ids_divisiones"].append(ins['id_division'])

        # 4. Llenar la memoria local
        for id_atl, data in atletas_agrupados.items():
            info = data["datos_bd"]
            texto_peso_oficial = " | ".join(data["pesos_text"])
            
            self.inscripciones_memoria.append({
                "id_atleta": id_atl, "peso": str(info['peso_pesaje']),
                "peso_oficial": texto_peso_oficial, "estilos": data["estilos"], "ids_divisiones": data["ids_divisiones"]
            })
            
        self.actualizar_opciones_filtros()
        self.actualizar_tabla_visual()

        # 5. --- APLICACIÓN MANUAL DE ESTADO "CONFIRMADO" ---
        self.torneo_debug_id = id_torneo
        self.torneo_nombre_conf = datos_torneo['nombre']
        self.torneo_lugar_conf = datos_torneo['lugar']
        self.categoria_confirmada = datos_torneo['categoria']

        # Consultar la BD por llaves cerradas antes de configurar la interfaz
        self.pesos_bloqueados_ids = self.db.obtener_divisiones_bloqueadas(id_torneo)

        # Bloquear Textos
        self.ent_tor_nombre.config(state="disabled")
        self.ent_tor_lugar.config(state="disabled")
        self.cmb_categoria.config(state="disabled")
        
        # Bloquear Botón de Edición (No se puede editar un torneo descargado de la BD)
        self.btn_confirmar_torneo.config(text="Modificar Torneo", state="disabled")
        self.btn_cancelar_torneo.pack_forget()

        # Activar temporalmente el ingreso de atletas para que el filtro corra bien
        self.form_frame.config(text="2. Inscripción y Pesaje (Habilitado)")
        self.cambiar_estado_inscripcion("normal")
        self.filtrar_atletas_por_edad()

        # 6. --- EVALUACIÓN DE BLOQUEOS DE LLAVE ---
        all_locked = True
        if not self.inscripciones_memoria:
            all_locked = False
        else:
            for ins in self.inscripciones_memoria:
                for div_id in ins['ids_divisiones']:
                    if div_id not in self.pesos_bloqueados_ids:
                        all_locked = False
                        break
                if not all_locked: break

        if all_locked and self.pesos_bloqueados_ids:
            # --- BLOQUEO ABSOLUTO ---
            self.todo_bloqueado = True
            self.cambiar_estado_inscripcion("disabled")
            if hasattr(self, 'btn_editar_memoria'):
                self.btn_editar_memoria.pack_forget()
                self.btn_eliminar_memoria.pack_forget()
            messagebox.showinfo("Torneo Cerrado", "Este torneo tiene TODAS sus llaves confirmadas.\nLa fase de inscripción pasa a modo de Solo Lectura.")
        else:
            # --- BLOQUEO PARCIAL ---
            self.todo_bloqueado = False
            if hasattr(self, 'btn_editar_memoria'):
                self.btn_editar_memoria.pack(side="left", padx=5)
                self.btn_eliminar_memoria.pack(side="left", padx=5)
            messagebox.showinfo("Cargado", "Torneo cargado en memoria.\nRecuerde que no podrá editar a los atletas cuyas categorías ya tengan una llave confirmada.")
            
        self.actualizar_btn_nuevo_limpiar()
