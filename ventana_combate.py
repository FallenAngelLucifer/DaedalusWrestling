import tkinter as tk
from tkinter import ttk, messagebox

class VentanaCombate(tk.Toplevel):
    def __init__(self, parent, match_node, p_rojo, p_azul, callback_ganador):
        super().__init__(parent)
        self.match_node = match_node
        self.p_rojo = p_rojo
        self.p_azul = p_azul
        self.callback_ganador = callback_ganador
        
        # Variables de puntuación (Total)
        self.score_rojo = tk.IntVar(value=0)
        self.score_azul = tk.IntVar(value=0)
        
        # Desglose de puntuación por periodos
        self.p1_rojo = tk.IntVar(value=0)
        self.p2_rojo = tk.IntVar(value=0)
        self.p1_azul = tk.IntVar(value=0)
        self.p2_azul = tk.IntVar(value=0)
        
        # Variables del Cronómetro y Periodos
        self.periodo_actual = 1 # 1 = P1, 0 = Descanso, 2 = P2, 3 = Fin
        self.duracion_periodo = 180 # 3 minutos por defecto
        self.tiempo_segundos = self.duracion_periodo
        self.timer_corriendo = False
        self.timer_id = None
        
        # Historial para Deshacer/Editar
        self.historial_acciones = []
        
        # Catálogo Oficial de Victorias (UWW)
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

        self.oficiales_db = parent.db.obtener_oficiales()
        self.nombres_oficiales = [f"{o['apellidos']}, {o['nombre']}" for o in self.oficiales_db]
        
        self.title("Marcador Oficial UWW - Combate en Curso")
        self.geometry("900x700") 
        self.configure(bg="#121212")
        self.transient(parent)
        self.grab_set() 
        
        self.crear_interfaz()
        self.actualizar_reloj_visual() 
        
    def crear_interfaz(self):
        # ================= ENCABEZADO =================
        header = tk.Frame(self, bg="#2a2a2a", height=60)
        header.pack(fill="x")
        
        tk.Label(header, text=f"RONDA {self.match_node['ronda']} - TAPIZ A", fg="white", bg="#2a2a2a", font=("Helvetica", 14, "bold")).pack(pady=(5, 0))
        self.lbl_estado_periodo = tk.Label(header, text="PERIODO 1", fg="#ffcc00", bg="#2a2a2a", font=("Helvetica", 12, "bold"))
        self.lbl_estado_periodo.pack(pady=(0, 5))

        # --- NUEVO: CUERPO ARBITRAL ANTES DE INICIAR ---
        frame_arbitros = tk.Frame(self, bg="#1e1e1e")
        frame_arbitros.pack(fill="x", pady=5)
        
        tk.Label(frame_arbitros, text="Árbitro:", bg="#1e1e1e", fg="white", font=("Helvetica", 9, "bold")).pack(side="left", padx=(20, 5))
        self.cmb_arbitro = ttk.Combobox(frame_arbitros, values=self.nombres_oficiales, state="readonly", width=20)
        self.cmb_arbitro.pack(side="left", padx=5)
        
        tk.Label(frame_arbitros, text="Juez:", bg="#1e1e1e", fg="white", font=("Helvetica", 9, "bold")).pack(side="left", padx=(15, 5))
        self.cmb_juez = ttk.Combobox(frame_arbitros, values=self.nombres_oficiales, state="readonly", width=20)
        self.cmb_juez.pack(side="left", padx=5)
        
        tk.Label(frame_arbitros, text="Jefe Tapiz:", bg="#1e1e1e", fg="white", font=("Helvetica", 9, "bold")).pack(side="left", padx=(15, 5))
        self.cmb_jefe = ttk.Combobox(frame_arbitros, values=self.nombres_oficiales, state="readonly", width=20)
        self.cmb_jefe.pack(side="left", padx=5)
        
        # Preseleccionar los 3 primeros de la base de datos si existen
        if self.nombres_oficiales:
            self.cmb_arbitro.current(0)
            self.cmb_juez.current(1 if len(self.nombres_oficiales) > 1 else 0)
            self.cmb_jefe.current(2 if len(self.nombres_oficiales) > 2 else 0)
        
        # ================= TABLERO PRINCIPAL =================
        board = tk.Frame(self, bg="#121212")
        board.pack(fill="both", expand=True, pady=10, padx=20)
        
        # --- ESQUINA ROJA ---
        f_rojo = tk.Frame(board, bg="#cc0000", width=350)
        f_rojo.pack(side="left", fill="both", expand=True, padx=10)
        f_rojo.pack_propagate(False) 
        
        tk.Label(f_rojo, text=self.p_rojo['nombre'], fg="white", bg="#cc0000", font=("Helvetica", 22, "bold"), wraplength=300).pack(pady=(20, 5))
        tk.Label(f_rojo, text=self.p_rojo['club'], fg="#ffcccc", bg="#cc0000", font=("Helvetica", 12)).pack()
        
        tk.Label(f_rojo, textvariable=self.score_rojo, fg="white", bg="#cc0000", font=("Helvetica", 90, "bold")).pack(pady=(10, 0))
        
        frame_desglose_r = tk.Frame(f_rojo, bg="#990000", padx=10, pady=5)
        frame_desglose_r.pack(pady=(0, 10))
        tk.Label(frame_desglose_r, text="P1:", fg="white", bg="#990000", font=("Helvetica", 12)).pack(side="left")
        tk.Label(frame_desglose_r, textvariable=self.p1_rojo, fg="white", bg="#990000", font=("Helvetica", 12, "bold")).pack(side="left", padx=(2, 15))
        tk.Label(frame_desglose_r, text="P2:", fg="white", bg="#990000", font=("Helvetica", 12)).pack(side="left")
        tk.Label(frame_desglose_r, textvariable=self.p2_rojo, fg="white", bg="#990000", font=("Helvetica", 12, "bold")).pack(side="left", padx=(2, 0))
        
        btn_frame_r = tk.Frame(f_rojo, bg="#cc0000")
        btn_frame_r.pack(pady=5)
        for pts in [1, 2, 4, 5]:
            tk.Button(btn_frame_r, text=f"+{pts}", font=("Helvetica", 14, "bold"), bg="white", fg="#cc0000", width=3, command=lambda p=pts: self.sumar('rojo', p)).pack(side="left", padx=5)
        tk.Button(btn_frame_r, text="P", font=("Helvetica", 14, "bold"), bg="yellow", fg="black", width=3, command=lambda: self.sumar('rojo', 0, es_penalizacion=True)).pack(side="left", padx=5)
        
        # Historial visual de recuadros Rojos
        self.log_rojo = tk.Frame(f_rojo, bg="#cc0000")
        self.log_rojo.pack(pady=5, fill="x", padx=10)

        tk.Button(f_rojo, text="🏆 DECLARAR GANADOR ROJO", font=("Helvetica", 12, "bold"), bg="#ff4d4d", fg="white", command=lambda: self.abrir_dialogo_victoria(self.p_rojo)).pack(side="bottom", pady=20, fill="x", padx=20)

        # --- ESQUINA AZUL ---
        f_azul = tk.Frame(board, bg="#0000cc", width=350)
        f_azul.pack(side="right", fill="both", expand=True, padx=10)
        f_azul.pack_propagate(False)
        
        tk.Label(f_azul, text=self.p_azul['nombre'], fg="white", bg="#0000cc", font=("Helvetica", 22, "bold"), wraplength=300).pack(pady=(20, 5))
        tk.Label(f_azul, text=self.p_azul['club'], fg="#ccccff", bg="#0000cc", font=("Helvetica", 12)).pack()
        
        tk.Label(f_azul, textvariable=self.score_azul, fg="white", bg="#0000cc", font=("Helvetica", 90, "bold")).pack(pady=(10, 0))
        
        frame_desglose_a = tk.Frame(f_azul, bg="#000099", padx=10, pady=5)
        frame_desglose_a.pack(pady=(0, 10))
        tk.Label(frame_desglose_a, text="P1:", fg="white", bg="#000099", font=("Helvetica", 12)).pack(side="left")
        tk.Label(frame_desglose_a, textvariable=self.p1_azul, fg="white", bg="#000099", font=("Helvetica", 12, "bold")).pack(side="left", padx=(2, 15))
        tk.Label(frame_desglose_a, text="P2:", fg="white", bg="#000099", font=("Helvetica", 12)).pack(side="left")
        tk.Label(frame_desglose_a, textvariable=self.p2_azul, fg="white", bg="#000099", font=("Helvetica", 12, "bold")).pack(side="left", padx=(2, 0))
        
        btn_frame_a = tk.Frame(f_azul, bg="#0000cc")
        btn_frame_a.pack(pady=5)
        for pts in [1, 2, 4, 5]:
            tk.Button(btn_frame_a, text=f"+{pts}", font=("Helvetica", 14, "bold"), bg="white", fg="#0000cc", width=3, command=lambda p=pts: self.sumar('azul', p)).pack(side="left", padx=5)
        tk.Button(btn_frame_a, text="P", font=("Helvetica", 14, "bold"), bg="yellow", fg="black", width=3, command=lambda: self.sumar('azul', 0, es_penalizacion=True)).pack(side="left", padx=5)

        # Historial visual de recuadros Azules
        self.log_azul = tk.Frame(f_azul, bg="#0000cc")
        self.log_azul.pack(pady=5, fill="x", padx=10)

        tk.Button(f_azul, text="🏆 DECLARAR GANADOR AZUL", font=("Helvetica", 12, "bold"), bg="#4d4dff", fg="white", command=lambda: self.abrir_dialogo_victoria(self.p_azul)).pack(side="bottom", pady=20, fill="x", padx=20)

        # --- CENTRO (CRONÓMETRO Y CONTROLES) ---
        center = tk.Frame(board, bg="#121212", width=160)
        center.pack(expand=True, fill="y")
        
        frame_ajuste = tk.Frame(center, bg="#121212")
        frame_ajuste.pack(pady=(20, 0))
        tk.Button(frame_ajuste, text="-1 Min", font=("Helvetica", 8), command=lambda: self.modificar_tiempo(-1)).pack(side="left", padx=5)
        tk.Button(frame_ajuste, text="+1 Min", font=("Helvetica", 8), command=lambda: self.modificar_tiempo(1)).pack(side="left", padx=5)

        self.lbl_reloj = tk.Label(center, fg="#ffcc00", bg="#121212", font=("Courier", 35, "bold"))
        self.lbl_reloj.pack(pady=(5, 10))
        
        tk.Button(center, text="▶ INICIAR", font=("Helvetica", 12, "bold"), bg="#28a745", fg="white", width=12, command=self.iniciar_cronometro).pack(pady=5)
        tk.Button(center, text="⏸ PAUSAR", font=("Helvetica", 12, "bold"), bg="#ffc107", fg="black", width=12, command=self.pausar_cronometro).pack(pady=5)
        tk.Button(center, text="⏱ 30s ACT", font=("Helvetica", 10, "bold"), bg="#17a2b8", fg="white", width=14).pack(pady=(20, 5))
        
        tk.Button(center, text="↩ DESHACER ÚLTIMO", font=("Helvetica", 9, "bold"), bg="gray", fg="white", width=18, command=self.deshacer_accion).pack(side="bottom", pady=20)

    # ================= LÓGICA DE TIEMPO Y PERIODOS =================
    def actualizar_reloj_visual(self):
        mins, secs = divmod(self.tiempo_segundos, 60)
        self.lbl_reloj.config(text=f"{mins:02d}:{secs:02d}")

    def modificar_tiempo(self, minutos):
        if not self.timer_corriendo:
            
            self.tiempo_segundos += (minutos * 60)
            if self.tiempo_segundos < 0: 
                self.tiempo_segundos = 0
                
            self.actualizar_reloj_visual()

    def avanzar_fase(self):
        """Lógica para saltar al siguiente periodo o descanso."""
        if self.periodo_actual == 1:
            # 1. Pasa del Periodo 1 al Descanso
            self.periodo_actual = 0
            self.tiempo_segundos = 30 # Descanso estricto de 30s
            self.lbl_estado_periodo.config(text="DESCANSO", fg="#ff4d4d")
            self.lbl_reloj.config(fg="#ff4d4d")
            self.actualizar_reloj_visual()
            
            # --- Limpiar los recuadritos de puntuación del P1 ---
            for widget in self.log_rojo.winfo_children(): widget.pack_forget()
            for widget in self.log_azul.winfo_children(): widget.pack_forget()
            
        elif self.periodo_actual == 0:
            # 2. Pasa del Descanso al Periodo 2
            self.periodo_actual = 2
            self.tiempo_segundos = self.duracion_periodo # Regresa a 3 mins (o lo modificado)
            self.lbl_estado_periodo.config(text="PERIODO 2", fg="#ffcc00")
            self.lbl_reloj.config(fg="#ffcc00")
            self.actualizar_reloj_visual()
            
        elif self.periodo_actual == 2:
            # 3. Fin de la partida por tiempo
            self.periodo_actual = 3
            self.lbl_estado_periodo.config(text="FIN DEL COMBATE", fg="#00ccff")
            self.actualizar_reloj_visual()

    def iniciar_cronometro(self):
        # Si el tiempo está en 0 y le damos a Iniciar, actúa como botón de "Siguiente Fase"
        if self.tiempo_segundos <= 0 and self.periodo_actual != 3:
            self.avanzar_fase()
        # Si tiene tiempo normal, arranca el reloj
        elif not self.timer_corriendo and self.periodo_actual != 3:
            self.timer_corriendo = True
            self.bucle_cronometro()

    def pausar_cronometro(self):
        self.timer_corriendo = False
        if self.timer_id:
            self.after_cancel(self.timer_id)
            self.timer_id = None

    def bucle_cronometro(self):
        if self.timer_corriendo and self.tiempo_segundos > 0:
            self.tiempo_segundos -= 1
            self.actualizar_reloj_visual()
            
            # Si el reloj llega a 0 de forma natural mientras corre
            if self.tiempo_segundos <= 0:
                self.timer_corriendo = False
                # Espera 1 segundo para mostrar el "00:00" y salta de fase
                self.after(1000, self.avanzar_fase)
            else:
                self.timer_id = self.after(1000, self.bucle_cronometro)

    # ================= MATEMÁTICAS CENTRALES DE PUNTUACIÓN =================
    def ajustar_puntuacion(self, esquina, periodo, cantidad):
        """Suma o resta puntos de forma segura a los totales y a los periodos"""
        if esquina == 'rojo':
            self.score_rojo.set(self.score_rojo.get() + cantidad)
            if periodo == 1: self.p1_rojo.set(self.p1_rojo.get() + cantidad)
            else: self.p2_rojo.set(self.p2_rojo.get() + cantidad)
        else:
            self.score_azul.set(self.score_azul.get() + cantidad)
            if periodo == 1: self.p1_azul.set(self.p1_azul.get() + cantidad)
            else: self.p2_azul.set(self.p2_azul.get() + cantidad)

    # ================= LÓGICA DE PUNTOS E HISTORIAL =================
    def sumar(self, esquina, puntos, es_penalizacion=False):
        if self.periodo_actual not in (1, 2): 
            return messagebox.showwarning("Reloj Pausado", "No se pueden anotar puntos durante el descanso o fuera de tiempo.")

        accion = {
            'esquina': esquina,
            'puntos': puntos,
            'periodo': self.periodo_actual,
            'is_p': es_penalizacion
        }

        self.ajustar_puntuacion(esquina, self.periodo_actual, puntos)

        bg_color = "yellow" if es_penalizacion else "white"
        txt_color = "black" if es_penalizacion else ("#cc0000" if esquina == 'rojo' else "#0000cc")
        texto_etiqueta = "P" if es_penalizacion else str(puntos)

        padre_frame = self.log_rojo if esquina == 'rojo' else self.log_azul
        
        btn = tk.Button(padre_frame, text=texto_etiqueta, bg=bg_color, fg=txt_color, font=("Helvetica", 11, "bold"), width=2, relief="solid", cursor="hand2", command=lambda a=accion: self.abrir_edicion_accion(a))
        btn.pack(side="left", padx=2, pady=2)
        
        accion['widget'] = btn
        self.historial_acciones.append(accion)

    def deshacer_accion(self):
        """Elimina rápidamente la última acción ejecutada"""
        if not self.historial_acciones: return
        ultima_accion = self.historial_acciones[-1]
        self.eliminar_accion_especifica(ultima_accion)

    # ================= EDICIÓN INDIVIDUAL DE ACCIONES =================
    def abrir_edicion_accion(self, accion):
        dialogo = tk.Toplevel(self)
        dialogo.title("Editar Acción")
        dialogo.geometry("300x150")
        dialogo.transient(self)
        dialogo.grab_set()
        
        ttk.Label(dialogo, text="Modificar puntaje:", font=("Helvetica", 10, "bold")).pack(pady=10)
        
        btn_frame = ttk.Frame(dialogo)
        btn_frame.pack(pady=5)
        
        for pts in [1, 2, 4, 5]:
            ttk.Button(btn_frame, text=str(pts), width=3, command=lambda p=pts: self.aplicar_modificacion(accion, p, False, dialogo)).pack(side="left", padx=2)
            
        ttk.Button(btn_frame, text="P", width=3, command=lambda: self.aplicar_modificacion(accion, 0, True, dialogo)).pack(side="left", padx=2)
        
        ttk.Button(dialogo, text="🗑 Eliminar Esta Acción", command=lambda: self.eliminar_accion_especifica(accion, dialogo)).pack(pady=15)

    def aplicar_modificacion(self, accion, nuevos_puntos, es_p, dialogo):
        # 1. Restar los puntos de la acción vieja y sumar los de la nueva
        self.ajustar_puntuacion(accion['esquina'], accion['periodo'], -accion['puntos'])
        self.ajustar_puntuacion(accion['esquina'], accion['periodo'], nuevos_puntos)
        
        # 2. Actualizar la memoria de esa acción
        accion['puntos'] = nuevos_puntos
        accion['is_p'] = es_p
        
        # 3. Actualizar el color y texto del cuadrito visual
        bg_color = "yellow" if es_p else "white"
        txt_color = "black" if es_p else ("#cc0000" if accion['esquina'] == 'rojo' else "#0000cc")
        texto_etiqueta = "P" if es_p else str(nuevos_puntos)
        accion['widget'].config(text=texto_etiqueta, bg=bg_color, fg=txt_color)
        
        dialogo.destroy()

    def eliminar_accion_especifica(self, accion, dialogo=None):
        # 1. Restar los puntos devuelta
        self.ajustar_puntuacion(accion['esquina'], accion['periodo'], -accion['puntos'])
        
        # 2. Destruir el cuadrito en la pantalla y borrarlo de la lista
        accion['widget'].destroy()
        if accion in self.historial_acciones:
            self.historial_acciones.remove(accion)
            
        if dialogo:
            dialogo.destroy()

    # ================= DECLARACIÓN DE VICTORIA =================
    def abrir_dialogo_victoria(self, peleador):
        self.pausar_cronometro() 
        dialogo = tk.Toplevel(self)
        dialogo.title("Declarar Victoria (UWW)")
        dialogo.geometry("400x200")
        dialogo.transient(self)
        dialogo.grab_set()
        
        ttk.Label(dialogo, text=f"Ganador: {peleador['nombre']}", font=("Helvetica", 12, "bold")).pack(pady=10)
        ttk.Label(dialogo, text="Seleccione el motivo de la victoria:").pack(pady=5)
        cmb_motivo = ttk.Combobox(dialogo, values=self.tipos_victoria, state="readonly", width=50)
        cmb_motivo.pack(pady=10)
        cmb_motivo.set(self.tipos_victoria[0]) 
        
        def confirmar():
            motivo = cmb_motivo.get()
            id_arb = self.oficiales_db[self.cmb_arbitro.current()]['id'] if self.cmb_arbitro.current() != -1 else None
            id_jue = self.oficiales_db[self.cmb_juez.current()]['id'] if self.cmb_juez.current() != -1 else None
            id_jef = self.oficiales_db[self.cmb_jefe.current()]['id'] if self.cmb_jefe.current() != -1 else None

            # Limpiar el historial (Quitar los widgets de TKinter para que no den error)
            historial_limpio = []
            for i, acc in enumerate(self.historial_acciones):
                historial_limpio.append({'esquina': acc['esquina'], 'puntos': acc['puntos'], 'periodo': acc['periodo'], 'is_p': acc['is_p'], 'orden': i + 1})
            
            totales = {'rojo': self.score_rojo.get(), 'azul': self.score_azul.get()}

            # Enviar tooooda la información a la pantalla de brackets
            self.callback_ganador(self.match_node['match_id'], peleador, motivo, id_arb, id_jue, id_jef, historial_limpio, totales)
            dialogo.destroy()
            self.destroy() 
            
        ttk.Button(dialogo, text="Confirmar y Finalizar", command=confirmar).pack(pady=15)