import tkinter as tk
from tkinter import ttk, messagebox
from utils.utilidades import ComboBuscador, aplicar_deseleccion_tabla
from ui.ventanas.ventana_previsualizacion_pdf import VentanaPrevisualizacionPDF

class LogicaCarteleraMixin:
    """Maneja el ordenamiento de peleas, el historial, el panel de combate embebido y la asignación de ganadores."""

    def construir_interfaz_cartelera(self):
        # --- 1. SUB-PESTAÑAS (Navegación Cartelera) ---
        self.filtro_cartelera = tk.StringVar(value="Pendientes")

        nav_frame = ttk.Frame(self.tab_cartelera)
        nav_frame.pack(fill="x", pady=(0, 5))

        # --- NUEVO: Guardar referencia a los Radiobuttons ---
        self.rb_pendientes = ttk.Radiobutton(nav_frame, text="🟢 Combates Activos / Pendientes", variable=self.filtro_cartelera, value="Pendientes", command=self.actualizar_cartelera, style="Toolbutton")
        self.rb_pendientes.pack(side="left", padx=5)
        
        self.rb_historial = ttk.Radiobutton(nav_frame, text="📜 Historial de Combates", variable=self.filtro_cartelera, value="Historial", command=self.actualizar_cartelera, style="Toolbutton")
        self.rb_historial.pack(side="left", padx=5)

        # --- 2. CONTENEDOR DE CABECERA (Alterna entre Modos) ---
        self.header_cartelera = ttk.Frame(self.tab_cartelera)
        self.header_cartelera.pack(fill="x", pady=5)

        # ================= MODO 1: ORDENAMIENTO (Pendientes) =================
        self.frame_orden = ttk.Frame(self.header_cartelera)
        
        ttk.Label(self.frame_orden, text="Modo de Ordenamiento:").pack(side="left", padx=5)
        self.combo_orden_cartelera = ComboBuscador(self.frame_orden, values=[
            "Por Rounds (Mezclando estilos por fase y peso)", 
            "Prioridad Femenina (Terminar estilo femenino primero)"
        ], state="readonly", width=50)
        self.combo_orden_cartelera.set("Por Rounds (Mezclando estilos por fase y peso)")
        self.combo_orden_cartelera.pack(side="left", padx=5)
        
        self.combo_orden_cartelera.bind("<<ComboboxSelected>>", lambda e: self.actualizar_cartelera())

        # ================= MODO 2: HISTORIAL (Terminados) =================
        self.frame_historial = ttk.Frame(self.header_cartelera)
        
        self.lbl_stats_historial = ttk.Label(self.frame_historial, text="Peleas: 0  |  Rondas: 0  |  Atletas: 0  |  Clubes: 0", foreground="#17a2b8", font=("Helvetica", 9, "bold"))
        self.lbl_stats_historial.pack(side="left", padx=10)

        frame_busqueda = ttk.Frame(self.frame_historial)
        frame_busqueda.pack(side="right", padx=10)
        
        ttk.Label(frame_busqueda, text="Buscar por:").pack(side="left", padx=5)
        self.cmb_buscar_historial = ttk.Combobox(frame_busqueda, values=["Ronda", "Estilo", "División", "Atleta", "Club"], state="readonly", width=12)
        self.cmb_buscar_historial.set("Atleta")
        self.cmb_buscar_historial.pack(side="left", padx=5)
        
        self.ent_buscar_historial = ttk.Entry(frame_busqueda, width=25)
        self.ent_buscar_historial.pack(side="left", padx=5)
        
        self.ent_buscar_historial.bind("<KeyRelease>", lambda e: self.actualizar_cartelera())
        self.cmb_buscar_historial.bind("<<ComboboxSelected>>", lambda e: [self.ent_buscar_historial.delete(0, tk.END), self.actualizar_cartelera()])

        # ================= 3. INICIO DE LA TABLA PERSONALIZADA =================
        contenedor_tabla = ttk.Frame(self.tab_cartelera)

        header_frame = tk.Frame(contenedor_tabla, height=30)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        def crear_celda_header(texto, ancho, bg_color):
            celda = tk.Frame(header_frame, width=ancho, bg=bg_color, highlightbackground="#555555", highlightthickness=1)
            celda.pack(side="left", fill="y")
            celda.pack_propagate(False)
            tk.Label(celda, text=texto, bg=bg_color, fg="white", font=("Helvetica", 10, "bold")).pack(expand=True)

        crear_celda_header("Ronda", 80, "#2a2a2a")
        crear_celda_header("Tapiz", 80, "#2a2a2a") 
        crear_celda_header("Estilo", 120, "#2a2a2a")
        crear_celda_header("División", 100, "#2a2a2a")
        crear_celda_header("Esquina Roja", 350, "#cc0000") 
        crear_celda_header("Esquina Azul", 350, "#0000cc") 
        
        filler = tk.Frame(header_frame, bg="#2a2a2a", highlightbackground="#555555", highlightthickness=1)
        filler.pack(side="left", fill="both", expand=True)

        columnas = ("ronda", "tapiz", "estilo", "peso", "rojo", "azul") 
        self.tree_cartelera = ttk.Treeview(contenedor_tabla, columns=columnas, show="", height=20)
        aplicar_deseleccion_tabla(self.tree_cartelera)
        self.tree_cartelera.column("#0", width=0, stretch=tk.NO) 
        
        self.tree_cartelera.column("ronda", width=80, anchor="center", stretch=False)
        self.tree_cartelera.column("tapiz", width=80, anchor="center", stretch=False) 
        self.tree_cartelera.column("estilo", width=120, anchor="center", stretch=False)
        self.tree_cartelera.column("peso", width=100, anchor="center", stretch=False)
        self.tree_cartelera.column("rojo", width=350, stretch=False)
        self.tree_cartelera.column("azul", width=350, stretch=False)
        
        self.tree_cartelera.bind("<Double-1>", self.accion_doble_clic_cartelera)
        self.tree_cartelera.bind("<<TreeviewSelect>>", self.accion_clic_cartelera)
        self.tree_cartelera.tag_configure("en_curso", background="#ffc107", foreground="black")

        self.tree_cartelera.bind("<Button-1>", self.evaluar_cierre_flotante, add="+")
        self.tree_cartelera.bind("<MouseWheel>", self.cerrar_panel_flotante_cartelera, add="+")
        self.tree_cartelera.bind("<Button-4>", self.cerrar_panel_flotante_cartelera, add="+")
        self.tree_cartelera.bind("<Button-5>", self.cerrar_panel_flotante_cartelera, add="+")

        # ================= 4. CONTENEDOR INFERIOR ANCLADO =================
        frame_inferior = ttk.Frame(self.tab_cartelera)
        frame_inferior.pack(side="bottom", fill="x", pady=(5, 5)) 

        self.lbl_hint_cartelera = ttk.Label(frame_inferior, text="* Haz doble clic en un combate para abrir el marcador oficial e iniciarlo.", font=("Helvetica", 9, "italic"))
        self.lbl_hint_cartelera.pack(pady=(0, 5))

        self.btn_cerrar_torneo = tk.Button(frame_inferior, text="🏆 CERRAR TORNEO Y GENERAR REPORTE", font=("Helvetica", 12, "bold"), bg="#ff4d4d", fg="white", command=self.cerrar_torneo)
        self.btn_cerrar_torneo.pack(ipadx=15, ipady=5)

        # --- NUEVO: Botón de Buscar en Llave anclado a la derecha ANTES de la tabla ---
        frame_btn_cartelera = ttk.Frame(self.tab_cartelera) 
        frame_btn_cartelera.pack(side="bottom", fill="x", pady=5)
        self.btn_buscar_en_llave = ttk.Button(frame_btn_cartelera, text="🎯 Buscar en Llave", state="disabled", command=self.buscar_seleccion_en_llave)
        self.btn_buscar_en_llave.pack(side="right")

        # ================= 5. EMPAQUETADO FINAL DE LA TABLA =================
        # La tabla DEBE ser lo último en empacarse para no devorar a los demás widgets
        contenedor_tabla.pack(side="top", fill="both", expand=True)
        self.tree_cartelera.pack(side="top", fill="both", expand=True)

        frame_btn_cartelera = ttk.Frame(self.tab_cartelera) 
        frame_btn_cartelera.pack(fill="x", pady=5)
        self.btn_buscar_en_llave = ttk.Button(frame_btn_cartelera, text="🎯 Buscar en Llave", state="disabled", command=self.buscar_seleccion_en_llave)
        self.btn_buscar_en_llave.pack(side="right")

    def accion_doble_clic_cartelera(self, event):
        """Se dispara con doble clic. Si estamos en historial o bloqueados, no hace nada."""
        if getattr(self, "cartelera_bloqueada", False) or getattr(self, "modo_historial", False):
            return 
        self.iniciar_pelea_desde_cartelera(event)

    def accion_clic_cartelera(self, event):
        """Se dispara al seleccionar o deseleccionar una fila en la tabla."""
        if getattr(self, "cartelera_bloqueada", False):
            # Expulsar la selección inmediatamente para que no se vea azul
            if self.tree_cartelera.selection():
                self.tree_cartelera.selection_remove(self.tree_cartelera.selection())
            return
            
        sel = self.tree_cartelera.selection()
        
        # Si no hay nada seleccionado (clic en el vacío)
        if not sel:
            self.cerrar_panel_flotante_cartelera()
            if hasattr(self, 'btn_buscar_en_llave'): 
                self.btn_buscar_en_llave.config(state="disabled")
            return

        # Si hay algo seleccionado, encendemos el botón de buscar
        if hasattr(self, 'btn_buscar_en_llave'): 
            self.btn_buscar_en_llave.config(state="normal")
            
        # Abrimos el panel flotante extrayendo los datos de la fila
        item_id = sel[0]
        llave_key = self.tree_cartelera.item(item_id, "text")
        match_node = getattr(self.tree_cartelera, f"nodo_{item_id}", None)
        
        if match_node:
            try:
                # Usamos tu función nativa para desplegar el panel lateral
                self.mostrar_panel_historial_cartelera(match_node, llave_key, item_id)
            except Exception as e:
                print(f"Error interno al abrir el panel de la cartelera: {e}")

    def cerrar_panel_flotante_cartelera(self, event=None):
        """Destruye el panel superpuesto si existe."""
        if hasattr(self, "panel_flotante") and self.panel_flotante.winfo_exists():
            self.panel_flotante.destroy()

    def evaluar_cierre_flotante(self, event):
        """Si el usuario hace clic fuera de los límites del panel flotante, lo destruye."""
        if not hasattr(self, "panel_flotante") or not self.panel_flotante.winfo_exists():
            return
            
        # Coordenadas globales del ratón en la pantalla
        x_root, y_root = event.x_root, event.y_root
        
        # Coordenadas globales de los límites del panel
        x1 = self.panel_flotante.winfo_rootx()
        y1 = self.panel_flotante.winfo_rooty()
        x2 = x1 + self.panel_flotante.winfo_width()
        y2 = y1 + self.panel_flotante.winfo_height()

        # Si el clic NO fue dentro del cuadrado del panel, lo cerramos
        if not (x1 <= x_root <= x2 and y1 <= y_root <= y2):
            self.cerrar_panel_flotante_cartelera()

    def mostrar_panel_historial_cartelera(self, match_node, llave_key, item_id):
        self.cerrar_panel_flotante_cartelera() 

        bbox = self.tree_cartelera.bbox(item_id)
        if not bbox: return 

        p_rojo = self.obtener_peleador_real(match_node["peleador_rojo"])
        p_azul = self.obtener_peleador_real(match_node["peleador_azul"])
        
        self.panel_flotante = tk.Frame(self.tree_cartelera, bg="#2d2d2d", highlightbackground="gray", highlightthickness=1)
        
        top_bar = tk.Frame(self.panel_flotante, bg="#1e1e1e")
        top_bar.pack(fill="x")
        ttk.Label(top_bar, text=f"Detalles del Combate (Ronda {match_node['ronda']})", font=("Helvetica", 10, "bold"), background="#1e1e1e", foreground="white").pack(pady=5)
        
        main_frame = ttk.Frame(self.panel_flotante, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        frame_vs = ttk.Frame(main_frame)
        frame_vs.pack(pady=5)
        
        is_rojo_fantasma = p_rojo and p_rojo.get("id") == -1
        is_azul_fantasma = p_azul and p_azul.get("id") == -1
        
        if is_rojo_fantasma and not is_azul_fantasma:
            ttk.Label(frame_vs, text=p_azul['nombre'], foreground="#6666ff", font=("Helvetica", 11, "bold")).pack()
            ttk.Label(frame_vs, text="Avanza por Incomparecencia (Op. Descalificado)", font=("Helvetica", 9, "italic"), foreground="#aaaaaa").pack()
        elif is_azul_fantasma and not is_rojo_fantasma:
            ttk.Label(frame_vs, text=p_rojo['nombre'], foreground="#ff6666", font=("Helvetica", 11, "bold")).pack()
            ttk.Label(frame_vs, text="Avanza por Incomparecencia (Op. Descalificado)", font=("Helvetica", 9, "italic"), foreground="#aaaaaa").pack()
        elif is_rojo_fantasma and is_azul_fantasma:
            ttk.Label(frame_vs, text="Llave Vacante", foreground="#dc3545", font=("Helvetica", 11, "bold")).pack()
            ttk.Label(frame_vs, text="(Ambos oponentes previos descalificados)", font=("Helvetica", 9, "italic"), foreground="#aaaaaa").pack()
        else:
            nom_rojo = p_rojo['nombre'] if p_rojo else "A la espera..."
            nom_azul = p_azul['nombre'] if p_azul else "A la espera..."
            ttk.Label(frame_vs, text=nom_rojo, foreground="#ff6666", font=("Helvetica", 10, "bold")).grid(row=0, column=0, padx=5)
            ttk.Label(frame_vs, text=" VS ", font=("Helvetica", 10, "bold")).grid(row=0, column=1)
            ttk.Label(frame_vs, text=nom_azul, foreground="#6666ff", font=("Helvetica", 10, "bold")).grid(row=0, column=2, padx=5)
        
        estado = "Finalizado" if match_node.get("ganador") else "Pendiente"
        color_estado = "#28a745" if estado == "Finalizado" else "#ffc107"
        ttk.Label(main_frame, text=f"Estado: {estado}", foreground=color_estado, font=("Helvetica", 9, "bold")).pack(pady=(10, 2))
        
        if match_node.get("ganador"):
            ganador = match_node["ganador"]
            motivo = ganador.get("motivo_victoria", "Decisión")
            ganador_id = ganador.get("id")
            
            if ganador_id == -1:
                ttk.Label(main_frame, text="Resultado: Doble Descalificación", foreground="#ff4d4d", font=("Helvetica", 10, "bold")).pack()
            else:
                ttk.Label(main_frame, text=f"Ganador: {ganador['nombre']}", foreground="#28a745", font=("Helvetica", 10, "bold")).pack()
            ttk.Label(main_frame, text=f"Método: {motivo}", foreground="#17a2b8", font=("Helvetica", 9)).pack(pady=(0, 5))
        
        # --- BOTONES INTELIGENTES SEGÚN EL ESTADO DEL COMBATE ---
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(10, 0))
        estilo_ext, peso_ext = llave_key.split("-")
        
        if is_rojo_fantasma or is_azul_fantasma:
            ttk.Label(btn_frame, text="Avance Automático (Sin Acta de Combate)", foreground="#17a2b8", font=("Helvetica", 9, "bold")).pack(side="left", padx=5)
        else:
            ganador_data = match_node.get("ganador") or {}
            ganador_id = ganador_data.get("id")
            motivo = ganador_data.get("motivo_victoria", "")

            # --- CAMBIO: SI ES PENDIENTE, MOSTRAMOS EL BOTÓN "INICIAR PELEA" ---
            if not match_node.get("ganador"):
                ttk.Button(btn_frame, text="Iniciar Pelea", command=lambda: self.iniciar_pelea_desde_cartelera(item_id_override=item_id)).pack(side="left", padx=5)
            # Si el combate terminó por DSQ
            elif ganador_id == -1 or "DSQ" in motivo:
                ttk.Label(btn_frame, text="Combate cerrado por Descalificación", foreground="#dc3545", font=("Helvetica", 9, "bold")).pack(side="left", padx=5)
            # Si el torneo ya finalizó completamente
            elif getattr(self, "torneo_cerrado_en_db", False) or getattr(self.controller, "torneo_finalizado", False):
                ttk.Label(btn_frame, text="Torneo Finalizado (Solo Lectura)", foreground="#17a2b8", font=("Helvetica", 9, "italic")).pack(side="left", padx=5)
                ttk.Button(btn_frame, text="👁 Ver Datos", command=lambda: VentanaPrevisualizacionPDF(self, match_node, estilo_ext, peso_ext)).pack(side="left", padx=5)
            # Pelea normal finalizada que se puede editar
            else:
                ttk.Button(btn_frame, text="Editar Pelea", command=lambda: self.abrir_edicion_desde_cartelera(match_node, llave_key)).pack(side="left", padx=5)
                ttk.Button(btn_frame, text="👁 Ver Datos", command=lambda: VentanaPrevisualizacionPDF(self, match_node, estilo_ext, peso_ext)).pack(side="left", padx=5)

        self.panel_flotante.update_idletasks()
        ancho_panel = self.panel_flotante.winfo_reqwidth()
        alto_panel = self.panel_flotante.winfo_reqheight()
        
        x_pos = (self.tree_cartelera.winfo_width() // 2) - (ancho_panel // 2)
        y_pos = bbox[1] + bbox[3] 
        
        if y_pos + alto_panel > self.tree_cartelera.winfo_height():
            y_pos = bbox[1] - alto_panel
            
        self.panel_flotante.place(x=max(10, x_pos), y=y_pos)

    def al_cambiar_pestana(self, event):
        self.cerrar_panel_combate()
            
        # Refresca la información inmediatamente al entrar a la pestaña
        idx = self.notebook.index(self.notebook.select())
        if idx == 0:
            self.actualizar_cartelera()
        else:
            tab = self.notebook.nametowidget(self.notebook.select())
            self.procesar_y_dibujar(tab)

    def actualizar_cartelera(self, event=None):
        self.cerrar_panel_flotante_cartelera() 

        for item in self.tree_cartelera.get_children():
            self.tree_cartelera.delete(item)
            
        # Sincronizar el modo ANTES de procesar
        self.modo_historial = (self.filtro_cartelera.get() == "Historial")
            
        # LÓGICA DE BLOQUEOS
        total_bloqueadas = len(getattr(self, "divisiones_bloqueadas", []))
        self.cartelera_bloqueada = total_bloqueadas == 0

        # --- 1. RECOLECTAR TODAS LAS PELEAS PRIMERO ---
        todas_peleas = []
        for llave_key in self.divisiones_bloqueadas:
            grid = self.grids_generados.get(llave_key, [])
            estilo, peso_str = llave_key.split("-")
            peso_int = int(peso_str.lower().replace("kg", "").replace(" ", "").strip())
            prio_estilo = 0 if "Femenina" in estilo else 1

            for r in range(len(grid)):
                for node in grid[r]:
                    if isinstance(node, dict) and node.get("tipo") == "combate":
                        p_rojo = self.obtener_peleador_real(node["peleador_rojo"])
                        p_azul = self.obtener_peleador_real(node["peleador_azul"])
                        
                        if p_rojo and p_azul:
                            is_terminada = node.get("ganador") is not None
                            tapiz_activo = getattr(self, 'combates_en_curso_red', {}).get(llave_key, {}).get(node.get("match_id"))
                            
                            todas_peleas.append({
                                "ronda": node["ronda"],
                                "prio_estilo": prio_estilo,
                                "estilo": estilo,
                                "peso_int": peso_int,
                                "peso_str": peso_str,
                                "id_rojo": p_rojo['id'],
                                "nom_rojo": f"{p_rojo['nombre']} ({p_rojo.get('club', 'Sin Club')})",
                                "id_azul": p_azul['id'],
                                "nom_azul": f"{p_azul['nombre']} ({p_azul.get('club', 'Sin Club')})",
                                "club_rojo": p_rojo.get('club', 'Sin Club'),
                                "club_azul": p_azul.get('club', 'Sin Club'),
                                "nodo_combate": node,
                                "llave_key": llave_key,
                                "terminada": is_terminada,
                                "tapiz_activo": tapiz_activo 
                            })

        # --- 2. CONTAR PENDIENTES Y FINALIZADOS ---
        combates_pendientes = [c for c in todas_peleas if not c['terminada']]
        total_pendientes = len(combates_pendientes)
        total_finalizados = len([c for c in todas_peleas if c['terminada']])

        # --- 3. LÓGICA VISUAL DE LAS PESTAÑAS DE NAVEGACIÓN ---
        torneo_cerrado = getattr(self, "torneo_cerrado_en_db", False) or getattr(self.controller, "torneo_finalizado", False)
        
        # Ocultar si está cerrado oficialmente O si ya hay peleas registradas pero 0 pendientes (Torneo finalizado en la práctica)
        if torneo_cerrado or (len(todas_peleas) > 0 and total_pendientes == 0):
            if hasattr(self, 'rb_pendientes'):
                try: self.rb_pendientes.pack_forget() 
                except: pass
                
            if hasattr(self, 'rb_historial'):
                self.rb_historial.config(state="normal") 
                
            # Si intentó pasarse a Pendientes o ya no hay, lo forzamos de vuelta a Historial
            if not self.modo_historial:
                self.filtro_cartelera.set("Historial")
                self.modo_historial = True
        else:
            # Comportamiento normal si el torneo sigue vivo y HAY pendientes
            if hasattr(self, 'rb_pendientes'):
                # Si estaba oculto, lo volvemos a mostrar ANTES del historial
                if not self.rb_pendientes.winfo_ismapped():
                    try: self.rb_pendientes.pack(side="left", padx=5, before=self.rb_historial) 
                    except: pass
                self.rb_pendientes.config(state="normal")
                
            if total_finalizados == 0:
                if hasattr(self, 'rb_historial'):
                    self.rb_historial.config(state="disabled")
                if self.modo_historial:
                    self.filtro_cartelera.set("Pendientes")
                    self.modo_historial = False 
            else:
                if hasattr(self, 'rb_historial'):
                    self.rb_historial.config(state="normal")

        # Evaluamos qué vista quiere el usuario finalmente
        self.modo_historial = (self.filtro_cartelera.get() == "Historial")
        
        if self.modo_historial:
            # === MODO HISTORIAL ===
            self.frame_orden.pack_forget()
            if not self.frame_historial.winfo_ismapped():
                self.frame_historial.pack(side="left", fill="x", expand=True)
            if hasattr(self, 'lbl_hint_cartelera'): 
                self.lbl_hint_cartelera.pack_forget()
            
            # Filtrar solo los terminados
            combates_base = [c for c in todas_peleas if c['terminada']]
            
            # Aplicar Filtros de Búsqueda
            search_term = self.ent_buscar_historial.get().lower().strip()
            search_by = self.cmb_buscar_historial.get()
            
            combates_mostrar = []
            for c in combates_base:
                if search_term:
                    if search_by == "Atleta" and (search_term in c['nom_rojo'].lower() or search_term in c['nom_azul'].lower()): combates_mostrar.append(c)
                    elif search_by == "Club" and (search_term in c['club_rojo'].lower() or search_term in c['club_azul'].lower()): combates_mostrar.append(c)
                    elif search_by == "Ronda" and search_term in str(c['ronda']): combates_mostrar.append(c)
                    elif search_by == "Estilo" and search_term in c['estilo'].lower(): combates_mostrar.append(c)
                    elif search_by == "División" and search_term in c['peso_str'].lower(): combates_mostrar.append(c)
                else:
                    combates_mostrar.append(c)
                    
            rondas_unicas = len(set(c['ronda'] for c in combates_mostrar))
            ids_atletas = set([c['id_rojo'] for c in combates_mostrar] + [c['id_azul'] for c in combates_mostrar])
            ids_clubes = set([c['club_rojo'] for c in combates_mostrar] + [c['club_azul'] for c in combates_mostrar])
            if "Sin Club" in ids_clubes: ids_clubes.remove("Sin Club") 
            
            self.lbl_stats_historial.config(text=f"Peleas: {len(combates_mostrar)}  |  Rondas: {rondas_unicas}  |  Atletas: {len(ids_atletas)}  |  Clubes: {len(ids_clubes)}")
            
            combates_mostrar.sort(key=lambda x: (x["ronda"], x["prio_estilo"], x["peso_int"]))
            cartelera_final = combates_mostrar
            
        else:
            # === MODO NORMAL (PENDIENTES) ===
            self.frame_historial.pack_forget()
            if not self.frame_orden.winfo_ismapped():
                self.frame_orden.pack(side="left", fill="x", expand=True)
            if hasattr(self, 'lbl_hint_cartelera') and not self.lbl_hint_cartelera.winfo_ismapped():
                self.lbl_hint_cartelera.pack(pady=(0, 5), before=self.btn_cerrar_torneo)
            
            # Filtrar solo los pendientes
            combates_pendientes = [c for c in todas_peleas if not c['terminada']]
            
            modo_seleccionado = getattr(self, "combo_orden_cartelera", None)
            if modo_seleccionado and "Prioridad Femenina" in modo_seleccionado.get():
                combates_pendientes.sort(key=lambda x: (x["prio_estilo"], x["ronda"], x["peso_int"]))
            else:
                combates_pendientes.sort(key=lambda x: (x["ronda"], x["peso_int"], x["prio_estilo"]))
            
            cartelera_final = []
            registro_descanso = {} 
            separacion_ideal = 3 

            while combates_pendientes:
                mejor_idx = 0 
                for i, c in enumerate(combates_pendientes):
                    distancia_r = len(cartelera_final) - registro_descanso.get(c["id_rojo"], -999)
                    distancia_a = len(cartelera_final) - registro_descanso.get(c["id_azul"], -999)
                    if distancia_r >= separacion_ideal and distancia_a >= separacion_ideal:
                        mejor_idx = i
                        break 
                
                elegido = combates_pendientes.pop(mejor_idx)
                cartelera_final.append(elegido)
                indice_actual = len(cartelera_final) - 1
                registro_descanso[elegido["id_rojo"]] = indice_actual
                registro_descanso[elegido["id_azul"]] = indice_actual

        for idx, c in enumerate(cartelera_final):
            tapiz_str = c['tapiz_activo'] if c['tapiz_activo'] else "N.A."
            tags_fila = [c['llave_key'], str(c['nodo_combate'])]
            if c['tapiz_activo']:
                tags_fila.append("en_curso") 

            self.tree_cartelera.insert("", "end", iid=str(idx), values=(
                f"Ronda {c['ronda']}", tapiz_str, c['estilo'], c['peso_str'], c['nom_rojo'], c['nom_azul']
            ), tags=tuple(tags_fila))
            
            self.tree_cartelera.item(str(idx), text=c['llave_key'])
            setattr(self.tree_cartelera, f"nodo_{idx}", c['nodo_combate'])

    def iniciar_pelea_desde_cartelera(self, event=None, item_id_override=None):
        # 1. --- VALIDACIÓN DE SEGURIDAD MEJORADA ---
        total_divisiones = sum(len(pesos) for pesos in self.datos.values())
        if len(self.divisiones_bloqueadas) < total_divisiones:
            faltantes = total_divisiones - len(self.divisiones_bloqueadas)
            return messagebox.showwarning("Llaves Pendientes", 
                f"No se puede iniciar la competencia.\n\nAún faltan {faltantes} categorías de peso por confirmar y bloquear.")

        # --- CAMBIO: Usamos el ID forzado del botón si existe, o el foco actual ---
        item_id = item_id_override or self.tree_cartelera.focus()
        if not item_id: return
        
        # ---> NUEVO: Bloquear si ya está en amarillo <---
        tags = self.tree_cartelera.item(item_id, "tags")
        if "en_curso" in tags:
            return messagebox.showwarning("Bloqueado", "Este combate ya está siendo arbitrado en otro tapiz.")

        llave_key = self.tree_cartelera.item(item_id, "text")
        match_node = getattr(self.tree_cartelera, f"nodo_{item_id}", None)
        
        if match_node:
            # Separar Estilo y Peso (ej: "Estilo Libre-60 kg")
            estilo, peso = llave_key.split("-")
            tab_estilo = None
            
            # 2. Buscar el TAB que corresponde al ESTILO únicamente
            for tab in self.notebook.winfo_children():
                if getattr(tab, "estilo", "") == estilo:
                    tab_estilo = tab
                    break
            
            if tab_estilo:
                # 3. --- CORRECCIÓN CRÍTICA ---
                # Forzamos al combobox de ese estilo a ponerse en el peso de la pelea
                tab_estilo.cmb_peso.set(peso)
                
                # Sincronizamos la memoria interna del tab con el nuevo peso
                self.procesar_y_dibujar(tab_estilo)
                
                # Ahora sí, iniciamos la pelea con el contexto correcto
                self.iniciar_pelea(match_node, tab_estilo, llave_key)

    def abrir_ventana_combate(self, match_node, tab, x_canvas, y_canvas, llave_key):
        p_rojo = self.obtener_peleador_real(match_node["peleador_rojo"])
        p_azul = self.obtener_peleador_real(match_node["peleador_azul"])
        
        self.cerrar_panel_combate() # Limpiar panel previo
        self.canvas_panel_actual = tab.canvas # Guardar referencia del canvas actual
        
        # --- CREAR EL PANEL COMO UN ELEMENTO INTERNO DEL CANVAS ---
        self.panel_combate = tk.Frame(tab.canvas, bg="#2d2d2d", highlightbackground="gray", highlightthickness=1)
        self.id_ventana_canvas = tab.canvas.create_window(x_canvas, y_canvas + 5, window=self.panel_combate, anchor="nw")
        
        # --- ENCABEZADO ---
        top_bar = tk.Frame(self.panel_combate, bg="#1e1e1e")
        top_bar.pack(fill="x")
        ttk.Label(top_bar, text=f"Detalles del Combate (Ronda {match_node['ronda']})", font=("Helvetica", 10, "bold"), background="#1e1e1e", foreground="white").pack(pady=5)
        
        # --- CUERPO DEL PANEL ---
        main_frame = ttk.Frame(self.panel_combate, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        frame_vs = ttk.Frame(main_frame)
        frame_vs.pack(pady=5)
        
        # --- DETECCIÓN DE DESCALIFICACIONES PREVIAS (Fantasmas) ---
        is_rojo_fantasma = p_rojo and p_rojo.get("id") == -1
        is_azul_fantasma = p_azul and p_azul.get("id") == -1
        
        if is_rojo_fantasma and not is_azul_fantasma:
            ttk.Label(frame_vs, text=p_azul['nombre'], foreground="#6666ff", font=("Helvetica", 11, "bold")).pack()
            ttk.Label(frame_vs, text="Avanza por Incomparecencia (Op. Descalificado)", font=("Helvetica", 9, "italic"), foreground="#aaaaaa").pack()
        elif is_azul_fantasma and not is_rojo_fantasma:
            ttk.Label(frame_vs, text=p_rojo['nombre'], foreground="#ff6666", font=("Helvetica", 11, "bold")).pack()
            ttk.Label(frame_vs, text="Avanza por Incomparecencia (Op. Descalificado)", font=("Helvetica", 9, "italic"), foreground="#aaaaaa").pack()
        elif is_rojo_fantasma and is_azul_fantasma:
            ttk.Label(frame_vs, text="Llave Vacante", foreground="#dc3545", font=("Helvetica", 11, "bold")).pack()
            ttk.Label(frame_vs, text="(Ambos oponentes previos descalificados)", font=("Helvetica", 9, "italic"), foreground="#aaaaaa").pack()
        else:
            nom_rojo = p_rojo['nombre'] if p_rojo else "A la espera..."
            nom_azul = p_azul['nombre'] if p_azul else "A la espera..."
            ttk.Label(frame_vs, text=nom_rojo, foreground="#ff6666", font=("Helvetica", 10, "bold")).grid(row=0, column=0, padx=5)
            ttk.Label(frame_vs, text=" VS ", font=("Helvetica", 10, "bold")).grid(row=0, column=1)
            ttk.Label(frame_vs, text=nom_azul, foreground="#6666ff", font=("Helvetica", 10, "bold")).grid(row=0, column=2, padx=5)
        
        # --- ESTADO Y GANADOR ---
        estado = "Finalizado" if match_node.get("ganador") else "Pendiente"
        color_estado = "#28a745" if estado == "Finalizado" else "#ffc107"
        
        ttk.Label(main_frame, text=f"Estado: {estado}", foreground=color_estado, font=("Helvetica", 9, "bold")).pack(pady=(10, 2))
        
        if match_node.get("ganador"):
            ganador = match_node["ganador"]
            motivo = ganador.get("motivo_victoria", "Decisión")
            ganador_id = ganador.get("id")
            
            # --- NUEVO: Adaptación de texto y color si hay ganador o 2DSQ ---
            if ganador_id == -1:
                ttk.Label(main_frame, text="Resultado: Doble Descalificación", foreground="#ff4d4d", font=("Helvetica", 10, "bold")).pack()
            else:
                # Color de letra verde para destacar al ganador real
                ttk.Label(main_frame, text=f"Ganador: {ganador['nombre']}", foreground="#28a745", font=("Helvetica", 10, "bold")).pack()
                
            ttk.Label(main_frame, text=f"Método: {motivo}", foreground="#17a2b8", font=("Helvetica", 9)).pack(pady=(0, 5))
        
        # --- BOTONES DE ACCIÓN ---
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(10, 0))
        
        if match_node.get("ganador") is not None:
            ganador_id = match_node["ganador"].get("id")
            motivo = match_node["ganador"].get("motivo_victoria", "")
            estilo_ext, peso_ext = llave_key.split("-")
            
            # --- NUEVO: Lógica de botones separando pase automático de peleas físicas ---
            if is_rojo_fantasma or is_azul_fantasma:
                # Pase por default (sin combate físico). NO se puede ver PDF ni Editar.
                ttk.Label(btn_frame, text="Avance Automático (Sin Acta de Combate)", foreground="#17a2b8", font=("Helvetica", 9, "bold")).pack(side="left", padx=5)
            else:
                # Hubo combate físico (aunque terminara en DSQ o 2DSQ), así que SÍ se pueden ver los datos
                if ganador_id == -1 or "DSQ" in motivo:
                    # Descalificación: se bloquea la edición, pero sí se puede "Ver Datos"
                    ttk.Label(btn_frame, text="Combate cerrado por Descalificación", foreground="#dc3545", font=("Helvetica", 9, "bold")).pack(side="left", padx=5)
                elif getattr(self, "torneo_cerrado_en_db", False):
                    # Torneo finalizado: se bloquea la edición
                    ttk.Label(btn_frame, text="Torneo Finalizado (Solo Lectura)", foreground="#17a2b8", font=("Helvetica", 9, "italic")).pack(side="left", padx=5)
                else:
                    # Pelea normal activa: se puede editar
                    ttk.Button(btn_frame, text="Editar Pelea", command=lambda: self.editar_pelea(match_node, tab, llave_key)).pack(side="left", padx=5)
                
                # --- BOTÓN DE VER DATOS: Siempre disponible si hubo combate físico ---
                ttk.Button(btn_frame, text="👁 Ver Datos", command=lambda: VentanaPrevisualizacionPDF(self, match_node, estilo_ext, peso_ext)).pack(side="left", padx=5)
                
        elif p_rojo is not None and p_azul is not None:
            if is_rojo_fantasma or is_azul_fantasma:
                ttk.Label(btn_frame, text="Avance Automático Pendiente", font=("Helvetica", 9, "italic")).pack()
            else:
                total_divisiones = sum(len(pesos) for pesos in self.datos.values())
                if len(self.divisiones_bloqueadas) >= total_divisiones:
                    ttk.Button(btn_frame, text="Iniciar Pelea", command=lambda: self.iniciar_pelea(match_node, tab, llave_key)).pack()
                else:
                    lbl_aviso = ttk.Label(btn_frame, text="Bloquee todas las llaves de peso\npara iniciar la competencia", 
                                          foreground="#f39c12", font=("Helvetica", 9, "bold"), justify="center")
                    lbl_aviso.pack()
        else:
            ttk.Label(btn_frame, text="Esperando clasificado...", font=("Helvetica", 9, "italic")).pack()

        # --- EXPANSIÓN DE SCROLL Y AUTO-DESPLAZAMIENTO AJUSTADO ---
        self.panel_combate.update_idletasks() 
        
        bbox = tab.canvas.bbox("all")
        if bbox:
            min_x, min_y, max_x, max_y = bbox[0] - 60, bbox[1] - 60, bbox[2] + 60, bbox[3] + 15
            tab.canvas.config(scrollregion=(min_x, min_y, max_x, max_y))
            
            altura_visible = tab.canvas.winfo_height()
            coord_fondo_panel = y_canvas + 5 + self.panel_combate.winfo_height() + 15 
            coord_fondo_actual = tab.canvas.canvasy(altura_visible)
            
            if coord_fondo_panel > coord_fondo_actual:
                altura_total = max_y - min_y
                nueva_fraccion = (coord_fondo_panel - altura_visible - min_y) / altura_total
                tab.canvas.yview_moveto(nueva_fraccion)

    def cerrar_panel_combate(self):
        """Cierra el panel incrustado, elimina el contenedor del canvas y restaura el scroll."""
        if hasattr(self, "panel_combate") and self.panel_combate.winfo_exists():
            self.panel_combate.destroy()
            
        if hasattr(self, "id_ventana_canvas") and hasattr(self, "canvas_panel_actual"):
            try:
                # 1. Eliminar el "hueco fantasma" del Canvas
                self.canvas_panel_actual.delete(self.id_ventana_canvas)
                self.canvas_panel_actual.update_idletasks()
                
                # 2. Recalcular el tamaño del scroll (ahora sí encogerá)
                bbox = self.canvas_panel_actual.bbox("all")
                if bbox:
                    self.canvas_panel_actual.config(scrollregion=(bbox[0] - 60, bbox[1] - 60, bbox[2] + 60, bbox[3] + 60))
            except Exception:
                pass
            
            # Limpiar referencias
            self.id_ventana_canvas = None
            self.canvas_panel_actual = None

    def iniciar_pelea(self, match_node, tab, llave_key):
        # 1. Verificación local rápida
        tapiz_activo = getattr(self, 'combates_en_curso_red', {}).get(llave_key, {}).get(match_node["match_id"])
        if tapiz_activo:
            return messagebox.showwarning("Bloqueado", f"Este combate ya está activo en: {tapiz_activo}")

        mi_tapiz = getattr(self.controller, 'tapiz_asignado', 'Tapiz X')
        
        # 2. --- NUEVO: Verificación estricta en la Base de Datos ---
        if hasattr(self.db, 'marcar_combate_en_curso'):
            exito = self.db.marcar_combate_en_curso(self.id_torneo, llave_key, match_node["match_id"], mi_tapiz)
            if not exito:
                # Si llegamos tarde por milisegundos, abortamos la apertura de la ventana
                return messagebox.showwarning("Acceso Denegado", "Demasiado tarde. Otro tapiz acaba de abrir este combate.")

        from ui.ventanas.ventana_combate import VentanaCombate 
        self.cerrar_panel_combate() 
            
        p_rojo = self.obtener_peleador_real(match_node["peleador_rojo"])
        p_azul = self.obtener_peleador_real(match_node["peleador_azul"])
        
        def liberar_combate():
            if hasattr(self.db, 'liberar_combate_en_curso'):
                self.db.liberar_combate_en_curso(self.id_torneo, llave_key, match_node["match_id"])

        # --- NUEVO: Callback de latido ---
        def latido_combate():
            if hasattr(self.db, 'mantener_latido_combate'):
                self.db.mantener_latido_combate(self.id_torneo, llave_key, match_node["match_id"])
        
        # Pasamos el callback extra como argumento
        VentanaCombate(self, match_node, p_rojo, p_azul, 
                       lambda m_id, gan, mot, arb, jue, jef, hist, tot: self.asignar_ganador(match_node, gan, mot, tab, llave_key, arb, jue, jef, hist, tot),
                       callback_cancelar=liberar_combate,
                       callback_latido=latido_combate) # <-- Inyectado aquí

    def editar_pelea(self, match_node, tab, llave_key): 
        from ui.ventanas.ventana_editar_pelea import VentanaEditarPelea
        
        self.cerrar_panel_combate() # <-- NUEVO
            
        p_rojo = self.obtener_peleador_real(match_node["peleador_rojo"])
        p_azul = self.obtener_peleador_real(match_node["peleador_azul"])
        VentanaEditarPelea(self, match_node, p_rojo, p_azul, tab, llave_key, self.asignar_ganador)

    def abrir_edicion_desde_cartelera(self, match_node, llave_key):
        tab_objetivo = None
        estilo, peso = llave_key.split("-")
        
        for tab in self.notebook.winfo_children():
            if getattr(tab, "estilo", "") == estilo:
                tab_objetivo = tab
                break
                
        p_rojo = self.obtener_peleador_real(match_node.get('peleador_rojo'))
        p_azul = self.obtener_peleador_real(match_node.get('peleador_azul'))
        
        from ui.ventanas.ventana_editar_pelea import VentanaEditarPelea
        # CORRECCIÓN: Usamos 'self' como parent en lugar de self.winfo_toplevel()
        VentanaEditarPelea(self, match_node, p_rojo, p_azul, tab_objetivo, llave_key, self.asignar_ganador)
        
        if hasattr(self, "panel_flotante") and getattr(self, "panel_flotante"):
            getattr(self, "panel_flotante").destroy()

    def asignar_ganador(self, match_node, ganador, motivo, tab, llave_key, id_arb=None, id_jue=None, id_jef=None, historial=None, totales=None):
        match_id = match_node["match_id"] 

        # Soltar el candado de la base de datos
        if hasattr(self.db, 'liberar_combate_en_curso'):
            self.db.liberar_combate_en_curso(self.id_torneo, llave_key, match_id)

        puntos_rojo = totales['rojo'] if totales else 0
        puntos_azul = totales['azul'] if totales else 0

        p_rojo = self.obtener_peleador_real(match_node["peleador_rojo"])
        p_azul = self.obtener_peleador_real(match_node["peleador_azul"])
        
        if p_rojo and p_azul:
            # Protegemos la Base de Datos: Si el ID es -1, pasamos None (NULL en SQL)
            id_ganador_db = ganador['id'] if ganador['id'] != -1 else None
            
            # --- NUEVO: Capturar el resultado de la BD ---
            exito = self.db.guardar_resultado_combate(
                self.id_torneo, tab.estilo, tab.cmb_peso.get(), 
                match_id, p_rojo['id'], p_azul['id'], id_ganador_db, motivo,
                id_arb, id_jue, id_jef, puntos_rojo, puntos_azul, historial
            )
            
            if not exito:
                messagebox.showerror("Error de Base de Datos", "No se pudo guardar el resultado del combate en el servidor.\n\nEl combate no avanzará.")
                return
        
        # --- NUEVO: RECONSTRUCCIÓN EN CASCADA ---
        # 1. Recargamos la memoria cruda desde la BD
        self.resultados_combates = self.db.cargar_resultados_combates(self.id_torneo)
        
        # 2. Reconstruimos la MATRIZ GLOBAL para que el ganador avance a la siguiente ronda matemáticamente
        self.pre_cargar_memoria() 
        
        # 3. Dibujamos la nueva realidad en el lienzo y actualizamos la cartelera
        self.procesar_y_dibujar(tab)
        self.actualizar_cartelera()
        self.verificar_estado_torneo()

    # --- Funciones de Búsqueda ---
    def buscar_seleccion_en_llave(self):
        sel = self.tree_cartelera.selection()
        if not sel: return
        item_id = sel[0]
        llave_key = self.tree_cartelera.item(item_id, "text")
        match_node = getattr(self.tree_cartelera, f"nodo_{item_id}", None)
        if not match_node: return
        self.navegar_a_match(llave_key, match_node['match_id'])

    def resetear_busqueda_atleta_tab(self, tab, event=None):
        if event and event.keysym in ('Return', 'Up', 'Down', 'Left', 'Right'): return
        tab.resultados_busqueda_atleta = []
        tab.idx_busqueda = -1
        tab.lbl_res_busqueda.config(text="")

    def iniciar_busqueda_atleta_tab(self, tab):
        term = tab.cmb_buscar_atleta.get().strip().lower()
        tab.resultados_busqueda_atleta = []
        tab.idx_busqueda = -1

        if not term:
            tab.lbl_res_busqueda.config(text="")
            return

        canvas = tab.canvas
        
        # Leemos todos los textos impresos en el lienzo actual
        for item in canvas.find_all():
            if canvas.type(item) == "text":
                texto = canvas.itemcget(item, "text").lower()
                if term in texto:
                    coords = canvas.coords(item)
                    if coords:
                        tab.resultados_busqueda_atleta.append(coords[1]) # Guardamos la altura Y

        if tab.resultados_busqueda_atleta:
            # Ordenamos de arriba hacia abajo
            tab.resultados_busqueda_atleta.sort()
            self.ejecutar_busqueda_atleta_tab(tab, 1)
        else:
            tab.lbl_res_busqueda.config(text="0/0")

    def ejecutar_busqueda_atleta_tab(self, tab, direccion):
        if not getattr(tab, "resultados_busqueda_atleta", []):
            self.iniciar_busqueda_atleta_tab(tab)
            return

        tab.idx_busqueda += direccion
        if tab.idx_busqueda >= len(tab.resultados_busqueda_atleta):
            tab.idx_busqueda = 0
        elif tab.idx_busqueda < 0:
            tab.idx_busqueda = len(tab.resultados_busqueda_atleta) - 1

        tab.lbl_res_busqueda.config(text=f"{tab.idx_busqueda + 1}/{len(tab.resultados_busqueda_atleta)}")

        y_target = tab.resultados_busqueda_atleta[tab.idx_busqueda]
        canvas = tab.canvas

        # Ajustar el scroll de Tkinter
        bbox = canvas.bbox("all")
        if bbox:
            total_h = bbox[3] - bbox[1]
            if total_h > 0:
                # El 150 es un offset para que la caja quede en el centro de la pantalla, no pegada arriba
                fraccion = max(0.0, (y_target - 150) / total_h)
                canvas.yview_moveto(fraccion)

        # --- NUEVO: Destello visual tipo escáner anti-spam ---
        # Si ya existe un destello previo en este canvas, lo borramos inmediatamente
        if getattr(canvas, "rect_flash_id", None):
            canvas.delete(canvas.rect_flash_id)
            
        # Creamos el nuevo destello y guardamos su ID en la memoria del canvas
        rect_flash = canvas.create_rectangle(20, max(0, y_target - 40), 1000, y_target + 40, fill="#ffff00", stipple="gray50", outline="red", width=2)
        canvas.rect_flash_id = rect_flash 
        
        def quitar_destello():
            # Solo lo borra si el canvas existe y si el ID actual sigue siendo este (evita que borre uno nuevo por accidente)
            if canvas.winfo_exists() and getattr(canvas, "rect_flash_id", None) == rect_flash:
                canvas.delete(rect_flash)
                canvas.rect_flash_id = None
                
        self.after(1000, quitar_destello)

    def busqueda_en_tiempo_real_tab(self, tab, event):
        """Búsqueda silenciosa mientras el usuario escribe, con autocompletado integrado."""
        # Ignorar flechas direccionales para no estropear la navegación en la lista desplegada
        if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Escape', 'Tab'): return
        
        term = tab.cmb_buscar_atleta.get().strip()
        
        # --- 1. LÓGICA DE AUTOCOMPLETADO DE LA LISTA ---
        if hasattr(tab, 'lista_atletas_original'):
            if not term:
                tab.cmb_buscar_atleta.config(values=tab.lista_atletas_original)
            else:
                # Filtrar ignorando mayúsculas y tildes (usando lower)
                filtrados = [a for a in tab.lista_atletas_original if term.lower() in a.lower()]
                tab.cmb_buscar_atleta.config(values=filtrados)
                
                # Comando interno de Tkinter para forzar el despliegue de la lista visualmente
                try:
                    tab.cmb_buscar_atleta.tk.call('ttk::combobox::Post', tab.cmb_buscar_atleta)
                except Exception:
                    pass
        # -------------------------------------------------
        
        # --- 2. LÓGICA DEL ESCÁNER AMARILLO ---
        if not term:
            self.resetear_busqueda_atleta_tab(tab)
        else:
            self.refrescar_busqueda_silenciosa(tab, term)

    def refrescar_busqueda_silenciosa(self, tab, term):
        """Re-escanea el canvas tras un cambio o mientras se escribe, actualizando contadores."""
        term = term.lower()
        tab.resultados_busqueda_atleta = []
        canvas = tab.canvas
        
        for item in canvas.find_all():
            if canvas.type(item) == "text":
                texto = canvas.itemcget(item, "text").lower()
                if term in texto:
                    coords = canvas.coords(item)
                    if coords:
                        tab.resultados_busqueda_atleta.append(coords[1])

        if tab.resultados_busqueda_atleta:
            tab.resultados_busqueda_atleta.sort()
            
            # Auto-ajuste de índice por si el atleta avanzó de ronda y hay un resultado extra
            if getattr(tab, "idx_busqueda", -1) >= len(tab.resultados_busqueda_atleta):
                tab.idx_busqueda = 0
            elif getattr(tab, "idx_busqueda", -1) < 0:
                tab.idx_busqueda = 0
                
            tab.lbl_res_busqueda.config(text=f"{tab.idx_busqueda + 1}/{len(tab.resultados_busqueda_atleta)}")
            
            # Reposicionar el destello amarillo silenciosamente
            y_target = tab.resultados_busqueda_atleta[tab.idx_busqueda]
            if getattr(canvas, "rect_flash_id", None):
                canvas.delete(canvas.rect_flash_id)
                
            rect_flash = canvas.create_rectangle(20, max(0, y_target - 40), 1000, y_target + 40, fill="#ffff00", stipple="gray50", outline="red", width=2)
            canvas.rect_flash_id = rect_flash 
        else:
            self.resetear_busqueda_atleta_tab(tab) # Llama a la limpieza completa
