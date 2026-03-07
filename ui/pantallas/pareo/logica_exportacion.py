import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import json
from PIL import Image, EpsImagePlugin, ImageDraw, ImageFont

# RUTA DINÁMICA: Detectar Ghostscript
gs_path = r"C:\Program Files\gs\gs10.06.0\bin\gswin64c.exe"
if os.path.exists(gs_path):
    EpsImagePlugin.gs_windows_binary = gs_path
else:
    print(f"ADVERTENCIA: No se encontró Ghostscript en {gs_path}.")

try:
    import fitz  # PyMuPDF
    PDF_DISPONIBLE = True
except ImportError:
    PDF_DISPONIBLE = False

class LogicaExportacionMixin:
    """Maneja la exportación a PNG, el horneado de PDFs, Reportes Finales y el cierre del torneo."""

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

    def cerrar_torneo(self):
        # 1. Validar lógicamente que no hayan combates pendientes en ninguna matriz
        hay_pendientes = False
        for llave_key, grid in self.grids_generados.items():
            for r in grid:
                for node in r:
                    if isinstance(node, dict) and node.get("tipo") == "combate":
                        if not node.get("ganador"):
                            hay_pendientes = True
                            break
                if hay_pendientes: break
            if hay_pendientes: break

        if hay_pendientes:
            messagebox.showwarning("Torneo Incompleto", "Aún hay combates pendientes en el torneo.\n\nTermine todos los combates programados antes de cerrar el torneo.")
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

            # --- NUEVO: TABLA DE MEDALLERÍA POR CLUBES ---
            elementos.append(Spacer(1, 0.2 * inch))
            estilo_medallero_tit = ParagraphStyle('MedalleroTit', parent=estilos['Heading2'], alignment=1, fontSize=14, textColor=colors.HexColor("#2c3e50"), fontName='Helvetica-Bold', spaceAfter=10)
            elementos.append(Paragraph("MEDALLERO GENERAL POR CLUBES", estilo_medallero_tit))

            # 1. Inicializar el medallero con todos los clubes inscritos (en 0)
            medallero = {}
            for ins in inscripciones:
                club = ins['club'] if ins['club'] and ins['club'] != "N/A" else "Sin Club"
                if club not in medallero:
                    medallero[club] = {"Oro": 0, "Plata": 0, "Bronce": 0}

            # 2. Contar las medallas según las posiciones calculadas
            for ins in inscripciones:
                club = ins['club'] if ins['club'] and ins['club'] != "N/A" else "Sin Club"
                pos = posiciones.get(ins['id_peleador'], "")
                
                if "1ro" in pos: medallero[club]["Oro"] += 1
                elif "2do" in pos: medallero[club]["Plata"] += 1
                elif "3ro" in pos: medallero[club]["Bronce"] += 1

            # 3. Ordenar: Primero por Oro, luego Plata, luego Bronce (Descendente)
            clubes_ordenados = sorted(medallero.keys(), key=lambda c: (medallero[c]["Oro"], medallero[c]["Plata"], medallero[c]["Bronce"]), reverse=True)

            # 4. Construir la tabla visual
            datos_medallero = [["CLUB / EQUIPO", "ORO", "PLATA", "BRONCE", "TOTAL"]]
            for club in clubes_ordenados:
                oros = medallero[club]["Oro"]
                platas = medallero[club]["Plata"]
                bronces = medallero[club]["Bronce"]
                total_medallas = oros + platas + bronces
                datos_medallero.append([club, str(oros), str(platas), str(bronces), str(total_medallas)])

            # Anchos calibrados para una página apaisada (Landscape)
            tabla_medallero = Table(datos_medallero, colWidths=[4*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch])
            
            # Estilos con colores para las medallas
            tabla_medallero.setStyle(TableStyle([
                # Encabezado principal
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#34495e")), 
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'), 
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                
                # Alineación de datos
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),   # Club a la izquierda
                ('LEFTPADDING', (0, 1), (0, -1), 10),
                ('ALIGN', (1, 1), (-1, -1), 'CENTER'), # Números centrados
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                
                # Colores de fondo por columna (Oro, Plata, Bronce)
                ('BACKGROUND', (1, 1), (1, -1), colors.HexColor("#fff8e1")), # Fondo sutil Oro
                ('BACKGROUND', (2, 1), (2, -1), colors.HexColor("#f2f3f4")), # Fondo sutil Plata
                ('BACKGROUND', (3, 1), (3, -1), colors.HexColor("#fbeee6")), # Fondo sutil Bronce
                ('BACKGROUND', (4, 1), (4, -1), colors.HexColor("#e8f8f5")), # Fondo sutil Total
                
                # Cuadrícula general
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ]))
            
            elementos.append(tabla_medallero)
            elementos.append(Spacer(1, 0.4 * inch))

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
