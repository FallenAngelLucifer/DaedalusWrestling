import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
from PIL import Image, ImageTk
import os
import json
import subprocess
import tempfile
import time

class VentanaPrevisualizacionPDF(tk.Toplevel):
    def __init__(self, parent, match_node, estilo, peso):
        super().__init__(parent)
        self.parent = parent
        self.match_node = match_node
        self.estilo = estilo
        self.peso = peso
        
        self.title("Visor Oficial y Editor de Acta")
        self.geometry("1300x800")
        self.transient(parent)
        self.grab_set()
        
        # --- VARIABLES DE ESTADO Y MOTOR ---
        self.estado_actual = None 
        self.selected_key = None
        self.drag_mode = None 
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.original_coords = []
        self.suppress_render = False
        self.render_after_id = None
        self.cambios_sin_guardar = False
        self.protocol("WM_DELETE_WINDOW", self.al_cerrar_ventana)
        
        self.cfg = self.parent.cargar_config_pdf()
        self.item_widgets = {} 
        self.zoom_var = tk.DoubleVar(value=1.5)
        
        self.construir_interfaz_base()
        self.cambiar_estado("INICIO")
        self.execute_render()

    def to_float(self, val):
        try:
            if val is None: return 0.0
            val_str = str(val).strip().replace(',', '.')
            if val_str in ('', '-', '+'): return 0.0
            return float(val_str)
        except ValueError: return 0.0

    # ================= GESTIÓN DE CONFIGURACIÓN DE IMPRESIÓN =================
    def cargar_config_impresion(self):
        """Pide la configuración de impresión al padre (que conoce la ruta en assets)."""
        # Delegamos completamente la carga al LogicaExportacionMixin
        if hasattr(self.parent, 'cargar_config_impresion'):
            return self.parent.cargar_config_impresion()
        return {"impresora": "", "papel": "A4", "color": "Color", "copias": 1}

    def guardar_config_impresion(self, *args):
        """Empaqueta las variables actuales y le pide al padre que las guarde en assets."""
        if not hasattr(self, 'var_impresora'): return
        
        cfg = {
            "impresora": self.var_impresora.get(),
            "papel": self.var_papel.get(),
            "color": self.var_color_print.get(),
            "copias": int(self.var_copias.get() or 1)
        }
        
        # Delegamos el guardado al LogicaExportacionMixin
        if hasattr(self.parent, 'guardar_config_impresion'):
            self.parent.guardar_config_impresion(cfg)

    def guardar_cambios(self):
        """Recopila los datos visuales, actualiza el diccionario cfg y lo envía a la clase padre para guardar."""
        for key, widgets in self.item_widgets.items():
            if key not in self.cfg:
                continue
                
            try:
                # 1. Recuperar Coordenadas (Obligatorias)
                nuevas_coords = [
                    float(widgets['coords'][0].get()),
                    float(widgets['coords'][1].get()),
                    float(widgets['coords'][2].get()),
                    float(widgets['coords'][3].get())
                ]
                self.cfg[key]['coords'] = nuevas_coords
                
                # 2. Recuperar Propiedades Tipográficas
                if 'size' in widgets:
                    self.cfg[key]['size'] = int(widgets['size'].get())
                if 'align' in widgets:
                    self.cfg[key]['align'] = widgets['align'].get()
                if 'color' in widgets:
                    self.cfg[key]['color'] = widgets['color'].get()
                    
                # 3. Recuperar Saltos Matriciales (step_x, step_y)
                if 'step_x' in widgets:
                    self.cfg[key]['step_x'] = float(widgets['step_x'].get())
                if 'step_y' in widgets:
                    self.cfg[key]['step_y'] = float(widgets['step_y'].get())
                    
                # 4. Checkboxes de estilo
                if 'bold_var' in widgets:
                    self.cfg[key]['bold'] = widgets['bold_var'].get()
                if 'italic_var' in widgets:
                    self.cfg[key]['italic'] = widgets['italic_var'].get()
                    
            except ValueError:
                messagebox.showerror("Error de Formato", f"Por favor, ingrese solo números válidos en '{key}'.")
                return

        # Delegamos el guardado real al LogicaExportacionMixin (que ya sabe la ruta en 'assets')
        exito = self.parent.guardar_config_pdf(self.cfg)
        
        if exito:
            self.cambios_sin_guardar = False
            messagebox.showinfo("Guardado Exitoso", "Las coordenadas han sido guardadas en la configuración.")
            
            # Si tienes un método que refresca el canvas, llámalo aquí. Ej: self.render_preview()
            if hasattr(self, 'render_preview'):
                self.render_preview()
        else:
            messagebox.showerror("Error", "Hubo un problema al intentar guardar el archivo JSON.")

    def obtener_impresoras_sistema(self):
        """Consulta a Windows la lista de impresoras instaladas vía PowerShell."""
        try:
            output = subprocess.check_output(['powershell', '-Command', 'Get-Printer | Select-Object -ExpandProperty Name'], text=True, creationflags=0x08000000)
            printers = [line.strip() for line in output.split('\n') if line.strip()]
            return printers if printers else ["Predeterminada del Sistema"]
        except Exception:
            return ["Predeterminada del Sistema"]

    def abrir_propiedades_impresora(self):
        """Abre la ventana nativa de Windows con las propiedades de la impresora seleccionada."""
        impresora = self.var_impresora.get()
        if not impresora or impresora == "Predeterminada del Sistema":
            return messagebox.showwarning("Aviso", "Seleccione una impresora real de la lista.")
        try:
            subprocess.Popen(['rundll32', 'printui.dll,PrintUIEntry', '/e', '/n', impresora])
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir las propiedades:\n{e}")

    # ================= 1. INTERFAZ MAESTRA Y ESTRUCTURA FIJA =================
    def construir_interfaz_base(self):
        self.left_frame = ttk.Frame(self, width=360, padding=10) 
        self.left_frame.pack_propagate(False) 
        self.left_frame.pack(side="left", fill="y")
        
        self.right_frame = ttk.Frame(self)
        self.right_frame.pack(side="right", fill="both", expand=True)

        self.header_frame = ttk.Frame(self.left_frame)
        self.header_frame.pack(side="top", fill="x", pady=(0, 10))
        
        self.lbl_titulo_izq = ttk.Label(self.header_frame, text="", font=("Helvetica", 14, "bold"))
        self.lbl_titulo_izq.pack()
        ttk.Label(self.header_frame, text=f"{self.estilo} - {self.peso}", font=("Helvetica", 10)).pack()
        ttk.Separator(self.left_frame, orient="horizontal").pack(fill="x", pady=(0, 5))

        self.dynamic_container = ttk.Frame(self.left_frame)
        self.dynamic_container.pack(side="top", fill="both", expand=True)

        self.panel_inicio = ttk.Frame(self.dynamic_container)
        self.construir_panel_inicio(self.panel_inicio)

        self.panel_impresion = ttk.Frame(self.dynamic_container)
        self.construir_panel_impresion(self.panel_impresion)

        self.panel_edicion = ttk.Frame(self.dynamic_container)
        self.construir_panel_edicion(self.panel_edicion)

        # Panel Derecho (Lienzo PDF)
        zoom_frame = ttk.Frame(self.right_frame, padding=5)
        zoom_frame.pack(fill="x")
        ttk.Label(zoom_frame, text="Zoom:").pack(side="left", padx=5)
        ttk.Button(zoom_frame, text="➖", width=3, command=lambda: self.cambiar_zoom(-0.25)).pack(side="left")
        slider_zoom = ttk.Scale(zoom_frame, from_=0.5, to=3.0, variable=self.zoom_var, orient="horizontal", length=200)
        slider_zoom.pack(side="left", padx=10)
        slider_zoom.bind("<ButtonRelease-1>", lambda e: self.execute_render()) 
        ttk.Button(zoom_frame, text="➕", width=3, command=lambda: self.cambiar_zoom(0.25)).pack(side="left")
        self.lbl_zoom = ttk.Label(zoom_frame, text="150%", width=5)
        self.lbl_zoom.pack(side="left", padx=5)
        self.zoom_var.trace_add("write", self.actualizar_texto_zoom)

        canvas_frame = ttk.Frame(self.right_frame)
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        scroll_y_pdf = ttk.Scrollbar(canvas_frame, orient="vertical")
        scroll_y_pdf.pack(side="right", fill="y")
        scroll_x_pdf = ttk.Scrollbar(canvas_frame, orient="horizontal")
        scroll_x_pdf.pack(side="bottom", fill="x")
        
        self.canvas_pdf = tk.Canvas(canvas_frame, bg="#2a2a2a", yscrollcommand=scroll_y_pdf.set, xscrollcommand=scroll_x_pdf.set, cursor="crosshair")
        self.canvas_pdf.pack(side="left", fill="both", expand=True)
        scroll_y_pdf.config(command=self.canvas_pdf.yview)
        scroll_x_pdf.config(command=self.canvas_pdf.xview)

        self.bind("<Control-MouseWheel>", self.on_ctrl_scroll)
        self.canvas_pdf.bind("<MouseWheel>", self.on_pdf_scroll_y)
        self.canvas_pdf.bind("<Shift-MouseWheel>", self.on_pdf_scroll_x)
        self.canvas_pdf.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas_pdf.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas_pdf.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.bind("<Button-1>", self.global_click, add="+")
        
        for key in ["Up", "Down", "Left", "Right"]:
            self.bind(f"<{key}>", lambda e, k=key, m="normal": self.mover_con_teclado(e, k, m))
            self.bind(f"<Shift-{key}>", lambda e, k=key, m="shift": self.mover_con_teclado(e, k, m))
            self.bind(f"<Control-{key}>", lambda e, k=key, m="ctrl": self.mover_con_teclado(e, k, m))
            self.bind(f"<Control-Shift-{key}>", lambda e, k=key, m="ctrl_shift": self.mover_con_teclado(e, k, m))

    # ================= 2. MÁQUINA DE ESTADOS =================
    def cambiar_estado(self, nuevo_estado):
        self.panel_inicio.pack_forget()
        self.panel_impresion.pack_forget()
        self.panel_edicion.pack_forget()

        self.estado_actual = nuevo_estado

        if nuevo_estado == "INICIO":
            self.lbl_titulo_izq.config(text="Resumen de Acta")
            self.panel_inicio.pack(fill="both", expand=True)
            self.deselect_box() 
            
        elif nuevo_estado == "EDICION":
            self.lbl_titulo_izq.config(text="Diseño de Plantilla")
            self.panel_edicion.pack(fill="both", expand=True)
            
        elif nuevo_estado == "IMPRESION":
            self.lbl_titulo_izq.config(text="Configurar Impresión")
            self.panel_impresion.pack(fill="both", expand=True)

    # ================= 3. VISTA: INICIO =================
    def construir_panel_inicio(self, container):
        p_rojo = self.parent.obtener_peleador_real(self.match_node["peleador_rojo"])
        p_azul = self.parent.obtener_peleador_real(self.match_node["peleador_azul"])
        ganador_data = self.match_node.get("ganador") or {}
        id_combate = ganador_data.get("id_combate")

        f_atl = ttk.Frame(container)
        f_atl.pack(fill="x", pady=5)
        f_atl.columnconfigure(0, weight=1)
        f_atl.columnconfigure(1, weight=1)

        nom_r = p_rojo['nombre'] if p_rojo else "A la espera..."
        nom_a = p_azul['nombre'] if p_azul else "A la espera..."

        tk.Label(f_atl, text=nom_r, bg="#cc0000", fg="white", font=("Helvetica", 9, "bold"), wraplength=140, height=2).grid(row=0, column=0, sticky="nsew", padx=(0,2))
        tk.Label(f_atl, text=nom_a, bg="#0000cc", fg="white", font=("Helvetica", 9, "bold"), wraplength=140, height=2).grid(row=0, column=1, sticky="nsew", padx=(2,0))

        f_pts = ttk.LabelFrame(container, text="Puntos Técnicos", padding=5)
        f_pts.pack(fill="both", expand=True, pady=10)

        tv = ttk.Treeview(f_pts, columns=("per", "esq", "pts", "tipo"), show="headings", height=5)
        tv.heading("per", text="Per"); tv.heading("esq", text="Esq")
        tv.heading("pts", text="Pts"); tv.heading("tipo", text="Tipo")
        tv.column("per", width=35, anchor="c"); tv.column("esq", width=35, anchor="c")
        tv.column("pts", width=35, anchor="c"); tv.column("tipo", width=120, anchor="w")
        tv.pack(fill="both", expand=True)

        if id_combate:
            pts = self.parent.db.obtener_puntuacion_combate(id_combate)
            for p in pts:
                tv.insert("", "end", values=(p['periodo'], p['color_esquina'][:3], p['valor_puntos'], p['tipo_accion']))

        f_res = ttk.LabelFrame(container, text="Resultado", padding=5)
        f_res.pack(fill="x", pady=5)
        ttk.Label(f_res, text=f"Ganador: {ganador_data.get('nombre', 'Pendiente')}", font=("Helvetica", 10, "bold"), foreground="#28a745", wraplength=300).pack(anchor="w")
        ttk.Label(f_res, text=f"Método: {ganador_data.get('motivo_victoria', 'N/A')}", font=("Helvetica", 9), wraplength=300).pack(anchor="w")

        f_btn = ttk.Frame(container)
        f_btn.pack(side="bottom", fill="x", pady=10)

        ttk.Button(f_btn, text="⚙️ Configurar Plantilla PDF", command=lambda: self.cambiar_estado("EDICION")).pack(fill="x", pady=3)
        ttk.Button(f_btn, text="🖨️ Opciones de Impresión", command=lambda: self.cambiar_estado("IMPRESION")).pack(fill="x", pady=3)
        ttk.Button(f_btn, text="📄 Exportar a PDF (Guardar)", command=self.accion_exportar).pack(fill="x", pady=3)

    # ================= 4. VISTA: IMPRESIÓN (NUEVO MOTOR) =================
    def construir_panel_impresion(self, container):
        cfg_print = self.cargar_config_impresion()
        impresoras_disp = self.obtener_impresoras_sistema()

        impresora_actual = cfg_print.get("impresora", "")
        if impresora_actual not in impresoras_disp:
            impresora_actual = impresoras_disp[0]

        self.var_impresora = tk.StringVar(value=impresora_actual)
        self.var_papel = tk.StringVar(value=cfg_print.get("papel", "A4"))
        self.var_color_print = tk.StringVar(value=cfg_print.get("color", "Color"))
        self.var_copias = tk.StringVar(value=str(cfg_print.get("copias", 1)))

        self.var_impresora.trace_add("write", self.guardar_config_impresion)
        self.var_papel.trace_add("write", self.guardar_config_impresion)
        self.var_color_print.trace_add("write", self.guardar_config_impresion)
        self.var_copias.trace_add("write", self.guardar_config_impresion)

        f_info = ttk.LabelFrame(container, text="Ajustes Locales", padding=10)
        f_info.pack(fill="both", expand=True, pady=(10, 0))

        ttk.Label(f_info, text="Seleccionar Impresora:").pack(anchor="w", pady=(5, 2))
        cb_impresoras = ttk.Combobox(f_info, textvariable=self.var_impresora, values=impresoras_disp, state="readonly", width=35)
        cb_impresoras.pack(fill="x", pady=(0, 5))
        
        ttk.Button(f_info, text="⚙️ Propiedades de Impresora", command=self.abrir_propiedades_impresora).pack(fill="x", pady=(0, 15))

        ttk.Label(f_info, text="Tamaño del Papel:").pack(anchor="w", pady=(5, 2))
        cb_papel = ttk.Combobox(f_info, textvariable=self.var_papel, values=["A4", "Carta", "Oficio"], state="readonly")
        cb_papel.pack(fill="x", pady=(0, 10))

        ttk.Label(f_info, text="Modo de Impresión:").pack(anchor="w", pady=(5, 2))
        cb_color = ttk.Combobox(f_info, textvariable=self.var_color_print, values=["Color", "Blanco y Negro"], state="readonly")
        cb_color.pack(fill="x", pady=(0, 10))

        ttk.Label(f_info, text="Número de Copias:").pack(anchor="w", pady=(5, 2))
        sp_copias = ttk.Spinbox(f_info, from_=1, to=20, textvariable=self.var_copias, width=10)
        sp_copias.pack(anchor="w", pady=(0, 10))

        f_btn = ttk.Frame(container)
        f_btn.pack(side="bottom", fill="x", pady=10)

        tk.Button(f_btn, text="🖨️ Mandar a Imprimir", bg="#17a2b8", fg="white", font=("Helvetica", 10, "bold"), command=self.accion_imprimir_silenciosa).pack(fill="x", pady=3, ipady=5)
        ttk.Button(f_btn, text="❌ Cancelar y Volver", command=lambda: self.cambiar_estado("INICIO")).pack(fill="x", pady=3)

    # ================= 5. VISTA: EDICIÓN =================
    def construir_panel_edicion(self, container):
        self.bottom_container_edicion = ttk.Frame(container)
        self.bottom_container_edicion.pack(side="bottom", fill="x")

        f_botones_edicion = ttk.Frame(self.bottom_container_edicion)
        f_botones_edicion.pack(side="bottom", fill="x", pady=(10, 0))

        tk.Button(f_botones_edicion, text="💾 Guardar Plantilla", bg="#28a745", fg="white", font=("Helvetica", 9, "bold"), command=self.guardar_edicion).pack(side="left", fill="x", expand=True, padx=(0, 2), ipady=3)
        tk.Button(f_botones_edicion, text="❌ Cancelar", bg="#dc3545", fg="white", font=("Helvetica", 9, "bold"), command=self.cancelar_edicion).pack(side="right", fill="x", expand=True, padx=(2, 0), ipady=3)

        self.prop_frame = ttk.LabelFrame(self.bottom_container_edicion, text="Estilos Visuales", padding=5)
        
        self.var_align = tk.StringVar()
        self.var_valign = tk.StringVar()
        self.var_font = tk.StringVar()
        self.var_size = tk.StringVar()
        self.var_color = tk.StringVar()
        self.var_bold = tk.BooleanVar()
        self.var_italic = tk.BooleanVar()
        self.var_underline = tk.BooleanVar()
        
        f_grids = ttk.Frame(self.prop_frame)
        f_grids.pack(fill="x")
        ttk.Label(f_grids, text="Alineado:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(f_grids, textvariable=self.var_align, values=["Izquierda", "Centro", "Derecha"], state="readonly", width=10).grid(row=0, column=1, pady=2)
        ttk.Label(f_grids, text="Pos. Vert:").grid(row=1, column=0, sticky="w")
        ttk.Combobox(f_grids, textvariable=self.var_valign, values=["Arriba", "Medio", "Abajo"], state="readonly", width=10).grid(row=1, column=1, pady=2)
        ttk.Label(f_grids, text="Fuente:").grid(row=2, column=0, sticky="w")
        ttk.Combobox(f_grids, textvariable=self.var_font, values=["Helvetica", "Times", "Courier"], state="readonly", width=10).grid(row=2, column=1, pady=2)
        ttk.Label(f_grids, text="Tamaño:").grid(row=3, column=0, sticky="w")
        
        sp_size = ttk.Spinbox(f_grids, from_=1, to=100, textvariable=self.var_size, width=10)
        sp_size.grid(row=3, column=1, pady=2)
        self.bind_scroll_izq(sp_size, is_spinbox=True) 
        
        f_checks = ttk.Frame(self.prop_frame)
        f_checks.pack(fill="x", pady=5)
        ttk.Checkbutton(f_checks, text="N", variable=self.var_bold, style="Toolbutton").pack(side="left", padx=1)
        ttk.Checkbutton(f_checks, text="C", variable=self.var_italic, style="Toolbutton").pack(side="left", padx=1)
        ttk.Checkbutton(f_checks, text="S", variable=self.var_underline, style="Toolbutton").pack(side="left", padx=1)
        self.btn_color = tk.Button(f_checks, text="Color", bg="#000000", fg="white", command=self.elegir_color, width=6)
        self.btn_color.pack(side="right")

        for var in [self.var_align, self.var_valign, self.var_font, self.var_size, self.var_bold, self.var_italic, self.var_underline]:
            var.trace_add("write", self.aplicar_estilo)

        self.list_container = ttk.Frame(container)
        self.list_container.pack(side="top", fill="both", expand=True)

        self.canvas_inputs = tk.Canvas(self.list_container, highlightthickness=0)
        scroll_inputs = ttk.Scrollbar(self.list_container, orient="vertical", command=self.canvas_inputs.yview)
        scroll_inputs.pack(side="right", fill="y")
        self.canvas_inputs.pack(side="left", fill="both", expand=True)

        self.scrollable_frame = ttk.Frame(self.canvas_inputs)
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas_inputs.configure(scrollregion=self.canvas_inputs.bbox("all")))
        self.canvas_window = self.canvas_inputs.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas_inputs.bind("<Configure>", lambda e: self.canvas_inputs.itemconfig(self.canvas_window, width=e.width))
        self.canvas_inputs.configure(yscrollcommand=scroll_inputs.set)

        self.bind_scroll_izq(self.canvas_inputs); self.bind_scroll_izq(self.scrollable_frame)
        
        for key, values in self.cfg.items():
            f_item = tk.Frame(self.scrollable_frame, bg="#2a2a2a", bd=1, relief="solid", highlightthickness=1, highlightbackground="#444444")
            f_item.pack(fill="x", padx=5, pady=3)

            lbl_title = tk.Label(f_item, text=key.replace("_", " ").title(), font=("Helvetica", 9, "bold"), bg="#2a2a2a", fg="#ffffff")
            lbl_title.pack(anchor="w", padx=5, pady=(2,0))

            f_coords = tk.Frame(f_item, bg="#2a2a2a")
            f_coords.pack(fill="x", padx=5, pady=2)
            
            vars_coords = []
            coords = values.get("coords", [0,0,50,20]) 
            for i in range(4):
                val_c = self.to_float(coords[i])
                sv = tk.StringVar(value=f"{val_c:.1f}")
                sv.trace_add("write", lambda *a, k=key: self.handle_spinbox_change(k))
                sp = ttk.Spinbox(f_coords, from_=-500.0, to=3000.0, increment=1.0, format="%.1f", width=6, textvariable=sv)
                sp.grid(row=0, column=i, padx=1)
                sp.bind("<FocusIn>", lambda e, k=key: self.select_box(k))
                sp.bind("<Button-1>", lambda e, k=key: self.select_box(k))
                self.bind_scroll_izq(sp, is_spinbox=True) 
                vars_coords.append(sv)

            f_steps = tk.Frame(f_item, bg="#2a2a2a")
            f_steps.pack(fill="x", padx=5, pady=(0,5))
            
            val_sx = self.to_float(values.get("step_x", 0.0))
            val_sy = self.to_float(values.get("step_y", 0.0))
            
            sv_sx = tk.StringVar(value=f"{val_sx:.3f}")
            sv_sy = tk.StringVar(value=f"{val_sy:.3f}")
            sv_sx.trace_add("write", lambda *a, k=key: self.handle_spinbox_change(k))
            sv_sy.trace_add("write", lambda *a, k=key: self.handle_spinbox_change(k))

            lbl_sx = tk.Label(f_steps, text="Salto X:", bg="#2a2a2a", fg="#aaaaaa", font=("Helvetica", 8))
            lbl_sx.pack(side="left")
            sp_sx = ttk.Spinbox(f_steps, from_=-500.0, to=500.0, increment=0.01, format="%.3f", width=7, textvariable=sv_sx)
            sp_sx.pack(side="left", padx=1)

            lbl_sy = tk.Label(f_steps, text="Salto Y:", bg="#2a2a2a", fg="#aaaaaa", font=("Helvetica", 8))
            lbl_sy.pack(side="left", padx=(5,0))
            sp_sy = ttk.Spinbox(f_steps, from_=-500.0, to=500.0, increment=0.01, format="%.3f", width=7, textvariable=sv_sy)
            sp_sy.pack(side="left", padx=1)

            for w in [f_item, lbl_title, f_coords, f_steps, lbl_sx, lbl_sy]:
                w.bind("<Button-1>", lambda e, k=key: self.select_box(k))
                self.bind_scroll_izq(w)
                
            sp_sx.bind("<FocusIn>", lambda e, k=key: self.select_box(k))
            sp_sy.bind("<FocusIn>", lambda e, k=key: self.select_box(k))
            self.bind_scroll_izq(sp_sx, is_spinbox=True); self.bind_scroll_izq(sp_sy, is_spinbox=True)
            
            self.item_widgets[key] = {
                'frame': f_item, 'lbl': lbl_title, 'f_coords': f_coords, 'f_steps': f_steps,
                'lbl_sx': lbl_sx, 'lbl_sy': lbl_sy,
                'coords': vars_coords, 'step_x': sv_sx, 'step_y': sv_sy
            }

    # ================= MÉTODOS DE ACCIÓN =================
    def accion_exportar(self):
        self.parent.exportar_pdf(self.match_node, self.estilo, self.peso)

    def accion_imprimir_silenciosa(self):
        """Genera el PDF oculto y lo manda directamente a la cola de impresión seleccionada."""
        
        # --- NUEVO: AUTO-GUARDAR ANTES DE IMPRIMIR ---
        if getattr(self, "cambios_sin_guardar", False):
            if messagebox.askyesno("Guardar Cambios", "Tiene modificaciones sin guardar en el diseño.\n\n¿Desea guardarlas antes de imprimir?"):
                self.guardar_cambios()
        # ---------------------------------------------

        impresora = self.var_impresora.get()
        if not impresora or impresora == "Predeterminada del Sistema":
            messagebox.showwarning("Impresora", "Por favor seleccione una impresora válida.")
            return

        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, f"print_temp_{int(time.time())}.pdf")
        
        self.parent.exportar_pdf(self.match_node, self.estilo, self.peso, ruta_directa=temp_file)
        
        if not os.path.exists(temp_file):
            return messagebox.showerror("Error", "No se pudo generar el documento para imprimir.")

        gs_path = r"C:\Program Files\gs\gs10.06.0\bin\gswin64c.exe"
        if not os.path.exists(gs_path):
            try:
                os.startfile(temp_file, "print")
                messagebox.showinfo("Imprimiendo", "Enviado al gestor predeterminado de Windows.")
                self.cambiar_estado("INICIO")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo enviar a imprimir:\n{e}")
            return

        try:
            copias = self.var_copias.get()
            papel = self.var_papel.get()
            color_mode = self.var_color_print.get()

            cmd = [gs_path, "-dPrinted", "-dBATCH", "-dNOPAUSE", "-dNOSAFER", "-q"]
            cmd.append(f"-dNumCopies={copias}")
            
            if papel == "Carta": cmd.append("-sPAPERSIZE=letter")
            elif papel == "Oficio": cmd.append("-sPAPERSIZE=legal")
            else: cmd.append("-sPAPERSIZE=a4")
            
            if color_mode == "Blanco y Negro":
                cmd.extend(["-sColorConversionStrategy=Gray", "-dProcessColorModel=/DeviceGray"])
                
            cmd.extend(["-sDEVICE=mswinpr2", f"-sOutputFile=%printer%{impresora}", temp_file])
            subprocess.run(cmd, creationflags=0x08000000)
            
            messagebox.showinfo("Enviado", f"El acta fue enviada a la cola de:\n{impresora}")
            self.cambiar_estado("INICIO")
            
        except Exception as e:
            messagebox.showerror("Error de Impresión", f"Fallo en el motor Ghostscript:\n{e}")

    def guardar_edicion(self):
        for k, w_dict in self.item_widgets.items():
            self.cfg[k]["coords"] = [self.to_float(v.get()) for v in w_dict['coords']]
            self.cfg[k]["step_x"] = self.to_float(w_dict['step_x'].get())
            self.cfg[k]["step_y"] = self.to_float(w_dict['step_y'].get())
            
        self.parent.guardar_config_pdf(self.cfg)
        self.cambios_sin_guardar = False 
        messagebox.showinfo("Guardado", "Plantilla actualizada permanentemente.")
        self.cambiar_estado("INICIO")

    def cancelar_edicion(self):
        if self.cambios_sin_guardar:
            if not messagebox.askyesno("Cancelar Edición", "Tiene modificaciones sin guardar.\n\n¿Desea descartarlas y volver al resumen?"):
                return
                
        self.cfg = self.parent.cargar_config_pdf()
        self.suppress_render = True
        for key, w_dict in self.item_widgets.items():
            coords = self.cfg[key].get("coords", [0,0,50,20])
            for i in range(4): w_dict['coords'][i].set(f"{self.to_float(coords[i]):.1f}")
            w_dict['step_x'].set(f"{self.to_float(self.cfg[key].get('step_x', 0.0)):.3f}")
            w_dict['step_y'].set(f"{self.to_float(self.cfg[key].get('step_y', 0.0)):.3f}")
        self.suppress_render = False
        
        self.cambios_sin_guardar = False
        self.cambiar_estado("INICIO")
        self.execute_render()

    def al_cerrar_ventana(self):
        if self.estado_actual == "EDICION" and self.cambios_sin_guardar:
            resp = messagebox.askyesnocancel("Cambios sin guardar", "Tiene modificaciones sin guardar.\n\n¿Desea guardarlas antes de salir?")
            if resp is True:
                self.guardar_edicion()
                self.destroy()
            elif resp is False:
                self.destroy()
        else:
            self.destroy()

    # ================= MÉTODOS DEL MOTOR GRÁFICO =================
    def mover_con_teclado(self, event, key, mode):
        if self.estado_actual != "EDICION" or not self.selected_key: return
        foco = self.focus_get()
        if isinstance(foco, (tk.Entry, ttk.Entry, tk.Spinbox, ttk.Spinbox)): return 
            
        paso = 0.1 if "shift" in mode else 1.0
        dx = dy = dsx = dsy = 0.0
        
        if "ctrl" in mode:
            if key == 'Up': dsy = -paso
            elif key == 'Down': dsy = paso
            elif key == 'Left': dsx = -paso
            elif key == 'Right': dsx = paso
        else:
            if key == 'Up': dy = -paso
            elif key == 'Down': dy = paso
            elif key == 'Left': dx = -paso
            elif key == 'Right': dx = paso
            
        w_dict = self.item_widgets[self.selected_key]
        try:
            self.suppress_render = True
            if "ctrl" in mode:
                sx = self.to_float(w_dict['step_x'].get()); sy = self.to_float(w_dict['step_y'].get())
                w_dict['step_x'].set(f"{sx + dsx:.3f}"); w_dict['step_y'].set(f"{sy + dsy:.3f}")
            else:
                x0 = self.to_float(w_dict['coords'][0].get()); y0 = self.to_float(w_dict['coords'][1].get())
                x1 = self.to_float(w_dict['coords'][2].get()); y1 = self.to_float(w_dict['coords'][3].get())
                w_dict['coords'][0].set(f"{x0 + dx:.1f}"); w_dict['coords'][1].set(f"{y0 + dy:.1f}")
                w_dict['coords'][2].set(f"{x1 + dx:.1f}"); w_dict['coords'][3].set(f"{y1 + dy:.1f}")
            self.suppress_render = False
            
            self.draw_overlay()
            if self.render_after_id: self.after_cancel(self.render_after_id)
            self.render_after_id = self.after(350, self.execute_render)
            self.cambios_sin_guardar = True
        except Exception: pass

    def elegir_color(self):
        color = colorchooser.askcolor(title="Elegir Color", initialcolor=self.var_color.get())[1]
        if color:
            self.var_color.set(color)
            self.btn_color.config(bg=color)
            self.aplicar_estilo()

    def aplicar_estilo(self, *args):
        if not self.selected_key or self.suppress_render: return
        self.cambios_sin_guardar = True
        
        self.cfg[self.selected_key]["align"] = self.var_align.get()
        self.cfg[self.selected_key]["valign"] = self.var_valign.get()
        self.cfg[self.selected_key]["font"] = self.var_font.get()
        try: self.cfg[self.selected_key]["size"] = int(self.var_size.get() or 10)
        except: pass
        self.cfg[self.selected_key]["bold"] = self.var_bold.get()
        self.cfg[self.selected_key]["italic"] = self.var_italic.get()
        self.cfg[self.selected_key]["underline"] = self.var_underline.get()
        self.cfg[self.selected_key]["color"] = self.var_color.get()
        
        self.handle_spinbox_change()

    def bind_scroll_izq(self, widget, is_spinbox=False):
        if is_spinbox:
            widget.bind("<MouseWheel>", self.on_left_scroll_y_break)
            widget.bind("<Button-4>", self.on_left_scroll_y_break)
            widget.bind("<Button-5>", self.on_left_scroll_y_break)
        else:
            widget.bind("<MouseWheel>", self.on_left_scroll_y, add="+")
            widget.bind("<Button-4>", self.on_left_scroll_y, add="+")
            widget.bind("<Button-5>", self.on_left_scroll_y, add="+")

    def on_left_scroll_y(self, event):
        delta = int(-1 * (event.delta / 120)) if getattr(event, 'delta', 0) else (-1 if getattr(event, 'num', 0) == 4 else 1)
        self.canvas_inputs.yview_scroll(delta, "units")

    def on_left_scroll_y_break(self, event):
        self.on_left_scroll_y(event)
        return "break"

    def on_pdf_scroll_y(self, event):
        if getattr(event, 'state', 0) & 0x0004: return 
        delta = int(-1 * (event.delta / 120)) if getattr(event, 'delta', 0) else (-1 if getattr(event, 'num', 0) == 4 else 1)
        self.canvas_pdf.yview_scroll(delta, "units")

    def on_pdf_scroll_x(self, event):
        delta = int(-1 * (event.delta / 120)) if getattr(event, 'delta', 0) else (-1 if getattr(event, 'num', 0) == 4 else 1)
        self.canvas_pdf.xview_scroll(delta, "units")

    def cambiar_zoom(self, delta):
        nuevo = max(0.5, min(3.0, self.zoom_var.get() + delta))
        self.zoom_var.set(nuevo)
        self.execute_render() 

    def actualizar_texto_zoom(self, *args): 
        self.lbl_zoom.config(text=f"{int(self.zoom_var.get() * 100)}%")

    def on_ctrl_scroll(self, event):
        delta = 0.1 if getattr(event, 'delta', 0) > 0 or getattr(event, 'num', 0) == 4 else -0.1
        self.cambiar_zoom(delta)

    def draw_overlay(self):
        self.canvas_pdf.delete("overlay")
        if self.estado_actual != "EDICION" or not self.selected_key: return
        w_dict = self.item_widgets.get(self.selected_key)
        if not w_dict: return
        try: 
            x0, y0, x1, y1 = [self.to_float(v.get()) for v in w_dict['coords']]
            step_x = self.to_float(w_dict['step_x'].get())
            step_y = self.to_float(w_dict['step_y'].get())
        except ValueError: return
        
        zoom = self.zoom_var.get()
        cx0, cy0 = x0 * zoom, y0 * zoom
        cx1, cy1 = x1 * zoom, y1 * zoom
        color_activo = "#ff9900"
        
        self.canvas_pdf.create_rectangle(cx0, cy0, cx1, cy1, outline=color_activo, width=2, tags="overlay")
        self.canvas_pdf.create_line(cx0, cy0, cx1, cy1, fill=color_activo, width=1, tags="overlay")
        self.canvas_pdf.create_line(cx0, cy1, cx1, cy0, fill=color_activo, width=1, tags="overlay")
        
        h_size = 5
        handles = [(cx0, cy0, "nw"), (cx1, cy0, "ne"), (cx1, cy1, "se"), (cx0, cy1, "sw")]
        for hx, hy, pos in handles:
            self.canvas_pdf.create_rectangle(hx-h_size, hy-h_size, hx+h_size, hy+h_size, fill=color_activo, outline="black", tags=("overlay", f"handle_{pos}"))
        
        self.canvas_pdf.create_text(cx0 + (cx1-cx0)/2, cy0 - 12, text=self.selected_key.replace("_", " ").upper(), fill=color_activo, font=("Helvetica", 10, "bold"), tags="overlay")

        limite = 11 if "check" in self.selected_key.lower() else (10 if (step_x != 0 or step_y != 0) else 1)
        for i in range(0, limite): 
            px0 = cx0 + (step_x * zoom * i); py0 = cy0 + (step_y * zoom * i)
            px1 = cx1 + (step_x * zoom * i); py1 = cy1 + (step_y * zoom * i)
            
            if i > 0:
                self.canvas_pdf.create_rectangle(px0, py0, px1, py1, outline="#88cc00", width=1, dash=(4, 4), tags="overlay")
            
            if "check" in self.selected_key.lower():
                p1 = (px0 + (px1-px0)*0.2, py0 + (py1-py0)*0.5)
                p2 = (px0 + (px1-px0)*0.4, py0 + (py1-py0)*0.8)
                p3 = (px0 + (px1-px0)*0.8, py0 + (py1-py0)*0.2)
                self.canvas_pdf.create_line(p1[0], p1[1], p2[0], p2[1], fill="#88cc00", width=max(1, int(2*zoom)), tags="overlay")
                self.canvas_pdf.create_line(p2[0], p2[1], p3[0], p3[1], fill="#88cc00", width=max(1, int(2*zoom)), tags="overlay")
            elif "pts" in self.selected_key.lower():
                self.canvas_pdf.create_text(px0 + (px1-px0)/2, py0 + (py1-py0)/2, text=str(i+1), fill="#88cc00", font=("Helvetica", max(8, int(8*zoom)), "bold"), tags="overlay")

    def handle_spinbox_change(self, key=None):
        if self.suppress_render: return
        self.cambios_sin_guardar = True
        if key and self.selected_key != key: self.selected_key = key
        if self.render_after_id: self.after_cancel(self.render_after_id)
        self.render_after_id = self.after(350, self.execute_render)
        self.draw_overlay()

    def execute_render(self):
        self.render_after_id = None
        new_cfg = {}
        for k, w_dict in self.item_widgets.items():
            try: 
                coords = [self.to_float(v.get()) for v in w_dict['coords']]
                sx = self.to_float(w_dict['step_x'].get())
                sy = self.to_float(w_dict['step_y'].get())
            except ValueError: return 
            
            item = self.cfg[k].copy()
            item["coords"] = coords
            item["step_x"] = sx
            item["step_y"] = sy
            new_cfg[k] = item
            
        pix = self.parent.exportar_pdf(self.match_node, self.estilo, self.peso, preview_mode=True, config_override=new_cfg, zoom_factor=self.zoom_var.get())
        if pix:
            mode = "RGBA" if pix.alpha else "RGB"
            img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
            self.tk_img = ImageTk.PhotoImage(img) 
            
            self.canvas_pdf.delete("pdf_img") 
            self.canvas_pdf.create_image(0, 0, anchor="nw", image=self.tk_img, tags="pdf_img")
            self.canvas_pdf.tag_lower("pdf_img") 
            self.canvas_pdf.config(scrollregion=self.canvas_pdf.bbox("all"))
            self.draw_overlay()

    def set_bg_color(self, w_dict, bg_color, fg_color, lbl_fg):
        w_dict['frame'].config(bg=bg_color)
        w_dict['lbl'].config(bg=bg_color, fg=fg_color)
        w_dict['f_coords'].config(bg=bg_color)
        w_dict['f_steps'].config(bg=bg_color)
        w_dict['lbl_sx'].config(bg=bg_color, fg=lbl_fg)
        w_dict['lbl_sy'].config(bg=bg_color, fg=lbl_fg)

    def select_box(self, key):
        if self.estado_actual != "EDICION": return
        if self.selected_key != key:
            if self.selected_key and self.selected_key in self.item_widgets:
                self.set_bg_color(self.item_widgets[self.selected_key], "#2a2a2a", "#ffffff", "#aaaaaa")
                
            self.selected_key = key
            self.draw_overlay()
            
            if key in self.item_widgets:
                w_dict = self.item_widgets[key]
                self.set_bg_color(w_dict, "#4a6984", "#ffffff", "#e0e0e0") 
                
                frame_y = w_dict['frame'].winfo_y()
                total_h = self.scrollable_frame.winfo_height()
                canvas_h = self.canvas_inputs.winfo_height()
                
                if total_h > canvas_h:
                    fraction = max(0, (frame_y - canvas_h/3) / total_h)
                    self.canvas_inputs.yview_moveto(fraction)
            
            self.suppress_render = True
            estilo = self.cfg[key]
            self.var_align.set(estilo.get("align", "Izquierda"))
            self.var_valign.set(estilo.get("valign", "Arriba"))
            self.var_font.set(estilo.get("font", "Helvetica"))
            self.var_size.set(str(estilo.get("size", 10)))
            self.var_bold.set(estilo.get("bold", False))
            self.var_italic.set(estilo.get("italic", False))
            self.var_underline.set(estilo.get("underline", False))
            self.var_color.set(estilo.get("color", "#000000"))
            self.btn_color.config(bg=self.var_color.get())
            self.suppress_render = False
            
            self.prop_frame.pack(side="top", fill="x", pady=(5, 5))
            
    def deselect_box(self):
        if self.selected_key:
            if self.selected_key in self.item_widgets:
                self.set_bg_color(self.item_widgets[self.selected_key], "#2a2a2a", "#ffffff", "#aaaaaa")
            self.selected_key = None
            self.prop_frame.pack_forget()
            self.draw_overlay()

    def get_clicked_box(self, x, y):
        zoom = self.zoom_var.get()
        for key, w_dict in reversed(list(self.item_widgets.items())):
            try:
                bx0, by0, bx1, by1 = [self.to_float(v.get()) * zoom for v in w_dict['coords']]
                if bx0 <= x <= bx1 and by0 <= y <= by1: return key
            except ValueError: pass
        return None

    def on_canvas_press(self, event):
        self.canvas_pdf.focus_set() 
        if self.estado_actual != "EDICION": return
        x, y = self.canvas_pdf.canvasx(event.x), self.canvas_pdf.canvasy(event.y)
        self.drag_mode = None
        
        if self.selected_key:
            zoom = self.zoom_var.get()
            try:
                bx0, by0, bx1, by1 = [self.to_float(v.get()) * zoom for v in self.item_widgets[self.selected_key]['coords']]
                hs = 8 
                if bx0-hs <= x <= bx0+hs and by0-hs <= y <= by0+hs: self.drag_mode = "nw"
                elif bx1-hs <= x <= bx1+hs and by0-hs <= y <= by0+hs: self.drag_mode = "ne"
                elif bx1-hs <= x <= bx1+hs and by1-hs <= y <= by1+hs: self.drag_mode = "se"
                elif bx0-hs <= x <= bx0+hs and by1-hs <= y <= by1+hs: self.drag_mode = "sw"
                elif bx0 <= x <= bx1 and by0 <= y <= by1: self.drag_mode = "move"
            except ValueError: pass

        if not self.drag_mode:
            new_sel = self.get_clicked_box(x, y)
            if new_sel:
                self.select_box(new_sel)
                self.drag_mode = "move"
            else:
                self.deselect_box()
                
        if self.drag_mode and self.selected_key:
            self.drag_start_x = x; self.drag_start_y = y
            self.original_coords = [self.to_float(v.get()) for v in self.item_widgets[self.selected_key]['coords']]

    def on_canvas_drag(self, event):
        if self.estado_actual != "EDICION" or not self.drag_mode or not self.selected_key: return
        x, y = self.canvas_pdf.canvasx(event.x), self.canvas_pdf.canvasy(event.y)
        zoom = self.zoom_var.get()
        
        dx = (x - self.drag_start_x) / zoom; dy = (y - self.drag_start_y) / zoom
        x0, y0, x1, y1 = self.original_coords
        
        if self.drag_mode == "move": x0 += dx; x1 += dx; y0 += dy; y1 += dy
        elif self.drag_mode == "nw": x0 += dx; y0 += dy
        elif self.drag_mode == "ne": x1 += dx; y0 += dy
        elif self.drag_mode == "se": x1 += dx; y1 += dy
        elif self.drag_mode == "sw": x0 += dx; y1 += dy
            
        if x0 > x1 - 5:
            if "w" in self.drag_mode: x0 = x1 - 5
            else: x1 = x0 + 5
        if y0 > y1 - 5:
            if "n" in self.drag_mode: y0 = y1 - 5
            else: y1 = y0 + 5
            
        self.suppress_render = True
        sv_list = self.item_widgets[self.selected_key]['coords']
        sv_list[0].set(f"{x0:.1f}"); sv_list[1].set(f"{y0:.1f}")
        sv_list[2].set(f"{x1:.1f}"); sv_list[3].set(f"{y1:.1f}")
        self.suppress_render = False
        self.draw_overlay() 
        
    def on_canvas_release(self, event):
        if self.drag_mode:
            self.drag_mode = None
            self.handle_spinbox_change(self.selected_key) 

    def global_click(self, event):
        if event.widget in (self, self.left_frame, self.right_frame, self.canvas_inputs, self.scrollable_frame):
            if self.estado_actual == "EDICION": self.deselect_box()
            self.focus_set()