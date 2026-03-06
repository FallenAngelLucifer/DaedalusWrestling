import tkinter as tk
from tkinter import ttk, messagebox
from database.conexion_db import ConexionDB
from utils.utilidades import aplicar_autocompletado, ComboBuscador

class VentanaEditarPelea(tk.Toplevel):
    def __init__(self, parent, match_node, p_rojo, p_azul, tab, llave_key, callback_actualizar):
        super().__init__(parent)
        self.match_node = match_node
        self.p_rojo = p_rojo
        self.p_azul = p_azul
        self.tab = tab
        self.llave_key = llave_key
        self.callback_actualizar = callback_actualizar
        self.db = ConexionDB()
        
        self.title("BOLETÍN DE PUNTUACIÓN - UWW")
        
        # --- CENTRAR VENTANA ---
        ancho, alto = 550, 500
        x = (self.winfo_screenwidth() // 2) - (ancho // 2)
        y = (self.winfo_screenheight() // 2) - (alto // 2)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")

        self.transient(parent)
        self.grab_set()

        # --- NUEVO: FILTRO Y CARGA DE ÁRBITROS ---
        oficiales_todos = self.db.obtener_oficiales()
        ganador_data = self.match_node.get("ganador", {})
        
        self.id_arb_orig = ganador_data.get("id_arbitro")
        self.id_jue_orig = ganador_data.get("id_juez")
        self.id_jefe_orig = ganador_data.get("id_jefe_tapiz")
        
        # Identificar quién es el Jefe de Tapiz original (Intocable)
        oficial_jefe = next((o for o in oficiales_todos if o['id'] == self.id_jefe_orig), None)
        self.nombre_jefe_tapiz = f"{oficial_jefe['apellidos']}, {oficial_jefe['nombre']}" if oficial_jefe else "Desconocido"

        # Buscar ocupados en la red
        id_torneo = getattr(parent, 'id_torneo', None) or getattr(parent.controller, 'torneo_debug_id', None)
        oficiales_ocupados = set()
        if id_torneo:
            conexiones = self.db.obtener_conexiones_torneo(id_torneo)
            for c in conexiones:
                if c.get('id_oficial'):
                    oficiales_ocupados.add(c['id_oficial'])

        # Filtrar: Mostrar solo los disponibles + los que ya estaban asignados a este combate
        self.oficiales_db = []
        for o in oficiales_todos:
            if o['id'] not in oficiales_ocupados or o['id'] in (self.id_arb_orig, self.id_jue_orig):
                self.oficiales_db.append(o)

        self.nombres_oficiales = [f"{o['apellidos']}, {o['nombre']}" for o in self.oficiales_db]
        
        self.tipos_victoria = [
            "VFA - Victoria por Toque (Fall)",
            "VAB - Victoria por Abandono",
            "VIN - Victoria por Lesión",
            "VFO - Victoria por Forfeit (Incomparecencia)",
            "DSQ - Descalificación por mala conducta",
            "VCA - Victoria por Amonestaciones (3 cautions)",
            "VSU - Superioridad Técnica (sin puntos del perdedor)",
            "VSU1 - Superioridad Técnica (con puntos del perdedor)",
            "VPO1 - Victoria por Puntos (con puntos del perdedor)",
            "VPO - Victoria por Puntos (sin puntos del perdedor)"
        ]

        # --- EXTRACCIÓN Y CÁLCULO DE PUNTOS DESDE LA BD ---
        self.id_combate = self.match_node.get("ganador", {}).get("id_combate")
        self.p1_r, self.p2_r, self.p1_a, self.p2_a = 0, 0, 0, 0
        self.puntos_historicos = [] 
        
        if self.id_combate:
            self.puntos_historicos = self.db.obtener_puntuacion_combate(self.id_combate)
            for pt in self.puntos_historicos:
                val = pt['valor_puntos']
                if pt['color_esquina'] == 'Rojo':
                    if pt['periodo'] == 1: self.p1_r += val
                    else: self.p2_r += val
                else:
                    if pt['periodo'] == 1: self.p1_a += val
                    else: self.p2_a += val
        
        self.total_r = self.p1_r + self.p2_r
        self.total_a = self.p1_a + self.p2_a

        self.crear_interfaz()

    def crear_interfaz(self):
        # --- NUEVO: MOSTRAR TAPIZ EN LA CABECERA ---
        tapiz_str = self.match_node.get("tapiz", "No Registrado")
        tk.Label(self, text=f"HOJA DE PUNTUACIÓN OFICIAL - {tapiz_str.upper()}", font=("Helvetica", 14, "bold"), bg="#2a2a2a", fg="white").pack(fill="x")

        # --- SECCIÓN: CUERPO ARBITRAL ---
        frame_arbitros = ttk.LabelFrame(self, text="Oficiales de Arbitraje (Asignados en el Tapiz)", padding=10)
        frame_arbitros.pack(fill="x", padx=15, pady=10)

        ttk.Label(frame_arbitros, text="Referee / Árbitro:").grid(row=0, column=0, sticky="w", pady=5)
        self.cmb_arbitro = ComboBuscador(frame_arbitros, values=self.nombres_oficiales, state="readonly", width=30)
        self.cmb_arbitro.grid(row=0, column=1, padx=10, pady=5)

        ttk.Label(frame_arbitros, text="Judge / Juez:").grid(row=1, column=0, sticky="w", pady=5)
        self.cmb_juez = ComboBuscador(frame_arbitros, values=self.nombres_oficiales, state="readonly", width=30)
        self.cmb_juez.grid(row=1, column=1, padx=10, pady=5)

        # --- NUEVO: JEFE DE TAPIZ INTOCABLE ---
        ttk.Label(frame_arbitros, text="Mat Chairman / Jefe de Tapiz:").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Label(frame_arbitros, text=f"⭐ {self.nombre_jefe_tapiz}", font=("Helvetica", 10, "bold"), foreground="#17a2b8").grid(row=2, column=1, sticky="w", padx=10, pady=5)

        aplicar_autocompletado(self.cmb_arbitro, self.nombres_oficiales)
        aplicar_autocompletado(self.cmb_juez, self.nombres_oficiales)

        def set_combo(cmb, id_oficial):
            if id_oficial:
                for i, of in enumerate(self.oficiales_db):
                    if of['id'] == id_oficial:
                        cmb.current(i)
                        break

        set_combo(self.cmb_arbitro, self.id_arb_orig)
        set_combo(self.cmb_juez, self.id_jue_orig)
        
        # --- NUEVO: PREPARAR INTERCAMBIO ---
        self.prev_arbitro_val = self.cmb_arbitro.get()
        self.prev_juez_val = self.cmb_juez.get()
        self.cmb_arbitro.bind("<<ComboboxSelected>>", self.validar_intercambio_arbitros)
        self.cmb_juez.bind("<<ComboboxSelected>>", self.validar_intercambio_arbitros)

        # --- SECCIÓN: RESULTADOS Y PUNTOS DESGLOSADOS ---
        frame_resultados = ttk.LabelFrame(self, text="Resultados del Combate", padding=10)
        frame_resultados.pack(fill="both", expand=True, padx=15, pady=5)

        ttk.Label(frame_resultados, text="RED - ROJO", foreground="red", font=("Helvetica", 10, "bold")).grid(row=0, column=0, pady=5)
        ttk.Label(frame_resultados, text="BLUE - AZUL", foreground="blue", font=("Helvetica", 10, "bold")).grid(row=0, column=2, pady=5)

        ttk.Label(frame_resultados, text=self.p_rojo['nombre']).grid(row=1, column=0)
        ttk.Label(frame_resultados, text="  VS  ", font=("Helvetica", 12, "bold")).grid(row=1, column=1, padx=20)
        ttk.Label(frame_resultados, text=self.p_azul['nombre']).grid(row=1, column=2)

        frame_pts_r = ttk.Frame(frame_resultados)
        frame_pts_r.grid(row=2, column=0, pady=10)
        ttk.Label(frame_pts_r, text=f"Periodo 1: {self.p1_r}  |  Periodo 2: {self.p2_r}", font=("Helvetica", 9)).pack()
        ttk.Label(frame_pts_r, text=f"TOTAL: {self.total_r}", font=("Helvetica", 11, "bold"), foreground="#cc0000").pack()

        frame_pts_a = ttk.Frame(frame_resultados)
        frame_pts_a.grid(row=2, column=2, pady=10)
        ttk.Label(frame_pts_a, text=f"Periodo 1: {self.p1_a}  |  Periodo 2: {self.p2_a}", font=("Helvetica", 9)).pack()
        ttk.Label(frame_pts_a, text=f"TOTAL: {self.total_a}", font=("Helvetica", 11, "bold"), foreground="#0000cc").pack()

        ttk.Label(frame_resultados, text="Ganador (Winner):", font=("Helvetica", 10, "bold")).grid(row=3, column=0, sticky="w", pady=(15, 5))
        self.cmb_ganador = ComboBuscador(frame_resultados, values=[self.p_rojo['nombre'], self.p_azul['nombre']], state="readonly", width=25)
        self.cmb_ganador.grid(row=3, column=1, columnspan=2, sticky="w", pady=(15, 5))
        
        self.cmb_ganador.bind("<<ComboboxSelected>>", self.actualizar_opciones_victoria)
        
        ganador_data = self.match_node.get("ganador", {})
        ganador_actual = ganador_data.get("nombre", "")
        if ganador_actual: 
            self.cmb_ganador.set(ganador_actual)

        ttk.Label(frame_resultados, text="Tipo de Victoria:", font=("Helvetica", 10, "bold")).grid(row=4, column=0, sticky="w", pady=5)
        self.cmb_victoria = ComboBuscador(frame_resultados, values=self.tipos_victoria, state="readonly", width=50)
        self.cmb_victoria.grid(row=4, column=1, columnspan=2, sticky="w", pady=5)
        
        if ganador_data and "motivo_victoria" in ganador_data: 
            self.cmb_victoria.set(ganador_data["motivo_victoria"])

        # --- LÓGICA DE SEGURIDAD ABSOLUTA ---
        if self.verificar_siguiente_combate_vacio():
            # ESTÁ LIBRE: Aplicamos autocompletado normal
            aplicar_autocompletado(self.cmb_ganador, [self.p_rojo['nombre'], self.p_azul['nombre']])
        else:
            # ESTÁ BLOQUEADO: Lo sellamos y omitimos aplicar_autocompletado para evitar inyecciones
            self.cmb_ganador.config(values=[ganador_actual], state="disabled")

        self.actualizar_opciones_victoria()

        # --- BOTONES FINALES ---
        botones_frame = tk.Frame(self)
        botones_frame.pack(pady=15)

        tk.Button(botones_frame, text="CANCELAR", font=("Helvetica", 10, "bold"), bg="#dc3545", fg="white", command=self.destroy).pack(side="left", padx=10, ipadx=10, ipady=5)
        
        tk.Button(botones_frame, text="GUARDAR Y CONFIRMAR EDICIÓN", font=("Helvetica", 10, "bold"), bg="#28a745", fg="white", command=self.guardar_datos).pack(side="left", padx=10, ipadx=10, ipady=5)

    def validar_intercambio_arbitros(self, event):
        """Si selecciona un árbitro que ya está en el otro cargo, los intercambia automáticamente."""
        val_arb = self.cmb_arbitro.get()
        val_juez = self.cmb_juez.get()
        
        if val_arb == val_juez and val_arb != "":
            if event.widget == self.cmb_arbitro:
                self.cmb_juez.set(getattr(self, 'prev_arbitro_val', ''))
            else:
                self.cmb_arbitro.set(getattr(self, 'prev_juez_val', ''))
                
        self.prev_arbitro_val = self.cmb_arbitro.get()
        self.prev_juez_val = self.cmb_juez.get()

    def guardar_datos(self):
        id_arb = self.oficiales_db[self.cmb_arbitro.current()]['id'] if self.cmb_arbitro.current() != -1 else None
        id_jue = self.oficiales_db[self.cmb_juez.current()]['id'] if self.cmb_juez.current() != -1 else None
        id_jef = self.id_jefe_orig 
        
        if not self.cmb_ganador.get(): 
            return messagebox.showwarning("Falta Ganador", "Debe seleccionar quién ganó el combate.")
            
        ganador_data = self.match_node.get("ganador", {})
        ganador_previo = ganador_data.get("nombre")
        motivo_previo = ganador_data.get("motivo_victoria", "")
        
        ganador_nuevo = self.cmb_ganador.get()
        motivo_nuevo = self.cmb_victoria.get()

        if ganador_previo and ganador_nuevo != ganador_previo:
            # --- BARRERA DE SEGURIDAD BACKEND ---
            if not self.verificar_siguiente_combate_vacio():
                return messagebox.showerror("Bloqueo de Seguridad", "Violación de integridad detectada.\n\nNo puedes cambiar el ganador de este combate porque el atleta actual ya avanzó y está registrado en una ronda posterior.\n\nPara corregir este resultado, primero debes deshacer la pelea futura.")

            if not messagebox.askyesno("Cambio de Ganador", f"Está a punto de cambiar al ganador de '{ganador_previo}' a '{ganador_nuevo}'.\n\n¿Está completamente seguro?"):
                return

        if "DSQ" in motivo_nuevo and "DSQ" not in str(motivo_previo):
            if not messagebox.askyesno("Descalificación Irreversible", "⚠️ ADVERTENCIA DE SEGURIDAD\n\nHa seleccionado una descalificación (DSQ).\n\nLos atletas descalificados serán eliminados del torneo de forma permanente y NO podrán ser reintegrados a la competencia.\n\n¿Desea aplicar esta descalificación?"):
                return
            
        ganador_dict = self.p_rojo if ganador_nuevo == self.p_rojo['nombre'] else self.p_azul
        totales = {'rojo': self.total_r, 'azul': self.total_a}

        self.callback_actualizar(self.match_node, ganador_dict, motivo_nuevo, self.tab, self.llave_key, id_arb, id_jue, id_jef, None, totales)
        self.destroy()

    def actualizar_opciones_victoria(self, event=None):
        ganador_seleccionado = self.cmb_ganador.get()
        if not ganador_seleccionado:
            return

        # Determinar los puntos del ganador y perdedor
        if ganador_seleccionado == self.p_rojo['nombre']:
            puntos_ganador = self.total_r
            puntos_perdedor = self.total_a
        else:
            puntos_ganador = self.total_a
            puntos_perdedor = self.total_r

        # Opciones base
        opciones_validas = [
            "VFA - Victoria por Toque (Fall)",
            "VAB - Victoria por Abandono",
            "VIN - Victoria por Lesión",
            "DSQ - Descalificación por mala conducta",
            "VCA - Victoria por Amonestaciones (3 cautions)"
        ]

        # Escenario 1: Ninguno anotó (0 - 0)
        if puntos_ganador == 0 and puntos_perdedor == 0:
            opciones_validas.extend([
                "VFO - Victoria por Forfeit (Incomparecencia)",
                "VPO - Victoria por Puntos (sin puntos del perdedor)"
            ])
            
        # Escenario 2: El perdedor anotó al menos 1 punto
        elif puntos_perdedor > 0:
            opciones_validas.extend([
                "VSU1 - Superioridad Técnica (con puntos del perdedor)",
                "VPO1 - Victoria por Puntos (con puntos del perdedor)"
            ])
            
        # Escenario 3: Solo el ganador anotó
        elif puntos_perdedor == 0 and puntos_ganador > 0:
            opciones_validas.extend([
                "VSU - Superioridad Técnica (sin puntos del perdedor)",
                "VPO - Victoria por Puntos (sin puntos del perdedor)"
            ])

        valor_actual = self.cmb_victoria.get()
        self.cmb_victoria.config(values=opciones_validas)
        aplicar_autocompletado(self.cmb_victoria, opciones_validas)

        # Si el valor actual no coincide con la nueva realidad, se limpia y se pone el primero de la lista
        if valor_actual not in opciones_validas:
            self.cmb_victoria.set(opciones_validas[0] if opciones_validas else "")

    def verificar_siguiente_combate_vacio(self):
        """Rastrea la llave matemática para verificar si el ganador ya participó en una ronda posterior."""
        match_id = self.match_node.get("match_id", "")
        if not match_id: return True
        
        try:
            r_actual = int(match_id.split("_")[0][1:]) # Ej: Extrae '1' de 'R1'
            k_actual = int(match_id.split("_")[1][1:]) # Ej: Extrae '0' de 'M0'
            
            # --- CORRECCIÓN CLAVE: Usamos self.master para acceder a PantallaPareo ---
            pantalla_pareo = self.master 
            grid = getattr(pantalla_pareo, "grids_generados", {}).get(self.llave_key, [])
            
            r_eval = r_actual + 1
            k_eval = k_actual // 2
            
            while r_eval < len(grid):
                nodo_siguiente = grid[r_eval][k_eval]
                
                if isinstance(nodo_siguiente, dict) and nodo_siguiente.get("tipo") == "combate":
                    # 1. Si el siguiente combate ya tiene un ganador, este atleta ya peleó
                    if nodo_siguiente.get("ganador"):
                        return False 
                    
                    # 2. Si el siguiente combate se está peleando AHORA MISMO en algún tapiz
                    tapiz_activo = getattr(pantalla_pareo, 'combates_en_curso_red', {}).get(self.llave_key, {}).get(nodo_siguiente.get("match_id"))
                    if tapiz_activo:
                        return False
                        
                    return True # El camino está libre
                
                # Si la casilla no es un combate (es un pase directo/SKIP), seguimos a la siguiente ronda
                r_eval += 1
                k_eval = k_eval // 2
                
            return True
        except Exception as e:
            print(f"Error evaluando bloqueo de ganador: {e}")
            return True
