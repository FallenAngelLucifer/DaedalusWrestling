import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import math
import os
from conexion_db import ConexionDB

try:
    import fitz  # PyMuPDF
    PDF_DISPONIBLE = True
except ImportError:
    PDF_DISPONIBLE = False

class PantallaPareo(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = ConexionDB()
        self.id_torneo = None
        
        # Estructura: self.datos[Estilo][Peso] = [Atleta1, Atleta2...]
        self.datos = {}
        
        # Variables de control
        self.modo_edicion = True
        self.caja_seleccionada = None
        self.llaves_generadas = {} # Guarda el array de atletas pareados por división
        self.resultados_combates = {} # <-- Guarda ganadores
        
        # Variables para Tooltip
        self.tooltip_window = None
        self.caja_hover_actual = None
        
        lbl_titulo = ttk.Label(self, text="Fase 2: Desarrollo de Pareo (Brackets)", font=("Helvetica", 16, "bold"))
        lbl_titulo.pack(pady=10)

        # Contenedor dinámico (se llenará cuando se cargue un torneo)
        self.contenedor_principal = ttk.Frame(self)
        self.contenedor_principal.pack(fill="both", expand=True)

    def cargar_torneo(self, id_torneo):
        self.id_torneo = id_torneo
        inscripciones = self.db.obtener_inscripciones_pareo(self.id_torneo)
        
        # 1. Limpiar pantalla anterior y diccionarios
        for widget in self.contenedor_principal.winfo_children(): widget.destroy()
        self.datos.clear()
        self.llaves_generadas.clear()
        self.resultados_combates = self.db.cargar_resultados_combates(self.id_torneo)

        # 2. Agrupar datos por Estilo y Peso
        for ins in inscripciones:
            est = ins['estilo']
            peso = f"{ins['peso_cat']} kg"
            if est not in self.datos: self.datos[est] = {}
            if peso not in self.datos[est]: self.datos[est][peso] = []
            
            self.datos[est][peso].append({
                "id": ins['id_peleador'],
                "nombre": f"{ins['apellidos']}, {ins['nombre']}",
                "club": ins['club'] or "Sin Club",
                "ciudad": ins.get('ciudad', 'No especificada')
            })

        # 3. Crear Pestañas Dinámicas (Solo los estilos que tienen atletas)
        self.notebook = ttk.Notebook(self.contenedor_principal)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=10)

        for estilo, pesos_dict in self.datos.items():
            tab = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(tab, text=estilo)
            self.construir_tab_estilo(tab, estilo, pesos_dict)

    def construir_tab_estilo(self, tab, estilo, pesos_dict):
        top_frame = ttk.Frame(tab)
        top_frame.pack(fill="x", pady=5)

        ttk.Label(top_frame, text="División de Peso:").pack(side="left", padx=5)
        
        lista_pesos = list(pesos_dict.keys())
        cmb_peso = ttk.Combobox(top_frame, values=lista_pesos, state="readonly", width=15)
        cmb_peso.pack(side="left", padx=5)
        cmb_peso.set(lista_pesos[0]) # Seleccionar el primero por defecto

        btn_confirmar = ttk.Button(top_frame, text="Confirmar y Bloquear Llave", command=lambda: self.bloquear_llave(estilo, cmb_peso.get()))
        btn_confirmar.pack(side="right", padx=20)

        # Lienzo (Canvas)
        canvas_frame = ttk.Frame(tab)
        canvas_frame.pack(fill="both", expand=True, pady=10)

        scroll_y = ttk.Scrollbar(canvas_frame, orient="vertical")
        scroll_y.pack(side="right", fill="y")
        scroll_x = ttk.Scrollbar(canvas_frame, orient="horizontal")
        scroll_x.pack(side="bottom", fill="x")

        canvas = tk.Canvas(canvas_frame, bg="#1e1e1e", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll_y.config(command=canvas.yview); scroll_x.config(command=canvas.xview)

        # Almacenar en el tab para uso posterior
        tab.canvas = canvas
        tab.estilo = estilo
        tab.cmb_peso = cmb_peso
        
        # Eventos
        cmb_peso.bind("<<ComboboxSelected>>", lambda e: self.procesar_y_dibujar(tab))
        canvas.bind("<Button-1>", lambda e: self.on_canvas_click(e, tab))
        
        # Nuevos Eventos para el Tooltip
        canvas.bind("<Motion>", lambda e: self.on_canvas_motion(e, tab))
        canvas.bind("<Leave>", lambda e: self.ocultar_tooltip())

        # Dibujar la primera llave apenas se carga la pestaña
        self.procesar_y_dibujar(tab)

    # ================= LÓGICA MATEMÁTICA Y DIBUJO =================
    def procesar_y_dibujar(self, tab):
        estilo = tab.estilo
        peso = tab.cmb_peso.get()
        llave_key = f"{estilo}-{peso}"

        if llave_key not in self.llaves_generadas:
            atletas = self.datos[estilo][peso]
            
            # Calcular el tamaño del torneo
            n = len(atletas)
            potencia = 2 ** math.ceil(math.log2(n)) if n > 1 else 1
            
            # --- MAGIA DE BASE DE DATOS: Intentar cargar la llave si ya fue bloqueada ---
            llave_guardada = self.db.cargar_llave_bloqueada(self.id_torneo, estilo, peso, potencia)
            
            if llave_guardada:
                # 1. Ya se bloqueó en el pasado. Se carga idéntica.
                self.llaves_generadas[llave_key] = llave_guardada
                self.modo_edicion = False
                if hasattr(tab, 'btn_confirmar'):
                    tab.btn_confirmar.pack_forget() # Ocultar botón permanentemente
            else:
                # 2. Es nueva. Se usa el algoritmo matemático.
                self.llaves_generadas[llave_key] = self.generar_pareo_optimo(atletas)
                self.modo_edicion = True
                if hasattr(tab, 'btn_confirmar'):
                    tab.btn_confirmar.pack(side="right", padx=20) # Mostrar el botón

        self.dibujar_llave(tab.canvas, self.llaves_generadas[llave_key], llave_key)
        
    def generar_pareo_optimo(self, atletas):
        """Algoritmo Seeding: Separa a los atletas del mismo club lo más lejos posible."""
        n = len(atletas)
        if n == 0: return []
        
        # --- REGLA ESTRICTA: Si es 1 solo atleta, devolvemos la lista de 1 elemento ---
        if n == 1: 
            return [atletas[0]] 
        
        # 1. Determinar tamaño de la llave (Próxima potencia de 2)
        potencia = 2 ** math.ceil(math.log2(n)) 
        
        # 2. Agrupar por club y ordenar de mayor a menor cantidad
        clubes = {}
        for a in atletas: clubes.setdefault(a['club'], []).append(a)
        clubes_ordenados = sorted(clubes.values(), key=len, reverse=True)
        
        # 3. Esparcir alternando para que no queden juntos en la lista inicial
        atletas_esparcidos = []
        while any(clubes_ordenados):
            for club_list in clubes_ordenados:
                if club_list: atletas_esparcidos.append(club_list.pop(0))
                    
        # 4. Generar patrón de siembra
        def generar_semillas(size):
            if size <= 1: return [0]
            if size == 2: return [0, 1]
            mitad = generar_semillas(size // 2)
            return [val for par in zip(mitad, [size - 1 - x for x in mitad]) for val in par]
            
        patron = generar_semillas(potencia)
        
        # 5. Insertar atletas en sus posiciones óptimas, dejando 'Vacío' (Byes)
        llave_final = [None] * potencia
        for i, atleta in enumerate(atletas_esparcidos):
            llave_final[patron[i]] = atleta
            
        return llave_final

    def dibujar_llave(self, canvas, llave_array, llave_key):
        canvas.delete("all")
        canvas.cajas_clickable = [] 
        canvas.combates_clickable = [] 
        canvas.zonas_tooltip = []   

        if not llave_array: return

        competidores_reales = [a for a in llave_array if a is not None]
        if len(competidores_reales) == 1:
            llave_array = [competidores_reales[0]]

        potencia = len(llave_array)
        rondas_totales = int(math.log2(potencia)) if potencia > 1 else 0

        box_w, box_h, x_pad, y_pad = 140, 30, 60, 20
        x_start, y_start = 20, 20

        # Coordenadas y Matriz (Mantenido igual)
        y_pos = []
        r0_y = []
        for i in range(potencia):
            bloque = i // 2
            y_top = y_start + (i * (box_h + y_pad)) + (bloque * y_pad * 1.5)
            r0_y.append(y_top + box_h / 2) 
        y_pos.append(r0_y)

        for r in range(1, rondas_totales + 1):
            prev_y = y_pos[r-1]
            cur_y = []
            for k in range(len(prev_y) // 2):
                cur_y.append((prev_y[2*k] + prev_y[2*k+1]) / 2)
            y_pos.append(cur_y)

        # 2. Construir matriz lógica de la llave
        grid = [list(llave_array)] 

        for r in range(rondas_totales):
            next_r = []
            for k in range(len(grid[r]) // 2):
                left = grid[r][2*k]
                right = grid[r][2*k+1]

                if left is not None and left != "SKIP" and right is not None and right != "SKIP":
                    match_id = f"R{r+1}_M{k}" # <-- CREA UN ID ÚNICO PARA EL COMBATE
                    
                    # Busca en la memoria si este combate ya se jugó y tiene ganador
                    ganador_guardado = self.resultados_combates.get(llave_key, {}).get(match_id)
                    
                    next_r.append({
                        "tipo": "combate",
                        "ronda": r + 1,
                        "match_id": match_id, # <- SE GUARDA AQUÍ
                        "peleador_rojo": left, 
                        "peleador_azul": right, 
                        "ganador": ganador_guardado # <- EL SISTEMA ES INTELIGENTE AHORA
                    })
                elif left is not None and left != "SKIP":
                    grid[r][2*k] = "SKIP" 
                    next_r.append(left)   
                elif right is not None and right != "SKIP":
                    grid[r][2*k+1] = "SKIP"
                    next_r.append(right)
                else:
                    next_r.append(None)
            grid.append(next_r)

        # Dibujar Cajas
        for r in range(rondas_totales + 1):
            for k in range(len(grid[r])):
                node = grid[r][k]
                if node is None or node == "SKIP":
                    continue 

                x = x_start + r * (box_w + x_pad)
                y = y_pos[r][k]

                box_y1 = y - box_h / 2
                box_y2 = y + box_h / 2

                if isinstance(node, dict) and node.get("tipo") == "combate":
                    # === LÓGICA DE COMBATES ===
                    p_rojo = self.obtener_peleador_real(node["peleador_rojo"])
                    p_azul = self.obtener_peleador_real(node["peleador_azul"])
                    ganador = self.obtener_peleador_real(node["ganador"])
                    
                    canvas.create_rectangle(x, box_y1, x + box_w, box_y2, outline="gray", fill="#1e1e1e")
                    
                    if self.modo_edicion:
                        # Si NO está bloqueado, mostramos tooltips sencillos para todo
                        nom_rojo = p_rojo['nombre'] if p_rojo else f"Ganador Ronda {node['ronda']-1}"
                        nom_azul = p_azul['nombre'] if p_azul else f"Ganador Ronda {node['ronda']-1}"
                        texto_combate = f"Combate de Ronda {node['ronda']}\nRojo: {nom_rojo}\nAzul: {nom_azul}\nEstado: Pendiente"
                        canvas.zonas_tooltip.append((x, box_y1, x + box_w, box_y2, texto_combate))
                    else:
                        # Si SÍ está bloqueado
                        if ganador:
                            # 1. Tiene Ganador: Escribe el nombre y hereda el tooltip de Atleta
                            canvas.create_text(x + 10, y, text=ganador['nombre'], fill="white", anchor="w", font=("Helvetica", 9))
                            ciudad = ganador.get('ciudad', 'No especificada')
                            motivo = ganador.get('motivo_victoria', 'No especificado')
                            texto_tooltip = f"Atleta: {ganador['nombre']}\nClub: {ganador['club']}\nCiudad: {ciudad}\nID: {ganador['id']}"
                            canvas.zonas_tooltip.append((x, box_y1, x + box_w, box_y2, texto_tooltip))
                        
                        # 2. Hace clicable SOLO si le precede al menos 1 atleta
                        if p_rojo is not None or p_azul is not None:
                            canvas.combates_clickable.append((x, box_y1, x + box_w, box_y2, node))

                else:
                    # === LÓGICA DE ATLETAS (Ronda 1) ===
                    idx = llave_array.index(node) 
                    color_borde = "yellow" if self.caja_seleccionada == idx else "white"
                    color_fondo = "#4a4a4a" if self.caja_seleccionada == idx else "#1e1e1e"

                    canvas.create_rectangle(x, box_y1, x + box_w, box_y2, outline=color_borde, fill=color_fondo)
                    canvas.create_text(x + 10, y, text=node['nombre'], fill="white", anchor="w", font=("Helvetica", 9))

                    if self.modo_edicion:
                        canvas.cajas_clickable.append((x, box_y1, x + box_w, box_y2, idx))

                    # Tooltip de atleta siempre visible
                    ciudad = node.get('ciudad', 'No especificada')
                    texto_tooltip = f"Atleta: {node['nombre']}\nClub: {node['club']}\nCiudad: {ciudad}\nID: {node['id']}"
                    canvas.zonas_tooltip.append((x, box_y1, x + box_w, box_y2, texto_tooltip))

        # Dibujar Horquillas
        for r in range(rondas_totales):
            for k in range(len(grid[r]) // 2):
                left = grid[r][2*k]
                right = grid[r][2*k+1]

                if left not in (None, "SKIP") and right not in (None, "SKIP"):
                    next_x = x_start + (r+1)*(box_w + x_pad)
                    next_y = y_pos[r+1][k]

                    left_x = x_start + r*(box_w + x_pad) + box_w
                    left_y = y_pos[r][2*k]
                    right_x = left_x
                    right_y = y_pos[r][2*k+1]

                    mid_x = left_x + x_pad / 2

                    canvas.create_line(left_x, left_y, mid_x, left_y, fill="white")
                    canvas.create_line(right_x, right_y, mid_x, right_y, fill="white")
                    canvas.create_line(mid_x, left_y, mid_x, right_y, fill="white")
                    canvas.create_line(mid_x, next_y, next_x, next_y, fill="white")

        canvas.config(scrollregion=canvas.bbox("all"))

    # ================= EVENTOS DE INTERACCIÓN =================
    def on_canvas_click(self, event, tab):
        canvas = tab.canvas
        x, y = canvas.canvasx(event.x), canvas.canvasy(event.y)
        llave_key = f"{tab.estilo}-{tab.cmb_peso.get()}" # <- Necesario aquí
        
        if self.modo_edicion:
            for (x1, y1, x2, y2, idx) in canvas.cajas_clickable:
                if x1 <= x <= x2 and y1 <= y <= y2:
                    if self.caja_seleccionada is None:
                        self.caja_seleccionada = idx 
                    elif self.caja_seleccionada == idx:
                        self.caja_seleccionada = None 
                    else:
                        array = self.llaves_generadas[llave_key]
                        array[self.caja_seleccionada], array[idx] = array[idx], array[self.caja_seleccionada]
                        self.caja_seleccionada = None 
                    
                    self.dibujar_llave(canvas, self.llaves_generadas[llave_key], llave_key)
                    return
        else:
            for (x1, y1, x2, y2, match_node) in getattr(canvas, 'combates_clickable', []):
                if x1 <= x <= x2 and y1 <= y <= y2:
                    x_root = canvas.winfo_rootx() + x1 - canvas.canvasx(0)
                    y_root = canvas.winfo_rooty() + y2 - canvas.canvasy(0)
                    self.abrir_ventana_combate(match_node, tab, x_root, y_root, llave_key)
                    return

    def abrir_ventana_combate(self, match_node, tab, x_root, y_root, llave_key):
        p_rojo = self.obtener_peleador_real(match_node["peleador_rojo"])
        p_azul = self.obtener_peleador_real(match_node["peleador_azul"])
        
        # Destruir un panel anterior si el usuario hace clic en otro lado
        if hasattr(self, "panel_combate") and self.panel_combate.winfo_exists():
            self.panel_combate.destroy()

        # Crear panel flotante sin decoraciones de Windows
        self.panel_combate = tk.Toplevel(self)
        self.panel_combate.wm_overrideredirect(True) 
        self.panel_combate.configure(bg="#2d2d2d", highlightbackground="gray", highlightthickness=1)
        
        # Ubicar exactamente 5 píxeles por debajo de la caja de combate
        self.panel_combate.geometry(f"+{int(x_root)}+{int(y_root + 5)}")
        
        # --- NUEVO ENCABEZADO CON LA "X" CORREGIDA ---
        top_bar = tk.Frame(self.panel_combate, bg="#1e1e1e")
        top_bar.pack(fill="x")
        
        ttk.Label(top_bar, text=f"Detalles del Combate (Ronda {match_node['ronda']})", font=("Helvetica", 10, "bold"), background="#1e1e1e", foreground="white").pack(side="left", padx=10, pady=5)
        
        # La X ahora es un Label interactivo (Evita el glitch visual de los botones en Windows)
        btn_cerrar = tk.Label(top_bar, text="✕", bg="#ff4d4d", fg="white", font=("Helvetica", 11, "bold"), cursor="hand2")
        btn_cerrar.pack(side="right", ipadx=10, fill="y")
        btn_cerrar.bind("<Button-1>", lambda e: self.panel_combate.destroy())
        
        # --- CUERPO DEL PANEL ---
        main_frame = ttk.Frame(self.panel_combate, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        frame_vs = ttk.Frame(main_frame)
        frame_vs.pack(pady=5)
        
        nom_rojo = p_rojo['nombre'] if p_rojo else "A la espera..."
        nom_azul = p_azul['nombre'] if p_azul else "A la espera..."
        
        ttk.Label(frame_vs, text=nom_rojo, foreground="#ff6666", font=("Helvetica", 10, "bold")).grid(row=0, column=0, padx=5)
        ttk.Label(frame_vs, text=" VS ", font=("Helvetica", 10, "bold")).grid(row=0, column=1)
        ttk.Label(frame_vs, text=nom_azul, foreground="#6666ff", font=("Helvetica", 10, "bold")).grid(row=0, column=2, padx=5)
        
        # --- NUEVAS GENERALIDADES (ESTADO Y GANADOR) ---
        estado = "Finalizado" if match_node.get("ganador") else "Pendiente"
        color_estado = "#28a745" if estado == "Finalizado" else "#ffc107"
        
        ttk.Label(main_frame, text=f"Estado: {estado}", foreground=color_estado, font=("Helvetica", 9, "bold")).pack(pady=(10, 2))
        
        if match_node.get("ganador"):
            ganador = match_node["ganador"]
            motivo = ganador.get("motivo_victoria", "Decisión")
            ttk.Label(main_frame, text=f"Ganador: {ganador['nombre']}", foreground="white", font=("Helvetica", 9)).pack()
            ttk.Label(main_frame, text=f"Método: {motivo}", foreground="#17a2b8", font=("Helvetica", 9)).pack(pady=(0, 5))
        
        # --- BOTONES DE ACCIÓN ---
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(10, 0))
        
        if match_node.get("ganador") is not None:
            ttk.Button(btn_frame, text="Editar Pelea", command=lambda: self.editar_pelea(match_node, tab, llave_key)).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="📄 PDF", command=lambda: self.exportar_pdf(match_node, tab)).pack(side="left", padx=5)
        elif p_rojo is not None and p_azul is not None:
            ttk.Button(btn_frame, text="Iniciar Pelea", command=lambda: self.iniciar_pelea(match_node, tab, llave_key)).pack()
        else:
            ttk.Label(btn_frame, text="Esperando clasificado...", font=("Helvetica", 9, "italic")).pack()

    # ================= EXPORTACIÓN A PDF DESDE PAREO =================
    def exportar_pdf(self, match_node, tab):
        if not PDF_DISPONIBLE: return messagebox.showerror("Error", "PyMuPDF no está instalada.")
            
        ruta_plantilla = "hoja_anotacion.pdf" 
        if not os.path.exists(ruta_plantilla): return messagebox.showerror("Error", f"No se encontró '{ruta_plantilla}'.")

        p_rojo = self.obtener_peleador_real(match_node["peleador_rojo"])
        p_azul = self.obtener_peleador_real(match_node["peleador_azul"])
        ganador_data = match_node.get("ganador", {})
        id_combate = ganador_data.get("id_combate")

        if not id_combate:
            return messagebox.showerror("Error", "No se encontró el ID del combate. Verifica que esté guardado en la base de datos.")

        apellido_rojo = p_rojo['nombre'].split(',')[0].replace(' ', '_')
        apellido_azul = p_azul['nombre'].split(',')[0].replace(' ', '_')
        ruta_guardado = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            initialfile=f"Hoja_Puntuacion_R{match_node['ronda']}_{apellido_rojo}_vs_{apellido_azul}.pdf"
        )
        if not ruta_guardado: return

        # 1. Recuperar los datos del Torneo y hora de fin
        torneo_nombre = ""
        torneo_fecha = ""
        hora_fin_combate = "" # <-- Nueva variable
        conexion = self.db.conectar()
        if conexion:
            try:
                with conexion.cursor() as cur:
                    # Añadimos c.hora_fin a la consulta
                    cur.execute("""
                        SELECT t.nombre, to_char(t.fecha_inicio, 'DD/MM/YYYY'), to_char(c.hora_fin, 'HH24:MI')
                        FROM combate c
                        JOIN torneo_division td ON c.id_torneo_division = td.id
                        JOIN torneo t ON td.id_torneo = t.id
                        WHERE c.id = %s
                    """, (id_combate,))
                    res = cur.fetchone()
                    if res:
                        torneo_nombre, torneo_fecha = res[0], res[1]
                        hora_fin_combate = res[2] # <-- Capturamos la hora
            except Exception as e: 
                print("Error consultando datos del torneo:", e)
            finally: 
                conexion.close()

        # 2. Extraer Nombres de Oficiales cruzando el ID con la BD
        oficiales_db = self.db.obtener_oficiales()
        dict_oficiales = {o['id']: f"{o['apellidos']}, {o['nombre']}" for o in oficiales_db}
        nom_arbitro = dict_oficiales.get(ganador_data.get("id_arbitro"), "")
        nom_juez = dict_oficiales.get(ganador_data.get("id_juez"), "")
        nom_jefe = dict_oficiales.get(ganador_data.get("id_jefe_tapiz"), "")

        # 3. Extraer y Calcular Puntos desde la BD
        puntos_historicos = self.db.obtener_puntuacion_combate(id_combate)
        p1_r, p2_r, p1_a, p2_a = 0, 0, 0, 0
        for pt in puntos_historicos:
            val = pt['valor_puntos']
            if pt['color_esquina'] == 'Rojo':
                if pt['periodo'] == 1: p1_r += val
                else: p2_r += val
            else:
                if pt['periodo'] == 1: p1_a += val
                else: p2_a += val
        
        total_r = p1_r + p2_r
        total_a = p1_a + p2_a
        
        nombre_ganador = ganador_data.get("nombre", "")
        motivo_victoria = ganador_data.get("motivo_victoria", "")
        codigo_victoria = motivo_victoria.split(" - ")[0] if motivo_victoria else ""

        # 4. Generación del PDF
        try:
            from datetime import datetime
            #hora_actual = datetime.now().strftime("%H:%M") 

            doc = fitz.open(ruta_plantilla)
            page = doc[0]

            def escribir(texto, x, y, size=10, color=(0, 0, 0)):
                if texto is not None and str(texto).strip() != "":
                    page.insert_text(fitz.Point(x, y), str(texto), fontsize=size, color=color)

            # ================= CALIBRACIÓN MILIMÉTRICA EXACTA =================
            
            # 1. ENCABEZADO SUPERIOR
            escribir(torneo_nombre, 78, 132, size=10) 
            
            escribir(nom_arbitro, 360, 115, size=8) 
            escribir(nom_juez, 360, 138, size=8)    
            escribir(nom_jefe, 360, 160, size=8)  

            # 2. FILA DE INFORMACIÓN DEL COMBATE
            y_info = 203
            escribir(torneo_fecha, 90, y_info, size=9)          
            escribir(f"{match_node['match_id']}", 170, y_info, size=9) 
            escribir(tab.cmb_peso.get(), 240, y_info, size=9)          
            escribir(tab.estilo, 295, y_info, size=9)                  
            escribir(f"{match_node['ronda']}", 375, y_info, size=9) 
            escribir("Fase", 430, y_info, size=9)                           
            escribir("Tapiz A", 495, y_info, size=9)                        

            # 3. NOMBRES DE ATLETAS Y CLUBES 
            y_nombres = 254
            escribir(p_rojo['nombre'], 75, y_nombres, size=8, color=(0, 0, 0))
            escribir(p_rojo['club'], 183, y_nombres, size=7)
            
            escribir(p_azul['nombre'], 322, y_nombres, size=8, color=(0, 0, 0))
            escribir(p_azul['club'], 429, y_nombres, size=7)

            # 4. CUADRÍCULA DE PUNTOS TÉCNICOS POR PERIODO
            x_p1_r, y_p1_r = 110, 292  
            x_p2_r, y_p2_r = 110, 320  
            
            x_p1_a, y_p1_a = 358, 292  
            x_p2_a, y_p2_a = 358, 320  
            
            espaciado = 15 
            ultimo_punto_ganador = None

            for pt in puntos_historicos:
                texto_pt = "P" if pt['tipo_accion'] == 'Penalización' else str(pt['valor_puntos'])
                
                if pt['color_esquina'] == 'Rojo':
                    if pt['periodo'] == 1:
                        escribir(texto_pt, x_p1_r, y_p1_r, color=(0.8, 0, 0), size=10)
                        if p_rojo['nombre'] == nombre_ganador: ultimo_punto_ganador = (x_p1_r, y_p1_r)
                        x_p1_r += espaciado
                    else:
                        escribir(texto_pt, x_p2_r, y_p2_r, color=(0.8, 0, 0), size=10)
                        if p_rojo['nombre'] == nombre_ganador: ultimo_punto_ganador = (x_p2_r, y_p2_r)
                        x_p2_r += espaciado
                else: 
                    if pt['periodo'] == 1:
                        escribir(texto_pt, x_p1_a, y_p1_a, color=(0, 0, 0.8), size=10)
                        if p_azul['nombre'] == nombre_ganador: ultimo_punto_ganador = (x_p1_a, y_p1_a)
                        x_p1_a += espaciado
                    else:
                        escribir(texto_pt, x_p2_a, y_p2_a, color=(0, 0, 0.8), size=10)
                        if p_azul['nombre'] == nombre_ganador: ultimo_punto_ganador = (x_p2_a, y_p2_a)
                        x_p2_a += espaciado

            # 5. TOTALES DESGLOSADOS POR PERIODO 
            escribir(p1_r, 269, y_p1_r, size=11, color=(0.8, 0, 0))
            escribir(p2_r, 269, y_p2_r, size=11, color=(0.8, 0, 0))
            
            escribir(p1_a, 518, y_p1_a, size=11, color=(0, 0, 0.8))
            escribir(p2_a, 518, y_p2_a, size=11, color=(0, 0, 0.8))

            # 6. TOTALES GENERALES DEL COMBATE 
            escribir(total_r, 82, 357, size=16, color=(0.8, 0, 0))
            escribir(total_a, 516, 357, size=16, color=(0, 0, 0.8))

            # 7. PUNTOS DE CLASIFICACIÓN Y TACHAR PERDEDOR
            pts_gan = 0; pts_per = 0
            
            if codigo_victoria in ["VFA", "VIN", "VCA", "DSQ", "VF", "VA", "VB"]: pts_gan = 5
            elif codigo_victoria == "VSU": pts_gan = 4
            elif codigo_victoria == "VSU1": pts_gan = 4; pts_per = 1
            elif codigo_victoria == "VPO": pts_gan = 3
            elif codigo_victoria == "VPO1": pts_gan = 3; pts_per = 1

            if nombre_ganador == p_rojo['nombre']:
                clas_rojo, clas_azul = pts_gan, pts_per
            else:
                clas_rojo, clas_azul = pts_per, pts_gan

            escribir(clas_rojo, 252, 408, size=16, color=(0.8, 0, 0))
            escribir(clas_azul, 346, 408, size=16, color=(0, 0, 0.8))

            # 8. GANADOR Y HORA DE FINALIZACIÓN
            # Si el combate terminó, usamos la hora de la BD. Si no (por algún error), ponemos --:--
            hora_pdf = hora_fin_combate if hora_fin_combate else "--:--" 
            
            escribir(nombre_ganador, 80, 448, size=11)
            escribir(hora_pdf, 448, 448, size=11)

            # 9. CÍRCULO EN EL ÚLTIMO PUNTO (Solo para VFA)
            if ultimo_punto_ganador:
                page.draw_circle(fitz.Point(ultimo_punto_ganador[0] + 3, ultimo_punto_ganador[1] - 3), radius=6, color=(0.1, 0.6, 0.1), width=1.5)
            
            # 10. EL CHECKMARK (✔) EN LA TABLA DE REGLAMENTO
            # --- Variables de calibración rápida ---
            x_base = 85        # Ajusta para mover a la izquierda/derecha
            y_base = 490       # Posición Y del primer elemento (VT / VFA)
            alto_fila = 23     # Distancia en píxeles entre cada fila
            
            # Orden de las opciones de arriba hacia abajo en tu PDF
            orden_victorias = ["VFA", "VAB", "VIN", "VFO", "DSQ", "VCA", "VSU", "VSU1", "VPO1", "VPO"]    
            
            if codigo_victoria in orden_victorias:
                indice = orden_victorias.index(codigo_victoria)
                y_check = y_base + (indice * alto_fila)
                
                # Dibujo del check (✔)
                p1 = fitz.Point(x_base, y_check - 2)
                p2 = fitz.Point(x_base + 5, y_check + 6)
                p3 = fitz.Point(x_base + 15, y_check - 8)
                page.draw_line(p1, p2, color=(0.1, 0.7, 0.1), width=2.5)
                page.draw_line(p2, p3, color=(0.1, 0.7, 0.1), width=2.5)

            doc.save(ruta_guardado)
            doc.close()
            messagebox.showinfo("Éxito", f"Hoja técnica exportada correctamente.")

        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al generar el PDF:\n{str(e)}")

    def iniciar_pelea(self, match_node, tab, llave_key):
        from ventana_combate import VentanaCombate 
        self.panel_combate.destroy() 
        p_rojo = self.obtener_peleador_real(match_node["peleador_rojo"])
        p_azul = self.obtener_peleador_real(match_node["peleador_azul"])
        
        # El callback ahora acepta los árbitros, el historial de puntos y los totales
        VentanaCombate(self, match_node, p_rojo, p_azul, lambda m_id, gan, mot, arb, jue, jef, hist, tot: self.asignar_ganador(match_node, gan, mot, tab, llave_key, arb, jue, jef, hist, tot))

    def editar_pelea(self, match_node, tab, llave_key): 
        from ventana_editar_pelea import VentanaEditarPelea
        self.panel_combate.destroy()
        p_rojo = self.obtener_peleador_real(match_node["peleador_rojo"])
        p_azul = self.obtener_peleador_real(match_node["peleador_azul"])
        VentanaEditarPelea(self, match_node, p_rojo, p_azul, tab, llave_key, self.asignar_ganador)

    def asignar_ganador(self, match_node, ganador, motivo, tab, llave_key, id_arb=None, id_jue=None, id_jef=None, historial=None, totales=None):
        match_id = match_node["match_id"] 
        puntos_rojo = totales['rojo'] if totales else 0
        puntos_azul = totales['azul'] if totales else 0

        if llave_key not in self.resultados_combates:
            self.resultados_combates[llave_key] = {}
        
        ganador_completo = ganador.copy()
        ganador_completo['motivo_victoria'] = motivo
        self.resultados_combates[llave_key][match_id] = ganador_completo
        
        p_rojo = self.obtener_peleador_real(match_node["peleador_rojo"])
        p_azul = self.obtener_peleador_real(match_node["peleador_azul"])
        
        if p_rojo and p_azul:
            self.db.guardar_resultado_combate(
                self.id_torneo, tab.estilo, tab.cmb_peso.get(), 
                match_id, p_rojo['id'], p_azul['id'], ganador['id'], motivo,
                id_arb, id_jue, id_jef, puntos_rojo, puntos_azul, historial
            )
        
        # Recargamos la memoria de victorias para traer los ID's de los árbitros y mostrarlos en edición
        self.resultados_combates = self.db.cargar_resultados_combates(self.id_torneo)
        self.procesar_y_dibujar(tab)

    def bloquear_llave(self, estilo, peso):
        llave_key = f"{estilo}-{peso}"
        array_actual = self.llaves_generadas[llave_key]
        
        respuesta = messagebox.askyesno("Confirmar", f"¿Está seguro de bloquear y confirmar la llave de {estilo} - {peso}? Ya no podrá intercambiar atletas manualmente.")
        if respuesta:
            # --- GUARDAR EN LA BASE DE DATOS AL BLOQUEAR ---
            exito = self.db.bloquear_y_guardar_llave(self.id_torneo, estilo, peso, array_actual)
            
            if exito:
                self.modo_edicion = False
                self.caja_seleccionada = None
                
                # Actualizar la pestaña actual
                for tab in self.notebook.winfo_children():
                    if getattr(tab, "estilo", "") == estilo and tab.cmb_peso.get() == peso:
                        if hasattr(tab, 'btn_confirmar'):
                            tab.btn_confirmar.pack_forget()
                        self.procesar_y_dibujar(tab)
                messagebox.showinfo("Bloqueado", "Llave confirmada y asegurada en la Base de Datos.")
            else:
                messagebox.showerror("Error", "Ocurrió un error al intentar guardar la llave en PostgreSQL.")

    # ================= MÉTODOS PARA EL TOOLTIP =================
    def on_canvas_motion(self, event, tab):
        canvas = tab.canvas
        # Convertir a coordenadas reales del canvas (por si el usuario ha hecho scroll)
        x, y = canvas.canvasx(event.x), canvas.canvasy(event.y)
        
        zona_encontrada = None
        texto_mostrar = ""
        
        # Buscar si el mouse está dentro de alguna de las zonas registradas
        for idx, (x1, y1, x2, y2, texto) in enumerate(canvas.zonas_tooltip):
            if x1 <= x <= x2 and y1 <= y <= y2:
                zona_encontrada = idx
                texto_mostrar = texto
                break

        if zona_encontrada is not None:
            # Solo redibujamos el tooltip si acabamos de entrar a una caja nueva
            if self.caja_hover_actual != zona_encontrada:
                self.caja_hover_actual = zona_encontrada
                # event.x_root da la posición global en la pantalla (necesaria para Toplevel)
                self.mostrar_tooltip(event.x_root, event.y_root, texto_mostrar)
        else:
            # Si el mouse salió de las cajas
            if self.caja_hover_actual is not None:
                self.caja_hover_actual = None
                self.ocultar_tooltip()

    def mostrar_tooltip(self, x, y, texto):
        self.ocultar_tooltip() # Limpiar el anterior por seguridad
        
        self.tooltip_window = tk.Toplevel(self)
        self.tooltip_window.wm_overrideredirect(True) # Quitar barra de título y bordes del SO
        
        # Un pequeño offset para que el mouse no tape el cuadro de texto
        self.tooltip_window.wm_geometry(f"+{x + 15}+{y + 15}")
        
        # Diseño visual del tooltip
        label = ttk.Label(
            self.tooltip_window, 
            text=texto, 
            background="#2d2d2d",   # Fondo oscuro elegante
            foreground="white",     # Letra blanca
            relief="solid", 
            borderwidth=1,
            padding=(8, 5),
            font=("Helvetica", 9)
        )
        label.pack()

    def ocultar_tooltip(self):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    # ================= MÉTODOS PARA PELEADORES =================
    def obtener_peleador_real(self, nodo):
        """Devuelve el diccionario del atleta si está definido, o None si aún es un combate pendiente."""
        if not isinstance(nodo, dict): 
            return None
        # Si el nodo es un combate, el atleta real es el que haya ganado ese combate
        if nodo.get("tipo") == "combate":
            return nodo.get("ganador") 
        # Si no es combate, es el diccionario del atleta directamente
        return nodo
