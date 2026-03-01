import tkinter as tk
from tkinter import ttk, messagebox
from conexion_db import ConexionDB
from utilidades import aplicar_autocompletado
from utilidades import ComboBuscador

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

        self.oficiales_db = self.db.obtener_oficiales()
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
        tk.Label(self, text="HOJA DE PUNTUACIÓN OFICIAL", font=("Helvetica", 14, "bold"), bg="#2a2a2a", fg="white").pack(fill="x")

        # --- SECCIÓN: CUERPO ARBITRAL ---
        frame_arbitros = ttk.LabelFrame(self, text="Oficiales de Arbitraje (Asignados en el Tapiz)", padding=10)
        frame_arbitros.pack(fill="x", padx=15, pady=10)

        ttk.Label(frame_arbitros, text="Referee / Árbitro:").grid(row=0, column=0, sticky="w", pady=5)
        self.cmb_arbitro = ComboBuscador(frame_arbitros, values=self.nombres_oficiales, state="readonly", width=30)
        self.cmb_arbitro.grid(row=0, column=1, padx=10, pady=5)

        ttk.Label(frame_arbitros, text="Judge / Juez:").grid(row=1, column=0, sticky="w", pady=5)
        self.cmb_juez = ComboBuscador(frame_arbitros, values=self.nombres_oficiales, state="readonly", width=30)
        self.cmb_juez.grid(row=1, column=1, padx=10, pady=5)

        ttk.Label(frame_arbitros, text="Mat Chairman / Jefe de Tapiz:").grid(row=2, column=0, sticky="w", pady=5)
        self.cmb_jefe = ComboBuscador(frame_arbitros, values=self.nombres_oficiales, state="readonly", width=30)
        self.cmb_jefe.grid(row=2, column=1, padx=10, pady=5)

        aplicar_autocompletado(self.cmb_arbitro, self.nombres_oficiales)
        aplicar_autocompletado(self.cmb_juez, self.nombres_oficiales)
        aplicar_autocompletado(self.cmb_jefe, self.nombres_oficiales)

        ganador_data = self.match_node.get("ganador", {})
        def set_combo(cmb, id_oficial):
            if id_oficial:
                for i, of in enumerate(self.oficiales_db):
                    if of['id'] == id_oficial:
                        cmb.current(i)
                        break

        set_combo(self.cmb_arbitro, ganador_data.get("id_arbitro"))
        set_combo(self.cmb_juez, ganador_data.get("id_juez"))
        set_combo(self.cmb_jefe, ganador_data.get("id_jefe_tapiz"))

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
        if ganador_data: self.cmb_ganador.set(ganador_data["nombre"])

        ttk.Label(frame_resultados, text="Tipo de Victoria:", font=("Helvetica", 10, "bold")).grid(row=4, column=0, sticky="w", pady=5)
        self.cmb_victoria = ComboBuscador(frame_resultados, values=self.tipos_victoria, state="readonly", width=50)
        self.cmb_victoria.grid(row=4, column=1, columnspan=2, sticky="w", pady=5)
        if ganador_data and "motivo_victoria" in ganador_data: self.cmb_victoria.set(ganador_data["motivo_victoria"])

        aplicar_autocompletado(self.cmb_ganador, [self.p_rojo['nombre'], self.p_azul['nombre']])
        aplicar_autocompletado(self.cmb_victoria, self.tipos_victoria)

        # --- BOTONES FINALES ---
        botones_frame = tk.Frame(self)
        botones_frame.pack(pady=15)

        tk.Button(botones_frame, text="GUARDAR Y CONFIRMAR EDICIÓN", font=("Helvetica", 10, "bold"), bg="#28a745", fg="white", command=self.guardar_datos).pack(side="left", padx=10, ipadx=10, ipady=5)

    def guardar_datos(self):
        id_arb = self.oficiales_db[self.cmb_arbitro.current()]['id'] if self.cmb_arbitro.current() != -1 else None
        id_jue = self.oficiales_db[self.cmb_juez.current()]['id'] if self.cmb_juez.current() != -1 else None
        id_jef = self.oficiales_db[self.cmb_jefe.current()]['id'] if self.cmb_jefe.current() != -1 else None
        
        if not self.cmb_ganador.get(): return messagebox.showwarning("Falta Ganador", "Debe seleccionar quién ganó el combate.")
            
        ganador_dict = self.p_rojo if self.cmb_ganador.get() == self.p_rojo['nombre'] else self.p_azul
        motivo = self.cmb_victoria.get()
        totales = {'rojo': self.total_r, 'azul': self.total_a}

        self.callback_actualizar(self.match_node, ganador_dict, motivo, self.tab, self.llave_key, id_arb, id_jue, id_jef, None, totales)
        self.destroy()
