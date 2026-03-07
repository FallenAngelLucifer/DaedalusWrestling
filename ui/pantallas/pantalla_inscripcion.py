import tkinter as tk
from tkinter import ttk, messagebox
import re
from datetime import datetime
from database.conexion_db import ConexionDB
from ui.ventanas.ventana_nuevo_atleta import VentanaNuevoRegistro
from utils.utilidades import aplicar_autocompletado, ComboBuscador, aplicar_deseleccion_tabla, aplicar_formato_fecha

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

        self.oficiales_db = self.db.obtener_oficiales()
        self.nombres_oficiales = [f"{o['apellidos']}, {o['nombre']}" for o in self.oficiales_db]

        self.crear_interfaz()
        self.cargar_datos_bd()

        self.pesos_bloqueados_ids = set()
        self.todo_bloqueado = False

        self.esta_editando_localmente = False # Bloqueo para que la red no interrumpa

    def crear_interfaz(self):
        lbl_titulo = ttk.Label(self, text="Fase 1: Configuración de Torneo e Inscripciones", font=("Helvetica", 14, "bold"))
        lbl_titulo.pack(pady=(10, 5)) # Mayor margen superior para respirar

        # --- CONTENEDOR SUPERIOR ---
        top_container = ttk.Frame(self)
        top_container.pack(fill="x", padx=15, pady=5) # Aumentado el padding exterior

        # ================= FRAME 1: DATOS DEL TORNEO (Izquierda) =================
        self.torneo_frame = ttk.LabelFrame(top_container, text="1. Datos Generales del Torneo", padding=10) # Padding interno vuelto a 10
        self.torneo_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Distribuir el espacio vertical uniformemente
        self.torneo_frame.rowconfigure(0, weight=1)
        self.torneo_frame.rowconfigure(1, weight=1)
        self.torneo_frame.rowconfigure(2, weight=1)
        self.torneo_frame.rowconfigure(3, weight=1)

        # pady aumentado a 5
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

        self.frame_red = ttk.LabelFrame(red_container, text="Gestión de Red y Operador", padding=10) # padding=10
        self.frame_red.pack(fill="both", expand=True)
        
        self.lbl_tapete_master = ttk.Label(self.frame_red, text="🥇 Tapete Máster: (Esperando creación de sala...)", font=("Helvetica", 9, "bold"))
        self.lbl_tapete_master.pack(anchor="w", pady=(0, 5))

        # --- Sub-contenedor: Tabla (Izquierda) + Botones Verticales (Derecha) ---
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
        self.tabla_red.tag_configure("yo_mismo", background="#ffff99") # <-- NUEVO: Color amarillo
        self.tabla_red.pack(side="left", fill="both", expand=True)

        # --- Botones Verticales de Gestión de Árbitro ---
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

        # --- Contenedor Inferior: Botones de Colores Compartiendo Fila ---
        botones_finales_red = ttk.Frame(self.frame_red)
        botones_finales_red.pack(fill="x", pady=(5, 0))

        texto_btn_guardar = "✅ Confirmar y Crear Sala" 
        self.btn_guardar_torneo = tk.Button(botones_finales_red, text=texto_btn_guardar, bg="#28a745", fg="white", font=("Helvetica", 9, "bold"), command=self.guardar_solo_torneo, state="disabled")
        self.btn_guardar_torneo.pack(side="left", fill="x", expand=True, padx=(0, 2))
        
        self.btn_avanzar_pareo = tk.Button(botones_finales_red, text="Fase de Llaves ➡", bg="#007bff", fg="white", font=("Helvetica", 9, "bold"), command=self.avanzar_fase_dos, state="disabled")
        self.btn_avanzar_pareo.pack(side="right", fill="x", expand=True, padx=(2, 0))

        # ================= CONTENEDOR CENTRAL =================
        middle_container = ttk.Frame(self)
        middle_container.pack(fill="x", padx=15, pady=5) # padding aumentado

        # --- FRAME 2: INSCRIPCIÓN (Izquierda) ---
        self.form_frame = ttk.LabelFrame(middle_container, text="2. Inscripción y Pesaje", padding=10) # padding=10
        self.form_frame.pack(side="left", fill="both", padx=(0, 10))

        # pady aumentado a 7 para mayor holgura vertical
        ttk.Label(self.form_frame, text="Atleta:").grid(row=0, column=0, sticky="w", pady=7, padx=5) 
        self.cmb_atleta = ComboBuscador(self.form_frame, state="readonly", width=25)
        self.cmb_atleta.grid(row=0, column=1, sticky="w", pady=7, padx=5)
        self.cmb_atleta.bind("<<ComboboxSelected>>", self.al_seleccionar_atleta)
        self.cmb_atleta.bind("<KeyRelease>", self.al_seleccionar_atleta, add="+")

        # --- NUEVO: Interceptar el clic físico del ratón ---
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
        self.panel_busqueda = ttk.LabelFrame(middle_container, text="Filtros y Búsqueda Avanzada", padding=10) # padding=10
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
        tabla_frame = ttk.LabelFrame(self, text="3. Atletas en Memoria (Pendientes de Subir)", padding=10) # padding=10
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
        
        # TABLA REDUCIDA (height=3 en vez de 4) para permitir que los elementos superiores usen el espacio
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
        
        self.tabla.tag_configure("eliminado_local", background="#f8d7da", foreground="#721c24") # Fondo rojo suave
        self.tabla.tag_configure("editado_local", background="#fff3cd", foreground="#856404")   # Fondo naranja suave
        
        # --- NUEVAS ETIQUETAS DE RED ---
        self.tabla.tag_configure("editado_red", background="#cce5ff", foreground="#004085")   # Azul claro
        self.tabla.tag_configure("eliminado_red", background="#e2e3e5", foreground="#383d41") # Gris

        btn_box = ttk.Frame(tabla_frame)
        btn_box.pack(fill="x", pady=5)

        self.frame_acciones_memoria = ttk.Frame(btn_box)
        self.frame_acciones_memoria.pack(side="left")

        self.btn_eliminar_memoria = ttk.Button(self.frame_acciones_memoria, text="Eliminar", command=self.eliminar_de_memoria, state="disabled")
        self.btn_eliminar_memoria.pack(side="left", padx=2)
        
        self.btn_editar_memoria = ttk.Button(self.frame_acciones_memoria, text="Editar", command=self.cargar_para_editar, state="disabled")
        self.btn_editar_memoria.pack(side="left", padx=2)
        
        # --- NUEVO BOTÓN DESHACER ---
        self.btn_deshacer_memoria = ttk.Button(self.frame_acciones_memoria, text="Deshacer Cambios", command=self.deshacer_cambios_locales, state="disabled")
        self.btn_deshacer_memoria.pack(side="left", padx=(10, 2))

        # Alineación de la etiqueta a la derecha (side="right") y se omite el botón repetido
        self.lbl_estadisticas = ttk.Label(btn_box, text="Atletas: 0  |  Clubes: 0  |  Ciudades: 0", foreground="#28a745", font=("Helvetica", 8, "bold"))
        self.lbl_estadisticas.pack(side="right", padx=(0, 10))
        
        self.tabla.bind("<<TreeviewSelect>>", self.al_seleccionar_tabla)
        self.tabla.bind("<Double-1>", self.on_double_click_tabla)

        # --- NUEVO: Interceptar el clic físico en la tabla durante la edición ---
        self.tabla.bind("<Button-1>", self._bloquear_clic_tabla_si_edita, add="+")

        self.cambiar_estado_inscripcion("disabled")
        self.actualizar_botones_guardado()

        self.actualizar_btn_nuevo_limpiar()

    def _bloquear_combo_si_edita(self, event):
        """Impide absolutamente que el combobox despliegue su lista si se está editando un atleta."""
        if getattr(self, "id_atleta_editando", None) is not None:
            return "break" # Detiene el evento de clic en seco

    def _bloquear_clic_tabla_si_edita(self, event):
        """Impide interactuar con otras filas o deseleccionar la tabla mientras se edita."""
        if getattr(self, "id_atleta_editando", None) is not None:
            return "break" # Detiene el clic del ratón por completo

    def deshacer_cambios_locales(self):
        if not messagebox.askyesno("Deshacer Cambios", "¿Desea descartar todos los cambios locales (eliminaciones, ediciones y nuevos) y recargar la tabla original?"):
            return
            
        self.esta_editando_localmente = True
        self.cancelar_edicion() # Limpia los campos de texto
        
        # 1. Borramos los atletas que no se han subido (los blancos)
        self.inscripciones_memoria = [i for i in self.inscripciones_memoria if i.get('de_red')]
        
        # 2. Limpiamos los estados de edición/eliminación de los que vienen de la red
        for ins in self.inscripciones_memoria:
            if 'estado_local' in ins:
                del ins['estado_local']
                
        # 3. Obligamos al radar a refrescar la vista en el próximo latido
        self._ultima_firma_red = None
        self.actualizar_tabla_visual()
        self.esta_editando_localmente = False
        messagebox.showinfo("Restaurado", "Se han descartado los cambios locales.")

    def bloquear_datos_torneo(self, es_guest):
        """Bloquea o desbloquea el panel izquierdo y gestiona el botón Modificar Torneo."""
        estado_normal = "disabled" if es_guest else "normal"
        estado_combo = "disabled" if es_guest else "readonly"

        controles = [
            (getattr(self, 'ent_tor_nombre', None), estado_normal),
            (getattr(self, 'cmb_categoria', None), estado_combo),
            (getattr(self, 'ent_tor_lugar', None), estado_normal),
            (getattr(self, 'cmb_tor_ciudad', None), estado_combo),
            (getattr(self, 'cmb_tor_tapices', None), estado_combo),
            (getattr(self, 'ent_fecha_inicio', None), estado_normal),
            (getattr(self, 'ent_fecha_fin', None), estado_normal)
            # --- CORRECCIÓN: Se eliminaron los chk_libre, chk_greco y chk_femenina de aquí ---
        ]
        
        for widget, est in controles:
            if widget: 
                widget.config(state=est)

        # --- NUEVO: Mostrar botón para todos, pero bloqueado para invitados ---
        if es_guest:
            if hasattr(self, 'btn_confirmar_torneo'):
                if not self.btn_confirmar_torneo.winfo_ismapped():
                    self.btn_confirmar_torneo.pack(side="left", padx=5, before=self.btn_nuevo_limpiar)
                self.btn_confirmar_torneo.config(state="disabled", text="Modificar Torneo")
            if hasattr(self, 'btn_cancelar_torneo'): 
                self.btn_cancelar_torneo.pack_forget()
        else:
            if hasattr(self, 'btn_confirmar_torneo'):
                if not self.btn_confirmar_torneo.winfo_ismapped():
                    self.btn_confirmar_torneo.pack(side="left", padx=5, before=self.btn_nuevo_limpiar)
                self.btn_confirmar_torneo.config(state="normal")

    def gestionar_estado_botones_red(self, event=None):
        """Activa o desactiva los botones de red según las reglas exactas de selección y el rol."""
        
        # --- NUEVO: CORTAFUEGOS PARA TORNEO FINALIZADO (MODO VISITANTE) ---
        if getattr(self, "torneo_finalizado", False):
            if hasattr(self, 'tabla_red') and self.tabla_red.selection():
                self.tabla_red.selection_remove(self.tabla_red.selection())
            return

        # --- ESCUDO PARA INVITADOS ---
        if not getattr(self.controller, 'es_master', False):
            # Si un invitado intenta hacer clic, deseleccionamos la fila al instante
            if hasattr(self, 'tabla_red') and self.tabla_red.selection():
                self.tabla_red.selection_remove(self.tabla_red.selection())
            
            # Asegurar que todos los controles de red estén apagados
            if hasattr(self, 'btn_confirmar_red'): self.btn_confirmar_red.config(state="disabled")
            if hasattr(self, 'btn_eliminar_red'): self.btn_eliminar_red.config(state="disabled")
            if hasattr(self, 'btn_intercambiar_tapiz'): self.btn_intercambiar_tapiz.config(state="disabled")
            if hasattr(self, 'btn_ceder_master'): self.btn_ceder_master.config(state="disabled")
            return

        # --- LÓGICA PARA EL MÁSTER ---
        seleccionados = self.tabla_red.selection()
        cantidad = len(seleccionados)
        
        # Estado por defecto (Todo bloqueado)
        est_conf = "disabled"
        est_elim = "disabled"
        est_inter = "disabled"
        est_ceder = "disabled"
        
        if cantidad == 1:
            tags = self.tabla_red.item(seleccionados[0], "tags")
            es_yo = "yo_mismo" in tags
            es_confirmado = "confirmado" in tags
            es_pendiente = "pendiente" in tags
            
            if es_yo:
                pass # Regla 1: Se seleccionó a sí mismo. Todo bloqueado.
            elif es_confirmado:
                # Regla 2: Seleccionó a alguien confirmado.
                est_elim = "normal"
                est_ceder = "normal"
            elif es_pendiente:
                # Regla 3: Seleccionó a un pendiente.
                est_conf = "normal"
                est_elim = "normal"
                
        elif cantidad == 2:
            # Regla 4: Dos seleccionados para intercambio.
            tags1 = self.tabla_red.item(seleccionados[0], "tags")
            tags2 = self.tabla_red.item(seleccionados[1], "tags")
            
            valido1 = "confirmado" in tags1 or "yo_mismo" in tags1
            valido2 = "confirmado" in tags2 or "yo_mismo" in tags2
            
            if valido1 and valido2:
                est_inter = "normal"

        # Aplicamos los estados
        if hasattr(self, 'btn_confirmar_red'): self.btn_confirmar_red.config(state=est_conf)
        if hasattr(self, 'btn_eliminar_red'): self.btn_eliminar_red.config(state=est_elim)
        if hasattr(self, 'btn_intercambiar_tapiz'): self.btn_intercambiar_tapiz.config(state=est_inter)
        if hasattr(self, 'btn_ceder_master'): self.btn_ceder_master.config(state=est_ceder)

    def actualizar_botones_guardado(self):
        """Evalúa las reglas visuales de los botones inferiores y de edición."""
        if not hasattr(self, 'btn_guardar_torneo'): return

        is_finalizado = getattr(self, "torneo_finalizado", False)
        is_todo_bloqueado = getattr(self, "todo_bloqueado", False)
        has_id = getattr(self, "torneo_debug_id", None) is not None
        es_master = getattr(self.controller, 'es_master', False)

        # --- NUEVO: Validar si soy un invitado en espera ---
        texto_lbl = self.lbl_tapete_master.cget("text") if hasattr(self, 'lbl_tapete_master') else ""
        soy_guest_pendiente = (not es_master and "⏳" in texto_lbl)

        # 1. SI EL TORNEO ESTÁ CERRADO O TODAS LAS LLAVES CONFIRMADAS
        if is_finalizado or is_todo_bloqueado:
            self.btn_guardar_torneo.pack_forget() 
            if hasattr(self, 'frame_acciones_memoria'):
                self.frame_acciones_memoria.pack_forget() 
            if hasattr(self, 'btn_avanzar_pareo'):
                # BLOQUEO: Si el invitado no está aprobado, no puede avanzar aunque el torneo esté listo
                # EXCEPCIÓN: Si el torneo está FINALIZADO, TODOS pueden avanzar para ver el historial
                if soy_guest_pendiente and not is_finalizado:
                    self.btn_avanzar_pareo.config(state="disabled")
                else:
                    self.btn_avanzar_pareo.config(state="normal")
            return

        # 2. SI EL TORNEO ESTÁ ACTIVO
        if hasattr(self, 'frame_acciones_memoria') and not self.frame_acciones_memoria.winfo_ismapped():
            self.frame_acciones_memoria.pack(side="left", before=self.lbl_estadisticas)

        if has_id:
            if not self.btn_guardar_torneo.winfo_ismapped():
                self.btn_guardar_torneo.pack(side="left", fill="x", expand=True, padx=(0, 2))
                
            if es_master:
                self.btn_guardar_torneo.config(state="normal", text="💾 Guardar Cambios")
                estado_pareo = "normal" 
            else:
                estado = "normal" if "✅" in texto_lbl else "disabled"
                self.btn_guardar_torneo.config(state=estado, text="☁️ Sincronizar Atletas")
                estado_pareo = estado 
                
            if hasattr(self, 'btn_avanzar_pareo'):
                self.btn_avanzar_pareo.config(state=estado_pareo)
                
        else:
            if not self.btn_guardar_torneo.winfo_ismapped():
                self.btn_guardar_torneo.pack(side="left", fill="x", expand=True, padx=(0, 2))
                
            if getattr(self, 'categoria_confirmada', None):
                self.btn_guardar_torneo.config(state="normal", text="✅ Confirmar y Crear Sala")
            else:
                self.btn_guardar_torneo.config(state="disabled", text="✅ Confirmar y Crear Sala")
                
            if hasattr(self, 'btn_avanzar_pareo'):
                self.btn_avanzar_pareo.config(state="disabled")

    def limpiar_buscador(self, entry, listbox, lista_completa):
        """Borra el texto del buscador y restaura la lista visual original."""
        entry.delete(0, tk.END)
        self.filtrar_listbox(listbox, entry, lista_completa)
        # Retorna el foco a la tabla para evitar que el cursor se quede en el buscador
        self.tabla.focus_set()

    def actualizar_categoria_dinamica(self, *args):
        # --- CORTAFUEGOS 1: Si el combobox de atleta está vacío, abortar silenciosamente ---
        # Esto evita el error emergente cuando acabas de añadir a alguien y el peso sigue ahí.
        if hasattr(self, 'cmb_atleta'):
            texto_atleta = self.cmb_atleta.get().strip()
            if not texto_atleta:
                if hasattr(self, 'lbl_cat_dinamica'):
                    self.lbl_cat_dinamica.config(text="Categoría: --", foreground="gray")
                return

            # --- REGLA DE NO DESELECCIONAR TODOS ---
            atleta = next((a for a in getattr(self, "atletas_filtrados_objetos", []) if f"{a.get('apellidos', '')}, {a.get('nombre', '')} (ID: {a.get('id', '')})" == texto_atleta), None)
            
            if atleta:
                if not (self.var_estilo_libre.get() or self.var_estilo_greco.get() or self.var_estilo_femenina.get()):
                    if str(atleta.get('sexo', '')).upper() == 'M': self.var_estilo_libre.set(True)
                    else: self.var_estilo_femenina.set(True)

        peso_str = getattr(self, 'var_peso', tk.StringVar()).get().strip()
        if not peso_str:
            if hasattr(self, 'lbl_cat_dinamica'):
                self.lbl_cat_dinamica.config(text="Categoría: --", foreground="gray")
            return
            
        try: peso_dado = float(peso_str)
        except ValueError:
            self.lbl_cat_dinamica.config(text="Categoría: Error", foreground="red")
            return
            
        if peso_dado <= 20: 
            self.lbl_cat_dinamica.config(text="Peso irreal", foreground="red")
            return

        if not getattr(self, 'categoria_confirmada', None):
            self.lbl_cat_dinamica.config(text="Confirme torneo primero", foreground="orange")
            return

        estilos_sel = []
        if self.var_estilo_libre.get(): estilos_sel.append(("Estilo Libre", 1)) 
        if self.var_estilo_greco.get(): estilos_sel.append(("Grecorromana", 2))
        if self.var_estilo_femenina.get(): estilos_sel.append(("Femenina", 3))

        # --- CORTAFUEGOS 2: Sustituimos el messagebox por un texto visual ---
        if not estilos_sel:
            if hasattr(self, 'lbl_cat_dinamica'):
                self.lbl_cat_dinamica.config(text="Categoría: Faltan Estilos", foreground="orange")
            return

        id_cat_torneo = next((c['id'] for c in self.categorias_db if c['nombre'] == self.categoria_confirmada), None)
        
        cats_encontradas = []
        for nombre_estilo, id_estilo in estilos_sel:
            bracket_encontrado = None
            for p in getattr(self, 'pesos_oficiales_db', []):
                if str(p['id_categoria_edad']) == str(id_cat_torneo) and str(p['id_estilo_lucha']) == str(id_estilo):
                    if float(p['peso_minimo']) <= peso_dado <= float(p['peso_maximo']):
                        bracket_encontrado = p
                        break
            
            abr = "Lib" if nombre_estilo == "Estilo Libre" else nombre_estilo[:3]
            
            if bracket_encontrado:
                cats_encontradas.append(f"{abr}: {bracket_encontrado['peso_maximo']}kg")
            else:
                cats_encontradas.append(f"{abr}: Fuera de Rango")
        
        texto_final = " | ".join(cats_encontradas)
        color = "red" if "Fuera" in texto_final else "#17a2b8"
        if hasattr(self, 'lbl_cat_dinamica'):
            self.lbl_cat_dinamica.config(text=f"Asignación: {texto_final}", foreground=color)

    def al_cambiar_filtro_estilo(self, event=None):
        """Manejador para cuando el usuario cambia la selección de estilos."""
        self.actualizar_opciones_filtros()
        self.actualizar_tabla_visual()

    def on_double_click_tabla(self, event):
        """Si se hace doble clic sobre una fila, evalúa si el atleta puede ser editado automáticamente."""
        # 1. Usar identify_row es 100% preciso basándose en la coordenada Y del ratón
        item_clickeado = self.tabla.identify_row(event.y)
        
        # Si no detecta ninguna fila (hizo clic en lo blanco), no hace nada
        if not item_clickeado: 
            return
            
        # 2. Forzamos la lectura del estado a string para evitar falsos negativos de Tkinter
        if str(self.btn_editar_memoria.cget("state")) == "normal":
            self.cargar_para_editar()

    def actualizar_btn_nuevo_limpiar(self):
        """Mantiene el botón siempre visible y con el texto/estado correcto según la fase."""
        if not hasattr(self, 'btn_nuevo_limpiar'): return
        
        # Asegurarse de que el botón esté visible en la interfaz
        if not self.btn_nuevo_limpiar.winfo_ismapped():
            self.btn_nuevo_limpiar.pack(side="left", padx=5)

        # EVALUACIÓN DE REGLAS:
        if getattr(self, "torneo_debug_id", None) is not None:
            # Reglas 2, 3 y 4: Torneo en Base de Datos (Guardado, Cargado o en Edición Post-Guardado)
            self.btn_nuevo_limpiar.config(text="Nuevo Torneo (Salir)", state="normal")
            
        elif getattr(self, "categoria_confirmada", None) is not None:
            # Regla 1: Torneo Nuevo con datos confirmados localmente (Aún no subido a la BD)
            self.btn_nuevo_limpiar.config(text="Limpiar Torneo", state="normal")
            
        else:
            # Regla 5: Estado inicial, vacío o recién clickeado en "Nuevo/Limpiar"
            self.btn_nuevo_limpiar.config(text="Limpiar Torneo", state="disabled")

    def resetear_torneo(self, forzar=False):
        """Borra la memoria y resetea la pantalla a su estado inicial de fábrica."""
        # Si no es un reseteo forzado (ej. el usuario hizo clic en el botón), preguntamos
        if not forzar:
            respuesta = messagebox.askyesno("Confirmar", "¿Está seguro de limpiar todos los datos y empezar de cero? Se perderán las inscripciones no guardadas.")
            if not respuesta: return
        
        # --- SALIR DE LA SALA DE RED ACTUAL Y HEREDAR MÁSTER ---
        if hasattr(self.controller, 'id_conexion_red') and self.controller.id_conexion_red:
            self.db.eliminar_conexion_instancia(self.controller.id_conexion_red)
            self.controller.id_conexion_red = None
            self.controller.es_master = False
            self.controller.tapiz_asignado = None

        # 1. Resetear variables lógicas
        self.torneo_debug_id = None
        self.categoria_confirmada = None
        self.torneo_nombre_conf = ""
        self.torneo_lugar_conf = ""
        self.torneo_ciudad_conf = ""
        self.todo_bloqueado = False
        self.bloquear_seleccion_tabla = False # <--- NUEVA LÍNEA AÑADIDA
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
        if hasattr(self, 'frame_acciones_memoria') and not self.frame_acciones_memoria.winfo_ismapped():
            self.frame_acciones_memoria.pack(side="left", before=self.lbl_estadisticas)
        
        # Asegurarse de que regresen desactivados
        if hasattr(self, 'btn_editar_memoria'):
            self.btn_editar_memoria.config(state="disabled")
            self.btn_eliminar_memoria.config(state="disabled")
        
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
        if hasattr(self, 'ent_busqueda'):
            self.limpiar_filtros()
        else:
            self.actualizar_opciones_filtros()
            self.actualizar_tabla_visual()
        
        self.cambiar_estado_inscripcion("disabled")
        self.form_frame.config(text="2. Inscripción y Pesaje (Confirmar torneo para habilitar)")

        # --- BLOQUEO DE GESTIÓN DE RED ---
        self.escuchando_red = False

        self.btn_guardar_torneo.config(
            state="disabled", 
            text="✅ Confirmar y Crear Sala",
            bg="#28a745"
        )
        self.btn_avanzar_pareo.config(state="disabled")
        
        self.btn_confirmar_red.config(state="disabled")
        self.btn_eliminar_red.config(state="disabled")
        self.btn_intercambiar_tapiz.config(state="disabled")
        self.btn_ceder_master.config(state="disabled")
        
        # Limpiar la tabla de red
        for item in self.tabla_red.get_children():
            self.tabla_red.delete(item)

        # --- NUEVO: RESTAURAR ETIQUETA DEL MÁSTER ---
        self.lbl_tapete_master.config(
            text="🥇 Tapete Máster: (Esperando creación de sala...)", 
            foreground="black" # Restauramos al color original (o el color por defecto de tu tema)
        )
        
        # --- NUEVO: Ocultar el botón tras limpiar ---
        self.actualizar_btn_nuevo_limpiar()
        
        # --- NUEVO: Ocultar el botón tras limpiar ---
        self.actualizar_btn_nuevo_limpiar()

        self.torneo_finalizado = False
        self.actualizar_botones_guardado()

    def al_seleccionar_tabla(self, event=None):
        # --- CORTAFUEGOS: Evitar deselección o cambio de fila con el teclado durante edición ---
        if getattr(self, "id_atleta_editando", None) is not None:
            # Forzar a mantener la selección en el atleta que se está editando
            for item in self.tabla.get_children():
                if self.tabla.item(item, "values") and int(self.tabla.item(item, "values")[0]) == self.id_atleta_editando:
                    if item not in self.tabla.selection():
                        self.tabla.selection_set(item)
                    break
            return

        # Resto de la lógica normal
        if getattr(self, "todo_bloqueado", False) or getattr(self, "bloquear_seleccion_tabla", False):
            if self.tabla.selection(): self.tabla.selection_remove(self.tabla.selection()[0])
            return
            
        item_sel = self.tabla.selection()
        if not item_sel: return
        valores = self.tabla.item(item_sel[0], "values")
        id_atleta = int(valores[0])
        
        ins_data = next((i for i in self.inscripciones_memoria if i['id_atleta'] == id_atleta), None)
        if not ins_data: return
        
        is_locked = any(div_id in getattr(self, "pesos_bloqueados_ids", set()) for div_id in ins_data['ids_divisiones'])
        
        is_deleted = ins_data.get('estado_local') == 'eliminado' or (ins_data.get('tipo_cambio_red') == 'eliminado' and ins_data.get('ciclos_red', 2) < 2)
        
        if is_locked or is_deleted:
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
        # 1. Se limpia la barra automáticamente al cambiar de opción
        self.ent_busqueda.delete(0, tk.END)
        
        tipo = self.cmb_tipo_busqueda.get()
        
        # 2. Se activa o desactiva la validación de "Solo Números"
        if tipo == "ID": 
            self.ent_busqueda.config(validate='key', validatecommand=self.vcmd_id)
        else: 
            self.ent_busqueda.config(validate='none')
            
        self.actualizar_tabla_visual()

    def limpiar_filtros(self):
        """Restablece todos los parámetros de búsqueda a su estado inicial."""
        self.cmb_tipo_busqueda.set("Nombre")
        self.cambiar_tipo_busqueda() # Esto limpia el entry y ajusta validaciones
        
        self.var_filtro_m.set(True)
        self.var_filtro_f.set(True)
        
        self.listbox_pesos.selection_clear(0, tk.END)
        self.listbox_estilos.selection_clear(0, tk.END)
        
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
        mapping = {"Lib": "Estilo Libre", "Gre": "Grecorromana", "Fem": "Femenina"}

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
        else:
            # Forzamos la validación para que los estilos nazcan apagados
            self.al_seleccionar_atleta()

    def gestionar_bloqueo_torneo(self):
        # --- BARRERA DE SEGURIDAD PARA TORNEOS FINALIZADOS ---
        if getattr(self, "torneo_finalizado", False):
            return messagebox.showwarning("Torneo Finalizado", "No se puede modificar la información de un torneo que ya ha sido cerrado.")

        if self.btn_confirmar_torneo.cget("text") == "Modificar Torneo":
            self.ent_tor_nombre.config(state="normal")
            self.ent_tor_lugar.config(state="normal")
            self.cmb_tor_ciudad.config(state="normal")
            
            # --- NUEVO: BLOQUEO ABSOLUTO DE CATEGORÍA ---
            # Si hay al menos un peso bloqueado/confirmado, la categoría no se puede tocar
            if getattr(self, "pesos_bloqueados_ids", set()):
                self.cmb_categoria.config(state="disabled")
            else:
                self.cmb_categoria.config(state="normal")
                
            self.btn_confirmar_torneo.config(text="Guardar Cambios")
            self.btn_cancelar_torneo.pack(side="left", padx=5)
            self.cambiar_estado_inscripcion("disabled")
            self.form_frame.config(text="2. Inscripción y Pesaje (Confirme datos para habilitar)")
            return

        nombre = self.ent_tor_nombre.get().strip()
        lugar = self.ent_tor_lugar.get().strip()
        cat = self.cmb_categoria.get()
        ciu = self.cmb_tor_ciudad.get()

        if not nombre or not lugar or not ciu or not cat:
            return messagebox.showwarning("Incompleto", "Llene nombre, lugar, ciudad y categoría.")

        if self.categoria_confirmada is not None and self.categoria_confirmada != cat:
            # --- NUEVO: Doble validación de seguridad contra cambios ilícitos ---
            if getattr(self, "pesos_bloqueados_ids", set()):
                self.cmb_categoria.set(self.categoria_confirmada)
                return messagebox.showwarning("Bloqueado", "No se puede cambiar la categoría porque ya existen llaves en curso.")
                
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
        self.torneo_ciudad_conf = ciu

        self.ent_tor_nombre.config(state="disabled")
        self.ent_tor_lugar.config(state="disabled")
        self.cmb_categoria.config(state="disabled")
        self.cmb_tor_ciudad.config(state="disabled") 
        
        self.btn_confirmar_torneo.config(text="Modificar Torneo")
        self.btn_cancelar_torneo.pack_forget()

        # --- AHORA SÍ: DESBLOQUEAMOS LAS INSCRIPCIONES ---
        self.form_frame.config(text="2. Inscripción y Pesaje (Habilitado)")
        self.cambiar_estado_inscripcion("normal")
        # Si los datos son válidos y se bloquea la edición de datos generales:
        self.btn_guardar_torneo.config(state="normal") # Se activa para permitir "Crear Sala"
        
        # Habilitar controles de red
        self.btn_confirmar_red.config(state="normal")
        self.btn_eliminar_red.config(state="normal")
        self.btn_intercambiar_tapiz.config(state="normal")
        
        # --- NUEVO: RECARGAMOS LOS ATLETAS AL CONFIRMAR LA CATEGORÍA ---
        self.filtrar_atletas_por_edad()

        self.actualizar_btn_nuevo_limpiar()

    def cancelar_edicion_torneo(self):
        # 1. Habilitar temporalmente para poder restaurar los datos
        self.ent_tor_nombre.config(state="normal")
        self.ent_tor_lugar.config(state="normal")
        self.cmb_tor_ciudad.config(state="normal")
        self.cmb_categoria.config(state="normal")

        # 2. Restaurar datos desde la memoria
        self.ent_tor_nombre.delete(0, tk.END)
        self.ent_tor_nombre.insert(0, self.torneo_nombre_conf)
        self.ent_tor_lugar.delete(0, tk.END)
        self.ent_tor_lugar.insert(0, self.torneo_lugar_conf)
        self.cmb_tor_ciudad.set(getattr(self, 'torneo_ciudad_conf', '')) 
        self.cmb_categoria.set(self.categoria_confirmada)

        # 3. Volver a bloquear la cabecera
        self.ent_tor_nombre.config(state="disabled")
        self.ent_tor_lugar.config(state="disabled")
        self.cmb_categoria.config(state="disabled")
        self.cmb_tor_ciudad.config(state="disabled") 
        
        self.btn_confirmar_torneo.config(text="Modificar Torneo")
        self.btn_cancelar_torneo.pack_forget()
        
        # --- NUEVO: PREGUNTAR ANTES DE HABILITAR LA INSCRIPCIÓN ---
        if getattr(self, "todo_bloqueado", False):
            self.form_frame.config(text="2. Inscripción y Pesaje (Torneo Bloqueado)")
            self.cambiar_estado_inscripcion("disabled")
        else:
            self.form_frame.config(text="2. Inscripción y Pesaje (Habilitado)")
            self.cambiar_estado_inscripcion("normal")

        self.actualizar_btn_nuevo_limpiar()

    # ================= LÓGICA DE INSCRIPCIONES Y PESOS OFICIALES =================
    def cargar_para_editar(self):
        item_sel = self.tabla.selection()
        if not item_sel: return messagebox.showwarning("Selección", "Seleccione un atleta de la tabla.")
        
        valores = self.tabla.item(item_sel[0], "values")
        self.id_atleta_editando = int(valores[0])

        # --- CORRECCIÓN: Limpiar prefijos visuales (RED, NUEVO, etc.) del nombre ---
        nombre_crudo = valores[2].replace("🌐 [RED] ", "").replace("✨ [NUEVO] ", "").replace("✏️ [EDITAR] ", "").replace("❌ [ELIMINAR] ", "").replace("🔄 [EDITADO] ", "").replace("🗑️ [BORRADO] ", "")

        # Asignar el valor limpio para que el buscador interno lo encuentre a la perfección
        atleta_str = f"{nombre_crudo} (ID: {self.id_atleta_editando})"
        self.cmb_atleta.set(atleta_str)
        
        # Al ejecutar esto ahora, SÍ encontrará al atleta y desbloqueará las casillas según su sexo
        self.al_seleccionar_atleta(None)
        
        self.var_peso.set(valores[6])

        self.var_estilo_libre.set(True if "Libre" in valores[8] else False) 
        self.var_estilo_greco.set(True if "Grecorromana" in valores[8] else False)
        self.var_estilo_femenina.set(True if "Femenina" in valores[8] else False)

        self.btn_agregar.config(text="Actualizar Inscripción")
        if hasattr(self, 'btn_cancelar_edicion'):
            self.btn_cancelar_edicion.pack(side="left", padx=5)
        self.cmb_atleta.config(state="disabled")

    def cancelar_edicion(self):
        self.id_atleta_editando = None
        self.item_tree_editando = None
        self.btn_agregar.config(text="Añadir a Memoria")
        if hasattr(self, 'btn_cancelar_edicion'):
            self.btn_cancelar_edicion.pack_forget()
            
        # --- DESBLOQUEAR Y VACIAR CAMPOS ---
        self.cmb_atleta.config(state="normal") 
        self.cmb_atleta.set('')
        
        if hasattr(self, 'var_peso'):
            self.var_peso.set('') # Vaciamos el peso explícitamente
            
        self.al_seleccionar_atleta() # Esto apagará y vaciará los checkboxes de estilo

    def agregar_a_memoria(self):
        self.esta_editando_localmente = True
        if getattr(self, "_procesando_agregado", False): return
        self._procesando_agregado = True

        # MANDAR EL FOCO A LA TABLA PARA "MATAR" EL ENTER DEL BOTÓN
        self.tabla.focus_set()
        
        try:
            texto_atleta = self.cmb_atleta.get().strip()
            peso_str = self.ent_peso.get().strip()
            
            # --- CORTAFUEGOS 1: Prevenir "clic fantasma" tras limpiar el formulario ---
            if not texto_atleta and not peso_str: 
                return
                
            if not texto_atleta or not peso_str: 
                messagebox.showwarning("Incompleto", "Seleccione atleta y peso.")
                return

            try: peso_dado = float(peso_str)
            except ValueError: return messagebox.showwarning("Error", "Peso inválido.")

            atleta = next((a for a in getattr(self, "atletas_filtrados_objetos", []) if f"{a['apellidos']}, {a['nombre']} (ID: {a['id']})" == texto_atleta), None)
            if not atleta: return messagebox.showwarning("Error", "Atleta no válido.")

            id_cat_torneo = next((int(c['id']) for c in self.categorias_db if c['nombre'] == self.categoria_confirmada), None)
            
            estilos_sel = []
            if self.var_estilo_libre.get(): estilos_sel.append(("Estilo Libre", 1))
            if self.var_estilo_greco.get(): estilos_sel.append(("Grecorromana", 2))
            if self.var_estilo_femenina.get(): estilos_sel.append(("Femenina", 3))

            if not estilos_sel: return messagebox.showwarning("Estilo Requerido", "Seleccione un estilo.")

            pesos_oficiales_text, estilos_memoria, ids_divisiones = [], [], []

            for nombre_estilo, id_estilo in estilos_sel:
                bracket_encontrado = None
                for p in self.pesos_oficiales_db:
                    if int(p['id_categoria_edad']) == id_cat_torneo and int(p['id_estilo_lucha']) == int(id_estilo):
                        if float(p['peso_minimo']) <= peso_dado <= float(p['peso_maximo']):
                            bracket_encontrado = p
                            break
                
                if not bracket_encontrado: 
                    return messagebox.showwarning("Fuera de Rango", f"El peso {peso_dado}kg no existe para {nombre_estilo}.")
            
                abr = "Lib" if nombre_estilo == "Estilo Libre" else nombre_estilo[:3]
                pesos_oficiales_text.append(f"{abr}: {bracket_encontrado['peso_maximo']}kg")
                estilos_memoria.append(nombre_estilo)
                ids_divisiones.append(int(bracket_encontrado['id']))

            texto_peso_oficial = " | ".join(pesos_oficiales_text)
            peso_formateado = f"{peso_dado:.2f}"

            # --- RUTA 1: ACTUALIZANDO UN ATLETA EXISTENTE ---
            if self.id_atleta_editando is not None:
                for ins in self.inscripciones_memoria:
                    if ins['id_atleta'] == self.id_atleta_editando:
                        ins.update({'peso': peso_formateado, 'peso_oficial': texto_peso_oficial, 'estilos': estilos_memoria, 'ids_divisiones': ids_divisiones})
                        if ins.get('de_red'):
                            ins['estado_local'] = 'editado'
                        break
                self.actualizar_tabla_visual()
                
                # Reseleccionar en la tabla tras actualizar
                for item in self.tabla.get_children():
                    if int(self.tabla.item(item, "values")[0]) == self.id_atleta_editando:
                        self.tabla.selection_set(item)
                        self.al_seleccionar_tabla(None)
                        break
                        
                self.cancelar_edicion()
                return messagebox.showinfo("Actualizado", "Inscripción actualizada localmente.\nRecuerde presionar 'Sincronizar' para guardar.")

            if any(ins['id_atleta'] == atleta['id'] for ins in self.inscripciones_memoria):
                return messagebox.showwarning("Duplicado", "Este atleta ya está en la lista.")

            # --- RUTA 2: AGREGANDO UN ATLETA NUEVO ---
            self.inscripciones_memoria.append({
                "id_atleta": int(atleta['id']), "peso": peso_formateado, "peso_oficial": texto_peso_oficial, 
                "estilos": estilos_memoria, "ids_divisiones": ids_divisiones, "de_red": False
            })
            self.actualizar_tabla_visual()
            
            # --- CORTAFUEGOS 2: Seleccionar automáticamente al atleta recién añadido ---
            for item in self.tabla.get_children():
                if int(self.tabla.item(item, "values")[0]) == int(atleta['id']):
                    self.tabla.selection_set(item)
                    self.al_seleccionar_tabla(None)
                    break

            # Limpiar y bloquear campos tras agregar a memoria de forma segura
            self.cmb_atleta.set('')
            self.al_seleccionar_atleta() 

        finally:
            self.esta_editando_localmente = False
            self.after(500, lambda: setattr(self, "_procesando_agregado", False))

    def eliminar_de_memoria(self):
        self.esta_editando_localmente = True
        item_sel = self.tabla.selection()
        if not item_sel: return
        
        valores = self.tabla.item(item_sel[0], "values")
        nombre_atleta = valores[2].replace("🌐 [RED] ", "").replace("✨ [NUEVO] ", "").replace("✏️ [EDITAR] ", "").replace("🔄 [EDITADO] ", "").replace("🗑️ [BORRADO] ", "")
        id_atleta = int(valores[0])
        
        if not messagebox.askyesno("Marcar Eliminación", f"¿Marcar a '{nombre_atleta}' para ser eliminado?\n\nEl cambio se aplicará a la sala cuando presione 'Sincronizar'."): 
            self.esta_editando_localmente = False
            return
            
        if self.id_atleta_editando == id_atleta: 
            self.cancelar_edicion() 
            
        # --- LÓGICA DE ELIMINACIÓN INTELIGENTE ---
        for ins in self.inscripciones_memoria:
            if ins['id_atleta'] == id_atleta:
                if not ins.get('de_red'):
                    # Si era local (blanco) y lo borras, desaparece de inmediato porque no existía en la BD
                    self.inscripciones_memoria.remove(ins)
                else:
                    # Si ya estaba en la red, lo marcamos para que se pinte de rojo
                    ins['estado_local'] = 'eliminado'
                break

        self.actualizar_opciones_filtros()
        self.actualizar_tabla_visual()
        self.esta_editando_localmente = False

    def actualizar_tabla_visual(self, event=None):
        if not hasattr(self, 'tabla'): return 
        
        # --- NUEVO: Memorizar qué atleta estaba seleccionado ---
        ids_seleccionados = [str(self.tabla.item(i, "values")[0]) for i in self.tabla.selection()]
        
        for item in self.tabla.get_children(): self.tabla.delete(item)

        tipo_busq = getattr(self, 'cmb_tipo_busqueda', None)
        if not tipo_busq: return 
        tipo = tipo_busq.get()
        term = self.ent_busqueda.get().strip().lower()

        mostrar_m = self.var_filtro_m.get()
        mostrar_f = self.var_filtro_f.get()
        sel_pesos = [self.listbox_pesos.get(i) for i in self.listbox_pesos.curselection()]
        sel_estilos = [self.listbox_estilos.get(i) for i in self.listbox_estilos.curselection()]

        total_atletas = 0
        clubes_unicos = set()
        ciudades_unicas = set()

        for ins in self.inscripciones_memoria:
            id_atl = ins['id_atleta']
            info = next((a for a in self.atletas_db if a['id'] == id_atl), None)
            if not info: continue

            if info['sexo'] == 'M' and not mostrar_m: continue
            if info['sexo'] == 'F' and not mostrar_f: continue

            if sel_pesos:
                pesos_atl = ins['peso_oficial'].split(" | ")
                if not any(p in sel_pesos for p in pesos_atl): continue
            
            if sel_estilos and not any(e in sel_estilos for e in ins['estilos']): continue

            nombre_completo = f"{info['apellidos']}, {info['nombre']}"
            club = info['club'] or "Sin Club"
            ciudad = info['ciudad'] or "Sin Ciudad"
            
            if term:
                if tipo == "ID" and str(id_atl) != term: continue
                if tipo == "Nombre" and term not in nombre_completo.lower(): continue
                if tipo == "Club" and term not in club.lower(): continue
                if tipo == "Ciudad" and term not in ciudad.lower(): continue

            is_dsq = id_atl in getattr(self, "atletas_descalificados_ids", set())
            tags_list = ["dsq"] if is_dsq else []
            
            divisiones_atleta = ins.get('ids_divisiones', [])
            bloqueadas = getattr(self, "pesos_bloqueados_ids", set())
            todas_bloqueadas = all((d in bloqueadas) for d in divisiones_atleta) if divisiones_atleta else False
            
            prefijo = ""
            estado_local = ins.get('estado_local')
            
            if estado_local == 'eliminado':
                prefijo = "❌ [ELIMINAR] "
                tags_list.append("eliminado_local")
            elif estado_local == 'editado':
                prefijo = "✏️ [EDITAR] "
                tags_list.append("editado_local")
            elif todas_bloqueadas:
                if not is_dsq: tags_list.append("confirmado")
            elif ins.get("de_red", False):
                ciclos = ins.get("ciclos_red", 2)
                tipo_cambio = ins.get("tipo_cambio_red", "nuevo")
                
                # --- FIX: Prioridad absoluta al estado de borrado ---
                if tipo_cambio == 'eliminado':
                    prefijo = "🗑️ [BORRADO] "
                    tags_list.append("eliminado_red")
                elif ciclos < 2:
                    if tipo_cambio == 'editado':
                        prefijo = "🔄 [EDITADO] "
                        tags_list.append("editado_red")
                    else:
                        prefijo = "✨ [NUEVO] "
                        tags_list.append("red_nuevo")
                else:
                    prefijo = "🌐 [RED] "
                    tags_list.append("sync_red")
                    
            nombre_mostrar = prefijo + nombre_completo
            tags = tuple(tags_list)

            fila_valores = (id_atl, 0, nombre_mostrar, info['sexo'], club, ciudad, ins['peso'], ins['peso_oficial'], " + ".join(ins['estilos']))
            
            # --- NUEVO: Insertar y devolver la selección automáticamente ---
            nuevo_item = self.tabla.insert("", "end", values=fila_valores, tags=tags)
            if str(id_atl) in ids_seleccionados:
                self.tabla.selection_add(nuevo_item)
            
            total_atletas += 1
            if club != "Sin Club": clubes_unicos.add(club)
            if ciudad != "Sin Ciudad": ciudades_unicas.add(ciudad)

        if hasattr(self, 'lbl_estadisticas'):
            color_estado = "#6f42c1" if getattr(self, "todo_bloqueado", False) else "#28a745"
            self.lbl_estadisticas.config(text=f"Atletas: {total_atletas}  |  Clubes: {len(clubes_unicos)}  |  Ciudades: {len(ciudades_unicas)}", foreground=color_estado)
            
        # --- CORTAFUEGOS: Re-evaluar botones en lugar de apagarlos ciegamente ---
        if self.tabla.selection():
            self.al_seleccionar_tabla(None)
        else:
            if hasattr(self, 'btn_editar_memoria'):
                self.btn_editar_memoria.config(state="disabled")
                self.btn_eliminar_memoria.config(state="disabled")

        hay_cambios_pendientes = any(i.get('estado_local') or not i.get('de_red') for i in self.inscripciones_memoria)
        if hasattr(self, 'btn_deshacer_memoria'):
            self.btn_deshacer_memoria.config(state="normal" if hay_cambios_pendientes else "disabled")

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

    def filtrar_atletas_por_edad(self):
        # 1. DESCARGA EN VIVO: Siempre usar datos frescos de la BD
        if hasattr(self, 'db'):
            self.atletas_db = self.db.obtener_atletas()

        # Usar la variable de memoria porque el combobox bloqueado devuelve vacío
        nombre_cat = getattr(self, 'categoria_confirmada', None)
        if not nombre_cat:
            nombre_cat = self.cmb_categoria.get().strip()
            
        if not nombre_cat: 
            return

        # 2. MATCH TOLERANTE: Ignora mayúsculas y espacios extra
        cat = next((c for c in getattr(self, 'categorias_db', []) if str(c.get('nombre', '')).strip().lower() == nombre_cat.lower()), None)
        
        # Si no hay categoría válida, la lista queda estrictamente vacía
        if not cat: 
            if hasattr(self, 'cmb_atleta'):
                self.cmb_atleta.config(values=[])
                self.cmb_atleta.set('')
            return

        anio_torneo = datetime.now().year
        self.atletas_filtrados_objetos = []
        atletas_permitidos = []

        # 3. TOLERANCIA DE COLUMNAS
        try: e_min = int(cat.get('edad_minima', cat.get('edad_min', 0)))
        except: e_min = 0
        try: e_max = int(cat.get('edad_maxima', cat.get('edad_max', 99)))
        except: e_max = 99

        import re
        for atleta in getattr(self, 'atletas_db', []):
            fecha_nac = atleta.get('fecha_nacimiento', '')
            anio_nac = anio_torneo 
            
            # EXTRACCIÓN CON EXPRESIÓN REGULAR
            if hasattr(fecha_nac, 'year'):
                anio_nac = fecha_nac.year
            else:
                match = re.search(r'\d{4}', str(fecha_nac))
                if match:
                    anio_nac = int(match.group())
            
            edad_uww = anio_torneo - anio_nac
            
            # Filtro ESTRICTO de Edad UWW
            if e_min <= edad_uww <= e_max:
                texto_combo = f"{atleta.get('apellidos', '')}, {atleta.get('nombre', '')} (ID: {atleta.get('id', '')})"
                atletas_permitidos.append(texto_combo)
                self.atletas_filtrados_objetos.append(atleta)

        # 4. INYECCIÓN AL COMBOBOX
        if hasattr(self, 'cmb_atleta'):
            self.cmb_atleta.config(values=atletas_permitidos)
            try:
                aplicar_autocompletado(self.cmb_atleta, atletas_permitidos)
            except:
                pass
            self.cmb_atleta.set('')

    def al_seleccionar_atleta(self, event=None):
        if not hasattr(self, 'cmb_atleta'): return
        
        texto_atleta = self.cmb_atleta.get().strip()
        
        # Función interna rápida para apagar y bloquear
        def forzar_bloqueo():
            self.var_estilo_libre.set(False)
            self.var_estilo_greco.set(False)
            self.var_estilo_femenina.set(False)
            if hasattr(self, 'chk_libre'): self.chk_libre.config(state="disabled")
            if hasattr(self, 'chk_greco'): self.chk_greco.config(state="disabled")
            if hasattr(self, 'chk_femenina'): self.chk_femenina.config(state="disabled")
            self.actualizar_categoria_dinamica()
        
        if not texto_atleta: 
            return forzar_bloqueo()
            
        atleta = next((a for a in getattr(self, "atletas_filtrados_objetos", []) if f"{a.get('apellidos', '')}, {a.get('nombre', '')} (ID: {a.get('id', '')})" == texto_atleta), None)
        
        if not atleta: 
            return forzar_bloqueo()

        self.var_estilo_libre.set(False)
        self.var_estilo_greco.set(False)
        self.var_estilo_femenina.set(False)

        sexo = str(atleta.get('sexo', '')).upper()
        if sexo == 'M':
            if hasattr(self, 'chk_libre'): self.chk_libre.config(state="normal")
            if hasattr(self, 'chk_greco'): self.chk_greco.config(state="normal")
            if hasattr(self, 'chk_femenina'): self.chk_femenina.config(state="disabled")
            self.var_estilo_libre.set(True)
        else:
            if hasattr(self, 'chk_libre'): self.chk_libre.config(state="disabled")
            if hasattr(self, 'chk_greco'): self.chk_greco.config(state="disabled")
            if hasattr(self, 'chk_femenina'): self.chk_femenina.config(state="normal")
            self.var_estilo_femenina.set(True)

        self.actualizar_categoria_dinamica()

    def abrir_ventana_nuevo(self):
        # Saber si soy un invitado
        es_master = getattr(self.controller, 'es_master', True)
        soy_guest = getattr(self, "torneo_debug_id", None) and not es_master
        
        VentanaNuevoRegistro(self, es_master=not soy_guest)

    def guardar_progreso(self):
        self._ejecutar_guardado(ir_a_pareo=False)

    def subir_inscripciones_bd(self):
        self._ejecutar_guardado(ir_a_pareo=True)

    def _ejecutar_guardado(self, ir_a_pareo=False):
        if not self.inscripciones_memoria: 
            return messagebox.showwarning("Sin Atletas", "No hay atletas inscritos.")
            
        # --- REGLA: SI ESTÁ TODO BLOQUEADO O FINALIZADO, SOLO AVANZAR ---
        if getattr(self, "torneo_finalizado", False) or getattr(self, "todo_bloqueado", False):
            if ir_a_pareo and getattr(self, "torneo_debug_id", None):
                from pantalla_pareo import PantallaPareo
                p_pareo = self.controller.pantallas.get(PantallaPareo)
                if p_pareo:
                    p_pareo.cargar_torneo(self.torneo_debug_id)
                    self.controller.mostrar_pantalla(PantallaPareo)
            return

        # 1. Agrupar y Validar Parejas
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
                if clave_div not in divisiones: divisiones[clave_div] = []
                divisiones[clave_div].append(nombre_atleta)
                
        hay_pareja = False
        atletas_solitarios = {} 
        for (id_div, estilo, peso_str), atletas in divisiones.items():
            if len(atletas) >= 2: 
                hay_pareja = True
            elif len(atletas) == 1:
                # --- NUEVA CONDICIÓN: Ignorar si la llave de esta división ya fue confirmada ---
                if id_div not in getattr(self, "pesos_bloqueados_ids", set()):
                    nombre = atletas[0]
                    if nombre not in atletas_solitarios: 
                        atletas_solitarios[nombre] = []
                    atletas_solitarios[nombre].append(f"{estilo} - {peso_str}")
                
        if not hay_pareja:
            return messagebox.showwarning("Parejas Insuficientes", "Debe haber al menos 2 atletas en una misma división.")
            
        if atletas_solitarios:
            mensaje = "Atletas solos en su división:\n\n" + "\n".join([f"• {n} ({', '.join(d)})" for n, d in list(atletas_solitarios.items())[:15]])
            if len(atletas_solitarios) > 15: mensaje += f"\n... y {len(atletas_solitarios) - 15} más."
            mensaje += "\n\n¿Desea continuar?"
            if not messagebox.askyesno("Atletas sin oponente", mensaje): return 

        # --- GUARDAR O SINCRONIZAR EN BD ---
        id_existente = getattr(self, "torneo_debug_id", None)
        
        if id_existente:
            # MODO: SINCRONIZAR ACTUALIZACIÓN
            if self.db.sincronizar_inscripciones(id_existente, self.inscripciones_memoria):
                self.actualizar_botones_guardado()
                if ir_a_pareo:
                    messagebox.showinfo("Éxito", "Cambios guardados. Pasando a Fase de Pareos.")
                    from pantalla_pareo import PantallaPareo
                    p_pareo = self.controller.pantallas.get(PantallaPareo)
                    if p_pareo:
                        p_pareo.cargar_torneo(id_existente)
                        self.controller.mostrar_pantalla(PantallaPareo)
                else:
                    messagebox.showinfo("Éxito", "Progreso sincronizado correctamente en la Base de Datos.")
            else:
                messagebox.showerror("Error", "No se pudo sincronizar la base de datos.")
        else:
            # MODO: CREAR NUEVO TORNEO
            id_cat = next((c['id'] for c in self.categorias_db if c['nombre'] == self.categoria_confirmada), None)
            try: fecha_db = datetime.strptime(self.ent_tor_fecha.get().strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
            except: fecha_db = datetime.now().strftime("%Y-%m-%d")
            id_ciu = self.map_ciudades_torneo.get(self.cmb_tor_ciudad.get())
            datos_torneo = {
                'nombre': self.var_nombre_torneo.get().strip(),
                'id_categoria': self.categoria_seleccionada_id,
                'lugar': self.var_lugar_torneo.get().strip(),
                'id_ciudad': self.id_ciudad_seleccionada,
                'fecha': self.var_fecha_torneo.get(),
                'num_tapices': int(self.cmb_num_tapices.get()) # <--- AÑADIR ESTA LÍNEA
            }
            
            nuevo_id = self.db.guardar_torneo_completo(datos_torneo, self.inscripciones_memoria)
            
            if nuevo_id:
                self.torneo_debug_id = nuevo_id
                self.ent_tor_nombre.config(state="disabled")
                self.ent_tor_lugar.config(state="disabled")
                self.cmb_categoria.config(state="disabled")
                if hasattr(self, 'cmb_tor_ciudad'): self.cmb_tor_ciudad.config(state="disabled")
                self.btn_confirmar_torneo.config(text="Modificar Torneo", state="disabled")
                self.btn_cancelar_torneo.pack_forget()
                self.actualizar_btn_nuevo_limpiar()
                self.actualizar_botones_guardado() # Se cambian los botones a modo "Guardado"
                
                if ir_a_pareo:
                    messagebox.showinfo("Éxito", "Torneo guardado en la BD. Pasando a Fase de Pareos.")
                    from pantalla_pareo import PantallaPareo
                    p_pareo = self.controller.pantallas.get(PantallaPareo)
                    if p_pareo:
                        p_pareo.cargar_torneo(nuevo_id)
                        self.controller.mostrar_pantalla(PantallaPareo)
                else:
                    messagebox.showinfo("Éxito", "Torneo inicial guardado correctamente.")
            else:
                messagebox.showerror("Error", "Error al crear el torneo en la base de datos.")

    def abrir_ventana_cargar_torneo(self):
        ventana = tk.Toplevel(self)
        ventana.title("Búsqueda y Selección de Torneos")

        # --- CENTRAR Y AGRANDAR VENTANA ---
        ancho, alto = 950, 500  
        x = (self.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.winfo_screenheight() // 2) - (alto // 2)
        ventana.geometry(f"{ancho}x{alto}+{x}+{y}")
        ventana.transient(self)
        ventana.grab_set()

        main_frame = ttk.Frame(ventana)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ================= PANEL IZQUIERDO (FILTROS) =================
        panel_filtros = ttk.LabelFrame(main_frame, text="Filtros de Búsqueda", padding=10)
        panel_filtros.pack(side="left", fill="y", padx=(0, 10))

        ttk.Label(panel_filtros, text="Buscar Nombre:").pack(anchor="w", pady=(0, 2))
        self.ent_filtro_nombre = ttk.Entry(panel_filtros, width=25)
        self.ent_filtro_nombre.pack(fill="x", pady=(0, 10))
        self.ent_filtro_nombre.bind("<KeyRelease>", lambda e: self.filtrar_tabla_torneos(tabla_torneos))

        ttk.Label(panel_filtros, text="Fecha Inicio (DD/MM/YYYY):").pack(anchor="w", pady=(0, 2))
        self.ent_filtro_fecha_ini = ttk.Entry(panel_filtros, width=25)
        self.ent_filtro_fecha_ini.pack(fill="x", pady=(0, 10))
        aplicar_formato_fecha(self.ent_filtro_fecha_ini)
        self.ent_filtro_fecha_ini.bind("<KeyRelease>", lambda e: self.filtrar_tabla_torneos(tabla_torneos))

        ttk.Label(panel_filtros, text="Fecha Fin (DD/MM/YYYY):").pack(anchor="w", pady=(0, 2))
        self.ent_filtro_fecha_fin = ttk.Entry(panel_filtros, width=25)
        self.ent_filtro_fecha_fin.pack(fill="x", pady=(0, 10))
        aplicar_formato_fecha(self.ent_filtro_fecha_fin)
        self.ent_filtro_fecha_fin.bind("<KeyRelease>", lambda e: self.filtrar_tabla_torneos(tabla_torneos))

        # --- FILTRO 1: CATEGORÍAS ---
        ttk.Label(panel_filtros, text="Categorías:").pack(anchor="w", pady=(0, 2))
        frame_cat_scroll = ttk.Frame(panel_filtros)
        frame_cat_scroll.pack(fill="x", pady=(0, 10))
        
        scroll_cat = ttk.Scrollbar(frame_cat_scroll, orient="vertical")
        self.listbox_filtro_cat = tk.Listbox(frame_cat_scroll, selectmode="multiple", height=4, yscrollcommand=scroll_cat.set, exportselection=False)
        scroll_cat.config(command=self.listbox_filtro_cat.yview)
        self.listbox_filtro_cat.pack(side="left", fill="both", expand=True)
        scroll_cat.pack(side="right", fill="y")
        self.listbox_filtro_cat.bind("<<ListboxSelect>>", lambda e: self.filtrar_tabla_torneos(tabla_torneos))

        for cat in self.categorias_db:
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
        self.listbox_filtro_est.bind("<<ListboxSelect>>", lambda e: self.filtrar_tabla_torneos(tabla_torneos))

        for est in ["En edición", "Iniciado", "En línea", "Terminado"]:
            self.listbox_filtro_est.insert(tk.END, est)

        ttk.Button(panel_filtros, text="Limpiar Filtros", command=lambda: self.limpiar_filtros_torneos(tabla_torneos)).pack(fill="x", pady=(5, 0))

        # ================= PANEL DERECHO (TABLA Y BOTONES) =================
        panel_derecho = ttk.Frame(main_frame)
        panel_derecho.pack(side="right", fill="both", expand=True)

        columnas = ("id", "nombre", "fecha", "categoria", "estado")
        tabla_torneos = ttk.Treeview(panel_derecho, columns=columnas, show="headings")
        aplicar_deseleccion_tabla(tabla_torneos)
        
        # CONFIGURACIÓN DE COLORES PARA LAS FILAS
        tabla_torneos.tag_configure("st_terminado", foreground="#dc3545") # Rojo
        tabla_torneos.tag_configure("st_en_linea", foreground="#28a745")  # Verde
        tabla_torneos.tag_configure("st_iniciado", foreground="#d39e00")  # Amarillo oscuro para legibilidad
        tabla_torneos.tag_configure("st_edicion", foreground="#6c757d")   # Gris
        
        # --- NUEVO: Fondo gris claro para el torneo que ya está cargado ---
        tabla_torneos.tag_configure("st_actual", background="#e9ecef")
        
        tabla_torneos.heading("id", text="ID"); tabla_torneos.column("id", width=40, anchor="center")
        tabla_torneos.heading("nombre", text="Nombre del Torneo"); tabla_torneos.column("nombre", width=250, anchor="w")
        tabla_torneos.heading("fecha", text="Fecha"); tabla_torneos.column("fecha", width=90, anchor="center")
        tabla_torneos.heading("categoria", text="Categoría"); tabla_torneos.column("categoria", width=120, anchor="center")
        tabla_torneos.heading("estado", text="Estado"); tabla_torneos.column("estado", width=120, anchor="w")
        tabla_torneos.pack(fill="both", expand=True, pady=(0, 10))

        # Controles inferiores
        btn_frame = ttk.Frame(panel_derecho)
        btn_frame.pack(fill="x")

        btn_cancelar = ttk.Button(btn_frame, text="Cancelar", command=ventana.destroy)
        btn_cancelar.pack(side="right", padx=(5, 0))

        btn_cargar = ttk.Button(btn_frame, text="Seleccionar Torneo", command=lambda: self.ejecutar_carga_torneo(tabla_torneos, ventana))
        btn_cargar.pack(side="right")

        tabla_torneos.bind("<Double-1>", lambda e: self.ejecutar_carga_torneo(tabla_torneos, ventana))

        # Desplegar datos iniciales
        self.cargar_memoria_torneos()
        self.filtrar_tabla_torneos(tabla_torneos)

        # Iniciar el motor de actualización en vivo
        self.bucle_refrescar_busqueda_torneos(ventana, tabla_torneos)

    def bucle_refrescar_busqueda_torneos(self, ventana, tabla):
        """Mantiene la tabla de torneos actualizada en tiempo real mientras la ventana exista."""
        if not ventana.winfo_exists(): return # Si el usuario cerró la ventana, detener el bucle
        
        # 1. Guardar qué fila tenía seleccionada el usuario para no arruinarle el clic
        seleccionados = [tabla.item(i, "values")[0] for i in tabla.selection()]
        
        # 2. Descargar los estados frescos desde la Base de Datos
        self.cargar_memoria_torneos()
        
        # 3. Refrescar la tabla aplicando los filtros que el usuario tenga escritos
        self.filtrar_tabla_torneos(tabla)
        
        # 4. Restaurar la selección silenciosamente
        for item in tabla.get_children():
            id_item = tabla.item(item, "values")[0]
            if str(id_item) in [str(x) for x in seleccionados]:
                tabla.selection_add(item)
                
        # 5. Volver a comprobar en 2 segundos
        ventana.after(2000, lambda: self.bucle_refrescar_busqueda_torneos(ventana, tabla))

    # --- FUNCIONES DE SOPORTE PARA EL BUSCADOR DE TORNEOS ---
    def cargar_memoria_torneos(self):
        """Descarga los torneos y calcula sus estados visuales con etiquetas de color."""
        torneos_raw = self.db.obtener_lista_torneos_debug()
        self.torneos_memoria_carga = []

        for t in torneos_raw:
            # 1. Terminado (Máxima prioridad, anula en línea)
            if t.get('fecha_fin'):
                estado_puro = "Terminado"
                tag = "st_terminado"
            # 2. En Línea (Hay un master activo)
            elif t.get('tiene_master'):
                estado_puro = "En línea"
                tag = "st_en_linea"
            else:
                # 3. Iniciado o En Edición (Depende de si ya hay llaves bloqueadas)
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

    def limpiar_filtros_torneos(self, tabla):
        self.ent_filtro_nombre.delete(0, tk.END)
        self.ent_filtro_fecha_ini.delete(0, tk.END)
        self.ent_filtro_fecha_fin.delete(0, tk.END)
        self.listbox_filtro_cat.selection_clear(0, tk.END)
        if hasattr(self, 'listbox_filtro_est'):
            self.listbox_filtro_est.selection_clear(0, tk.END)
        self.filtrar_tabla_torneos(tabla)

    def filtrar_tabla_torneos(self, tabla):
        for item in tabla.get_children(): tabla.delete(item)

        term_nombre = self.ent_filtro_nombre.get().strip().lower()
        term_fini = self.ent_filtro_fecha_ini.get().strip()
        term_ffin = self.ent_filtro_fecha_fin.get().strip()
        sel_cats = [self.listbox_filtro_cat.get(i) for i in self.listbox_filtro_cat.curselection()]
        sel_ests = [self.listbox_filtro_est.get(i) for i in self.listbox_filtro_est.curselection()] if hasattr(self, 'listbox_filtro_est') else []

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

            # --- NUEVO: Inyectar el TAG de color y verificar si es el actual ---
            tags_fila = [t['tag_estado']]
            if getattr(self, "torneo_debug_id", None) == t['id']:
                tags_fila.append("st_actual")
                # Opcional: Modificamos el texto para que sea obvio
                t['estado_str'] = f"{t['estado_str']} (Actual)"
                
            tabla.insert("", "end", values=(t['id'], t['nombre'], t['fecha'], t['categoria'], t['estado_str']), tags=tuple(tags_fila))

    def ejecutar_carga_torneo(self, tabla, ventana):
        seleccion = tabla.selection()
        if not seleccion:
            return messagebox.showwarning("Aviso", "Seleccione un torneo de la lista.")

        id_torneo = int(tabla.item(seleccion[0], "values")[0])
        
        # --- NUEVO: Bloqueo de seguridad para evitar el glitch de recarga ---
        if getattr(self, "torneo_debug_id", None) == id_torneo:
            return messagebox.showinfo("Torneo Activo", "Este torneo ya está cargado y activo actualmente.")

        # Desconectar de sala previa si aplica
        if hasattr(self.controller, 'id_conexion_red') and self.controller.id_conexion_red:
            if getattr(self, 'torneo_debug_id', None) != id_torneo:
                self.db.eliminar_conexion_instancia(self.controller.id_conexion_red)
                self.controller.id_conexion_red = None

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
        
        # Seleccionar la categoría correctamente con set
        self.cmb_categoria.config(state="normal")
        self.cmb_categoria.set(datos_torneo['categoria'])

        # 2. Limpiar memoria y tabla
        self.inscripciones_memoria.clear()
        for item in self.tabla.get_children(): self.tabla.delete(item)

        # 3. Agrupar estilos por atleta (reconstrucción de memoria)
        atletas_agrupados = {}
        for ins in inscripciones:
            id_atl = ins['id_peleador']
            
            # --- FIX: Extraer peso inteligentemente ---
            p_bd = ins.get('peso_pesaje')
            try: val_p = float(p_bd)
            except: val_p = 0
            if val_p <= 0:
                p_bd = ins.get('peso_dado')
                try: val_p = float(p_bd)
                except: val_p = 0
            if val_p <= 0:
                p_bd = ins.get('peso')
                try: val_p = float(p_bd)
                except: val_p = 0
            peso_fila = str(p_bd) if val_p > 0 else '0'

            if id_atl not in atletas_agrupados:
                atletas_agrupados[id_atl] = {"datos_bd": ins, "estilos": [], "pesos_text": [], "ids_divisiones": [], "peso_exacto": peso_fila}
            else:
                peso_actual = atletas_agrupados[id_atl]["peso_exacto"]
                if peso_actual in ['0', '0.0'] and peso_fila not in ['0', '0.0']:
                    atletas_agrupados[id_atl]["peso_exacto"] = peso_fila
                elif val_p > 0:
                    try:
                        if val_p > float(peso_actual):
                            atletas_agrupados[id_atl]["peso_exacto"] = peso_fila
                    except: pass
            
            # NORMALIZAR ESTILOS DE LA BD
            est_db = str(ins.get('estilo', ''))
            if 'libre' in est_db.lower(): est_norm = 'Estilo Libre'
            elif 'greco' in est_db.lower(): est_norm = 'Grecorromana'
            elif 'fem' in est_db.lower(): est_norm = 'Femenina'
            else: est_norm = est_db

            abr = "Lib" if est_norm == "Estilo Libre" else est_norm[:3]
            atletas_agrupados[id_atl]["estilos"].append(est_norm)
            atletas_agrupados[id_atl]["pesos_text"].append(f"{abr}: {ins['peso_maximo']}kg")
            
            id_div = ins.get('id_division') or ins.get('id_peso_oficial_uww')
            if id_div is None:
                p_max = ins.get('peso_maximo') or ins.get('peso_cat')
                id_estilo = 1 if 'libre' in est_db.lower() else (2 if 'greco' in est_db.lower() else 3)
                for p in self.pesos_oficiales_db:
                    if float(p['peso_maximo']) == float(p_max) and int(p['id_estilo_lucha']) == id_estilo:
                        id_div = p['id']
                        break
                        
            if id_div is not None:
                atletas_agrupados[id_atl]["ids_divisiones"].append(int(id_div))

        # 4. Llenar la memoria local
        for id_atl, data in atletas_agrupados.items():
            texto_peso_oficial = " | ".join(data["pesos_text"])
            
            self.inscripciones_memoria.append({
                "id_atleta": id_atl, "peso": str(data["peso_exacto"]),
                "peso_oficial": texto_peso_oficial, "estilos": data["estilos"], "ids_divisiones": data["ids_divisiones"],
                "de_red": True 
            })
            
        self.actualizar_opciones_filtros()

        # 5. --- APLICACIÓN MANUAL DE ESTADO "CONFIRMADO" ---
        self.torneo_debug_id = id_torneo
        self.categoria_confirmada = datos_torneo['categoria']
        
        # --- NUEVO: Guardar en la memoria de respaldo para que el botón 'Cancelar' funcione ---
        self.torneo_nombre_conf = datos_torneo['nombre']
        self.torneo_lugar_conf = datos_torneo['lugar']
        self.torneo_ciudad_conf = datos_torneo.get('ciudad_nombre', '')
        
        self.oficiales_db = self.db.obtener_oficiales()

        # Configuración por defecto: Torneo Confirmado y Listo para Inscribir
        self.btn_confirmar_torneo.config(text="Modificar Torneo")
        self.btn_cancelar_torneo.pack_forget()
        self.form_frame.config(text="2. Inscripción y Pesaje (Habilitado)")
        self.cambiar_estado_inscripcion("normal")
        
        # --- NUEVO: Rellenar el combobox con los atletas válidos al cargar el torneo ---
        self.filtrar_atletas_por_edad()

        # --- GESTIÓN DE RED SEGURA ---
        import socket, os
        nombre_pc = f"{socket.gethostname()}-{os.getpid()}"
        id_oficial = getattr(self.controller, 'id_operador', None)
        master_activo = self.db.verificar_master_activo(id_torneo)
            
        if not master_activo or master_activo == nombre_pc:
            # Soy MÁSTER
            if not master_activo:
                id_conexion = self.db.registrar_conexion_instancia(id_torneo, id_oficial, nombre_pc, es_master=True)
            else:
                m_db = self.db.verificar_master_existente(id_torneo)
                id_conexion = m_db['id'] if m_db else None
                
            self.controller.id_conexion_red = id_conexion
            self.controller.es_master = True
            self.controller.tapiz_asignado = "Tapiz A"
            
            self.bloquear_datos_torneo(False) # Abre permisos de Master (Muestra botón modificar)
            
            # Re-aplicar estado readonly a campos para que nazcan bloqueados
            self.ent_tor_nombre.config(state="disabled")
            self.ent_tor_lugar.config(state="disabled")
            self.cmb_categoria.config(state="disabled")
            if hasattr(self, 'cmb_tor_ciudad'): self.cmb_tor_ciudad.config(state="disabled")

            if hasattr(self, 'btn_avanzar_pareo'): self.btn_avanzar_pareo.config(state="normal")
            if hasattr(self, 'btn_guardar_torneo'):
                if not self.btn_guardar_torneo.winfo_ismapped():
                    self.btn_guardar_torneo.pack(side="left", fill="x", expand=True, padx=(0, 2))
                self.btn_guardar_torneo.config(state="normal", text="💾 Guardar Cambios")
                
        else:
            # Soy INVITADO (GUEST)
            self.controller.es_master = False
            id_conexion = self.db.registrar_conexion_instancia(id_torneo, id_oficial, nombre_pc, es_master=False)
            self.controller.id_conexion_red = id_conexion
            
            self.bloquear_datos_torneo(True) # Oculta botón modificar y bloquea campos
            if hasattr(self, 'btn_guardar_torneo'):
                if not self.btn_guardar_torneo.winfo_ismapped():
                    self.btn_guardar_torneo.pack(side="left", fill="x", expand=True, padx=(0, 2))
                # Nace bloqueado, el radar lo activará solo si es Aprobado
                self.btn_guardar_torneo.config(state="disabled", text="☁️ Sincronizar Atletas")
                
            self.comprobar_estado_guest(id_torneo, id_conexion)

        self.iniciar_escucha_red()
        self.actualizar_tabla_visual()
        self.refrescar_estado_bloqueos()

        # --- NUEVO: Forzar actualización del botón Limpiar/Nuevo Torneo ---
        self.actualizar_btn_nuevo_limpiar()

    def aplicar_interfaz_visitante(self):
        """Bloquea toda la edición y red, dejando solo la lectura y el avance a llaves."""
        self.todo_bloqueado = True
        self.cambiar_estado_inscripcion("disabled")
        
        # 1. Bloquear edición del Torneo
        if hasattr(self, 'btn_confirmar_torneo'):
            self.btn_confirmar_torneo.config(state="disabled")
        if hasattr(self, 'btn_guardar_torneo'):
            self.btn_guardar_torneo.config(state="disabled")
            
        # 2. Cambiar texto a Modo Visitante
        if hasattr(self, 'lbl_tapete_master'):
            self.lbl_tapete_master.config(text="🏁 Torneo Finalizado (Modo Visitante)", foreground="#17a2b8")
            
        # 3. Apagar controles de red permanentemente
        self.escuchando_red = False
        if hasattr(self, 'btn_confirmar_red'): self.btn_confirmar_red.config(state="disabled")
        if hasattr(self, 'btn_eliminar_red'): self.btn_eliminar_red.config(state="disabled")
        if hasattr(self, 'btn_intercambiar_tapiz'): self.btn_intercambiar_tapiz.config(state="disabled")
        if hasattr(self, 'btn_ceder_master'): self.btn_ceder_master.config(state="disabled")
        
        # --- NUEVO: VACIAR LA TABLA DE RED ---
        if hasattr(self, 'tabla_red'):
            for item in self.tabla_red.get_children():
                self.tabla_red.delete(item)
        
        # 4. Permitir SIEMPRE ir a las llaves
        if hasattr(self, 'btn_avanzar_pareo'):
            self.btn_avanzar_pareo.config(state="normal")

    def refrescar_estado_bloqueos(self):
        """Consulta la BD y actualiza la interfaz si hubo cambios en la pantalla de Pareo."""
        if getattr(self, "torneo_debug_id", None) is None: 
            return

        # Guardamos el estado anterior para no spamear el mensaje emergente
        ya_estaba_cerrado = getattr(self, "torneo_finalizado", False)

        # 1. Consultar si el torneo fue cerrado por completo (tiene fecha_fin)
        conexion = self.db.conectar()
        if conexion:
            try:
                with conexion.cursor() as cur:
                    cur.execute("SELECT fecha_fin FROM torneo WHERE id = %s", (self.torneo_debug_id,))
                    res = cur.fetchone()
                    self.torneo_finalizado = True if (res and res[0]) else False
            finally: 
                conexion.close()

        # --- NUEVO: SI ESTÁ FINALIZADO, APLICAR INTERFAZ VISITANTE Y CORTAR ---
        if getattr(self, "torneo_finalizado", False):
            self.aplicar_interfaz_visitante()
            self.actualizar_botones_guardado()
            self.actualizar_tabla_visual()
            
            # Lanzamos el mensaje SOLO a los invitados, el Máster no necesita este aviso extra
            if not ya_estaba_cerrado and not getattr(self.controller, 'es_master', False):
                messagebox.showinfo("Torneo Finalizado", "El Director ha cerrado oficialmente el torneo.\n\nEl sistema de red se ha desconectado y has pasado a modo de Solo Lectura (Visitante).")
            return

        # 2. Consultar qué llaves están bloqueadas ahora y quiénes fueron descalificados
        self.pesos_bloqueados_ids = self.db.obtener_divisiones_bloqueadas(self.torneo_debug_id)
        self.atletas_descalificados_ids = self.db.obtener_peleadores_descalificados(self.torneo_debug_id)

        # 3. Evaluar si TODAS las divisiones están bloqueadas
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

        # 4. Aplicar cambios visuales de bloqueo
        if all_locked and self.pesos_bloqueados_ids:
            self.todo_bloqueado = True
            self.cambiar_estado_inscripcion("disabled")
            if hasattr(self, 'frame_acciones_memoria'):
                self.frame_acciones_memoria.pack_forget()
        else:
            self.todo_bloqueado = False
            if hasattr(self, 'frame_acciones_memoria') and not self.frame_acciones_memoria.winfo_ismapped():
                self.frame_acciones_memoria.pack(side="left", before=self.lbl_estadisticas)

        # 5. Refrescar colores y botones
        self.actualizar_botones_guardado()
        self.actualizar_tabla_visual()

    def guardar_solo_torneo(self):
        """Sincroniza forzando el reemplazo de los atletas editados para que la BD no los ignore."""
        id_existente = getattr(self, 'torneo_debug_id', None)
        es_master = getattr(self.controller, 'es_master', False)
        soy_guest = bool(id_existente) and not es_master

        # --- ESCUDO ANTI-NULL Y ANTI-DUPLICADOS UNIVERSAL ---
        datos_limpios = []
        datos_pre_sync = [] # Lista temporal sin los atletas editados
        hay_editados = False
        divisiones = {} 
        
        for ins in self.inscripciones_memoria:
            # 1. Saltamos los que marcamos con el botón "Eliminar" O los que la red ya eliminó
            if ins.get('estado_local') == 'eliminado' or ins.get('tipo_cambio_red') == 'eliminado':
                continue
                
            ins_copia = ins.copy()
            ins_copia['peso_pesaje'] = ins.get('peso') 
            ins_copia['peso_dado'] = ins.get('peso')   
            
            divs_validas = []
            estilos_validos = []
            
            for idx, d in enumerate(ins.get('ids_divisiones', [])):
                if d is not None and int(d) not in divs_validas:
                    id_div = int(d)
                    divs_validas.append(id_div)
                    estilo = ins.get('estilos', [])[idx] if idx < len(ins.get('estilos', [])) else "Estilo Libre"
                    estilos_validos.append(estilo)
                    
                    if id_div not in divisiones: divisiones[id_div] = []
                    divisiones[id_div].append(ins['id_atleta'])
            
            if divs_validas:
                ins_copia['ids_divisiones'] = divs_validas
                ins_copia['estilos'] = estilos_validos
                
                # --- TRUCO DE MAGIA: Separamos a los editados ---
                if ins.get('estado_local') == 'editado':
                    ins_copia['de_red'] = False 
                    hay_editados = True
                    datos_limpios.append(ins_copia)
                    # NO lo agregamos a datos_pre_sync (Forzamos a la BD a creer que lo borramos)
                else:
                    datos_limpios.append(ins_copia)
                    datos_pre_sync.append(ins_copia)

        # --- VALIDACIÓN GLOBAL: AL MENOS 1 PAREJA ---
        hay_pareja = any(len(atletas) >= 2 for atletas in divisiones.values())
        if not hay_pareja:
            return messagebox.showerror("Error de Sincronización", "Debe haber al menos 2 atletas en una misma categoría.\n\nNo puedes sincronizar una lista vacía o sin parejas válidas.")

        # --- FILTRO PARA INVITADOS (GUEST) ---
        if soy_guest:
            if not messagebox.askyesno("Sincronizar", "¿Deseas enviar tus cambios a la base de datos?"):
                return
            self.esta_editando_localmente = True
            
            # 1. Engañar a la BD para que purgue la versión vieja del atleta
            if hay_editados:
                self.db.sincronizar_inscripciones(id_existente, datos_pre_sync)
                
            # 2. Insertar la versión nueva y editada del atleta
            exito = self.db.sincronizar_inscripciones(id_existente, datos_limpios)
            
            if exito:
                self.inscripciones_memoria = [i for i in self.inscripciones_memoria if i.get('estado_local') != 'eliminado']
                for ins in self.inscripciones_memoria:
                    ins['de_red'] = True
                    if 'estado_local' in ins: del ins['estado_local']
                    
                self._ultima_firma_red = None 
                messagebox.showinfo("Éxito", "Sincronización completada.")
                self.actualizar_tabla_visual()
            else:
                messagebox.showerror("Error", "No se pudo sincronizar.")
            self.esta_editando_localmente = False
            return

        # --- LÓGICA PARA EL MÁSTER ---
        if id_existente:
            self.esta_editando_localmente = True 
            
            # 1. Engañar a la BD para que purgue la versión vieja
            if hay_editados:
                self.db.sincronizar_inscripciones(id_existente, datos_pre_sync)
                
            # 2. Insertar la versión nueva
            if self.db.sincronizar_inscripciones(id_existente, datos_limpios):
                
                # --- FIX CRÍTICO: Limpiar estados locales para el Máster también ---
                self.inscripciones_memoria = [i for i in self.inscripciones_memoria if i.get('estado_local') != 'eliminado']
                for ins in self.inscripciones_memoria:
                    ins['de_red'] = True
                    if 'estado_local' in ins: del ins['estado_local']
                    
                self._ultima_firma_red = None 
                self.actualizar_tabla_visual() 
                messagebox.showinfo("Éxito", "Cambios sincronizados correctamente.")
                if hasattr(self, 'btn_avanzar_pareo'): self.btn_avanzar_pareo.config(state="normal")
            self.esta_editando_localmente = False
            return

        # --- LÓGICA DE CREACIÓN DEL TORNEO (NUNCA ANTES GUARDADO) ---
        if not self.inscripciones_memoria:
            return messagebox.showwarning("Sin Atletas", "Debe inscribir atletas antes de guardar.")

        # Re-construir divisiones para validación de sala
        divisiones_nuevas = {}
        for ins in datos_limpios:
            for i, id_div in enumerate(ins['ids_divisiones']):
                if id_div in getattr(self, "pesos_bloqueados_ids", set()):
                    continue
                estilo = ins['estilos'][i] if i < len(ins['estilos']) else "Estilo"
                nombre_atl = next((f"{a['apellidos']}, {a['nombre']}" for a in self.atletas_db if a['id'] == ins['id_atleta']), "Atleta")
            
                if id_div not in divisiones_nuevas:
                    divisiones_nuevas[id_div] = {"estilo": estilo, "atletas": []}
                divisiones_nuevas[id_div]["atletas"].append(nombre_atl)

        hay_pareja_nueva = any(len(d["atletas"]) >= 2 for d in divisiones_nuevas.values())
        if not hay_pareja_nueva:
            return messagebox.showerror("Error", "Debe haber al menos 2 atletas en una misma categoría para crear la sala.")

        id_cat = next((c['id'] for c in self.categorias_db if c['nombre'] == self.categoria_confirmada), None)
        id_ciu = self.map_ciudades_torneo.get(self.torneo_ciudad_conf, None)
        
        try: fecha_db = datetime.strptime(self.ent_tor_fecha.get().strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError: fecha_db = datetime.now().strftime("%Y-%m-%d")

        datos_torneo = {
            'nombre': self.torneo_nombre_conf,
            'id_categoria': id_cat,
            'lugar': self.torneo_lugar_conf,
            'id_ciudad': id_ciu,
            'fecha': fecha_db
        }
        
        id_torneo = self.db.guardar_torneo_completo(datos_torneo, datos_limpios)
        if not id_torneo:
            return messagebox.showerror("Error", "Fallo al conectar con la base de datos para crear el torneo.")
        
        self.torneo_debug_id = id_torneo

        import socket
        import os 
        nombre_pc = f"{socket.gethostname()}-{os.getpid()}"
        id_oficial = getattr(self.controller, 'id_operador', None) or (self.oficiales_db[0]['id'] if getattr(self, 'oficiales_db', None) else 1)
            
        id_conexion = self.db.registrar_conexion_instancia(id_torneo, id_oficial, nombre_pc, es_master=True)
        
        if id_conexion:
            self.controller.id_conexion_red = id_conexion
            self.controller.es_master = True
            self.controller.tapiz_asignado = "Tapiz A"
            
            for ins in self.inscripciones_memoria:
                ins['de_red'] = True
            self.actualizar_tabla_visual()
            
            id_oficial = getattr(self.controller, 'id_operador', None)
            oficial = next((o for o in self.oficiales_db if o['id'] == id_oficial), None)
            nombre_oficial = f"{oficial['nombre']} {oficial['apellidos']}" if oficial else "Desconocido"
            
            self.lbl_tapete_master.config(text=f"🥇 Tapiz A (Máster: {nombre_oficial}) - {nombre_pc}", foreground="#28a745")
            
            self.bloquear_datos_torneo(False) 
            self.ent_tor_nombre.config(state="disabled")
            self.ent_tor_lugar.config(state="disabled")
            self.cmb_categoria.config(state="disabled")
            if hasattr(self, 'cmb_tor_ciudad'): self.cmb_tor_ciudad.config(state="disabled")
            
            self.btn_guardar_torneo.config(state="normal", text="💾 Guardar Cambios")
            self.btn_avanzar_pareo.config(state="normal")
            
            self.actualizar_btn_nuevo_limpiar()
            messagebox.showinfo("Sala Creada", f"¡Éxito! Torneo creado.\n\nEres el MASTER desde '{nombre_pc}'.")
            self.iniciar_escucha_red()
        else:
            messagebox.showerror("Error de Red", "El torneo se guardó, pero falló la creación de la sala.")

    def avanzar_fase_dos(self):
        """Sincroniza y decide qué lógica de red aplicar al abrir la Cartelera."""
        if not getattr(self, 'torneo_debug_id', None):
            return messagebox.showwarning("Acceso Denegado", "Debes GUARDAR EL TORNEO en la BD primero.")
        
        if not self.inscripciones_memoria:
            return messagebox.showwarning("Sin Atletas", "Inscribe al menos un atleta antes de generar llaves.")

        # Sincroniza cualquier atleta nuevo antes de salir
        if not self.db.sincronizar_inscripciones(self.torneo_debug_id, self.inscripciones_memoria):
            return messagebox.showerror("Error", "Fallo al guardar los atletas en la base de datos.")

        from ui.pantallas.pantalla_pareo import PantallaPareo
        p_pareo = self.controller.pantallas.get(PantallaPareo)
        
        if p_pareo:
            # ---> Ahora ESTA ÚNICA línea carga el torneo e inicia la red silenciosamente
            p_pareo.cargar_torneo(self.torneo_debug_id)
            self.controller.mostrar_pantalla(PantallaPareo)

    def iniciar_torneo_red(self, id_conexion, es_master, tapiz):
        self.id_conexion_red = id_conexion
        self.es_master = es_master
        self.tapiz_asignado = tapiz
        
        # ---> NUEVO: ENCENDER EL MOTOR DE RED <---
        self.escuchando_red = True

        inscripciones = self.db.obtener_inscripciones_pareo(self.id_torneo)

    # ================= LÓGICA DE GESTIÓN DE RED Y TAPICES =================
    def confirmar_arbitro_red(self):
        item_sel = self.tabla_red.selection()
        if not item_sel: return messagebox.showwarning("Selección", "Seleccione un árbitro pendiente de la tabla.")
        
        # PROTECCIÓN: Evitar auto-confirmar al Máster
        tags = self.tabla_red.item(item_sel[0], "tags")
        if "yo_mismo" in tags and getattr(self.controller, 'es_master', False):
            return messagebox.showwarning("Aviso", "No puedes confirmarte a ti mismo, ya eres el administrador de la sala.")
            
        self.tabla_red.item(item_sel[0], tags=("confirmado",))
        self.actualizar_letras_tapices()
        self.sincronizar_tapices_db()

    def eliminar_arbitro_red(self):
        item_sel = self.tabla_red.selection()
        if not item_sel: return messagebox.showwarning("Selección", "Seleccione un árbitro de la tabla.")
        
        id_conexion = self.tabla_red.item(item_sel[0], "values")[0]
        
        # PROTECCIÓN: Evitar auto-eliminación
        if str(id_conexion) == str(self.controller.id_conexion_red):
            return messagebox.showwarning("Aviso", "No puedes eliminarte a ti mismo.\n\nSi deseas abandonar la sala, utiliza el botón de Cerrar Sesión o Cede el Máster.")
            
        if messagebox.askyesno("Confirmar", "¿Desea desconectar y eliminar a este árbitro de la sala?"):
            self.db.eliminar_conexion_instancia(id_conexion) 
            if getattr(self, 'torneo_debug_id', None):
                self.refrescar_tabla_red_master(self.torneo_debug_id)

    def intercambiar_tapiz(self):
        """Cruza los tapices asignados de los dos árbitros seleccionados."""
        seleccionados = self.tabla_red.selection()
        if len(seleccionados) != 2:
            return messagebox.showwarning("Aviso", "Seleccione exactamente dos árbitros confirmados para intercambiar.")
            
        # Extraemos los datos del Árbitro 1
        id1 = self.tabla_red.item(seleccionados[0], "values")[0]
        tapiz1 = self.tabla_red.item(seleccionados[0], "values")[3]
        
        # Extraemos los datos del Árbitro 2
        id2 = self.tabla_red.item(seleccionados[1], "values")[0]
        tapiz2 = self.tabla_red.item(seleccionados[1], "values")[3]
        
        # Hacemos el cruce directo en la Base de Datos
        if hasattr(self.db, 'asignar_tapiz_a_cliente'):
            self.db.asignar_tapiz_a_cliente(id1, tapiz2)
            self.db.asignar_tapiz_a_cliente(id2, tapiz1)
            
        # Si uno de los involucrados es el Máster, actualizamos su variable interna
        mi_id = str(self.controller.id_conexion_red)
        if str(id1) == mi_id:
            self.controller.tapiz_asignado = tapiz2
        elif str(id2) == mi_id:
            self.controller.tapiz_asignado = tapiz1
            
        # Forzamos refresco visual instantáneo
        self.refrescar_tabla_red_master(self.torneo_debug_id)

    # --- NUEVA FUNCIÓN A AGREGAR ---
    def sincronizar_tapices_db(self):
        for item in self.tabla_red.get_children():
            valores = self.tabla_red.item(item, "values")
            tags = self.tabla_red.item(item, "tags")
            
            es_master_local = ("yo_mismo" in tags and getattr(self.controller, 'es_master', False))
            if "confirmado" in tags or es_master_local:
                self.db.asignar_tapiz_a_cliente(valores[0], valores[3])

    def actualizar_letras_tapices(self):
        """Asigna las letras (Tapiz A, B, C) por orden de lista, incluyendo al Máster."""
        items = self.tabla_red.get_children()
        ascii_letra = 65 # Empezamos en la letra 'A'
        
        for item in items:
            valores_actuales = list(self.tabla_red.item(item, "values"))
            tags_actuales = self.tabla_red.item(item, "tags")
            
            # El Máster siempre cuenta como confirmado para la letra
            es_master_local = ("yo_mismo" in tags_actuales and getattr(self.controller, 'es_master', False))
            
            if "confirmado" in tags_actuales or es_master_local:
                valores_actuales[3] = f"Tapiz {chr(ascii_letra)}"
                ascii_letra += 1
                
                # Si es mi fila de Máster, actualizo mi variable interna para que mi computadora lo sepa
                if es_master_local:
                    self.controller.tapiz_asignado = valores_actuales[3]
            else:
                valores_actuales[3] = "Pendiente"
                
            self.tabla_red.item(item, values=valores_actuales)

    def confirmar_arbitro_red(self):
        item_sel = self.tabla_red.selection()
        if not item_sel: return messagebox.showwarning("Selección", "Seleccione un árbitro pendiente de la tabla.")
        
        # PROTECCIÓN: Evitar auto-confirmar al Máster
        tags = self.tabla_red.item(item_sel[0], "tags")
        if "yo_mismo" in tags and getattr(self.controller, 'es_master', False):
            return messagebox.showwarning("Aviso", "No puedes confirmarte a ti mismo, ya eres el administrador de la sala.")
            
        self.tabla_red.item(item_sel[0], tags=("confirmado",))
        self.actualizar_letras_tapices()
        self.sincronizar_tapices_db()

    def eliminar_arbitro_red(self):
        item_sel = self.tabla_red.selection()
        if not item_sel: return messagebox.showwarning("Selección", "Seleccione un árbitro de la tabla.")
        
        id_conexion = self.tabla_red.item(item_sel[0], "values")[0]
        
        # PROTECCIÓN: Evitar auto-eliminación
        if str(id_conexion) == str(self.controller.id_conexion_red):
            return messagebox.showwarning("Aviso", "No puedes eliminarte a ti mismo.\n\nSi deseas abandonar la sala, utiliza el botón de Cerrar Sesión o Cede el Máster.")
            
        if messagebox.askyesno("Confirmar", "¿Desea desconectar y eliminar a este árbitro de la sala?"):
            self.db.eliminar_conexion_instancia(id_conexion) 
            if getattr(self, 'torneo_debug_id', None):
                self.refrescar_tabla_red_master(self.torneo_debug_id)

    def actualizar_letras_tapices(self):
        """Asigna las letras (Tapiz A, B, C) por orden de lista, incluyendo al Máster."""
        items = self.tabla_red.get_children()
        ascii_letra = 65 # Empezamos en la letra 'A'
        
        for item in items:
            valores_actuales = list(self.tabla_red.item(item, "values"))
            tags_actuales = self.tabla_red.item(item, "tags")
            
            # El Máster siempre cuenta como confirmado para la letra
            es_master_local = ("yo_mismo" in tags_actuales and getattr(self.controller, 'es_master', False))
            
            if "confirmado" in tags_actuales or es_master_local:
                valores_actuales[3] = f"Tapiz {chr(ascii_letra)}"
                ascii_letra += 1
                
                # Si es mi fila de Máster, actualizo mi variable interna para que mi computadora lo sepa
                if es_master_local:
                    self.controller.tapiz_asignado = valores_actuales[3]
            else:
                valores_actuales[3] = "Pendiente"
                
            self.tabla_red.item(item, values=valores_actuales)

    def sincronizar_tapices_db(self):
        for item in self.tabla_red.get_children():
            valores = self.tabla_red.item(item, "values")
            tags = self.tabla_red.item(item, "tags")
            
            es_master_local = ("yo_mismo" in tags and getattr(self.controller, 'es_master', False))
            if "confirmado" in tags or es_master_local:
                self.db.asignar_tapiz_a_cliente(valores[0], valores[3])

    def ceder_master(self):
        """Transfiere los poderes de administrador a otro árbitro."""
        item_sel = self.tabla_red.selection()
        if not item_sel: return messagebox.showwarning("Selección", "Seleccione al árbitro al que desea transferir el mando.")
        
        id_conexion_sel = self.tabla_red.item(item_sel[0], "values")[0]
        nombre_sel = self.tabla_red.item(item_sel[0], "values")[1].replace("⭐ ", "") 
        
        if str(id_conexion_sel) == str(self.controller.id_conexion_red):
            return messagebox.showwarning("Aviso", "No puedes cederte el control a ti mismo.")
            
        tags = self.tabla_red.item(item_sel[0], "tags")
        if "pendiente" in tags:
            return messagebox.showwarning("Aviso", "El árbitro debe estar confirmado en la red antes de poder cederle el control.")

        mensaje = f"Está a punto de CEDER EL CONTROL de la sala a:\n\n{nombre_sel}\n\nSi cede el Máster, usted pasará a ser un invitado y perderá los privilegios.\nSólo podrá recuperar el control si el nuevo Máster se lo devuelve o se desconecta.\n\n¿Desea continuar?"
        
        if messagebox.askyesno("Ceder Máster", mensaje):
            if hasattr(self.db, 'transferir_master'):
                exito = self.db.transferir_master(self.torneo_debug_id, id_conexion_sel)
                if exito:
                    # 1. Degradación de rol
                    self.controller.es_master = False
                    
                    # 2. Deseleccionar todo para limpiar la interfaz
                    self.tabla_red.selection_remove(self.tabla_red.selection())
                    
                    # 3. Llamar al cerebro para que aplique el Escudo de Invitado
                    self.gestionar_estado_botones_red()
                    
                    # 4. --- NUEVO: Activar Escudo de Torneo y Botón Sincronizar ---
                    self.bloquear_datos_torneo(True)
                    if hasattr(self, 'btn_guardar_torneo'):
                        self.btn_guardar_torneo.config(state="normal", text="☁️ Sincronizar Atletas")
                    
                    messagebox.showinfo("Control Cedido", "Has cedido el control. Ahora eres un invitado en la sala.")
                    
                    # 5. Entrar en modo Invitado
                    self.comprobar_estado_guest(self.torneo_debug_id, self.controller.id_conexion_red)
            else:
                messagebox.showerror("Error", "La función no está implementada en la base de datos.")

    # ================= RADAR DE RED (AUTO-REFRESCO) =================
    def escuchar_nuevos_atletas_red(self):
        """Sincroniza usando la consulta completa a la BD para no perder jamás el peso decimal."""
        if getattr(self, "esta_editando_localmente", False) or not getattr(self, 'escuchando_red', False):
            return
            
        try:
            # --- FIX DEFINITIVO: Usar la consulta COMPLETA en lugar de la consulta rápida ---
            # Esto obliga a PostgreSQL a devolver TODAS las columnas, incluyendo peso_pesaje y peso_dado reales.
            resultado_bd = self.db.obtener_torneo_completo_debug(self.torneo_debug_id)
            if not resultado_bd: return
            
            # Desempaquetamos la tupla (datos_torneo, inscripciones)
            _, inscripciones_bd = resultado_bd
            
            if inscripciones_bd is not None:
                atletas_agrupados = {}
                for ins in inscripciones_bd:
                    id_atl = ins.get('id_peleador')
                    if id_atl is None: continue
                    id_atl = int(id_atl)
                    
                    # Extracción agresiva del peso
                    p_bd = ins.get('peso_pesaje')
                    try: val_p = float(p_bd)
                    except: val_p = 0
                    
                    if val_p <= 0:
                        p_bd = ins.get('peso_dado')
                        try: val_p = float(p_bd)
                        except: val_p = 0
                        
                    if val_p <= 0:
                        p_bd = ins.get('peso')
                        try: val_p = float(p_bd)
                        except: val_p = 0
                        
                    peso_fila = str(p_bd) if val_p > 0 else '0'
                    
                    if id_atl not in atletas_agrupados:
                        atletas_agrupados[id_atl] = {"pesos_text": [], "ids_divs": [], "estilos": [], "peso_exacto": peso_fila}
                    else:
                        peso_actual = atletas_agrupados[id_atl]["peso_exacto"]
                        if peso_actual in ['0', '0.0'] and peso_fila not in ['0', '0.0']:
                            atletas_agrupados[id_atl]["peso_exacto"] = peso_fila
                        elif val_p > 0:
                            try:
                                if val_p > float(peso_actual):
                                    atletas_agrupados[id_atl]["peso_exacto"] = str(val_p)
                            except: pass
                    
                    est_db = str(ins.get('estilo', ''))
                    abr = "Lib" if 'libre' in est_db.lower() else est_db[:3]
                    p_max = ins.get('peso_maximo') or ins.get('peso_cat') or '?'
                    
                    p_str = f"{abr}: {p_max}kg"
                    if p_str not in atletas_agrupados[id_atl]["pesos_text"]:
                        atletas_agrupados[id_atl]["pesos_text"].append(p_str)
                        
                        id_div = ins.get('id_division') or ins.get('id_peso_oficial_uww')
                        if id_div is None and p_max != '?':
                            id_estilo = 1 if 'libre' in est_db.lower() else (2 if 'greco' in est_db.lower() else 3)
                            for p in self.pesos_oficiales_db:
                                if float(p['peso_maximo']) == float(p_max) and int(p['id_estilo_lucha']) == id_estilo:
                                    id_div = p['id']
                                    break
                                    
                        if id_div is not None:
                            atletas_agrupados[id_atl]["ids_divs"].append(int(id_div))

                    if est_db not in atletas_agrupados[id_atl]["estilos"]:
                        atletas_agrupados[id_atl]["estilos"].append(est_db)

                # --- COMPARACIÓN INTELIGENTE DIRECTA ---
                hubo_cambios = False
                nueva_memoria = []
                self.atletas_db = self.db.obtener_atletas()
                
                for id_atl, data in atletas_agrupados.items():
                    existente = next((i for i in self.inscripciones_memoria if int(i['id_atleta']) == id_atl), None)
                    peso_red = data["peso_exacto"]
                    
                    if existente:
                        if existente.get('estado_local') in ['eliminado', 'editado']:
                            nueva_memoria.append(existente)
                            continue
                        
                        if peso_red in ['0', '0.0'] and existente.get('peso', '0') not in ['0', '0.0']:
                            peso_red = existente.get('peso', '0')

                        texto_oficial = " | ".join(data["pesos_text"])
                        
                        try: cambio_peso = float(existente.get('peso', '0')) != float(peso_red)
                        except: cambio_peso = str(existente.get('peso', '0')) != str(peso_red)
                            
                        cambio_oficial = str(existente.get('peso_oficial')) != str(texto_oficial)
                        cambio_estilos = set(existente.get('estilos', [])) != set(data["estilos"])
                        
                        if cambio_peso or cambio_oficial or cambio_estilos:
                            existente['peso'] = str(peso_red)
                            existente['peso_oficial'] = texto_oficial
                            existente['estilos'] = data["estilos"]
                            existente['ids_divisiones'] = data["ids_divs"]
                            # --- NUEVO: Resetear ciclo y marcar como editado por la red ---
                            existente['ciclos_red'] = 0
                            existente['tipo_cambio_red'] = 'editado'
                            hubo_cambios = True
                            
                        if existente.get('de_red') and existente.get('ciclos_red', 2) < 2:
                            existente['ciclos_red'] = existente.get('ciclos_red', 0) + 1
                            hubo_cambios = True
                            
                        nueva_memoria.append(existente)
                    else:
                        nueva_memoria.append({
                            "id_atleta": id_atl, "peso": str(peso_red), "peso_oficial": " | ".join(data["pesos_text"]),
                            "estilos": data["estilos"], "ids_divisiones": data["ids_divs"],
                            "de_red": True, "ciclos_red": 0, "tipo_cambio_red": "nuevo" # <--- Etiqueta inicial
                        })
                        hubo_cambios = True
                        
                # --- NUEVO: DETECTAR Y MANTENER ELIMINADOS DE LA RED POR 2 CICLOS ---
                for loc in self.inscripciones_memoria:
                    id_loc = int(loc['id_atleta'])
                    if id_loc not in atletas_agrupados:
                        if not loc.get('de_red'):
                            # Local puro, se conserva en pantalla
                            nueva_memoria.append(loc)
                        else:
                            # Era de red, pero ya no está en BD (fue eliminado por alguien más)
                            ciclos = loc.get('ciclos_red', 2)
                            tipo = loc.get('tipo_cambio_red', '')
                            
                            if tipo != 'eliminado':
                                # Recién descubierto que lo borraron, iniciamos su velorio visual
                                loc['tipo_cambio_red'] = 'eliminado'
                                loc['ciclos_red'] = 0
                                nueva_memoria.append(loc)
                                hubo_cambios = True
                            elif ciclos < 1: # --- FIX: Reducimos de 2 a 1 para que desaparezca a los 3-6 segundos ---
                                loc['ciclos_red'] += 1
                                nueva_memoria.append(loc)
                                hubo_cambios = True
                            else:
                                hubo_cambios = True
                        
                ids_en_red = set(atletas_agrupados.keys())
                ids_azules_locales = set(int(i['id_atleta']) for i in self.inscripciones_memoria if i.get('de_red') and i.get('tipo_cambio_red') != 'eliminado')
                if ids_en_red != ids_azules_locales:
                    hubo_cambios = True

                if hubo_cambios:
                    self.inscripciones_memoria = nueva_memoria
                    self.actualizar_tabla_visual()
                    self.actualizar_opciones_filtros()
                    
        except Exception as e:
            print(f"Error en radar de red: {e}")

    def iniciar_escucha_red(self):
        """Inicia el bucle que consulta la BD cada 3 segundos."""
        if not hasattr(self, 'escuchando_red') or not self.escuchando_red:
            self.escuchando_red = True
            self.ciclo_escucha_red()
            self.escuchar_nuevos_atletas_red() # <--- NUEVO MOTOR ACTIVADO

    def ciclo_escucha_red(self):
        if not getattr(self, "escuchando_red", False): return
        
        id_torneo = getattr(self, 'torneo_debug_id', None)
        id_mi_conexion = getattr(self.controller, 'id_conexion_red', None)
        if not id_torneo or not id_mi_conexion: return

        mi_estado = self.db.verificar_estado_mi_conexion(id_mi_conexion)
        if not mi_estado:
            self.escuchando_red = False
            self.controller.id_conexion_red = None
            self.controller.es_master = False
            messagebox.showwarning("Desconectado", "Has sido desconectado de la sala.")
            self.resetear_torneo(forzar=True)
            return

        if hasattr(self.db, 'mantener_latido_conexion'):
            self.db.mantener_latido_conexion(id_mi_conexion)

        is_master_db = mi_estado.get('es_master', False)
        was_master_local = getattr(self.controller, 'es_master', False)

        # 2. TRANSICIONES DE PODER PACÍFICAS
        if is_master_db and not was_master_local:
            # --- ASCENSO ---
            self.controller.es_master = True
            self.controller.tapiz_asignado = mi_estado.get('tapiz_asignado', 'Tapiz A')
            
            self.bloquear_datos_torneo(False) # Muestra botón Modificar
            
            # --- CORRECCIÓN: Inicia bloqueado, requiere clic en "Modificar" ---
            self.ent_tor_nombre.config(state="disabled")
            self.ent_tor_lugar.config(state="disabled")
            self.cmb_categoria.config(state="disabled")
            if hasattr(self, 'cmb_tor_ciudad'): self.cmb_tor_ciudad.config(state="disabled")
            
            if hasattr(self, 'btn_guardar_torneo'):
                self.btn_guardar_torneo.config(state="normal", text="💾 Guardar Cambios")
            
            messagebox.showinfo("Control de Sala", "¡Has recibido los privilegios de Máster!")

        elif not is_master_db and was_master_local:
            # --- DESCENSO ---
            self.controller.es_master = False
            
            self.bloquear_datos_torneo(True) # Activa el escudo
            if hasattr(self, 'tabla_red') and self.tabla_red.selection():
                self.tabla_red.selection_remove(self.tabla_red.selection())
            self.gestionar_estado_botones_red() 
            
            if hasattr(self, 'btn_guardar_torneo'):
                self.btn_guardar_torneo.config(state="normal", text="☁️ Sincronizar Atletas")

        # 3. HERENCIA POR DESCONEXIÓN ABRUPTA
        if not is_master_db:
            master_activo = self.db.verificar_master_activo(id_torneo)
            if not master_activo:
                if hasattr(self.db, 'heredar_master'):
                    heredado = self.db.heredar_master(id_torneo, id_mi_conexion)
                    if heredado:
                        messagebox.showwarning("Máster Caído", "El Máster anterior se desconectó.\nHas heredado automáticamente el control de la sala.")

        # 4. ACTUALIZAR VISUALES Y BLOQUEOS
        self.refrescar_estado_bloqueos()

        # --- CORTAFUEGOS: Si el torneo cerró, detener todo ---
        if getattr(self, "torneo_finalizado", False):
            return

        # Sincronización de atletas para TODOS (Master y Guest)
        self.escuchar_nuevos_atletas_red()

        if self.controller.es_master:
            if hasattr(self.db, 'limpiar_conexiones_muertas'):
                self.db.limpiar_conexiones_muertas(id_torneo)
            self.refrescar_tabla_red_master(id_torneo)
        else:
            self.comprobar_estado_guest(id_torneo, id_mi_conexion)

        # Repetir cada 3 segundos
        self.after(3000, self.ciclo_escucha_red)

    def refrescar_tabla_red_master(self, id_torneo):
        """Actualiza la lista para el Admin, preservando selecciones múltiples."""
        
        # FIJAR SIEMPRE LA ETIQUETA VERDE DEL MÁSTER
        id_oficial = getattr(self.controller, 'id_operador', None)
        oficial = next((o for o in self.oficiales_db if o['id'] == id_oficial), None)
        nom_ofi = f"{oficial['nombre']} {oficial['apellidos']}" if oficial else "Desconocido"
        mi_tapiz = getattr(self.controller, 'tapiz_asignado', 'Tapiz A')
        self.lbl_tapete_master.config(text=f"🥇 {mi_tapiz} (Máster: {nom_ofi})", foreground="#28a745")

        # --- NUEVO CORTAFUEGOS: Si ya cerró, vaciar y no hacer nada más ---
        if getattr(self, "torneo_finalizado", False):
            for item in self.tabla_red.get_children(): 
                self.tabla_red.delete(item)
            return

        # 1. Guardar TODAS las selecciones actuales...
        ids_seleccionados = [str(self.tabla_red.item(i, "values")[0]) for i in self.tabla_red.selection()]

        conexiones = self.db.obtener_conexiones_torneo(id_torneo)
        for item in self.tabla_red.get_children(): 
            self.tabla_red.delete(item)

        if not conexiones: 
            self.gestionar_estado_botones_red()
            return

        for c in conexiones:
            es_master = c.get('es_master', False)
            mi_id = getattr(self.controller, 'id_conexion_red', None)
            
            tag = "yo_mismo" if str(c['id_conexion']) == str(mi_id) else ("confirmado" if c['estado_conexion'] == 'Aprobado' else "pendiente")
            nombre_visual = f"⭐ {c['nombre']} {c['apellidos']}" if es_master else f"{c['nombre']} {c['apellidos']}"
            tapiz_visual = c['tapiz_asignado'] or "N.A."
            
            valores = (c['id_conexion'], nombre_visual, c['nombre_dispositivo'], tapiz_visual, c['estado_conexion'])
            new_item = self.tabla_red.insert("", "end", values=valores, tags=(tag,))
            
            # 2. Restaurar selección múltiple
            if str(c['id_conexion']) in ids_seleccionados:
                self.tabla_red.selection_add(new_item)
                
        # 3. Re-evaluar los botones de seguridad tras refrescar
        self.gestionar_estado_botones_red()

    def comprobar_estado_guest(self, id_torneo, id_mi_conexion):
        """El Guest verifica su estado y actualiza la UI e invitados al instante."""
        estado_bd = self.db.verificar_estado_mi_conexion(id_mi_conexion)
        
        if not estado_bd: return # Seguridad por si se borra la conexión

        estado_conexion = estado_bd['estado_conexion']
        tapiz = estado_bd['tapiz_asignado']
        self.controller.tapiz_asignado = tapiz

        # Obtener a todos los presentes en la sala
        conexiones = self.db.obtener_conexiones_torneo(id_torneo)
        master_nombre = "Desconocido"

        for item in self.tabla_red.get_children(): self.tabla_red.delete(item)

        for c in conexiones:
            es_master = c.get('es_master', False)
            if es_master: master_nombre = f"{c['nombre']} {c['apellidos']}"
            
            es_yo = (str(c['id_conexion']) == str(id_mi_conexion))
            tag = "yo_mismo" if es_yo else ("confirmado" if c['estado_conexion'] == 'Aprobado' else "pendiente")
            
            nombre_visual = f"⭐ {c['nombre']} {c['apellidos']}" if es_master else f"{c['nombre']} {c['apellidos']}"
            tapiz_visual = c['tapiz_asignado'] or "N.A."
            
            self.tabla_red.insert("", "end", values=(c['id_conexion'], nombre_visual, c['nombre_dispositivo'], tapiz_visual, c['estado_conexion']), tags=(tag,))

        # Actualización de etiqueta basada en la realidad de la BD
        if estado_conexion == 'Aprobado':
            self.lbl_tapete_master.config(text=f"✅ {tapiz} (Máster: {master_nombre})", foreground="#17a2b8")
            if hasattr(self, 'btn_avanzar_pareo'): self.btn_avanzar_pareo.config(state="normal")
            
            # --- CORTAFUEGOS: Solo habilitar interfaz si NO estoy editando un atleta ---
            if str(self.cmb_atleta.cget("state")) == "disabled" and not getattr(self, "todo_bloqueado", False):
                if getattr(self, "id_atleta_editando", None) is None: # <--- CONDICIÓN DE BLOQUEO
                    self.cambiar_estado_inscripcion("normal")
            self.bloquear_seleccion_tabla = False
        else:
            # Invitado Pendiente: Todo congelado
            self.lbl_tapete_master.config(text=f"⏳ Esperando aprobación (Máster: {master_nombre})", foreground="#fd7e14")
            if hasattr(self, 'btn_avanzar_pareo'): self.btn_avanzar_pareo.config(state="disabled")
            
            self.cambiar_estado_inscripcion("disabled")
            self.bloquear_seleccion_tabla = True

        self.actualizar_botones_guardado()
