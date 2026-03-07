import tkinter as tk
from tkinter import ttk, messagebox
import re
from datetime import datetime

from database.conexion_db import ConexionDB
from ui.ventanas.ventana_nuevo_atleta import VentanaNuevoRegistro
from utils.utilidades import aplicar_autocompletado, ComboBuscador, aplicar_deseleccion_tabla, aplicar_formato_fecha

# --- IMPORTACIÓN DE LOS MÓDULOS DE LÓGICA (MIXINS) ---
from ui.pantallas.inscripcion.logica_torneo import LogicaTorneoMixin
from ui.pantallas.inscripcion.logica_memoria import LogicaMemoriaMixin
from ui.pantallas.inscripcion.logica_red import LogicaRedMixin

class PantallaInscripcion(ttk.Frame, LogicaTorneoMixin, LogicaMemoriaMixin, LogicaRedMixin):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = ConexionDB()
        
        self.categorias_db = []
        self.atletas_db = [] 
        self.pesos_oficiales_db = [] # <- Almacena las reglas de la UWW
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

        self.oficiales_db = self.db.obtener_oficiales()
        self.nombres_oficiales = [f"{o['apellidos']}, {o['nombre']}" for o in self.oficiales_db]

        # Bloqueos lógicos y estados
        self.pesos_bloqueados_ids = set()
        self.todo_bloqueado = False
        self.esta_editando_localmente = False # Bloqueo para que la red no interrumpa
        self.escuchando_red = False

        # Inicialización
        self.crear_interfaz()
        self.cargar_datos_bd()

    def crear_interfaz(self):
        lbl_titulo = ttk.Label(self, text="Fase 1: Configuración de Torneo e Inscripciones", font=("Helvetica", 14, "bold"))
        lbl_titulo.pack(pady=(10, 5)) 

        # --- CONTENEDOR SUPERIOR ---
        top_container = ttk.Frame(self)
        top_container.pack(fill="x", padx=15, pady=5) 

        # ================= FRAME 1: DATOS DEL TORNEO (Izquierda) =================
        self.torneo_frame = ttk.LabelFrame(top_container, text="1. Datos Generales del Torneo", padding=10) 
        self.torneo_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.torneo_frame.rowconfigure(0, weight=1)
        self.torneo_frame.rowconfigure(1, weight=1)
        self.torneo_frame.rowconfigure(2, weight=1)
        self.torneo_frame.rowconfigure(3, weight=1)

        ttk.Label(self.torneo_frame, text="Nombre:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
        self.ent_tor_nombre = ttk.Entry(self.torneo_frame, width=35)
        self.ent_tor_nombre.grid(row=0, column=1, columnspan=3, sticky="we", pady=5, padx=5)

        ttk.Label(self.torneo_frame, text="Lugar:").grid(row=1, column=0, sticky="w", pady=5, padx=5)
        self.ent_tor_lugar = ttk.Entry(self.torneo_frame, width=20)
        self.ent_tor_lugar.grid(row=1, column=1, sticky="w", pady=5, padx=5)

        ttk.Label(self.torneo_frame, text="Ciudad:").grid(row=1, column=2, sticky="e", pady=5, padx=5)
        self.cmb_tor_ciudad = ComboBuscador(self.torneo_frame, state="readonly", width=18)
        self.cmb_tor_ciudad.grid(row=1, column=3, sticky="w", pady=5, padx=5)

        ttk.Label(self.torneo_frame, text="Fecha Realización:").grid(row=2, column=0, sticky="w", pady=5, padx=5)
        self.ent_tor_fecha = ttk.Entry(self.torneo_frame, width=15)
        self.ent_tor_fecha.grid(row=2, column=1, sticky="w", pady=5, padx=5)
        self.ent_tor_fecha.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.ent_tor_fecha.config(state="readonly") 

        ttk.Label(self.torneo_frame, text="Categoría Edad:").grid(row=2, column=2, sticky="e", pady=5, padx=5)
        self.cmb_categoria = ComboBuscador(self.torneo_frame, state="readonly", width=18)
        self.cmb_categoria.grid(row=2, column=3, sticky="w", pady=5, padx=5)
        self.cmb_categoria.bind("<<ComboboxSelected>>", lambda e: self.actualizar_btn_nuevo_limpiar())

        btn_torneo_box = ttk.Frame(self.torneo_frame)
        btn_torneo_box.grid(row=3, column=0, columnspan=4, pady=(10, 0))

        self.btn_confirmar_torneo = ttk.Button(btn_torneo_box, text="Confirmar Datos", command=self.gestionar_bloqueo_torneo)
        self.btn_confirmar_torneo.pack(side="left", padx=5)

        self.btn_cancelar_torneo = ttk.Button(btn_torneo_box, text="Cancelar Edición", command=self.cancelar_edicion_torneo)
        self.btn_nuevo_limpiar = ttk.Button(btn_torneo_box, text="", command=self.resetear_torneo)

        self.btn_cargar_torneo = ttk.Button(btn_torneo_box, text="Cargar Torneo (Debug)", command=self.abrir_ventana_cargar_torneo)
        self.btn_cargar_torneo.pack(side="right", padx=5)
        self.torneo_debug_id = None 

        # ================= APARTADO DE GESTIÓN DE RED (Derecha) =================
        red_container = ttk.Frame(top_container)
        red_container.pack(side="right", fill="both", expand=True, padx=(5, 0))

        self.frame_red = ttk.LabelFrame(red_container, text="Gestión de Red y Operador", padding=10) 
        self.frame_red.pack(fill="both", expand=True)
        
        self.lbl_tapete_master = ttk.Label(self.frame_red, text="🥇 Tapete Máster: (Esperando creación de sala...)", font=("Helvetica", 9, "bold"))
        self.lbl_tapete_master.pack(anchor="w", pady=(0, 5))

        net_middle_frame = ttk.Frame(self.frame_red)
        net_middle_frame.pack(fill="both", expand=True, pady=(0, 5))

        columnas_red = ("id", "nombre", "dispositivo", "tapiz", "estado")
        self.tabla_red = ttk.Treeview(net_middle_frame, columns=columnas_red, show="headings", height=3)
        aplicar_deseleccion_tabla(self.tabla_red)
        self.tabla_red.bind("<<TreeviewSelect>>", self.gestionar_estado_botones_red)
        self.tabla_red.heading("id", text="ID"); self.tabla_red.column("id", width=30, anchor="center")
        self.tabla_red.heading("nombre", text="Árbitro"); self.tabla_red.column("nombre", width=100, anchor="w")
        self.tabla_red.heading("dispositivo", text="Dispositivo"); self.tabla_red.column("dispositivo", width=80, anchor="w")
        self.tabla_red.heading("tapiz", text="Tapiz"); self.tabla_red.column("tapiz", width=70, anchor="center")
        self.tabla_red.heading("estado", text="Estado"); self.tabla_red.column("estado", width=0, stretch=tk.NO)
        self.tabla_red.tag_configure("confirmado", background="white")
        self.tabla_red.tag_configure("pendiente", background="#e9ecef")
        self.tabla_red.tag_configure("yo_mismo", background="#ffff99") 
        self.tabla_red.pack(side="left", fill="both", expand=True)

        frame_controles_red = ttk.Frame(net_middle_frame)
        frame_controles_red.pack(side="right", fill="y", padx=(5, 0))

        self.btn_confirmar_red = ttk.Button(frame_controles_red, text="Confirmar Árbitro", command=self.confirmar_arbitro_red, state="disabled")
        self.btn_confirmar_red.pack(fill="x", pady=5)

        self.btn_eliminar_red = ttk.Button(frame_controles_red, text="Eliminar Árbitro", command=self.eliminar_arbitro_red, state="disabled")
        self.btn_eliminar_red.pack(fill="x", pady=5)

        self.btn_intercambiar_tapiz = ttk.Button(frame_controles_red, text="Intercambiar", command=self.intercambiar_tapiz, width=12, state="disabled")
        self.btn_intercambiar_tapiz.pack(fill="x", pady=5)

        self.btn_ceder_master = ttk.Button(frame_controles_red, text="Ceder Máster", command=self.ceder_master, width=12, state="disabled")
        self.btn_ceder_master.pack(fill="x", pady=(0, 5))

        botones_finales_red = ttk.Frame(self.frame_red)
        botones_finales_red.pack(fill="x", pady=(5, 0))

        texto_btn_guardar = "✅ Confirmar y Crear Sala" 
        self.btn_guardar_torneo = tk.Button(botones_finales_red, text=texto_btn_guardar, bg="#28a745", fg="white", font=("Helvetica", 9, "bold"), command=self.guardar_solo_torneo, state="disabled")
        self.btn_guardar_torneo.pack(side="left", fill="x", expand=True, padx=(0, 2))
        
        self.btn_avanzar_pareo = tk.Button(botones_finales_red, text="Fase de Llaves ➡", bg="#007bff", fg="white", font=("Helvetica", 9, "bold"), command=self.avanzar_fase_dos, state="disabled")
        self.btn_avanzar_pareo.pack(side="right", fill="x", expand=True, padx=(2, 0))

        # ================= CONTENEDOR CENTRAL =================
        middle_container = ttk.Frame(self)
        middle_container.pack(fill="x", padx=15, pady=5) 

        # --- FRAME 2: INSCRIPCIÓN (Izquierda) ---
        self.form_frame = ttk.LabelFrame(middle_container, text="2. Inscripción y Pesaje", padding=10) 
        self.form_frame.pack(side="left", fill="both", padx=(0, 10))

        ttk.Label(self.form_frame, text="Atleta:").grid(row=0, column=0, sticky="w", pady=7, padx=5) 
        self.cmb_atleta = ComboBuscador(self.form_frame, state="readonly", width=25)
        self.cmb_atleta.grid(row=0, column=1, sticky="w", pady=7, padx=5)
        self.cmb_atleta.bind("<<ComboboxSelected>>", self.al_seleccionar_atleta)
        self.cmb_atleta.bind("<KeyRelease>", self.al_seleccionar_atleta, add="+")
        self.cmb_atleta.bind("<Button-1>", self._bloquear_combo_si_edita, add="+")

        self.btn_agregar = ttk.Button(self.form_frame, text="Añadir a Memoria", command=self.agregar_a_memoria)
        self.btn_agregar.grid(row=0, column=2, sticky="w", padx=5)

        vcmd_peso = (self.register(self.validar_peso), '%P')
        ttk.Label(self.form_frame, text="Peso (kg):").grid(row=1, column=0, sticky="w", pady=7, padx=5) 
        
        frame_peso_dinamico = ttk.Frame(self.form_frame)
        frame_peso_dinamico.grid(row=1, column=1, columnspan=2, sticky="w", pady=7, padx=5) 
        self.var_peso = tk.StringVar()
        self.var_peso.trace_add("write", lambda *args: self.actualizar_categoria_dinamica())
        self.ent_peso = ttk.Spinbox(frame_peso_dinamico, from_=20.0, to=150.0, increment=0.1, width=8, validate='key', validatecommand=vcmd_peso, textvariable=self.var_peso)
        self.ent_peso.pack(side="left")
        self.lbl_cat_dinamica = ttk.Label(frame_peso_dinamico, text="Categoría: --", foreground="gray", font=("Helvetica", 8, "italic"))
        self.lbl_cat_dinamica.pack(side="left", padx=5)

        estilos_frame = ttk.Frame(self.form_frame)
        estilos_frame.grid(row=2, column=0, columnspan=3, sticky="w", pady=7, padx=5) 
        self.chk_libre = ttk.Checkbutton(estilos_frame, text="Libre", variable=self.var_estilo_libre, command=self.actualizar_categoria_dinamica)
        self.chk_libre.pack(side="left", padx=(0, 10))
        self.chk_greco = ttk.Checkbutton(estilos_frame, text="Greco", variable=self.var_estilo_greco, command=self.actualizar_categoria_dinamica)
        self.chk_greco.pack(side="left", padx=10)
        self.chk_femenina = ttk.Checkbutton(estilos_frame, text="Fem", variable=self.var_estilo_femenina, command=self.actualizar_categoria_dinamica)
        self.chk_femenina.pack(side="left", padx=10)

        botones_form_frame = ttk.Frame(self.form_frame)
        botones_form_frame.grid(row=3, column=0, columnspan=3, pady=(10, 0), sticky="w", padx=5)
        self.btn_nuevo_atleta = ttk.Button(botones_form_frame, text="+ Gestión BD Atletas", command=self.abrir_ventana_nuevo)
        self.btn_nuevo_atleta.pack(side="left", padx=(0, 5))
        self.btn_cancelar_edicion = ttk.Button(botones_form_frame, text="Cancelar Edición", command=self.cancelar_edicion)

        # --- PANEL DE BÚSQUEDA Y FILTROS (Derecha) ---
        self.panel_busqueda = ttk.LabelFrame(middle_container, text="Filtros y Búsqueda Avanzada", padding=10) 
        self.panel_busqueda.pack(side="left", fill="both", expand=True)
        
        frame_busq_izq = ttk.Frame(self.panel_busqueda)
        frame_busq_izq.pack(side="left", fill="y", padx=(0, 10))
        
        ttk.Label(frame_busq_izq, text="Buscar por:").grid(row=0, column=0, sticky="w", pady=5)
        self.cmb_tipo_busqueda = ttk.Combobox(frame_busq_izq, values=["ID", "Nombre", "Club", "Ciudad"], state="readonly", width=8)
        self.cmb_tipo_busqueda.set("Nombre")
        self.cmb_tipo_busqueda.grid(row=0, column=1, sticky="w", pady=5, padx=(2, 0))
        
        self.vcmd_id = (self.register(self.validar_solo_numeros), '%P')
        self.ent_busqueda = ttk.Entry(frame_busq_izq, width=18)
        self.ent_busqueda.grid(row=1, column=0, columnspan=2, sticky="we", pady=5)
        self.ent_busqueda.bind("<KeyRelease>", self.actualizar_tabla_visual)
        self.cmb_tipo_busqueda.bind("<<ComboboxSelected>>", self.cambiar_tipo_busqueda)
        self.cambiar_tipo_busqueda()
        
        frame_sexo = ttk.Frame(frame_busq_izq)
        frame_sexo.grid(row=2, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Label(frame_sexo, text="Sexo:").pack(side="left", padx=(0,5))
        self.var_filtro_m = tk.BooleanVar(value=True); self.var_filtro_f = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame_sexo, text="M", variable=self.var_filtro_m, command=self.actualizar_tabla_visual).pack(side="left")
        ttk.Checkbutton(frame_sexo, text="F", variable=self.var_filtro_f, command=self.actualizar_tabla_visual).pack(side="left")
        
        ttk.Button(frame_busq_izq, text="Limpiar Filtros", command=self.limpiar_filtros).grid(row=3, column=0, columnspan=2, pady=(10, 0), sticky="we")

        frame_listas = ttk.Frame(self.panel_busqueda)
        frame_listas.pack(side="left", fill="both", expand=True)

        frame_peso = ttk.Frame(frame_listas)
        frame_peso.pack(side="left", fill="both", expand=True, padx=(0, 5))
        lbl_peso_box = ttk.Frame(frame_peso); lbl_peso_box.pack(fill="x")
        ttk.Label(lbl_peso_box, text="Categoría:").pack(side="left")
        ttk.Button(lbl_peso_box, text="Ninguno", width=6, command=lambda: self.limpiar_listbox(self.listbox_pesos)).pack(side="right")
        search_peso_frame = ttk.Frame(frame_peso); search_peso_frame.pack(fill="x", pady=(2, 2))
        self.ent_buscar_peso = ttk.Entry(search_peso_frame, width=12); self.ent_buscar_peso.pack(side="left", fill="x", expand=True)
        btn_clear_peso = tk.Label(search_peso_frame, text="✕", fg="gray", cursor="hand2", font=("Helvetica", 8, "bold")); btn_clear_peso.pack(side="right", padx=1)
        self.ent_buscar_peso.bind("<KeyRelease>", lambda e: self.filtrar_listbox(self.listbox_pesos, self.ent_buscar_peso, self.pesos_memoria_completa))
        btn_clear_peso.bind("<Button-1>", lambda e: self.limpiar_buscador(self.ent_buscar_peso, self.listbox_pesos, self.pesos_memoria_completa))

        frame_peso_scroll = ttk.Frame(frame_peso); frame_peso_scroll.pack(fill="both", expand=True)
        scroll_peso = ttk.Scrollbar(frame_peso_scroll, orient="vertical")
        self.listbox_pesos = tk.Listbox(frame_peso_scroll, selectmode="multiple", height=3, width=12, yscrollcommand=scroll_peso.set, exportselection=False)
        scroll_peso.config(command=self.listbox_pesos.yview)
        self.listbox_pesos.pack(side="left", fill="both", expand=True); scroll_peso.pack(side="right", fill="y")
        self.listbox_pesos.bind("<<ListboxSelect>>", self.actualizar_tabla_visual)
        
        frame_estilo = ttk.Frame(frame_listas)
        frame_estilo.pack(side="left", fill="both", expand=True)
        lbl_estilo_box = ttk.Frame(frame_estilo); lbl_estilo_box.pack(fill="x")
        ttk.Label(lbl_estilo_box, text="Estilos:").pack(side="left")
        ttk.Button(lbl_estilo_box, text="Ninguno", width=6, command=lambda: self.limpiar_listbox(self.listbox_estilos)).pack(side="right")
        search_estilo_frame = ttk.Frame(frame_estilo); search_estilo_frame.pack(fill="x", pady=(2, 2))
        self.ent_buscar_estilo = ttk.Entry(search_estilo_frame, width=12); self.ent_buscar_estilo.pack(side="left", fill="x", expand=True)
        btn_clear_estilo = tk.Label(search_estilo_frame, text="✕", fg="gray", cursor="hand2", font=("Helvetica", 8, "bold")); btn_clear_estilo.pack(side="right", padx=1)
        self.ent_buscar_estilo.bind("<KeyRelease>", lambda e: self.filtrar_listbox(self.listbox_estilos, self.ent_buscar_estilo, self.estilos_memoria_completa))
        btn_clear_estilo.bind("<Button-1>", lambda e: self.limpiar_buscador(self.ent_buscar_estilo, self.listbox_estilos, self.estilos_memoria_completa))

        frame_estilo_scroll = ttk.Frame(frame_estilo); frame_estilo_scroll.pack(fill="both", expand=True)
        scroll_estilo = ttk.Scrollbar(frame_estilo_scroll, orient="vertical")
        self.listbox_estilos = tk.Listbox(frame_estilo_scroll, selectmode="multiple", height=3, width=12, yscrollcommand=scroll_estilo.set, exportselection=False)
        scroll_estilo.config(command=self.listbox_estilos.yview)
        self.listbox_estilos.pack(side="left", fill="both", expand=True); scroll_estilo.pack(side="right", fill="y")
        self.listbox_estilos.bind("<<ListboxSelect>>", self.al_cambiar_filtro_estilo)

        self.pesos_memoria_completa = []
        self.estilos_memoria_completa = []

        # ================= FRAME 3: TABLA DE MEMORIA =================
        tabla_frame = ttk.LabelFrame(self, text="3. Atletas en Memoria (Pendientes de Subir)", padding=10) 
        tabla_frame.pack(fill="both", expand=True, padx=15, pady=(5, 10))

        header_frame = tk.Frame(tabla_frame, height=22)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False) 

        def crear_celda(texto, ancho):
            celda = tk.Frame(header_frame, width=ancho, bg="#2a2a2a", highlightbackground="#555555", highlightthickness=1)
            celda.pack(side="left", fill="y")
            celda.pack_propagate(False)
            tk.Label(celda, text=texto, bg="#2a2a2a", fg="white", font=("Helvetica", 8, "bold")).pack(expand=True)

        crear_celda("ID", 40)
        crear_celda("Atleta", 160)
        crear_celda("Sexo", 40)
        crear_celda("Club", 120)
        crear_celda("Ciudad", 120)
        crear_celda("Peso Dado", 90)
        crear_celda("Peso Oficial", 90)

        celda_estilos = tk.Frame(header_frame, bg="#2a2a2a", highlightbackground="#555555", highlightthickness=1)
        celda_estilos.pack(side="left", fill="both", expand=True) 
        tk.Label(celda_estilos, text="Estilos", bg="#2a2a2a", fg="white", font=("Helvetica", 8, "bold")).pack(expand=True)

        columnas = ("id", "idx_local", "atleta", "sexo", "club", "ciudad", "peso", "peso_oficial", "estilos")
        
        self.tabla = ttk.Treeview(tabla_frame, columns=columnas, show="", height=3)
        aplicar_deseleccion_tabla(self.tabla)
        
        self.tabla.column("#0", width=0, stretch=tk.NO)
        self.tabla.column("id", width=40, anchor="center", stretch=False) 
        self.tabla.column("idx_local", width=0, stretch=tk.NO) 
        self.tabla.column("atleta", width=160, anchor="w", stretch=False)
        self.tabla.column("sexo", width=40, anchor="center", stretch=False)
        self.tabla.column("club", width=120, anchor="w", stretch=False)
        self.tabla.column("ciudad", width=120, anchor="w", stretch=False)
        self.tabla.column("peso", width=90, anchor="center", stretch=False)
        self.tabla.column("peso_oficial", width=90, anchor="center", stretch=False)
        self.tabla.column("estilos", width=120, anchor="w", stretch=True)
        
        self.tabla.pack(side="top", fill="both", expand=True)
        self.tabla.tag_configure("dsq", foreground="#dc3545")
        self.tabla.tag_configure("sync_red", background="#d1ecf1", foreground="#0c5460")
        self.tabla.tag_configure("red_nuevo", background="#d4edda", foreground="#155724") 
        self.tabla.tag_configure("confirmado", background="white", foreground="black") 
        
        self.tabla.tag_configure("eliminado_local", background="#f8d7da", foreground="#721c24") 
        self.tabla.tag_configure("editado_local", background="#fff3cd", foreground="#856404")   
        self.tabla.tag_configure("editado_red", background="#cce5ff", foreground="#004085")   
        self.tabla.tag_configure("eliminado_red", background="#e2e3e5", foreground="#383d41") 

        btn_box = ttk.Frame(tabla_frame)
        btn_box.pack(fill="x", pady=5)

        self.frame_acciones_memoria = ttk.Frame(btn_box)
        self.frame_acciones_memoria.pack(side="left")

        self.btn_eliminar_memoria = ttk.Button(self.frame_acciones_memoria, text="Eliminar", command=self.eliminar_de_memoria, state="disabled")
        self.btn_eliminar_memoria.pack(side="left", padx=2)
        
        self.btn_editar_memoria = ttk.Button(self.frame_acciones_memoria, text="Editar", command=self.cargar_para_editar, state="disabled")
        self.btn_editar_memoria.pack(side="left", padx=2)
        
        self.btn_deshacer_memoria = ttk.Button(self.frame_acciones_memoria, text="Deshacer Cambios", command=self.deshacer_cambios_locales, state="disabled")
        self.btn_deshacer_memoria.pack(side="left", padx=(10, 2))

        self.lbl_estadisticas = ttk.Label(btn_box, text="Atletas: 0  |  Clubes: 0  |  Ciudades: 0", foreground="#28a745", font=("Helvetica", 8, "bold"))
        self.lbl_estadisticas.pack(side="right", padx=(0, 10))
        
        self.tabla.bind("<<TreeviewSelect>>", self.al_seleccionar_tabla)
        self.tabla.bind("<Double-1>", self.on_double_click_tabla)
        self.tabla.bind("<Button-1>", self._bloquear_clic_tabla_si_edita, add="+")

        self.cambiar_estado_inscripcion("disabled")
        self.actualizar_botones_guardado()
        self.actualizar_btn_nuevo_limpiar()

    def _bloquear_combo_si_edita(self, event):
        """Impide absolutamente que el combobox despliegue su lista si se está editando un atleta."""
        if getattr(self, "id_atleta_editando", None) is not None:
            return "break"

    def _bloquear_clic_tabla_si_edita(self, event):
        """Impide interactuar con otras filas o deseleccionar la tabla mientras se edita."""
        if getattr(self, "id_atleta_editando", None) is not None:
            return "break" 

    def al_cambiar_filtro_estilo(self, event=None):
        """Manejador para cuando el usuario cambia la selección de estilos."""
        self.actualizar_opciones_filtros()
        self.actualizar_tabla_visual()

    def on_double_click_tabla(self, event):
        """Si se hace doble clic sobre una fila, evalúa si el atleta puede ser editado automáticamente."""
        item_clickeado = self.tabla.identify_row(event.y)
        if not item_clickeado: 
            return
            
        if str(self.btn_editar_memoria.cget("state")) == "normal":
            self.cargar_para_editar()