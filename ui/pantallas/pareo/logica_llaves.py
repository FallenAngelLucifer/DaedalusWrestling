import tkinter as tk
from tkinter import ttk, messagebox
import math
from utils.utilidades import ComboBuscador, aplicar_autocompletado

class LogicaLlavesMixin:
    """Contiene la lógica de creación de matrices, distribución de BYEs, dibujado en el Canvas y tooltips."""

    def pre_cargar_memoria(self):
        """Genera el grid de todas las llaves sin necesidad de visualizarlas."""
        self.divisiones_bloqueadas.clear()
        self.grids_generados.clear()
        
        for estilo, pesos_dict in self.datos.items():
            for peso, atletas in pesos_dict.items():
                llave_key = f"{estilo}-{peso}"
                n = len(atletas)
                potencia = 2 ** math.ceil(math.log2(n)) if n > 1 else 1
                
                # Cargar desde BD
                llave_guardada = self.db.cargar_llave_bloqueada(self.id_torneo, estilo, peso, potencia)
                if llave_guardada:
                    self.llaves_generadas[llave_key] = llave_guardada
                    self.divisiones_bloqueadas.add(llave_key)
                else:
                    self.llaves_generadas[llave_key] = self.generar_pareo_optimo(atletas)
                    
                # Construir el grid lógico (necesario para el reporte y cartelera)
                llave_array = self.llaves_generadas[llave_key]
                potencia_grid = len(llave_array)
                rondas_totales = int(math.log2(potencia_grid)) if potencia_grid > 1 else 0
                grid = [list(llave_array)] 

                for r in range(rondas_totales):
                    next_r = []
                    for k in range(len(grid[r]) // 2):
                        left, right = grid[r][2*k], grid[r][2*k+1]
                        if left not in (None, "SKIP") and right not in (None, "SKIP"):
                            match_id = f"R{r+1}_M{k}"
                            ganador = self.resultados_combates.get(llave_key, {}).get(match_id)
                            
                            # --- AUTO-AVANCE DE VICTORIAS POR DESCALIFICACIÓN ---
                            p_rojo = self.obtener_peleador_real(left)
                            p_azul = self.obtener_peleador_real(right)
                            
                            if not ganador and p_rojo and p_azul:
                                if p_rojo.get("id") == -1 and p_azul.get("id") != -1:
                                    ganador = p_azul.copy(); ganador["motivo_victoria"] = "VFO - Op. Descalificado"
                                elif p_azul.get("id") == -1 and p_rojo.get("id") != -1:
                                    ganador = p_rojo.copy(); ganador["motivo_victoria"] = "VFO - Op. Descalificado"
                                elif p_rojo.get("id") == -1 and p_azul.get("id") == -1:
                                    ganador = {"id": -1, "nombre": "Doble Descalificación", "club": "---", "ciudad": "---", "motivo_victoria": "2DSQ"}

                            next_r.append({
                                "tipo": "combate", "ronda": r + 1, "match_id": match_id, 
                                "ganador": ganador, "peleador_rojo": left, "peleador_azul": right
                            })
                        else:
                            next_r.append(left if left not in (None, "SKIP") else right if right not in (None, "SKIP") else None)
                    grid.append(next_r)

                # ---> CORRECCIÓN VITAL AQUÍ: Guardar la matriz calculada en la memoria global <---
                self.grids_generados[llave_key] = grid

    def construir_tab_estilo(self, tab, estilo, pesos_dict):
        top_frame = ttk.Frame(tab)
        top_frame.pack(fill="x", pady=5)

        ttk.Label(top_frame, text="División de Peso:").pack(side="left", padx=5)
        
        lista_pesos = sorted(list(pesos_dict.keys()), key=lambda x: float(x.lower().replace("kg", "").replace(" ", "").strip()))
        
        cmb_peso = ComboBuscador(top_frame, values=lista_pesos, state="readonly", width=15)
        cmb_peso.pack(side="left", padx=5)
        cmb_peso.set(lista_pesos[0])

        # ================= NUEVO: BUSCADOR INTERNO =================
        ttk.Separator(top_frame, orient="vertical").pack(side="left", fill="y", padx=15)
        ttk.Label(top_frame, text="🔍 Buscar Atleta:").pack(side="left", padx=5)

        # La lista nace vacía. Se llenará dinámicamente con los de esta categoría.
        tab.cmb_buscar_atleta = ComboBuscador(top_frame, values=[], width=25)
        tab.cmb_buscar_atleta.pack(side="left", padx=5)

        tab.btn_busq_arriba = ttk.Button(top_frame, text="▲", width=3, command=lambda: self.ejecutar_busqueda_atleta_tab(tab, -1))
        tab.btn_busq_arriba.pack(side="left", padx=1)
        tab.btn_busq_abajo = ttk.Button(top_frame, text="▼", width=3, command=lambda: self.ejecutar_busqueda_atleta_tab(tab, 1))
        tab.btn_busq_abajo.pack(side="left", padx=1)

        tab.lbl_res_busqueda = ttk.Label(top_frame, text="", width=5, foreground="#17a2b8", font=("Helvetica", 9, "bold"))
        tab.lbl_res_busqueda.pack(side="left", padx=5)

        tab.resultados_busqueda_atleta = []
        tab.idx_busqueda = -1

        # Eventos Inteligentes
        tab.cmb_buscar_atleta.bind("<<ComboboxSelected>>", lambda e: self.iniciar_busqueda_atleta_tab(tab))
        tab.cmb_buscar_atleta.bind("<Return>", lambda e: self.iniciar_busqueda_atleta_tab(tab))
        # ==========================================================

        # --- BOTONES DE LA PESTAÑA ---
        # (Asegúrate de dejarlos tal cual, ya que se empacan con side="right" dinámicamente luego)
        tab.btn_img = ttk.Button(top_frame, text="📸 Exportar Llave (PNG)", command=lambda t=tab: self.exportar_imagen_llave(t))
        tab.btn_confirmar = ttk.Button(top_frame, text="Confirmar Llave", command=lambda: self.bloquear_llave(estilo, cmb_peso.get()))
        tab.btn_confirmar_todas = ttk.Button(top_frame, text="✅ Confirmar Todas las Llaves", command=self.confirmar_todas_las_llaves)

        tab.lbl_estado_categoria = ttk.Label(top_frame, text="", font=("Helvetica", 9, "bold"))

        # ================= ¡AQUÍ ESTABA EL BLOQUE PERDIDO! =================
        # Lienzo (Canvas) y sus barras de desplazamiento clásicas
        canvas_frame = ttk.Frame(tab)
        canvas_frame.pack(fill="both", expand=True, pady=10)

        scroll_y = ttk.Scrollbar(canvas_frame, orient="vertical")
        scroll_y.pack(side="right", fill="y")
        scroll_x = ttk.Scrollbar(canvas_frame, orient="horizontal")
        scroll_x.pack(side="bottom", fill="x")

        canvas = tk.Canvas(canvas_frame, bg="#1e1e1e", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll_y.config(command=canvas.yview); scroll_x.config(command=canvas.xview)
        # ===================================================================

        # Almacenar en el tab para uso posterior
        tab.canvas = canvas
        tab.estilo = estilo
        tab.cmb_peso = cmb_peso
        
        # --- FUNCIONES DE SCROLL CON RUEDA DEL RATÓN ---
        def on_mousewheel_y(event):
            # Soporte cruzado: Windows/MacOS usan event.delta, Linux usa num 4 y 5
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif event.num == 4: canvas.yview_scroll(-1, "units")
            elif event.num == 5: canvas.yview_scroll(1, "units")

        def on_mousewheel_x(event):
            if event.delta:
                canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
            elif event.num == 4: canvas.xview_scroll(-1, "units")
            elif event.num == 5: canvas.xview_scroll(1, "units")

        # TRUCO TKINTER: El canvas necesita tener el "foco" para escuchar la rueda del ratón.
        canvas.bind("<Enter>", lambda e: canvas.focus_set())
        
        # Asignar Scroll Vertical (Rueda normal)
        canvas.bind("<MouseWheel>", on_mousewheel_y)
        canvas.bind("<Button-4>", on_mousewheel_y) # Soporte Linux
        canvas.bind("<Button-5>", on_mousewheel_y) # Soporte Linux

        # Asignar Scroll Horizontal (Manteniendo Shift + Rueda)
        canvas.bind("<Shift-MouseWheel>", on_mousewheel_x)
        canvas.bind("<Shift-Button-4>", on_mousewheel_x) 
        canvas.bind("<Shift-Button-5>", on_mousewheel_x) 
        
        # Eventos Originales
        cmb_peso.bind("<<ComboboxSelected>>", lambda e: self.procesar_y_dibujar(tab))
        canvas.bind("<Button-1>", lambda e: self.on_canvas_click(e, tab))
        
        # Eventos para el Tooltip
        canvas.bind("<Motion>", lambda e: self.on_canvas_motion(e, tab))
        # Al salir, quitamos el tooltip y soltamos el foco para no interferir con otras ventanas
        canvas.bind("<Leave>", lambda e: [self.ocultar_tooltip(), self.focus_set()])

        # Dibujar la primera llave apenas se carga la pestaña
        self.procesar_y_dibujar(tab)

    def procesar_y_dibujar(self, tab):
        estilo = tab.estilo
        peso = tab.cmb_peso.get()
        llave_key = f"{estilo}-{peso}"

        total_divs = sum(len(p) for p in self.datos.values())
        todas_bloqueadas = (len(self.divisiones_bloqueadas) >= total_divs) and (total_divs > 0)

        # 1. Ocultar todos los botones primero para limpiar la interfaz
        if hasattr(tab, 'btn_img'): tab.btn_img.pack_forget()
        if hasattr(tab, 'btn_confirmar'): tab.btn_confirmar.pack_forget()
        if hasattr(tab, 'btn_confirmar_todas'): tab.btn_confirmar_todas.pack_forget()
        if hasattr(tab, 'lbl_estado_categoria'): tab.lbl_estado_categoria.pack_forget()

        # 2. DEFINIR EL MODO DE EDICIÓN (¡CRÍTICO! Debe ser antes de dibujar)
        if todas_bloqueadas or llave_key in self.divisiones_bloqueadas:
            self.modo_edicion = False
        else:
            self.modo_edicion = True

        # 3. DIBUJAR LA LLAVE (Ahora sí usará el modo correcto desde el inicio)
        self.dibujar_llave(tab.canvas, self.llaves_generadas[llave_key], llave_key)

        # 4. MOSTRAR BOTONES Y ETIQUETAS SEGÚN EL ESTADO
        if todas_bloqueadas:
            # Torneo completo: Solo aparece exportar imagen
            if hasattr(tab, 'btn_img'): tab.btn_img.pack(side="right", padx=10)

            # --- LÓGICA DE ETIQUETA LOCAL ---
            grid = self.grids_generados.get(llave_key, [])
            total_cat = 0
            completadas_cat = 0
            
            # Contar peleas en la matriz de esta pestaña específica
            for r in grid:
                for node in r:
                    if isinstance(node, dict) and node.get("tipo") == "combate":
                        total_cat += 1
                        if node.get("ganador"):
                            completadas_cat += 1
            
            faltan_cat = total_cat - completadas_cat
            
            if total_cat == 0:
                texto_lbl = "Sin combates"
                color_lbl = "gray"
            elif faltan_cat == 0:
                texto_lbl = f"Peleas Totales: {total_cat}  |  Categoría Finalizada"
                color_lbl = "#28a745" # Verde
            else:
                texto_lbl = f"Peleas: {total_cat}  |  Completadas: {completadas_cat}  |  Faltantes: {faltan_cat}"
                color_lbl = "#17a2b8" # Azul

            if hasattr(tab, 'lbl_estado_categoria'):
                tab.lbl_estado_categoria.config(text=texto_lbl, foreground=color_lbl)
                tab.lbl_estado_categoria.pack(side="right", padx=10)

        else:
            if llave_key in self.divisiones_bloqueadas:
                # Llave confirmada: Solo aparece confirmar todas a la derecha
                if hasattr(tab, 'btn_confirmar_todas'): tab.btn_confirmar_todas.pack(side="right", padx=10)
            else:
                # Llave abierta: Aparece confirmar a la derecha, y a su izquierda confirmar todas
                if hasattr(tab, 'btn_confirmar'): tab.btn_confirmar.pack(side="right", padx=10)
                if hasattr(tab, 'btn_confirmar_todas'): tab.btn_confirmar_todas.pack(side="right", padx=5)

        self.gestionar_botones_globales()

        # --- NUEVO: 5. ACTUALIZAR LISTA DE LA COMBOBOX ---
        if hasattr(tab, 'cmb_buscar_atleta'):
            atletas_en_llave = []
            
            # Solución: Leemos la matriz original de inscritos, ignorando los "SKIP" visuales
            atletas_categoria = self.datos.get(tab.estilo, {}).get(tab.cmb_peso.get(), [])
            for a in atletas_categoria:
                if isinstance(a, dict) and "nombre" in a:
                    atletas_en_llave.append(a['nombre'])
            
            lista_final = sorted(list(set(atletas_en_llave)))
            tab.cmb_buscar_atleta.config(values=lista_final)
            
            # --- LA MAGIA: Aplicamos tu función nativa de autocompletado ---
            aplicar_autocompletado(tab.cmb_buscar_atleta, lista_final)
            
            # Auto-rastreo silencioso si la pelea termina y el atleta avanza de ronda
            term = tab.cmb_buscar_atleta.get().strip()
            if term and term in lista_final:
                # Usamos silenciosa para que no te robe la cámara si estás viendo otra pelea
                self.refrescar_busqueda_silenciosa(tab, term)
        
    def generar_pareo_optimo(self, atletas):
        """Algoritmo Seeding UWW: Separa clubes y distribuye Byes simétricamente."""
        n = len(atletas)
        if n == 0: return []
        if n == 1: return [atletas[0]] 
        
        # 1. Determinar tamaño del bracket
        potencia = 2 ** math.ceil(math.log2(n)) 
        
        # 2. Separación de Clubes
        clubes = {}
        for a in atletas: clubes.setdefault(a['club'], []).append(a)
        clubes_ordenados = sorted(clubes.values(), key=len, reverse=True)
        
        atletas_esparcidos = []
        while any(clubes_ordenados):
            for club_list in clubes_ordenados:
                if club_list: atletas_esparcidos.append(club_list.pop(0))
                    
        # --- 3. DISTRIBUCIÓN SIMÉTRICA DE BYES (REGLA UWW) ---
        byes = potencia - n
        llave_final = [None] * potencia
        
        # Índices impares corresponden a los oponentes. Si está vacío, es un Bye.
        indices_impares = [i for i in range(1, potencia, 2)]
        
        # Repartir Byes equitativamente arriba y abajo
        byes_top = math.ceil(byes / 2)
        byes_bottom = byes - byes_top
        
        posiciones_byes = set()
        
        # Colocar Byes en la parte superior (bajando)
        for i in range(byes_top):
            posiciones_byes.add(indices_impares[i])
            
        # Colocar Byes en la parte inferior (subiendo)
        for i in range(byes_bottom):
            posiciones_byes.add(indices_impares[-(i+1)])
        
        # 4. Las posiciones disponibles son todas las que NO fueron marcadas como byes
        posiciones_disponibles = [i for i in range(potencia) if i not in posiciones_byes]
        
        # --- NUEVO: DISTRIBUCIÓN EN EXTREMOS OPUESTOS (Siembra Oficial) ---
        # Alternamos: uno arriba, uno abajo, uno arriba, uno abajo...
        # Esto garantiza que atletas del mismo club queden en llaves diferentes (se topan hasta la final)
        posiciones_extremas = []
        izq = 0
        der = len(posiciones_disponibles) - 1
        
        while izq <= der:
            posiciones_extremas.append(posiciones_disponibles[izq])
            if izq != der:
                posiciones_extremas.append(posiciones_disponibles[der])
            izq += 1
            der -= 1

        # Insertar a los atletas usando el nuevo orden de extremos
        for i, atleta in enumerate(atletas_esparcidos):
            llave_final[posiciones_extremas[i]] = atleta
            
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

        box_w, box_h, x_pad, y_pad = 155, 40, 60, 20 
        x_start, y_start = 60, 60

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
                    match_id = f"R{r+1}_M{k}" 
                    ganador_guardado = self.resultados_combates.get(llave_key, {}).get(match_id)
                    
                    # --- AUTO-AVANCE VISUAL ---
                    p_rojo = self.obtener_peleador_real(left)
                    p_azul = self.obtener_peleador_real(right)
                    
                    if not ganador_guardado and p_rojo and p_azul:
                        if p_rojo.get("id") == -1 and p_azul.get("id") != -1:
                            ganador_guardado = p_azul.copy(); ganador_guardado["motivo_victoria"] = "VFO - Op. Descalificado"
                        elif p_azul.get("id") == -1 and p_rojo.get("id") != -1:
                            ganador_guardado = p_rojo.copy(); ganador_guardado["motivo_victoria"] = "VFO - Op. Descalificado"
                        elif p_rojo.get("id") == -1 and p_azul.get("id") == -1:
                            ganador_guardado = {"id": -1, "nombre": "Doble Descalificación", "club": "---", "ciudad": "---", "motivo_victoria": "2DSQ"}
                    
                    next_r.append({
                        "tipo": "combate", "ronda": r + 1, "match_id": match_id, 
                        "peleador_rojo": left, "peleador_azul": right, "ganador": ganador_guardado
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

        self.grids_generados[llave_key] = grid

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
                    
                    # --- BLOQUEO MULTI-TAPIZ ---
                    tapiz_activo = getattr(self, 'combates_en_curso_red', {}).get(llave_key, {}).get(node.get("match_id"))
                    color_borde = "#ffc107" if (tapiz_activo and not ganador) else "gray"
                    
                    canvas.create_rectangle(x, box_y1, x + box_w, box_y2, outline=color_borde, fill="#1e1e1e", width=2 if tapiz_activo else 1)
                    
                    if tapiz_activo and not ganador:
                        canvas.create_text(x + box_w/2, y,text=f"En curso: {tapiz_activo}", fill="#ffc107", font=("Helvetica", 7, "bold"))
                    
                    if self.modo_edicion:
                        nom_rojo = p_rojo['nombre'] if p_rojo else f"Ganador Ronda {node['ronda']-1}"
                        nom_azul = p_azul['nombre'] if p_azul else f"Ganador Ronda {node['ronda']-1}"
                        texto_combate = f"Combate de Ronda {node['ronda']}\nRojo: {nom_rojo}\nAzul: {nom_azul}\nEstado: Pendiente"
                        canvas.zonas_tooltip.append((x, box_y1, x + box_w, box_y2, texto_combate))
                    else:
                        if ganador:
                            color_texto = "#ff4d4d" if ganador['id'] == -1 else "white"
                            if ganador['id'] == -1:
                                canvas.create_text(x + 10, y, text="Doble Descalificación", fill=color_texto, anchor="w", font=("Helvetica", 9, "bold"))
                            else:
                                canvas.create_text(x + 10, y - 7, text=ganador['nombre'], fill=color_texto, anchor="w", font=("Helvetica", 9, "bold"))
                                canvas.create_text(x + 10, y + 8, text=ganador.get('club', 'Sin Club'), fill="#aaaaaa", anchor="w", font=("Helvetica", 7))
                            
                            ciudad = ganador.get('ciudad', 'No especificada')
                            texto_tooltip = f"Atleta: {ganador['nombre']}\nClub: {ganador.get('club', '')}\nCiudad: {ciudad}\nID: {ganador['id']}"
                            canvas.zonas_tooltip.append((x, box_y1, x + box_w, box_y2, texto_tooltip))
                        
                        # Si NO está bloqueado por la red, permitir que sea clicable
                        if not tapiz_activo or ganador:
                            if p_rojo is not None or p_azul is not None:
                                canvas.combates_clickable.append((x, box_y1, x + box_w, box_y2, node))
                else:
                    # === LÓGICA DE ATLETAS (Ronda 1) ===
                    idx = llave_array.index(node) 
                    color_borde = "yellow" if self.caja_seleccionada == idx else "white"
                    color_fondo = "#4a4a4a" if self.caja_seleccionada == idx else "#1e1e1e"

                    # --- Dentro del bucle de "Dibujar Cajas" -> Lógica de Atletas ---
                    canvas.create_rectangle(x, box_y1, x + box_w, box_y2, outline=color_borde, fill=color_fondo)

                    # NUEVO: Indicador de esquina (Rojo para el superior del par, Azul para el inferior)
                    color_esquina = "#ff4d4d" if k % 2 == 0 else "#4d4dff"
                    canvas.create_rectangle(x, box_y1, x + 5, box_y2, fill=color_esquina, outline="") 

                    # --- NUEVO: Nombre en negrita y club en gris ---
                    canvas.create_text(x + 10, y - 7, text=node['nombre'], fill="white", anchor="w", font=("Helvetica", 9, "bold"))
                    canvas.create_text(x + 10, y + 8, text=node.get('club', 'Sin Club'), fill="#aaaaaa", anchor="w", font=("Helvetica", 7))

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

                    # --- Dentro del bucle de "Dibujar Horquillas" ---
                    mid_x = left_x + x_pad / 2

                    # Línea superior (Esquina Roja) con grosor aumentado para visibilidad
                    canvas.create_line(left_x, left_y, mid_x, left_y, fill="#ff4d4d", width=2)
                    canvas.create_line(mid_x, left_y, mid_x, next_y, fill="#ff4d4d", width=2)

                    # Línea inferior (Esquina Azul)
                    canvas.create_line(right_x, right_y, mid_x, right_y, fill="#4d4dff", width=2)
                    canvas.create_line(mid_x, right_y, mid_x, next_y, fill="#4d4dff", width=2)

                    # Línea de salida hacia la siguiente ronda
                    canvas.create_line(mid_x, next_y, next_x, next_y, fill="white", width=2)

        # --- CAMBIO: Margen interno dinámico simétrico ---
        bbox = canvas.bbox("all")
        if bbox:
            # Agregamos 60px exactos de margen en las 4 direcciones (Izquierda, Arriba, Derecha, Abajo)
            min_x, min_y, max_x, max_y = bbox[0] - 60, bbox[1] - 60, bbox[2] + 60, bbox[3] + 60
            canvas.config(scrollregion=(min_x, min_y, max_x, max_y))

    def on_canvas_click(self, event, tab):
        canvas = tab.canvas
        x, y = canvas.canvasx(event.x), canvas.canvasy(event.y)
        llave_key = f"{tab.estilo}-{tab.cmb_peso.get()}" 
        
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
            clic_en_combate = False
            for (x1, y1, x2, y2, match_node) in getattr(canvas, 'combates_clickable', []):
                if x1 <= x <= x2 and y1 <= y <= y2:
                    # --- CAMBIO: Pasamos las coordenadas x1 y y2 del Canvas directamente ---
                    self.abrir_ventana_combate(match_node, tab, x1, y2, llave_key)
                    clic_en_combate = True
                    break
            
            # Si hizo clic en un espacio vacío del canvas, se cierra el panel
            if not clic_en_combate:
                self.cerrar_panel_combate() # <-- NUEVO (Y borra todo lo que habías puesto del scroll aquí)

    def bloquear_llave(self, estilo, peso, mostrar_msg=True): # <-- Añadir mostrar_msg
        llave_key = f"{estilo}-{peso}"
        array_actual = self.llaves_generadas[llave_key]
        
        # Solo preguntamos si no es una confirmación masiva
        respuesta = True
        if mostrar_msg:
            respuesta = messagebox.askyesno("Confirmar", f"¿Está seguro de bloquear y confirmar la llave de {estilo} - {peso}? Ya no podrá intercambiar atletas manualmente.")
            
        if respuesta:
            exito = self.db.bloquear_y_guardar_llave(self.id_torneo, estilo, peso, array_actual)
            
            if exito:
                self.divisiones_bloqueadas.add(llave_key)
                self.modo_edicion = False
                self.caja_seleccionada = None
            
                for tab in self.notebook.winfo_children():
                    if getattr(tab, "estilo", "") == estilo:
                        self.procesar_y_dibujar(tab)
            
                if mostrar_msg:
                    messagebox.showinfo("Bloqueado", "Llave confirmada y asegurada.")
                    # --- NUEVO: Refrescar la cartelera al confirmar llave individual ---
                    self.actualizar_cartelera()
                    
                self.verificar_estado_torneo()
                
                # --- CORRECCIÓN: Evaluar visibilidad de exportaciones ---
                self.gestionar_botones_globales()
            else:
                if mostrar_msg:
                    messagebox.showerror("Error", "Error al guardar en la base de datos.")

    def confirmar_todas_las_llaves(self):
        """Bloquea todas las divisiones del torneo de un solo golpe."""
        if not self.datos: return
        confirmado = messagebox.askyesno("Confirmación Masiva", "¿Desea confirmar y bloquear TODAS las llaves del torneo?")
        if confirmado:
            for estilo, pesos in self.datos.items():
                for peso in pesos.keys():
                    # Llamamos a tu lógica de bloqueo (pasar mostrar_msg=False para evitar spam de alertas)
                    self.bloquear_llave(estilo, peso, mostrar_msg=False)
            messagebox.showinfo("Éxito", "Todas las llaves han sido bloqueadas.")

            # Refrescar la vista actual para reordenar botones de las pestañas
            for tab in self.notebook.winfo_children():
                if hasattr(tab, "cmb_peso"):
                    self.procesar_y_dibujar(tab)

            self.gestionar_botones_globales()
            
            # ---> NUEVO: Forzamos la reconstrucción de la memoria antes de dibujar <---
            self.pre_cargar_memoria()
            self.actualizar_cartelera()

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

    def obtener_peleador_real(self, nodo):
        """Devuelve el diccionario del atleta si está definido, o None si aún es un combate pendiente."""
        if not isinstance(nodo, dict): 
            return None
        # Si el nodo es un combate, el atleta real es el que haya ganado ese combate
        if nodo.get("tipo") == "combate":
            return nodo.get("ganador") 
        # Si no es combate, es el diccionario del atleta directamente
        return nodo
