import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from conexion_db import ConexionDB
import os

try:
    import fitz  # PyMuPDF
    PDF_DISPONIBLE = True
except ImportError:
    PDF_DISPONIBLE = False

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
        self.geometry("700x650") 
        self.transient(parent)
        self.grab_set()

        self.oficiales_db = self.db.obtener_oficiales()
        self.nombres_oficiales = [f"{o['apellidos']}, {o['nombre']}" for o in self.oficiales_db]
        
        self.tipos_victoria = [
            "VFA - Victoria por Toque (Fall)", "VIN - Victoria por Lesión", "VCA - Victoria por Amonestaciones (3 cautions)",
            "VSU - Superioridad Técnica (sin puntos del perdedor)", "VSU1 - Superioridad Técnica (con puntos del perdedor)",
            "VPO - Victoria por Puntos (sin puntos del perdedor)", "VPO1 - Victoria por Puntos (con puntos del perdedor)", "DSQ - Descalificación por mala conducta"
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
        self.cmb_arbitro = ttk.Combobox(frame_arbitros, values=self.nombres_oficiales, state="readonly", width=30)
        self.cmb_arbitro.grid(row=0, column=1, padx=10, pady=5)

        ttk.Label(frame_arbitros, text="Judge / Juez:").grid(row=1, column=0, sticky="w", pady=5)
        self.cmb_juez = ttk.Combobox(frame_arbitros, values=self.nombres_oficiales, state="readonly", width=30)
        self.cmb_juez.grid(row=1, column=1, padx=10, pady=5)

        ttk.Label(frame_arbitros, text="Mat Chairman / Jefe de Tapiz:").grid(row=2, column=0, sticky="w", pady=5)
        self.cmb_jefe = ttk.Combobox(frame_arbitros, values=self.nombres_oficiales, state="readonly", width=30)
        self.cmb_jefe.grid(row=2, column=1, padx=10, pady=5)

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
        self.cmb_ganador = ttk.Combobox(frame_resultados, values=[self.p_rojo['nombre'], self.p_azul['nombre']], state="readonly", width=25)
        self.cmb_ganador.grid(row=3, column=1, columnspan=2, sticky="w", pady=(15, 5))
        if ganador_data: self.cmb_ganador.set(ganador_data["nombre"])

        ttk.Label(frame_resultados, text="Tipo de Victoria:", font=("Helvetica", 10, "bold")).grid(row=4, column=0, sticky="w", pady=5)
        self.cmb_victoria = ttk.Combobox(frame_resultados, values=self.tipos_victoria, state="readonly", width=50)
        self.cmb_victoria.grid(row=4, column=1, columnspan=2, sticky="w", pady=5)
        if ganador_data and "motivo_victoria" in ganador_data: self.cmb_victoria.set(ganador_data["motivo_victoria"])

        # --- BOTONES FINALES ---
        botones_frame = tk.Frame(self)
        botones_frame.pack(pady=15)

        tk.Button(botones_frame, text="GUARDAR Y CONFIRMAR EDICIÓN", font=("Helvetica", 10, "bold"), bg="#28a745", fg="white", command=self.guardar_datos).pack(side="left", padx=10, ipadx=10, ipady=5)

        if ganador_data:
            tk.Button(botones_frame, text="📄 EXPORTAR HOJA A PDF", font=("Helvetica", 10, "bold"), bg="#17a2b8", fg="white", command=self.exportar_pdf).pack(side="left", padx=10, ipadx=10, ipady=5)

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

    def exportar_pdf(self):
        if not PDF_DISPONIBLE: return messagebox.showerror("Error", "PyMuPDF no está instalada.")
            
        ruta_plantilla = "hoja_anotacion.pdf" 
        if not os.path.exists(ruta_plantilla): return messagebox.showerror("Error", f"No se encontró '{ruta_plantilla}'.")

        apellido_rojo = self.p_rojo['nombre'].split(',')[0].replace(' ', '_')
        apellido_azul = self.p_azul['nombre'].split(',')[0].replace(' ', '_')
        ruta_guardado = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            initialfile=f"Hoja_Puntuacion_R{self.match_node['ronda']}_{apellido_rojo}_vs_{apellido_azul}.pdf"
        )
        if not ruta_guardado: return

        # 1. Recuperar los datos del Torneo
        torneo_nombre = ""
        torneo_fecha = ""
        conexion = self.db.conectar()
        if conexion and self.id_combate:
            try:
                with conexion.cursor() as cur:
                    cur.execute("""
                        SELECT t.nombre, to_char(t.fecha_inicio, 'DD/MM/YYYY')
                        FROM combate c
                        JOIN torneo_division td ON c.id_torneo_division = td.id
                        JOIN torneo t ON td.id_torneo = t.id
                        WHERE c.id = %s
                    """, (self.id_combate,))
                    res = cur.fetchone()
                    if res:
                        torneo_nombre, torneo_fecha = res[0], res[1]
            except: pass
            finally: conexion.close()

        try:
            from datetime import datetime
            hora_actual = datetime.now().strftime("%H:%M") 

            doc = fitz.open(ruta_plantilla)
            page = doc[0]

            def escribir(texto, x, y, size=10, color=(0, 0, 0)):
                if texto is not None and str(texto).strip() != "":
                    page.insert_text(fitz.Point(x, y), str(texto), fontsize=size, color=color)

            # ================= CALIBRACIÓN MILIMÉTRICA EXACTA =================
            
            # 1. ENCABEZADO SUPERIOR
            escribir(torneo_nombre, 80, 150, size=10) 
            
            escribir(self.cmb_arbitro.get(), 430, 120, size=9) 
            escribir(self.cmb_juez.get(), 430, 145, size=9)    
            escribir(self.cmb_jefe.get(), 430, 170, size=9)    

            # 2. FILA DE INFORMACIÓN DEL COMBATE (Centrado en sus celdas)
            y_info = 200
            escribir(torneo_fecha, 80, y_info, size=9)          # DATE
            escribir(f"{self.match_node['match_id']}", 155, y_info, size=9) # MATCH N°
            escribir(self.tab.cmb_peso.get(), 230, y_info, size=9)          # WEIGHT
            escribir(self.tab.estilo, 295, y_info, size=9)                  # STYLE
            escribir(f"Ronda {self.match_node['ronda']}", 360, y_info, size=9) # ROUND
            escribir("Fase", 430, y_info, size=9)                           # PLACE
            escribir("Tapiz A", 495, y_info, size=9)                        # MAT

            # 3. NOMBRES DE ATLETAS Y CLUBES (Centrado en la celda blanca)
            y_nombres = 250
            escribir(self.p_rojo['nombre'], 65, y_nombres, size=10, color=(0.8, 0, 0))
            escribir(self.p_rojo['club'], 190, y_nombres, size=8)
            
            escribir(self.p_azul['nombre'], 325, y_nombres, size=10, color=(0, 0, 0.8))
            escribir(self.p_azul['club'], 455, y_nombres, size=8)

            # 4. CUADRÍCULA DE PUNTOS TÉCNICOS POR PERIODO
            x_p1_r, y_p1_r = 90, 305  # P1 Rojo
            x_p2_r, y_p2_r = 90, 345  # P2 Rojo
            
            x_p1_a, y_p1_a = 390, 305  # P1 Azul
            x_p2_a, y_p2_a = 390, 345  # P2 Azul
            
            espaciado = 15 
            ultimo_punto_ganador = None
            nombre_ganador = self.cmb_ganador.get()

            for pt in self.puntos_historicos:
                texto_pt = "P" if pt['tipo_accion'] == 'Penalización' else str(pt['valor_puntos'])
                
                if pt['color_esquina'] == 'Rojo':
                    if pt['periodo'] == 1:
                        escribir(texto_pt, x_p1_r, y_p1_r, color=(0.8, 0, 0), size=12)
                        if self.p_rojo['nombre'] == nombre_ganador: ultimo_punto_ganador = (x_p1_r, y_p1_r)
                        x_p1_r += espaciado
                    else:
                        escribir(texto_pt, x_p2_r, y_p2_r, color=(0.8, 0, 0), size=12)
                        if self.p_rojo['nombre'] == nombre_ganador: ultimo_punto_ganador = (x_p2_r, y_p2_r)
                        x_p2_r += espaciado
                else: 
                    if pt['periodo'] == 1:
                        escribir(texto_pt, x_p1_a, y_p1_a, color=(0, 0, 0.8), size=12)
                        if self.p_azul['nombre'] == nombre_ganador: ultimo_punto_ganador = (x_p1_a, y_p1_a)
                        x_p1_a += espaciado
                    else:
                        escribir(texto_pt, x_p2_a, y_p2_a, color=(0, 0, 0.8), size=12)
                        if self.p_azul['nombre'] == nombre_ganador: ultimo_punto_ganador = (x_p2_a, y_p2_a)
                        x_p2_a += espaciado

            # 5. TOTALES DESGLOSADOS POR PERIODO 
            escribir(self.p1_r, 290, 305, size=11, color=(0.8, 0, 0))
            escribir(self.p2_r, 290, 345, size=11, color=(0.8, 0, 0))
            
            escribir(self.p1_a, 565, 305, size=11, color=(0, 0, 0.8))
            escribir(self.p2_a, 565, 345, size=11, color=(0, 0, 0.8))

            # 6. TOTALES GENERALES DEL COMBATE (Alineados en sus cajas)
            escribir(self.total_r, 70, 390, size=16, color=(0.8, 0, 0))
            escribir(self.total_a, 545, 390, size=16, color=(0, 0, 0.8))

            # 7. PUNTOS DE CLASIFICACIÓN Y TACHAR PERDEDOR
            codigo_victoria = self.cmb_victoria.get().split(" - ")[0]
            pts_gan = 0; pts_per = 0
            
            if codigo_victoria in ["VFA", "VIN", "VCA", "DSQ", "VF", "VA", "VB"]: pts_gan = 5
            elif codigo_victoria == "VSU": pts_gan = 4
            elif codigo_victoria == "VSU1": pts_gan = 4; pts_per = 1
            elif codigo_victoria == "VPO": pts_gan = 3
            elif codigo_victoria == "VPO1": pts_gan = 3; pts_per = 1

            if nombre_ganador == self.p_rojo['nombre']:
                clas_rojo, clas_azul = pts_gan, pts_per
                # TACHAR AL AZUL
                page.draw_line(fitz.Point(325, y_nombres - 3), fitz.Point(585, y_nombres - 3), color=(0,0,0), width=1.5)
            else:
                clas_rojo, clas_azul = pts_per, pts_gan
                # TACHAR AL ROJO
                page.draw_line(fitz.Point(65, y_nombres - 3), fitz.Point(310, y_nombres - 3), color=(0,0,0), width=1.5)

            escribir(clas_rojo, 230, 450, size=16, color=(0.8, 0, 0))
            escribir(clas_azul, 350, 450, size=16, color=(0, 0, 0.8))

            # 8. GANADOR Y HORA DE FINALIZACIÓN
            escribir(nombre_ganador, 160, 495, size=12)
            escribir(hora_actual, 480, 495, size=12)

            # 9. CÍRCULO EN EL ÚLTIMO PUNTO (Solo para VFA)
            if codigo_victoria == "VFA" and ultimo_punto_ganador:
                page.draw_circle(fitz.Point(ultimo_punto_ganador[0] + 4, ultimo_punto_ganador[1] - 4), radius=8, color=(0.1, 0.6, 0.1), width=1.5)
            
            # 10. EL CHECKMARK (✔) EN LA TABLA DE REGLAMENTO
            # Calculado a 21 píxeles por fila basándonos en tu captura
            coord_tabla_victorias = {
                "VFA": 490, # VT 5:0
                "VA": 511,  # VA 5:0
                "VIN": 532, # VB 5:0
                "VF": 553,  # VF 5:0
                "DSQ": 574, # EV 5:0
                "VCA": 595, # EX 5:0
                "VSU": 616, # ST 4:0
                "VSU1": 637,# SP 4:1
                "VPO1": 658,# PP 3:1
                "VPO": 679  # PO 3:0
            }
            
            y_check = coord_tabla_victorias.get(codigo_victoria)
            if y_check:
                x_c = 40 # Posición horizontal a la izquierda de la letra
                p1 = fitz.Point(x_c, y_check - 2)
                p2 = fitz.Point(x_c + 5, y_check + 6)
                p3 = fitz.Point(x_c + 15, y_check - 8)
                page.draw_line(p1, p2, color=(0.1, 0.7, 0.1), width=2.5)
                page.draw_line(p2, p3, color=(0.1, 0.7, 0.1), width=2.5)

            doc.save(ruta_guardado)
            doc.close()
            messagebox.showinfo("Éxito", f"Hoja técnica exportada correctamente.")

        except Exception as e:
            messagebox.showerror("Error", f"Ocurrió un error al generar el PDF:\n{str(e)}")
