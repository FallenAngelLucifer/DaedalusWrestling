import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import math
import os
import json
from PIL import Image, EpsImagePlugin, ImageDraw, ImageFont
from database.conexion_db import ConexionDB
from utils.utilidades import ComboBuscador, aplicar_deseleccion_tabla, aplicar_autocompletado
from ui.ventanas.ventana_previsualizacion_pdf import VentanaPrevisualizacionPDF
from ui.ventanas.ventana_login_red import VentanaLoginRed

# --- COLOR ORIGINAL DEL FONDO ---
COLOR_FONDO_UI = (30, 30, 30) # Corresponde a #1e1e1e en RGB

# RUTA DINÁMICA: Intenta detectar si el archivo existe antes de asignarlo
gs_path = r"C:\Program Files\gs\gs10.06.0\bin\gswin64c.exe"

if os.path.exists(gs_path):
    EpsImagePlugin.gs_windows_binary = gs_path
else:
    print(f"ADVERTENCIA: No se encontró Ghostscript en {gs_path}. Verifique la instalación.")

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
        self.llaves_generadas = {} 
        self.resultados_combates = {} 
        self.divisiones_bloqueadas = set() 
        self.grids_generados = {}          

        # Variables para Tooltip
        self.tooltip_window = None
        self.caja_hover_actual = None

        # --- NUEVO: Frame de encabezado para navegación y título ---
        header_frame = ttk.Frame(self)
        header_frame.pack(fill="x", pady=(10, 5))

        # Botón para regresar a la pantalla anterior
        self.btn_regresar = ttk.Button(header_frame, text="⬅ Regresar a Inscripción", command=self.regresar_a_inscripcion)
        self.btn_regresar.pack(side="left", padx=20)

        lbl_titulo = ttk.Label(header_frame, text="Fase 2: Desarrollo de Pareo (Brackets)", font=("Helvetica", 16, "bold"))
        lbl_titulo.pack(side="left", padx=(0, 20))

        # --- NUEVO: Etiqueta de mi Tapiz Actual ---
        self.lbl_mi_tapiz_header = ttk.Label(header_frame, text="📍 Tapiz Asignado: Pendiente", font=("Helvetica", 12, "bold"), foreground="#007bff")
        self.lbl_mi_tapiz_header.pack(side="left", expand=True, anchor="w")
        
        # CORRECCIÓN: Usar header_frame en lugar de self.frame_header
        self.btn_gestion_red = tk.Button(header_frame, text="👥 Gestionar Red", font=("Helvetica", 9, "bold"), bg="#17a2b8", fg="white", cursor="hand2", command=self.abrir_panel_red)

        # --- NUEVA FILA: Frame exclusivo para exportaciones masivas ---
        self.export_frame = ttk.Frame(self)
        self.export_frame.pack(fill="x", padx=20, pady=(0, 0)) 

        # --- NUEVO: Etiqueta de Estado del Torneo (Alineada a la derecha) ---
        self.lbl_estado_torneo = ttk.Label(self.export_frame, text="", font=("Helvetica", 10, "bold"))
        self.lbl_estado_torneo.pack(side="right", padx=10, anchor="s")

        # --- BOTONES GLOBALES DE EXPORTACIÓN (Nacen ocultos por defecto) ---
        self.btn_exportar_todas_img = tk.Button(self.export_frame, text="🖼 Exportar Todas (IMG)", bg="#17a2b8", fg="white", command=self.exportar_todas_las_imagenes)
        self.btn_exportar_fichas_pdf = tk.Button(self.export_frame, text="📄 Exportar Fichas (PDF)", bg="#d9534f", fg="white", command=self.exportar_todas_las_fichas_pdf)

        self.after(100, self.gestionar_botones_globales)

        # Contenedor dinámico
        self.contenedor_principal = ttk.Frame(self)
        self.contenedor_principal.pack(fill="both", expand=True)

    def gestionar_botones_globales(self):
        if not hasattr(self, 'btn_exportar_todas_img'): return
        
        total_divs = sum(len(p) for p in self.datos.values())
        todas_bloqueadas = (len(self.divisiones_bloqueadas) >= total_divs) and (total_divs > 0)
        
        if todas_bloqueadas:
            # Torneo Cerrado: Mostramos botones de exportación masiva a la IZQUIERDA
            # Empaquetamos primero IMG y luego PDF para mantener el orden
            if not self.btn_exportar_todas_img.winfo_ismapped():
                self.btn_exportar_todas_img.pack(side="left", padx=(0, 10))
            if not self.btn_exportar_fichas_pdf.winfo_ismapped():
                self.btn_exportar_fichas_pdf.pack(side="left", padx=(0, 10))
        else:
            # Torneo Abierto: Ocultamos exportación masiva
            self.btn_exportar_fichas_pdf.pack_forget()
            self.btn_exportar_todas_img.pack_forget()

    def actualizar_estado_torneo(self):
        if not hasattr(self, 'lbl_estado_torneo'): return
        
        if getattr(self, "torneo_cerrado_en_db", False):
            self.lbl_estado_torneo.config(text="🏆 Torneo Finalizado", foreground="#28a745")
            return
            
        total_divs = sum(len(p) for p in self.datos.values())
        bloqueadas = len(self.divisiones_bloqueadas)
        
        # CASO 1: Faltan llaves por confirmar
        if bloqueadas < total_divs:
            faltan = total_divs - bloqueadas
            self.lbl_estado_torneo.config(text=f"⚠️ Faltan {faltan} llaves por confirmar", foreground="#f39c12")
            return
            
        # CASO 2: Torneo Corriendo (Todas las llaves listas)
        total_peleas = 0
        completadas = 0
        pendientes = []
        
        for llave_key, grid in self.grids_generados.items():
            rondas_totales_bracket = len(grid) - 1 # El tamaño total del bracket
            for r in range(1, len(grid)):
                for node in grid[r]:
                    if isinstance(node, dict) and node.get("tipo") == "combate":
                        total_peleas += 1
                        if node.get("ganador"):
                            completadas += 1
                        else:
                            pendientes.append({
                                "ronda": node["ronda"],
                                "distancia": rondas_totales_bracket - node["ronda"]
                            })
        
        faltan = total_peleas - completadas
        
        if faltan == 0:
            texto_listo = f"Torneo Finalizado - Listo para Cerrar\nPeleas: {total_peleas}  |  Completadas: {completadas}  |  Faltantes: 0"
            self.lbl_estado_torneo.config(text=texto_listo, foreground="#28a745", justify="right")
        else:
            # Encontrar la ronda más baja en la que hay peleas pendientes
            ronda_actual = min(p["ronda"] for p in pendientes)
            restantes_ronda = sum(1 for p in pendientes if p["ronda"] == ronda_actual)
            
            # Buscar el bracket más grande involucrado para darle nombre a la fase
            max_dist = max(p["distancia"] for p in pendientes if p["ronda"] == ronda_actual)
            
            # Calcular rondas totales faltantes en todo el torneo
            rondas_faltantes = max(p["distancia"] for p in pendientes) + 1
            
            if max_dist == 0: nombre_fase = "Finales"
            elif max_dist == 1: nombre_fase = "Semifinales"
            elif max_dist == 2: nombre_fase = "Cuartos de final"
            elif max_dist == 3: nombre_fase = "Octavos de final"
            else: nombre_fase = "Eliminatorias"
            
            # --- NUEVO: Texto dividido en dos líneas y justificado a la derecha ---
            linea_rondas = f"Fase: {nombre_fase} (Ronda {ronda_actual}, {restantes_ronda} restantes)  |  Rondas Faltantes: {rondas_faltantes}"
            linea_peleas = f"Peleas Totales: {total_peleas}  |  Completadas: {completadas}  |  Faltantes: {faltan}"
            
            texto = f"{linea_rondas}\n{linea_peleas}"
            self.lbl_estado_torneo.config(text=texto, foreground="#17a2b8", justify="right")

    def exportar_todas_las_fichas_pdf(self):
        """Exporta todas las hojas de anotación de combates finalizados a una carpeta."""
        if not PDF_DISPONIBLE: 
            return messagebox.showerror("Error", "PyMuPDF no está instalada.")
            
        dir_padre = filedialog.askdirectory(title="Seleccione dónde crear la carpeta de Fichas PDF")
        if not dir_padre: return

        # Chequear si la carpeta ya existe y usarla, si no, crearla
        nombre_carpeta = f"Torneo_{self.id_torneo}_Fichas_PDF"
        ruta_final = os.path.join(dir_padre, nombre_carpeta)
        if not os.path.exists(ruta_final): 
            os.makedirs(ruta_final)

        exitos = 0
        # Recorrer todas las llaves generadas buscando combates terminados
        for llave_key, grid in self.grids_generados.items():
            estilo, peso = llave_key.split("-")
            
            for r in grid:
                for node in r:
                    # Validar que es un combate y que tiene un ganador definido
                    if isinstance(node, dict) and node.get("tipo") == "combate" and node.get("ganador"):
                        p_rojo = self.obtener_peleador_real(node["peleador_rojo"])
                        p_azul = self.obtener_peleador_real(node["peleador_azul"])
                        
                        if p_rojo and p_azul:
                            apellido_rojo = p_rojo['nombre'].split(',')[0].replace(' ', '_')
                            apellido_azul = p_azul['nombre'].split(',')[0].replace(' ', '_')
                            nombre_archivo = f"R{node['ronda']}_{estilo}_{peso}_{apellido_rojo}_vs_{apellido_azul}.pdf".replace(" ", "_")
                            ruta_pdf = os.path.join(ruta_final, nombre_archivo)
                            
                            # Llamamos al exportador individual de forma silenciosa
                            self.exportar_pdf(node, estilo, peso, ruta_directa=ruta_pdf)
                            exitos += 1
                            
        if exitos > 0:
            messagebox.showinfo("Proceso Terminado", f"Se exportaron exitosamente {exitos} hojas de anotación en:\n{ruta_final}")
        else:
            messagebox.showinfo("Aviso", "No hay combates finalizados para exportar.")

    def verificar_visibilidad_confirmar_todas(self):
        if not hasattr(self, 'btn_confirmar_todas'): return
        
        total_divs = sum(len(p) for p in self.datos.values())
        if len(self.divisiones_bloqueadas) >= total_divs and total_divs > 0:
            self.btn_confirmar_todas.pack_forget()
        else:
            # Si faltan llaves y el botón estaba oculto, lo volvemos a mostrar
            if not self.btn_confirmar_todas.winfo_ismapped():
                # 'after' lo coloca exactamente a la derecha del botón regresar
                self.btn_confirmar_todas.pack(side="left", padx=5, after=self.btn_regresar)

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

    def exportar_imagen_llave(self, tab=None, ruta_directa=None):
        """Exporta la llave horneando el fondo y muestreando su color para eliminar bordes residuales."""
        self.cerrar_panel_combate() # <-- NUEVO: Elimina residuos visuales antes de la foto

        if not tab: tab = self.notebook.nametowidget(self.notebook.select())
        tab.canvas.update()
        
        region = tab.canvas.cget("scrollregion")
        if not region: return False
        
        x1, y1, x2, y2 = map(int, region.split())
        ancho, alto = (x2 - x1), (y2 - y1)
        estilo = getattr(tab, "estilo", "Estilo")
        peso = tab.cmb_peso.get() or "Peso"
        
        if not ruta_directa:
            ruta_directa = filedialog.asksaveasfilename(
                defaultextension=".png", filetypes=[("Imagen PNG", "*.png")],
                initialfile=f"Llave_{estilo}_{peso}.png"
            )
        if not ruta_directa: return False

        ps_temp = f"temp_export_{self.id_torneo}.ps"
        
        # --- 1. HORNEADO DE FONDO EXTENDIDO ---
        # Creamos un rectángulo gigante del mismo gris oscuro para tapar el "papel" de Ghostscript
        bg_color_hex = "#1e1e1e"
        bg_rect = tab.canvas.create_rectangle(x1-200, y1-200, x2+200, y2+200, 
                                              fill=bg_color_hex, outline=bg_color_hex, width=2)
        tab.canvas.tag_lower(bg_rect)

        try:
            tab.canvas.postscript(file=ps_temp, colormode='color', x=x1, y=y1, 
                                  width=ancho, height=alto, pagewidth=ancho, pageheight=alto)
            
            # Limpiamos el canvas inmediatamente para no afectar la UI
            tab.canvas.delete(bg_rect)

            with Image.open(ps_temp) as img:
                img.load(scale=4) 
                img = img.convert("RGB") # Convertimos a RGB puro
                
                # --- 2. RECORTE DE SEGURIDAD (Corta el marco blanco) ---
                # Cortamos 15 píxeles por lado. Como tenemos 60px de margen en la UI (que son 240px a scale=4), 
                # no tocaremos las casillas, pero amputamos cualquier borde raro de Ghostscript.
                recorte = 15
                img = img.crop((recorte, recorte, img.width - recorte, img.height - recorte))
                
                # --- 3. MUESTREO DE COLOR (El gotero) ---
                # Tomamos el color exacto que renderizó Ghostscript tomando un pixel de la esquina superior.
                # Esto garantiza que el lienzo se fusione perfectamente sin dejar líneas divisorias.
                color_fondo_real = img.getpixel((10, 10))

                # 4. Consultar Información del Torneo
                torneo_info = {"nombre": "Torneo", "lugar": "", "ciudad": "", "fecha": ""}
                conexion = self.db.conectar()
                if conexion:
                    try:
                        with conexion.cursor() as cur:
                            cur.execute("""
                                SELECT t.nombre, t.lugar_exacto, ciu.nombre, to_char(t.fecha_inicio, 'DD/MM/YYYY') 
                                FROM torneo t LEFT JOIN ciudad ciu ON t.id_ciudad = ciu.id 
                                WHERE t.id = %s
                            """, (self.id_torneo,))
                            res = cur.fetchone()
                            if res: torneo_info = {"nombre": res[0], "lugar": res[1] or "", "ciudad": res[2] or "", "fecha": res[3] or ""}
                    finally: conexion.close()

                # 5. Crear Lienzo Final con el color muestreado
                margen_top, margen_bottom, margen_x = 220, 150, 100
                final_w = max(img.width + (margen_x * 2), 1400)
                final_h = img.height + margen_top + margen_bottom
                
                lienzo = Image.new("RGB", (final_w, final_h), color_fondo_real)
                
                # Pegar imagen centrada
                offset_x = (final_w - img.width) // 2
                lienzo.paste(img, (offset_x, margen_top))
                
                draw = ImageDraw.Draw(lienzo)
                
                # 6. Rótulos Oficiales
                try:
                    font_titulo = ImageFont.truetype("arialbd.ttf", 65)
                    font_sub = ImageFont.truetype("arial.ttf", 38)
                    font_cat = ImageFont.truetype("arialbd.ttf", 55)
                except:
                    font_titulo = font_sub = font_cat = ImageFont.load_default()

                def escribir_derecha(texto, y, font, color):
                    bbox_t = draw.textbbox((0, 0), texto, font=font)
                    tw = bbox_t[2] - bbox_t[0]
                    draw.text((lienzo.width - tw - 80, y), texto, font=font, fill=color)

                escribir_derecha(torneo_info['nombre'].upper(), 45, font_titulo, "white")
                ubicacion = f"{torneo_info['lugar']}, {torneo_info['ciudad']}" if torneo_info['ciudad'] else torneo_info['lugar']
                escribir_derecha(f"{ubicacion}  |  {torneo_info['fecha']}", 130, font_sub, "#aaaaaa")
                
                cat_peso_txt = f"{estilo.upper()} - {peso}"
                bbox_c = draw.textbbox((0, 0), cat_peso_txt, font=font_cat)
                escribir_derecha(cat_peso_txt, lienzo.height - (bbox_c[3]-bbox_c[1]) - 70, font_cat, "#ffc107")

                # 7. Guardar
                lienzo.save(ruta_directa, "PNG", dpi=(300, 300))
            
            if os.path.exists(ps_temp): os.remove(ps_temp)
            return True
            
        except Exception as e:
            if 'bg_rect' in locals(): tab.canvas.delete(bg_rect)
            if os.path.exists(ps_temp): os.remove(ps_temp)
            messagebox.showerror("Error", f"Fallo al crear imagen: {e}")
            return False

    def exportar_todas_las_imagenes(self):
        """Crea carpeta con ID_Torneo/Categoría_Peso.png en el directorio elegido."""
        self.cerrar_panel_combate() # <-- NUEVO: Elimina residuos visuales antes de la foto

        dir_padre = filedialog.askdirectory(title="Seleccione dónde crear la carpeta de llaves")
        if not dir_padre: return

        nombre_carpeta = f"Torneo_{self.id_torneo}_Llaves_IMG"
        ruta_final = os.path.join(dir_padre, nombre_carpeta)
        if not os.path.exists(ruta_final): os.makedirs(ruta_final)

        for tab in self.notebook.winfo_children():
            if not hasattr(tab, "cmb_peso"): continue
            
            estilo = getattr(tab, "estilo")
            for p in tab.cmb_peso['values']:
                tab.cmb_peso.set(p)
                self.procesar_y_dibujar(tab)
                self.update() # Forzar refresco para capturar atletas reales
                
                nombre_archivo = f"{estilo}_{p}.png".replace(" ", "_")
                self.exportar_imagen_llave(tab, os.path.join(ruta_final, nombre_archivo))

        messagebox.showinfo("Proceso Terminado", f"Imágenes guardadas en:\n{ruta_final}")

    def cargar_config_pdf(self):
        ruta_config = "config_pdf.json"
        
        # Estructura maestra que incluye estilos y los "saltos" matemáticos para matrices
        def estilo(coords, size=9, align="Izquierda", bold=False, color="#000000", step_x=0, step_y=0):
            return {"coords": coords, "align": align, "valign": "Medio", "font": "Helvetica", "size": size, "bold": bold, "italic": False, "underline": False, "color": color, "step_x": step_x, "step_y": step_y}

        defaults = {
            "torneo_box": estilo([65, 120, 310, 150], 10, "Centro", True), 
            "arbitro_nom": estilo([360, 105, 540, 125], 8), "arbitro_id": estilo([550, 105, 580, 125], 8, "Centro"),
            "juez_nom": estilo([360, 128, 540, 148], 8), "juez_id": estilo([550, 128, 580, 148], 8, "Centro"),
            "jefe_nom": estilo([360, 150, 540, 170], 8), "jefe_id": estilo([550, 150, 580, 170], 8, "Centro"),
            "fecha": estilo([65, 193, 130, 213], 9, "Centro"), "match_id": estilo([135, 193, 205, 213], 9, "Centro"), 
            "peso": estilo([210, 193, 265, 213], 9, "Centro"), "estilo": estilo([270, 193, 345, 213], 9, "Centro"), 
            "ronda": estilo([350, 193, 400, 213], 9, "Centro"), "fase": estilo([405, 193, 465, 213], 9, "Centro"), "tapiz": estilo([470, 193, 530, 213], 9, "Centro"),
            "rojo_nom": estilo([75, 244, 180, 264], 8), "rojo_club": estilo([183, 244, 275, 264], 7), "rojo_id": estilo([280, 244, 305, 264], 8, "Centro"),
            "azul_nom": estilo([322, 244, 425, 264], 8), "azul_club": estilo([429, 244, 515, 264], 7), "azul_id": estilo([520, 244, 545, 264], 8, "Centro"),
            
            # --- NUEVOS CAMPOS: PUNTOS, TOTALES Y CHEQUES ---
            "pts_r_p1": estilo([110, 278, 125, 298], 10, "Centro", False, "#cc0000", 15, 0),
            "pts_r_p2": estilo([110, 306, 125, 326], 10, "Centro", False, "#cc0000", 15, 0),
            "pts_a_p1": estilo([358, 278, 373, 298], 10, "Centro", False, "#0000cc", 15, 0),
            "pts_a_p2": estilo([358, 306, 373, 326], 10, "Centro", False, "#0000cc", 15, 0),
            "subtot_r_p1": estilo([260, 278, 285, 298], 11, "Centro", True, "#cc0000"),
            "subtot_r_p2": estilo([260, 306, 285, 326], 11, "Centro", True, "#cc0000"),
            "subtot_a_p1": estilo([510, 278, 535, 298], 11, "Centro", True, "#0000cc"),
            "subtot_a_p2": estilo([510, 306, 535, 326], 11, "Centro", True, "#0000cc"),
            "total_pts_r": estilo([70, 345, 110, 375], 16, "Centro", True, "#cc0000"),
            "total_pts_a": estilo([500, 345, 540, 375], 16, "Centro", True, "#0000cc"),
            "clas_pts_r": estilo([240, 395, 275, 425], 16, "Centro", True, "#cc0000"),
            "clas_pts_a": estilo([330, 395, 365, 425], 16, "Centro", True, "#0000cc"),
            "ganador_nom": estilo([75, 435, 250, 460], 11, "Izquierda", True),
            "hora_fin": estilo([430, 435, 530, 460], 11, "Centro", False),
            "check_vic": estilo([80, 485, 105, 500], 10, "Centro", False, "#00aa00", 0, 23)
        }
        
        # Corrigiendo el typo de la variable clas_pts_a
        defaults["clas_pts_a"] = estilo([330, 395, 365, 425], 16, "Centro", True, "#0000cc")
        
        if os.path.exists(ruta_config):
            try:
                with open(ruta_config, "r", encoding="utf-8") as f:
                    cargado = json.load(f)
                    for k, v in cargado.items():
                        if isinstance(v, list): 
                            cargado[k] = estilo(v)
                            if k in defaults: 
                                cargado[k]["align"] = defaults[k]["align"]
                                cargado[k]["size"] = defaults[k]["size"]
                                cargado[k]["bold"] = defaults[k]["bold"]
                        else:
                            for prop in ["align", "valign", "font", "size", "bold", "italic", "underline", "color", "step_x", "step_y"]:
                                if prop not in v: v[prop] = defaults.get(k, estilo(v.get("coords", [0,0,50,20]))).get(prop)

                    defaults.update(cargado)
            except: pass
        return defaults

    def guardar_config_pdf(self, config):
        with open("config_pdf.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

    def regresar_a_inscripcion(self):
        """Regresa a la pantalla de inscripción manteniendo la conexión de red activa."""
        self.cerrar_panel_combate()
            
        from ui.pantallas.pantalla_inscripcion import PantallaInscripcion
        p_inscripcion = self.controller.pantallas.get(PantallaInscripcion)
        if p_inscripcion:
            p_inscripcion.refrescar_estado_bloqueos()
            
        self.controller.mostrar_pantalla(PantallaInscripcion)

    def cargar_torneo(self, id_torneo):
        """Intercepta la carga para heredar la sesión de red automáticamente o bloquear si ya terminó."""
        self.id_torneo = id_torneo
        
        # Verificar si el torneo está cerrado ANTES de armar la red
        conexion = self.db.conectar()
        self.torneo_cerrado_en_db = False
        if conexion:
            try:
                with conexion.cursor() as cur:
                    cur.execute("SELECT fecha_fin FROM torneo WHERE id = %s", (self.id_torneo,))
                    res = cur.fetchone()
                    if res and res[0] is not None: self.torneo_cerrado_en_db = True
            finally: conexion.close()
            
        if self.torneo_cerrado_en_db:
            # Bypass: Entra directo en modo visualización
            self.iniciar_torneo_red(None, False, "Visualización")
        else:
            # Heredar silenciosamente los datos de sesión desde el Controller
            id_conn = getattr(self.controller, 'id_conexion_red', None)
            es_master = getattr(self.controller, 'es_master', False)
            tapiz = getattr(self.controller, 'tapiz_asignado', 'Pendiente')
            
            self.iniciar_torneo_red(id_conn, es_master, tapiz)

    def iniciar_torneo_red(self, id_conexion, es_master, tapiz):
        self.id_conexion_red = id_conexion
        self.es_master = es_master
        self.tapiz_asignado = tapiz

        # --- NUEVO: Lógica de visibilidad del botón de red ---
        if self.es_master:
            self.btn_gestion_red.pack(side="right", padx=10, pady=5)
        else:
            self.btn_gestion_red.pack_forget()

        self.escuchando_red = True

        inscripciones = self.db.obtener_inscripciones_pareo(self.id_torneo)
        
        for widget in self.contenedor_principal.winfo_children(): widget.destroy()
        self.datos.clear()
        self.resultados_combates = self.db.cargar_resultados_combates(self.id_torneo)

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

        self.pre_cargar_memoria()
        
        self.frame_llaves = ttk.Frame(self.contenedor_principal)
        self.frame_llaves.pack(side="left", fill="both", expand=True)

        self.notebook = ttk.Notebook(self.frame_llaves)
        self.notebook.pack(fill="both", expand=True, padx=(20, 10), pady=10)

        # --- NUEVO: BUSCADOR DE ATLETAS EN LLAVES ---
        
        self.idx_busqueda = -1
        # ---------------------------------------------

        self.tab_cartelera = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_cartelera, text="📋 CARTELERA GENERAL")
        self.construir_interfaz_cartelera()
        self.notebook.bind("<<NotebookTabChanged>>", self.al_cambiar_pestana)

        for estilo, pesos_dict in self.datos.items():
            tab = ttk.Frame(self.notebook, padding=10)
            self.notebook.add(tab, text=estilo)
            self.construir_tab_estilo(tab, estilo, pesos_dict)
            
        self.verificar_estado_torneo()
        self.gestionar_botones_globales()
        self.actualizar_bucle_red()

    def actualizar_bucle_red(self):
        if not getattr(self, "escuchando_red", False): return

        # --- 0. DETECCIÓN INSTANTÁNEA DE CIERRE DE TORNEO ---
        if not getattr(self, "torneo_cerrado_en_db", False):
            conexion = self.db.conectar()
            if conexion:
                try:
                    with conexion.cursor() as cur:
                        # CORRECCIÓN: Apuntando a la tabla 'torneo' y evaluando 'fecha_fin'
                        cur.execute("SELECT fecha_fin FROM torneo WHERE id = %s", (self.id_torneo,))
                        res = cur.fetchone()
                        
                        if res and res[0] is not None:
                            self.torneo_cerrado_en_db = True
                            self.controller.torneo_finalizado = True
                            self.escuchando_red = False # Apaga el motor de red permanentemente
                            self.cerrar_panel_combate() # Cierra cualquier pelea abierta
                            
                            self.verificar_estado_torneo() # Transforma toda la UI
                            self.actualizar_cartelera()    # Obliga a cambiar al Historial
                            
                            messagebox.showinfo("Torneo Finalizado", "El Director ha cerrado oficialmente el torneo.\n\nEl sistema de red se ha desconectado y has pasado a modo de Solo Lectura (Visitante).")
                            return # Cortamos la ejecución
                except Exception as e:
                    pass
                finally:
                    conexion.close()

        # --- 1. VERIFICACIÓN DE SUPERVIVENCIA Y CAMBIOS DE ROL ---
        if not getattr(self, "torneo_cerrado_en_db", False) and hasattr(self, 'id_conexion_red') and self.id_conexion_red:
            mi_estado = self.db.verificar_estado_mi_conexion(self.id_conexion_red)
            
            # --- NUEVO: TOLERANCIA DE RED (Previene expulsiones por carga de interfaz o BD) ---
            if not hasattr(self, 'strikes_desconexion'): self.strikes_desconexion = 0
            
            # A) Expulsión o Corte de Red
            if not mi_estado or (not mi_estado.get('es_master', False) and mi_estado.get('estado_conexion') != 'Aprobado'):
                self.strikes_desconexion += 1
                # Si falla 3 veces seguidas (aprox 9 segundos), asumimos que la expulsión es real
                if self.strikes_desconexion >= 3:
                    self.escuchando_red = False 
                    self.cerrar_panel_combate() 
                    messagebox.showwarning("Desconectado", "El Director del torneo ha cerrado tu sesión, o se perdió la conexión con el servidor.")
                    self.regresar_a_inscripcion()
                    return 
            else:
                self.strikes_desconexion = 0 # La conexión es saludable, reseteamos a 0.

                # B) Detección de transferencia de poder (Máster)
                estado_master_bd = mi_estado.get('es_master', False)
                if estado_master_bd != getattr(self, "es_master", False):
                    self.es_master = estado_master_bd
                    self.controller.es_master = estado_master_bd
                    
                    if self.es_master:
                        self.btn_gestion_red.pack(side="right", padx=10, pady=5)
                    else:
                        self.btn_gestion_red.pack_forget()
                        if hasattr(self, 'popup_red') and self.popup_red.winfo_exists():
                            self.popup_red.destroy()
                            
                    self.verificar_estado_torneo()

                # C) Actualización dinámica de mi Tapiz asignado
                nuevo_tapiz = mi_estado.get('tapiz_asignado') or "Pendiente"
                if nuevo_tapiz != getattr(self.controller, 'tapiz_asignado', ''):
                    self.controller.tapiz_asignado = nuevo_tapiz
                    self.tapiz_asignado = nuevo_tapiz

        # 2. Actualizar etiqueta superior con el tapiz asignado
        if hasattr(self, 'lbl_mi_tapiz_header'):
            tapiz_actual = getattr(self.controller, 'tapiz_asignado', 'Pendiente')
            color_tapiz = "#28a745" if tapiz_actual != "Pendiente" else "#f39c12"
            self.lbl_mi_tapiz_header.config(text=f"📍 Tapiz Asignado: {tapiz_actual}", foreground=color_tapiz)

        # --- LÓGICA DEL PANEL FLOTANTE DE RED ---
        if hasattr(self.db, 'obtener_conexiones_torneo'):
            conexiones = self.db.obtener_conexiones_torneo(self.id_torneo)
            
            # Badge de Notificación Inteligente para el Master
            if getattr(self, "es_master", False) and hasattr(self, "btn_gestion_red"):
                pendientes = sum(1 for c in conexiones if c.get('estado_conexion') == 'Esperando')
                if pendientes > 0:
                    self.btn_gestion_red.config(text=f"👥 Gestionar Red ({pendientes} Solicitudes)", bg="#fd7e14")
                else:
                    self.btn_gestion_red.config(text="👥 Gestionar Red", bg="#17a2b8")

            # Actualizar la tabla solo si el popup de Master está abierto
            if hasattr(self, 'popup_red') and self.popup_red.winfo_exists() and hasattr(self, 'tabla_red_popup'):
                
                # A) GUARDAR LA SELECCIÓN ACTUAL
                selecciones_guardadas = []
                for item_id in self.tabla_red_popup.selection():
                    item_val = self.tabla_red_popup.item(item_id, 'values')
                    if item_val: selecciones_guardadas.append(str(item_val[0]))
                
                # B) BORRAR TABLA
                for item in self.tabla_red_popup.get_children():
                    self.tabla_red_popup.delete(item)

                # C) RE-INSERTAR DATOS
                nuevos_items = {}
                for c in conexiones:
                    es_yo = (c['id_conexion'] == getattr(self, "id_conexion_red", -1))
                    tag = "yo_mismo" if es_yo else ("confirmado" if c['estado_conexion'] == 'Aprobado' else "pendiente")
                    nombre_visual = f"⭐ {c['nombre']} {c['apellidos']}" if c.get('es_master') else f"{c['nombre']} {c['apellidos']}"
                    tapiz_visual = c['tapiz_asignado'] or "N.A."
                    
                    item_insertado = self.tabla_red_popup.insert("", "end", values=(c['id_conexion'], nombre_visual, c['nombre_dispositivo'], tapiz_visual, c['estado_conexion']), tags=(tag,))
                    nuevos_items[str(c['id_conexion'])] = item_insertado
                
                # D) RESTAURAR SELECCIÓN Y FOCO
                for id_guardado in selecciones_guardadas:
                    if id_guardado in nuevos_items:
                        self.tabla_red_popup.selection_add(nuevos_items[id_guardado])
                        self.tabla_red_popup.focus(nuevos_items[id_guardado])
                
                # E) RE-EVALUAR LOS BOTONES DE LA UI
                self.evaluar_seleccion_red()
        # -----------------------------------------------

        # 2. Descargar combates bloqueados (en progreso)
        nuevos_combates = self.db.obtener_combates_en_curso(self.id_torneo) if hasattr(self.db, 'obtener_combates_en_curso') else {}

        # 3. Descargar resultados de combates ya finalizados
        nuevos_resultados = self.db.cargar_resultados_combates(self.id_torneo) if hasattr(self.db, 'cargar_resultados_combates') else getattr(self, 'resultados_combates', {})

        # 4. Detectar si hubo cambios en progreso o en ganadores
        estado_anterior_curso = getattr(self, 'combates_en_curso_red', {})
        estado_anterior_resultados = getattr(self, 'resultados_combates', {})
        hubo_cambios = (nuevos_combates != estado_anterior_curso) or (nuevos_resultados != estado_anterior_resultados)
        
        self.combates_en_curso_red = nuevos_combates
        
        # Si hubo nuevos ganadores, reconstruimos la matriz lógica ANTES de dibujar
        if nuevos_resultados != estado_anterior_resultados:
            self.resultados_combates = nuevos_resultados
            self.pre_cargar_memoria() 

        # 5. Refrescar la interfaz SOLO si hubo un cambio real para evitar parpadeos
        if self.notebook.tabs() and self.notebook.select():
            if hubo_cambios:
                idx_pestana = self.notebook.index(self.notebook.select())
                if idx_pestana == 0:
                    self.actualizar_cartelera()
                else:
                    tab_actual = self.notebook.nametowidget(self.notebook.select())
                    self.procesar_y_dibujar(tab_actual)
                self.verificar_estado_torneo()
        
        # 6. Latido de supervivencia
        if hasattr(self, 'id_conexion_red') and self.id_conexion_red and hasattr(self.db, 'ping_actividad_conexion'):
            self.db.ping_actividad_conexion(self.id_conexion_red)

        # Repetir bucle
        self.after(3000, self.actualizar_bucle_red)

    # ================= MÉTODOS DE RED EN PAREO (POPUP MÁSTER) =================
    def abrir_panel_red(self):
        """Abre un panel flotante con la gestión de red sin salir de la pantalla de pareo."""
        if hasattr(self, 'popup_red') and self.popup_red.winfo_exists():
            self.popup_red.lift()
            return

        self.popup_red = tk.Toplevel(self)
        self.popup_red.title("Gestión de Red (Torneo en Vivo)")
        self.popup_red.geometry("700x320")
        self.popup_red.transient(self)
        
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (700 // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (320 // 2)
        self.popup_red.geometry(f"+{x}+{y}")

        columnas_red = ("ID", "Usuario", "Dispositivo", "Tapiz", "Estado")
        self.tabla_red_popup = ttk.Treeview(self.popup_red, columns=columnas_red, show="headings", height=8, selectmode="extended")
        self.tabla_red_popup.heading("ID", text="ID")
        self.tabla_red_popup.heading("Usuario", text="Oficial / Árbitro")
        self.tabla_red_popup.heading("Dispositivo", text="Dispositivo")
        self.tabla_red_popup.heading("Tapiz", text="Tapiz Asignado")
        self.tabla_red_popup.heading("Estado", text="Estado")

        self.tabla_red_popup.column("ID", width=30, anchor="center")
        self.tabla_red_popup.column("Usuario", width=180)
        self.tabla_red_popup.column("Dispositivo", width=120)
        self.tabla_red_popup.column("Tapiz", width=100, anchor="center")
        self.tabla_red_popup.column("Estado", width=100, anchor="center")

        self.tabla_red_popup.tag_configure("yo_mismo", background="#d4edda")
        self.tabla_red_popup.tag_configure("pendiente", background="#fff3cd")
        self.tabla_red_popup.tag_configure("confirmado", background="#ffffff")
        self.tabla_red_popup.pack(fill="both", expand=True, padx=10, pady=10)

        # CONTROLES DE RED
        frame_controles = tk.Frame(self.popup_red)
        frame_controles.pack(fill="x", padx=10, pady=5)

        # Corregido: Solo dice "Aprobar", ya no "Asignar"
        self.btn_aprobar_red = tk.Button(frame_controles, text="✅ Aprobar", bg="#28a745", fg="white", state="disabled", command=self.aprobar_conexion)
        self.btn_aprobar_red.pack(side="left", padx=5)
        
        self.btn_rechazar_red = tk.Button(frame_controles, text="❌ Expulsar / Rechazar", bg="#dc3545", fg="white", state="disabled", command=self.rechazar_conexion)
        self.btn_rechazar_red.pack(side="left", padx=5)

        self.btn_hacer_master = tk.Button(frame_controles, text="👑 Ceder Máster", bg="#ffc107", fg="black", state="disabled", command=self.ceder_master)
        self.btn_hacer_master.pack(side="left", padx=5)

        ttk.Separator(frame_controles, orient="vertical").pack(side="left", fill="y", padx=10)
        
        self.btn_intercambiar_tapiz = tk.Button(frame_controles, text="🔀 Intercambiar Tapices", bg="#6f42c1", fg="white", state="disabled", command=self.intercambiar_tapices)
        self.btn_intercambiar_tapiz.pack(side="left", padx=5)

        self.tabla_red_popup.bind("<<TreeviewSelect>>", self.evaluar_seleccion_red)
        self.actualizar_bucle_red()

    def evaluar_seleccion_red(self, event=None):
        if not hasattr(self, 'tabla_red_popup') or not self.tabla_red_popup.winfo_exists(): return
        sel = self.tabla_red_popup.selection()
        
        if len(sel) == 1:
            item = self.tabla_red_popup.item(sel[0])
            estado = item['values'][4]
            es_master = "⭐" in str(item['values'][1])
            es_yo_mismo = item['values'][0] == getattr(self, "id_conexion_red", -1)
            
            if es_master or es_yo_mismo:
                self.btn_aprobar_red.config(state="disabled")
                self.btn_rechazar_red.config(state="disabled")
                self.btn_hacer_master.config(state="disabled")
                self.btn_intercambiar_tapiz.config(state="disabled")
            else:
                self.btn_intercambiar_tapiz.config(state="disabled")
                if estado == 'Esperando':
                    self.btn_aprobar_red.config(state="normal")
                    self.btn_rechazar_red.config(state="normal")
                    self.btn_hacer_master.config(state="disabled")
                elif estado == 'Aprobado':
                    # CORREGIDO: Bloquea el botón "Aprobar" si ya está aprobado, igual que en Inscripción
                    self.btn_aprobar_red.config(state="disabled") 
                    self.btn_rechazar_red.config(state="normal")
                    self.btn_hacer_master.config(state="normal")
                else:
                    self.btn_aprobar_red.config(state="disabled")
                    self.btn_rechazar_red.config(state="disabled")
                    self.btn_hacer_master.config(state="disabled")
                    
        elif len(sel) == 2:
            self.btn_aprobar_red.config(state="disabled")
            self.btn_rechazar_red.config(state="disabled")
            self.btn_hacer_master.config(state="disabled")
            
            item1 = self.tabla_red_popup.item(sel[0])
            item2 = self.tabla_red_popup.item(sel[1])
            est1, est2 = item1['values'][4], item2['values'][4]
            mas1, mas2 = "⭐" in str(item1['values'][1]), "⭐" in str(item2['values'][1])
            
            if est1 == 'Aprobado' and est2 == 'Aprobado' and not mas1 and not mas2:
                self.btn_intercambiar_tapiz.config(state="normal")
            else:
                self.btn_intercambiar_tapiz.config(state="disabled")
        else:
            self.btn_aprobar_red.config(state="disabled")
            self.btn_rechazar_red.config(state="disabled")
            self.btn_hacer_master.config(state="disabled")
            self.btn_intercambiar_tapiz.config(state="disabled")

    def aprobar_conexion(self):
        if not hasattr(self, 'tabla_red_popup') or not self.tabla_red_popup.winfo_exists(): return
        sel = self.tabla_red_popup.selection()
        if not sel: return
        
        item = self.tabla_red_popup.item(sel[0])
        id_conexion = item['values'][0]

        # --- LÓGICA DE ASIGNACIÓN AUTOMÁTICA EXTRAÍDA DE INSCRIPCIÓN ---
        conexiones = self.db.obtener_conexiones_torneo(self.id_torneo)
        tapices_ocupados = [c['tapiz_asignado'] for c in conexiones if c['tapiz_asignado'] and c['estado_conexion'] == 'Aprobado']
        
        num_tapices_global = getattr(self.controller, 'num_tapices', 4)
        tapiz_a_asignar = None

        for i in range(num_tapices_global):
            tapiz_candidato = f"Tapiz {chr(65+i)}"
            if tapiz_candidato not in tapices_ocupados:
                tapiz_a_asignar = tapiz_candidato
                break
        
        if not tapiz_a_asignar:
            messagebox.showwarning("Sin Tapices", "No hay tapices disponibles. Por favor, asigne más tapices al torneo o expulse a un cliente.", parent=self.popup_red)
            return

        # Aprobar y Asignar automáticamente en la DB
        if hasattr(self.db, 'aprobar_conexion_cliente'):
            if self.db.aprobar_conexion_cliente(id_conexion):
                self.db.asignar_tapiz_a_cliente(id_conexion, tapiz_a_asignar)
                self.actualizar_bucle_red()
        else:
            conexion = self.db.conectar()
            if conexion:
                try:
                    with conexion.cursor() as cur:
                        cur.execute("UPDATE conexiones_torneo SET estado_conexion = 'Aprobado', tapiz_asignado = %s WHERE id = %s", (tapiz_a_asignar, id_conexion,))
                        conexion.commit()
                except Exception: pass
                finally: conexion.close()
            self.actualizar_bucle_red()

    def rechazar_conexion(self):
        if not hasattr(self, 'tabla_red_popup') or not self.tabla_red_popup.winfo_exists(): return
        sel = self.tabla_red_popup.selection()
        if not sel: return
        
        item = self.tabla_red_popup.item(sel[0])
        id_conexion = item['values'][0]
        
        if id_conexion == getattr(self, "id_conexion_red", -1):
            return messagebox.showerror("Error", "No puedes expulsarte a ti mismo.", parent=self.popup_red)

        if messagebox.askyesno("Confirmar", "¿Expulsar / Rechazar a este cliente?", parent=self.popup_red):
            if self.db.rechazar_conexion_cliente(id_conexion):
                self.actualizar_bucle_red()

    def ceder_master(self):
        sel = self.tabla_red_popup.selection()
        if not sel: return
        
        item = self.tabla_red_popup.item(sel[0])
        id_conexion = item['values'][0]
        nombre_usuario = item['values'][1]
        estado = item['values'][4]
        
        if id_conexion == getattr(self, "id_conexion_red", -1):
            return messagebox.showinfo("Aviso", "Ya eres el Director (Máster) del torneo.", parent=self.popup_red)
            
        if estado != 'Aprobado':
            return messagebox.showwarning("Estado", "El cliente debe estar aprobado antes de cederle el control.", parent=self.popup_red)
            
        if messagebox.askyesno("Ceder Control", f"¿Está seguro de transferir los permisos de Máster a {nombre_usuario}?\n\nUsted pasará a ser un Oficial Invitado y perderá los privilegios de administración.", parent=self.popup_red):
            if self.db.transferir_master(self.id_torneo, id_conexion):
                self.es_master = False
                self.controller.es_master = False
                self.btn_gestion_red.pack_forget() 
                self.popup_red.destroy() 
                messagebox.showinfo("Control Cedido", "Se han transferido los permisos exitosamente.")
                self.verificar_estado_torneo()

    def intercambiar_tapices(self):
        sel = self.tabla_red_popup.selection()
        if len(sel) != 2: return
        
        item1 = self.tabla_red_popup.item(sel[0])
        item2 = self.tabla_red_popup.item(sel[1])
        
        id1, tapiz1, estado1 = item1['values'][0], item1['values'][3], item1['values'][4]
        id2, tapiz2, estado2 = item2['values'][0], item2['values'][3], item2['values'][4]
        
        if estado1 != 'Aprobado' or estado2 != 'Aprobado':
            return messagebox.showwarning("Estado", "Ambos clientes deben estar aprobados para intercambiar sus tapices.", parent=self.popup_red)
            
        if tapiz1 == tapiz2:
            return messagebox.showinfo("Aviso", "Ambos clientes ya están en el mismo tapiz.", parent=self.popup_red)

        if self.db.asignar_tapiz_a_cliente(id1, tapiz2) and self.db.asignar_tapiz_a_cliente(id2, tapiz1):
            self.actualizar_bucle_red()
            messagebox.showinfo("Éxito", "Tapices intercambiados correctamente.", parent=self.popup_red)

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

    def verificar_estado_torneo(self):
        """Mantiene el botón en Rojo hasta que el usuario cierre el torneo manualmente, respetando roles de red."""
        # Dispara la actualización de la etiqueta superior en tiempo real
        self.actualizar_estado_torneo()

        # Si ya se cerró y se guardó en la BD, todos ven el botón de Exportar (Verde) y activo
        if getattr(self, "torneo_cerrado_en_db", False) or getattr(self.controller, "torneo_finalizado", False):
            self.btn_cerrar_torneo.config(text="📄 EXPORTAR REPORTE PDF", bg="#28a745", state="normal", command=self.generar_reporte_pdf)
            
            # --- CAMBIO: Ocultar rb_pendientes (nombre correcto) ---
            if hasattr(self, 'rb_pendientes'):
                try: self.rb_pendientes.pack_forget() 
                except: pass
                
            if hasattr(self, 'rb_historial'):
                self.rb_historial.config(state="normal")
            if hasattr(self, 'filtro_cartelera'):
                self.filtro_cartelera.set("Historial")
                
            if hasattr(self, 'btn_gestion_red'):
                self.btn_gestion_red.pack_forget()
            if hasattr(self, 'lbl_mi_tapiz_header'):
                self.lbl_mi_tapiz_header.config(text="🏁 Torneo Finalizado (Modo Visitante)", foreground="#17a2b8")
            
            self.escuchando_red = False
            return

        # Si no se ha cerrado en BD, evaluamos los roles
        if getattr(self, "es_master", False):
            self.btn_cerrar_torneo.config(text="🏆 CERRAR TORNEO Y GENERAR REPORTE", bg="#ff4d4d", state="normal", command=self.cerrar_torneo)
        else:
            self.btn_cerrar_torneo.config(text="📄 EXPORTAR REPORTE PDF", bg="#6c757d", state="disabled")

    # ================= SISTEMA DE CARTELERA (ORDEN DE COMBATES) =================
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
        total_finalizados = sum(len(matches) for matches in getattr(self, "resultados_combates", {}).values())

        self.cartelera_bloqueada = total_bloqueadas == 0

        # --- ESCUDO DEFINITIVO PARA TORNEOS CERRADOS ---
        if getattr(self, "torneo_cerrado_en_db", False) or getattr(self.controller, "torneo_finalizado", False):
            if hasattr(self, 'rb_pendientes'):
                try: self.rb_pendientes.pack_forget() 
                except: pass
                
            if hasattr(self, 'rb_historial'):
                self.rb_historial.config(state="normal") 
                
            # Si intentó pasarse a Pendientes, lo forzamos de vuelta a Historial
            if not self.modo_historial:
                self.filtro_cartelera.set("Historial")
                self.modo_historial = True
        else:
            # Comportamiento normal si el torneo sigue vivo
            if hasattr(self, 'rb_pendientes'):
                # Si estaba oculto, lo volvemos a mostrar ANTES del de historial
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
                            
        # Evaluamos qué vista quiere el usuario
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

    # ================= LÓGICA MATEMÁTICA Y DIBUJO =================
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

    # ================= EVENTOS DE INTERACCIÓN =================
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

    

    def imprimir_combate(self, match_node, estilo, peso):
        """Genera el PDF y lo abre para que el usuario pueda imprimirlo nativamente (Evita Error 1155)."""
        import tempfile
        import time
        
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, f"acta_combate_{match_node['match_id']}_{int(time.time())}.pdf")
        
        # Generar silenciosamente
        self.exportar_pdf(match_node, estilo, peso, ruta_directa=temp_file)
        
        # Abrir archivo con el lector de PDF por defecto
        if os.path.exists(temp_file):
            try:
                os.startfile(temp_file)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir el archivo PDF.\n\nDetalle: {e}")

    # ================= EXPORTACIÓN A PDF DESDE PAREO =================
    def exportar_pdf(self, match_node, estilo, peso, ruta_directa=None, preview_mode=False, config_override=None, zoom_factor=1.5):
        if not PDF_DISPONIBLE: 
            if not preview_mode and not ruta_directa: messagebox.showerror("Error", "PyMuPDF no está instalada.")
            return None
            
        ruta_plantilla = "hoja_anotacion.pdf" 
        if not os.path.exists(ruta_plantilla): 
            if not preview_mode and not ruta_directa: messagebox.showerror("Error", f"No se encontró '{ruta_plantilla}'.")
            return None

        cfg = config_override if config_override else self.cargar_config_pdf()

        p_rojo = self.obtener_peleador_real(match_node["peleador_rojo"])
        p_azul = self.obtener_peleador_real(match_node["peleador_azul"])
        ganador_data = match_node.get("ganador", {})
        id_combate = ganador_data.get("id_combate")

        apellido_rojo = p_rojo['nombre'].split(',')[0].replace(' ', '_') if p_rojo else "Rojo"
        apellido_azul = p_azul['nombre'].split(',')[0].replace(' ', '_') if p_azul else "Azul"

        if not preview_mode and not ruta_directa:
            ruta_guardado = filedialog.asksaveasfilename(
                defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                initialfile=f"Hoja_Puntuacion_R{match_node['ronda']}_{apellido_rojo}_vs_{apellido_azul}.pdf"
            )
            if not ruta_guardado: return None
        else:
            ruta_guardado = ruta_directa

        # 1. Recuperar datos de BD
        torneo_nombre = "Torneo"
        torneo_fecha = "--/--/----"
        hora_fin_combate = "" 
        
        id_arbitro = str(ganador_data.get("id_arbitro", ""))
        id_juez = str(ganador_data.get("id_juez", ""))
        id_jefe = str(ganador_data.get("id_jefe_tapiz", ""))
        id_rojo_str = str(p_rojo['id']) if p_rojo and p_rojo['id'] != -1 else ""
        id_azul_str = str(p_azul['id']) if p_azul and p_azul['id'] != -1 else ""

        conexion = self.db.conectar()
        if conexion:
            try:
                with conexion.cursor() as cur:
                    if id_combate:
                        cur.execute("""
                            SELECT t.nombre, to_char(t.fecha_inicio, 'DD/MM/YYYY'), to_char(c.hora_fin, 'HH24:MI')
                            FROM combate c JOIN torneo_division td ON c.id_torneo_division = td.id JOIN torneo t ON td.id_torneo = t.id
                            WHERE c.id = %s
                        """, (id_combate,))
                        res = cur.fetchone()
                        if res: torneo_nombre, torneo_fecha, hora_fin_combate = res
            except Exception: pass
            finally: conexion.close()

        oficiales_db = self.db.obtener_oficiales()
        dict_oficiales = {o['id']: f"{o['apellidos']}, {o['nombre']}" for o in oficiales_db}
        nom_arbitro = dict_oficiales.get(ganador_data.get("id_arbitro"), "")
        nom_juez = dict_oficiales.get(ganador_data.get("id_juez"), "")
        nom_jefe = dict_oficiales.get(ganador_data.get("id_jefe_tapiz"), "")

        puntos_historicos = self.db.obtener_puntuacion_combate(id_combate) if id_combate else []

        nombre_ganador = ganador_data.get("nombre", "")
        motivo_victoria = ganador_data.get("motivo_victoria", "")
        codigo_victoria = motivo_victoria.split(" - ")[0] if motivo_victoria else ""

        # ================= INYECCIÓN DE DATOS AL PDF =================
        try:
            doc = fitz.open(ruta_plantilla)
            page = doc[0]

            def hex_a_rgb(hex_color):
                hex_color = hex_color.lstrip('#')
                return tuple(int(hex_color[i:i+2], 16)/255.0 for i in (0, 2, 4))

            # --- NUEVA FUNCIÓN MAESTRA BASADA EN MATEMÁTICAS INFALIBLES ---
            def escribir_caja(texto, config_dict, is_multiline=False):
                if texto is None or str(texto).strip() == "" or "coords" not in config_dict: return
                texto_str = str(texto).strip()
                
                rect = fitz.Rect(config_dict["coords"])
                al = config_dict.get("align", "Izquierda")
                valign = config_dict.get("valign", "Medio")
                font_base = config_dict.get("font", "Helvetica")
                b = config_dict.get("bold", False)
                i = config_dict.get("italic", False)
                
                if font_base == "Helvetica": fname = "heboit" if b and i else "hebo" if b else "heit" if i else "helv"
                elif font_base == "Times": fname = "tiboit" if b and i else "tibo" if b else "tiit" if i else "tiro"
                else: fname = "coboit" if b and i else "cobo" if b else "coit" if i else "cour"
                
                color = hex_a_rgb(config_dict.get("color", "#000000"))
                size = config_dict.get("size", 10)

                if is_multiline:
                    al_map = {"Izquierda": fitz.TEXT_ALIGN_LEFT, "Centro": fitz.TEXT_ALIGN_CENTER, "Derecha": fitz.TEXT_ALIGN_RIGHT}
                    page.insert_textbox(rect, texto_str, fontsize=size, fontname=fname, align=al_map.get(al, 0), color=color)
                else:
                    tw = len(texto_str) * (size * 0.55) 
                    if al == "Centro": x = rect.x0 + (rect.width - tw) / 2
                    elif al == "Derecha": x = rect.x1 - tw - 2
                    else: x = rect.x0 + 2
                    
                    ascender = size * 0.8
                    if valign == "Arriba": y = rect.y0 + ascender
                    elif valign == "Abajo": y = rect.y1 - (size * 0.2)
                    else: y = rect.y0 + (rect.height / 2) + (ascender / 2) - 1 
                    
                    page.insert_text(fitz.Point(x, y), texto_str, fontsize=size, fontname=fname, color=color)
                
                if config_dict.get("underline", False):
                    page.draw_line(fitz.Point(rect.x0, rect.y1), fitz.Point(rect.x1, rect.y1), color=color, width=1)

            # --- SIMULADOR VISUAL Y FORMATEO DE GANADOR ---
            hubo_combate = match_node.get("ganador") is not None
            
            # Formatear el texto del ganador para que incluya el Club
            texto_ganador = nombre_ganador
            if hubo_combate and ganador_data:
                club_ganador = ganador_data.get("club", "")
                if club_ganador and club_ganador not in ["Sin Club", "---"]:
                    texto_ganador = f"{nombre_ganador} ({club_ganador})"
            
            if preview_mode:
                # CORRECCIÓN: Respetamos los datos reales si existen. Solo simulamos los vacíos.
                if not p_rojo:
                    p_rojo = {'nombre': "Atleta Rojo (Simulado)", 'club': "Club Rojo", 'id': 99}
                if not p_azul:
                    p_azul = {'nombre': "Atleta Azul (Simulado)", 'club': "Club Azul", 'id': 88}
                
                # Si el combate real aún no se ha jugado, forzamos un ganador para ver las palomitas en el editor
                if not match_node.get("ganador"):
                    hubo_combate = True
                    nombre_ganador = p_rojo.get('nombre', 'Ganador')
                    club_ganador = p_rojo.get('club', 'Club Rojo')
                    texto_ganador = f"{nombre_ganador} ({club_ganador})"
                    codigo_victoria = "VFA"

            # Inyección de Textos Básicos
            escribir_caja(torneo_nombre.upper(), cfg.get("torneo_box", {}), is_multiline=True)
            escribir_caja(nom_arbitro, cfg.get("arbitro_nom", {})) 
            escribir_caja(id_arbitro, cfg.get("arbitro_id", {})) 
            escribir_caja(nom_juez, cfg.get("juez_nom", {}))    
            escribir_caja(id_juez, cfg.get("juez_id", {})) 
            escribir_caja(nom_jefe, cfg.get("jefe_nom", {}))  
            escribir_caja(id_jefe, cfg.get("jefe_id", {}))

            escribir_caja(torneo_fecha, cfg.get("fecha", {}))          
            escribir_caja(f"{match_node.get('match_id', '')}", cfg.get("match_id", {})) 
            escribir_caja(peso, cfg.get("peso", {}))
            escribir_caja(estilo, cfg.get("estilo", {}))                
            escribir_caja(f"{match_node.get('ronda', '')}", cfg.get("ronda", {})) 
            escribir_caja("Fase", cfg.get("fase", {}))                           
            
            # --- CORRECCIÓN: TAPIZ DINÁMICO EN EL PDF ---
            tapiz_actual = getattr(self.controller, 'tapiz_asignado', 'Tapiz A')
            escribir_caja(tapiz_actual, cfg.get("tapiz", {}))                        

            if p_rojo:
                escribir_caja(p_rojo.get('nombre', ''), cfg.get("rojo_nom", {}))
                escribir_caja(p_rojo.get('club', ''), cfg.get("rojo_club", {}))
                escribir_caja(id_rojo_str, cfg.get("rojo_id", {}))
            if p_azul:
                escribir_caja(p_azul.get('nombre', ''), cfg.get("azul_nom", {}))
                escribir_caja(p_azul.get('club', ''), cfg.get("azul_club", {}))
                escribir_caja(id_azul_str, cfg.get("azul_id", {}))

            # --- LÓGICA MATRICIAL PARA PUNTOS TÉCNICOS ---
            cfg_r1 = cfg.get("pts_r_p1", {}); cfg_r2 = cfg.get("pts_r_p2", {})
            cfg_a1 = cfg.get("pts_a_p1", {}); cfg_a2 = cfg.get("pts_a_p2", {})

            idx_r1 = idx_r2 = idx_a1 = idx_a2 = 0
            ultimo_punto_ganador = None 

            def dibujar_punto(texto, cfg_base, index):
                if not cfg_base or "coords" not in cfg_base: return None
                cfg_temp = cfg_base.copy()
                x0, y0, x1, y1 = cfg_temp["coords"]
                # CORRECCIÓN: Usar float para permitir saltos con decimales
                sx = float(cfg_temp.get("step_x", 0.0))
                sy = float(cfg_temp.get("step_y", 0.0))
                cfg_temp["coords"] = [x0 + sx*index, y0 + sy*index, x1 + sx*index, y1 + sy*index]
                escribir_caja(texto, cfg_temp)
                return ((x0 + x1)/2 + sx*index, (y0 + y1)/2 + sy*index)

            sum_p1_r = sum_p2_r = sum_p1_a = sum_p2_a = 0
            has_p1_r = has_p2_r = has_p1_a = has_p2_a = False

            for pt in puntos_historicos:
                texto_pt = "P" if pt['tipo_accion'] == 'Penalización' else str(pt['valor_puntos'])
                val = pt['valor_puntos']
                if pt['color_esquina'] == 'Rojo':
                    if pt['periodo'] == 1:
                        coord_center = dibujar_punto(texto_pt, cfg_r1, idx_r1); idx_r1 += 1
                        sum_p1_r += val; has_p1_r = True
                    else:
                        coord_center = dibujar_punto(texto_pt, cfg_r2, idx_r2); idx_r2 += 1
                        sum_p2_r += val; has_p2_r = True
                else: 
                    if pt['periodo'] == 1:
                        coord_center = dibujar_punto(texto_pt, cfg_a1, idx_a1); idx_a1 += 1
                        sum_p1_a += val; has_p1_a = True
                    else:
                        coord_center = dibujar_punto(texto_pt, cfg_a2, idx_a2); idx_a2 += 1
                        sum_p2_a += val; has_p2_a = True

                if coord_center and ((pt['color_esquina'] == 'Rojo' and p_rojo and p_rojo['nombre'] == nombre_ganador) or
                                     (pt['color_esquina'] == 'Azul' and p_azul and p_azul['nombre'] == nombre_ganador)):
                    ultimo_punto_ganador = coord_center

            # --- SUB-TOTALES Y TOTALES CON CERO FORZADO ---
            # P1 siempre muestra 0 si hubo combate 
            val_p1_r = str(sum_p1_r) if (has_p1_r or has_p1_a or hubo_combate) else ""
            val_p1_a = str(sum_p1_a) if (has_p1_r or has_p1_a or hubo_combate) else ""
            
            # NUEVO: P2 siempre muestra 0 si hubo combate (Igualando la lógica del P1)
            val_p2_r = str(sum_p2_r) if (has_p2_r or has_p2_a or hubo_combate) else ""
            val_p2_a = str(sum_p2_a) if (has_p2_r or has_p2_a or hubo_combate) else ""

            escribir_caja(val_p1_r, cfg.get("subtot_r_p1", {}))
            escribir_caja(val_p2_r, cfg.get("subtot_r_p2", {}))
            escribir_caja(val_p1_a, cfg.get("subtot_a_p1", {}))
            escribir_caja(val_p2_a, cfg.get("subtot_a_p2", {}))

            total_r = sum_p1_r + sum_p2_r
            total_a = sum_p1_a + sum_p2_a

            escribir_caja(str(total_r) if hubo_combate else "", cfg.get("total_pts_r", {}))
            escribir_caja(str(total_a) if hubo_combate else "", cfg.get("total_pts_a", {}))

            pts_gan = 0; pts_per = 0
            if codigo_victoria in ["VFA", "VIN", "VCA", "DSQ", "VF", "VA", "VB"]: pts_gan = 5
            elif codigo_victoria == "VSU": pts_gan = 4
            elif codigo_victoria == "VSU1": pts_gan = 4; pts_per = 1
            elif codigo_victoria == "VPO": pts_gan = 3
            elif codigo_victoria == "VPO1": pts_gan = 3; pts_per = 1

            if p_rojo and nombre_ganador == p_rojo.get('nombre'): clas_rojo, clas_azul = pts_gan, pts_per
            else: clas_rojo, clas_azul = pts_per, pts_gan

            if hubo_combate:
                escribir_caja(str(clas_rojo), cfg.get("clas_pts_r", {}))
                escribir_caja(str(clas_azul), cfg.get("clas_pts_a", {}))
                
                # CORRECCIÓN: Se quitó is_multiline=True 
                escribir_caja(texto_ganador, cfg.get("ganador_nom", {}))
                
                hora_pdf = hora_fin_combate if hora_fin_combate else "--:--" 
                escribir_caja(hora_pdf, cfg.get("hora_fin", {}))

            if ultimo_punto_ganador:
                page.draw_circle(fitz.Point(ultimo_punto_ganador[0], ultimo_punto_ganador[1]), radius=6, color=(0.1, 0.6, 0.1), width=1.5)
            
            # --- DIBUJADO DE CHECKS (MATRIX INTELIGENTE) ---
            # CORRECCIÓN: Se añadió "2DSQ" (E2 0:0 - Doble Descalificación) al final
            orden_victorias = ["VFA", "VAB", "VIN", "VFO", "DSQ", "VCA", "VSU", "VSU1", "VPO1", "VPO", "2DSQ"]    
            if codigo_victoria in orden_victorias:
                cfg_vic = cfg.get("check_vic", {})
                if "coords" in cfg_vic:
                    index = orden_victorias.index(codigo_victoria)
                    x0, y0, x1, y1 = cfg_vic["coords"]
                    # CORRECCIÓN: Usar float para saltos milimétricos
                    sx, sy = float(cfg_vic.get("step_x", 0.0)), float(cfg_vic.get("step_y", 0.0))
                    
                    bx0, by0, bx1, by1 = x0 + sx*index, y0 + sy*index, x1 + sx*index, y1 + sy*index
                    color_check = hex_a_rgb(cfg_vic.get("color", "#00aa00"))
                    p1 = fitz.Point(bx0 + (bx1-bx0)*0.2, by0 + (by1-by0)*0.5)
                    p2 = fitz.Point(bx0 + (bx1-bx0)*0.4, by0 + (by1-by0)*0.8)
                    p3 = fitz.Point(bx0 + (bx1-bx0)*0.8, by0 + (by1-by0)*0.2)
                    page.draw_line(p1, p2, color=color_check, width=2.5)
                    page.draw_line(p2, p3, color=color_check, width=2.5)

            # --- SI ES MODO PREVISUALIZACIÓN, RENDERIZAR IMAGEN ESCALADA Y SALIR ---
            if preview_mode:
                return page.get_pixmap(matrix=fitz.Matrix(zoom_factor, zoom_factor))

            # SI NO, GUARDAR NORMALMENTE
            doc.save(ruta_guardado)
            doc.close()
            
            if not ruta_directa:
                messagebox.showinfo("Éxito", "Hoja técnica exportada correctamente.")
            return None

        except Exception as e:
            if not preview_mode: messagebox.showerror("Error", f"Ocurrió un error al generar el PDF:\n{str(e)}")
            return None

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

    # ================= CIERRE DE TORNEO Y REPORTES =================
    def cerrar_torneo(self):
        # 1. Validar que no hayan combates pendientes en la cartelera
        if len(self.tree_cartelera.get_children()) > 0:
            messagebox.showwarning("Torneo Incompleto", "Aún hay combates pendientes en la cartelera.\n\nTermine todos los combates programados antes de cerrar el torneo.")
            return
        
        # 2. Validar que todas las divisiones hayan sido bloqueadas
        total_divisiones = sum(len(pesos) for pesos in self.datos.values())
        if len(self.divisiones_bloqueadas) < total_divisiones:
            messagebox.showwarning("Torneo Incompleto", "Existen divisiones de peso que no han sido confirmadas ni bloqueadas.\n\nRevise las pestañas de estilos y asegúrese de generar todas las llaves.")
            return

        # 3. Confirmación de seguridad
        respuesta = messagebox.askyesno("Confirmar Cierre", "¿Está seguro de proceder?")
        if respuesta:
            exito = self.db.finalizar_torneo(self.id_torneo)
            if exito:
                self.torneo_cerrado_en_db = True # <-- CRÍTICO: Marcamos el estado
                self.controller.torneo_finalizado = True
                
                # --- NUEVO: Avisar silenciosamente a Inscripción y vaciar su tabla de inmediato ---
                from ui.pantallas.pantalla_inscripcion import PantallaInscripcion
                p_inscripcion = self.controller.pantallas.get(PantallaInscripcion)
                if p_inscripcion:
                    p_inscripcion.torneo_finalizado = True
                    p_inscripcion.aplicar_interfaz_visitante() 
                
                messagebox.showinfo("Torneo Finalizado", "¡El torneo ha sido cerrado exitosamente!")
                self.verificar_estado_torneo() 
            else:
                messagebox.showerror("Error", "No se pudo cerrar el torneo.")

    def generar_reporte_pdf(self):
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from tkinter import filedialog, messagebox
        except ImportError:
            messagebox.showerror("Error", "Falta la librería ReportLab. Ejecuta: pip install reportlab")
            return

        ruta_guardado = filedialog.asksaveasfilename(
            defaultextension=".pdf", 
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"Reporte_Final_Resultados_{self.id_torneo}.pdf"
        )
        if not ruta_guardado: return

        # Configuración de página horizontal (landscape)
        doc = SimpleDocTemplate(ruta_guardado, pagesize=landscape(letter),
                                rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
        elementos = []
        estilos = getSampleStyleSheet()

        # --- ESTILOS DE TEXTO PERSONALIZADOS ---
        estilo_titulo = ParagraphStyle('Titulo', parent=estilos['Heading1'], alignment=1, fontSize=18, spaceAfter=20, textColor=colors.HexColor("#1e3d59"))
        estilo_estilo_label = ParagraphStyle('EstiloHeader', parent=estilos['Heading2'], alignment=1, fontSize=14, spaceBefore=20, spaceAfter=5, textColor=colors.black, backgroundColor=colors.HexColor("#fdfd96"), borderPadding=8)

        conexion = self.db.conectar()
        if not conexion: return
        try:
            with conexion.cursor() as cur:
                # 1. Obtener datos básicos del torneo incluyendo Ciudad
                cur.execute("""
                    SELECT t.nombre, t.lugar_exacto, ciu.nombre as ciudad,
                           to_char(t.fecha_inicio, 'DD/MM/YYYY'), 
                           to_char(t.fecha_fin, 'DD/MM/YYYY HH12:MI AM') 
                    FROM torneo t
                    LEFT JOIN ciudad ciu ON t.id_ciudad = ciu.id
                    WHERE t.id = %s
                """, (self.id_torneo,))
                torneo = cur.fetchone()
            
            # 2. Obtener TODAS las inscripciones PRIMERO (Corrección del error)
            inscripciones = self.db.obtener_datos_reporte(self.id_torneo)

            # --- PROCESAMIENTO DE ESTADÍSTICAS GENERALES ---
            total_atletas = len(inscripciones)
            clubes_list = set(ins['club'] for ins in inscripciones if ins['club'] and ins['club'] != "Sin Club")
            colegios_list = set(ins['colegio'] for ins in inscripciones if ins['colegio'] and ins['colegio'] != "N/A")
            departamentos_list = set(ins['departamento'] for ins in inscripciones if ins['departamento'] and ins['departamento'] != "N/A")
            
            # --- SECCIÓN DE DATOS GENERALES (Encabezado del Informe) ---
            elementos.append(Paragraph(f"<b>REPORTE OFICIAL DE RESULTADOS</b>", estilo_titulo))
            
            sede_completa = f"{torneo[1]}, {torneo[2]}" if torneo[2] else torneo[1]

            fecha_fin_texto = torneo[4] if torneo[4] else "En curso / Pendiente"
                
            info_basica_data = [
                [Paragraph(f"<b>Evento:</b> {torneo[0]}", estilos['Normal']), Paragraph(f"<b>Atletas Inscritos:</b> {total_atletas}", estilos['Normal'])],
                [Paragraph(f"<b>Sede:</b> {sede_completa}", estilos['Normal']), Paragraph(f"<b>Clubes:</b> {len(clubes_list)}", estilos['Normal'])],
                [Paragraph(f"<b>Fechas:</b> {torneo[3]} al {fecha_fin_texto}", estilos['Normal']), Paragraph(f"<b>Colegios:</b> {len(colegios_list)}", estilos['Normal'])]
            ]
            
            info_table = Table(info_basica_data, colWidths=[6*inch, 2.5*inch])
            info_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.lightgrey)
            ]))
            elementos.append(info_table)
            elementos.append(Spacer(1, 0.15 * inch))

            deps_texto = ", ".join(sorted(departamentos_list)) if departamentos_list else "Ninguno"
            elementos.append(Paragraph(f"<b>Departamentos participantes:</b> {deps_texto}", estilos['Normal']))
            elementos.append(Spacer(1, 0.25 * inch))

            # 3. CÁLCULO DE POSICIONES (ORO, PLATA, BRONCE)
            posiciones = {}
            for llave_key, grid in self.grids_generados.items():
                rondas_validas = [r for r in grid if any(isinstance(n, dict) and n.get("tipo")=="combate" for n in r)]
                if rondas_validas:
                    # Final: Oro y Plata
                    final = rondas_validas[-1]
                    for n in final:
                        if isinstance(n, dict) and n.get("ganador"):
                            p_gan = self.obtener_peleador_real(n["ganador"])
                            p_rojo = self.obtener_peleador_real(n["peleador_rojo"])
                            p_azul = self.obtener_peleador_real(n["peleador_azul"])
                            if p_gan and p_rojo and p_azul:
                                posiciones[p_gan['id']] = "1ro (Oro)"
                                id_perd = p_azul['id'] if p_gan['id'] == p_rojo['id'] else p_rojo['id']
                                posiciones[id_perd] = "2do (Plata)"
                    # Semifinales: Bronces
                    if len(rondas_validas) >= 2:
                        semis = rondas_validas[-2]
                        for n in semis:
                            if isinstance(n, dict) and n.get("ganador"):
                                p_gan = self.obtener_peleador_real(n["ganador"])
                                p_rojo = self.obtener_peleador_real(n["peleador_rojo"])
                                p_azul = self.obtener_peleador_real(n["peleador_azul"])
                                if p_gan and p_rojo and p_azul:
                                    id_perd = p_azul['id'] if p_gan['id'] == p_rojo['id'] else p_rojo['id']
                                    posiciones[id_perd] = "3ro (Bronce)"

            # 4. AGRUPACIÓN JERÁRQUICA: ESTILO -> PESO
            datos_organizados = {}
            for ins in inscripciones:
                est = ins['estilo'].upper()
                peso_txt = f"{ins['peso_cat']} kg"
                if est not in datos_organizados: datos_organizados[est] = {}
                if peso_txt not in datos_organizados[est]: datos_organizados[est][peso_txt] = []
                
                pos = posiciones.get(ins['id_peleador'], "--")
                datos_organizados[est][peso_txt].append([
                    pos, f"{ins['apellidos']}, {ins['nombre']}", peso_txt,
                    ins['club'] or "Sin Club", ins['colegio'] or "N/A", ins['departamento'] or "N/A",
                    str(int(ins['anio_nac'])) if ins['anio_nac'] else "N/A"
                ])

            # 5. GENERACIÓN DE TABLAS POR ESTILO CON SEPARADORES DE PESO
            for est_nom in sorted(datos_organizados.keys()):
                elementos.append(Paragraph(f"<b>RESULTADOS {est_nom}</b>", estilo_estilo_label))
                
                header = [["POS", "ATLETA", "PESO", "CLUB", "COLEGIO", "DEPARTAMENTO", "AÑO NAC."]]
                cuerpo_tabla = []
                indices_separadores = []
                
                pesos_ordenados = sorted(datos_organizados[est_nom].keys(), key=lambda x: int(x.split()[0]))
                
                for peso_nom in pesos_ordenados:
                    indices_separadores.append(len(header) + len(cuerpo_tabla))
                    cuerpo_tabla.append([f"CATEGORÍA DE PESO {peso_nom}", "", "", "", "", "", ""])
                    
                    filas_atletas = datos_organizados[est_nom][peso_nom]
                    filas_atletas.sort(key=lambda x: (1 if "1ro" in x[0] else 2 if "2do" in x[0] else 3 if "3ro" in x[0] else 4, x[1]))
                    cuerpo_tabla.extend(filas_atletas)
                
                data_final = header + cuerpo_tabla
                
                t = Table(data_final, colWidths=[0.9*inch, 2.0*inch, 0.7*inch, 1.5*inch, 2.5*inch, 1.3*inch, 0.7*inch])
                
                estilo_t = TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2c3e50")), 
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'), # Encabezados centrados
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    
                    # --- ALINEACIÓN ESPECÍFICA DE COLUMNAS ---
                    ('ALIGN', (0, 1), (0, -1), 'CENTER'), # Columna 0: POS
                    ('ALIGN', (1, 1), (1, -1), 'LEFT'),   # Columna 1: ATLETA
                    ('ALIGN', (2, 1), (2, -1), 'CENTER'), # Columna 2: PESO
                    ('ALIGN', (3, 1), (5, -1), 'LEFT'),   # Columnas 3,4,5: CLUB, COLEGIO, DEP
                    ('ALIGN', (6, 1), (6, -1), 'CENTER'), # Columna 6: AÑO NAC.
                ])
                
                for idx in indices_separadores:
                    estilo_t.add('SPAN', (0, idx), (6, idx)) 
                    estilo_t.add('BACKGROUND', (0, idx), (6, idx), colors.HexColor("#fff9c4")) 
                    estilo_t.add('ALIGN', (0, idx), (6, idx), 'CENTER')
                    estilo_t.add('FONTNAME', (0, idx), (6, idx), 'Helvetica-Bold')
                    estilo_t.add('FONTSIZE', (0, idx), (6, idx), 10)

                for i in range(1, len(data_final)):
                    if i not in indices_separadores:
                        if i % 2 == 0:
                            estilo_t.add('BACKGROUND', (0, i), (-1, i), colors.HexColor("#f8f9fa"))

                t.setStyle(estilo_t)
                elementos.append(t)
                elementos.append(Spacer(1, 0.3 * inch))

            # --- NUEVO: LISTA DE OFICIALES PARTICIPANTES AL FINAL DEL REPORTE ---
            elementos.append(Spacer(1, 0.4 * inch))
            
            # Extraer la lista consolidada desde la BD
            oficiales_participantes = self.db.obtener_oficiales_reporte(self.id_torneo)
            
            if oficiales_participantes:
                # Título de la sección
                estilo_oficiales_tit = ParagraphStyle('OficialesTit', parent=estilos['Heading3'], alignment=1, fontSize=12, textColor=colors.HexColor("#2c3e50"), fontName='Helvetica-Bold', spaceAfter=10)
                elementos.append(Paragraph("OFICIALES DE ARBITRAJE PARTICIPANTES", estilo_oficiales_tit))
                
                # Construcción de la tabla con la información completa
                datos_oficiales = [["NOMBRE Y APELLIDOS", "CÉDULA", "CORREO", "CELULAR", "ROLES DESEMPEÑADOS"]]
                for ofi in oficiales_participantes:
                    nombre_completo = f"{ofi['apellidos']}, {ofi['nombre']}"
                    correo = ofi['correo'] if ofi['correo'] else "N/A"
                    celular = ofi['celular'] if ofi['celular'] else "N/A"
                    
                    datos_oficiales.append([
                        nombre_completo, 
                        ofi['cedula'], 
                        correo, 
                        celular, 
                        ofi['roles_desempenados']
                    ])
                
                # Calibración de columnas para ancho total de ~10 pulgadas
                tabla_oficiales = Table(datos_oficiales, colWidths=[2.2*inch, 1.5*inch, 2.3*inch, 1.2*inch, 2.8*inch])
                tabla_oficiales.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e5e8e8")), # Gris claro para encabezado
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'), # Encabezados centrados
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    
                    # --- ALINEACIÓN ESPECÍFICA DE DATOS ---
                    ('ALIGN', (0, 1), (-1, -1), 'CENTER'), # Centra todas las columnas por defecto
                    
                    ('ALIGN', (0, 1), (0, -1), 'LEFT'),    # Alinea a la izquierda Col 0: NOMBRES
                    ('LEFTPADDING', (0, 1), (0, -1), 10),  # Margen izquierdo para que no toque la línea
                    
                    ('ALIGN', (2, 1), (2, -1), 'LEFT'),    # Alinea a la izquierda Col 2: CORREO
                    ('LEFTPADDING', (2, 1), (2, -1), 10),  # Margen izquierdo para que no toque la línea
                ]))
                elementos.append(tabla_oficiales)

            # --- FINALIZAR Y CONSTRUIR PDF ---
            doc.build(elementos)
            messagebox.showinfo("Éxito", "Reporte PDF final generado y optimizado correctamente.")
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el reporte:\n{e}")
        finally:
            conexion.close()

    # ================= FUNCIONES DE BÚSQUEDA Y NAVEGACIÓN =================
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

    def buscar_seleccion_en_llave(self):
        sel = self.tree_cartelera.selection()
        if not sel: return
        item_id = sel[0]
        llave_key = self.tree_cartelera.item(item_id, "text")
        match_node = getattr(self.tree_cartelera, f"nodo_{item_id}", None)
        if not match_node: return
        self.navegar_a_match(llave_key, match_node['match_id'])

    # ================= FUNCIONES DEL BUSCADOR EN LLAVE =================
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

    def resetear_busqueda_atleta_tab(self, tab, event=None):
        if event and event.keysym in ('Return', 'Up', 'Down', 'Left', 'Right'): return
        tab.resultados_busqueda_atleta = []
        tab.idx_busqueda = -1
        tab.lbl_res_busqueda.config(text="")
        
        # Elimina el rectángulo si quedaba alguno vivo
        if getattr(tab.canvas, "rect_flash_id", None):
            tab.canvas.delete(tab.canvas.rect_flash_id)
            tab.canvas.rect_flash_id = None
