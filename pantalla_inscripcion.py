import tkinter as tk
from tkinter import ttk, messagebox
import re
from datetime import datetime
from conexion_db import ConexionDB
from ventana_nuevo_atleta import VentanaNuevoRegistro

class PantallaInscripcion(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.db = ConexionDB()
        
        self.categorias_db = []
        self.atletas_db = [] 
        self.pesos_oficiales_db = [] # <- NUEVO: Almacena las reglas de la UWW
        self.inscripciones_memoria = []
        
        self.categoria_confirmada = None
        self.torneo_nombre_conf = ""
        self.torneo_lugar_conf = ""

        self.id_atleta_editando = None 
        self.item_tree_editando = None 

        self.var_estilo_libre = tk.BooleanVar()
        self.var_estilo_greco = tk.BooleanVar()
        self.var_estilo_femenina = tk.BooleanVar()

        self.crear_interfaz()
        self.cargar_datos_bd()

    def crear_interfaz(self):
        lbl_titulo = ttk.Label(self, text="Fase 1: Configuración de Torneo e Inscripciones", font=("Helvetica", 16, "bold"))
        lbl_titulo.pack(pady=10)

        # ================= FRAME 1: DATOS DEL TORNEO =================
        self.torneo_frame = ttk.LabelFrame(self, text="1. Datos Generales del Torneo", padding=10)
        self.torneo_frame.pack(fill="x", padx=20, pady=5)

        ttk.Label(self.torneo_frame, text="Nombre:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
        self.ent_tor_nombre = ttk.Entry(self.torneo_frame, width=40)
        self.ent_tor_nombre.grid(row=0, column=1, columnspan=2, sticky="w", pady=5, padx=5)

        ttk.Label(self.torneo_frame, text="Lugar:").grid(row=1, column=0, sticky="w", pady=5, padx=5)
        self.ent_tor_lugar = ttk.Entry(self.torneo_frame, width=40)
        self.ent_tor_lugar.grid(row=1, column=1, columnspan=2, sticky="w", pady=5, padx=5)

        ttk.Label(self.torneo_frame, text="Fecha Realización:").grid(row=2, column=0, sticky="w", pady=5, padx=5)
        self.ent_tor_fecha = ttk.Entry(self.torneo_frame, width=15)
        self.ent_tor_fecha.grid(row=2, column=1, sticky="w", pady=5, padx=5)
        self.ent_tor_fecha.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.ent_tor_fecha.config(state="readonly") 

        ttk.Label(self.torneo_frame, text="Categoría Edad:").grid(row=2, column=2, sticky="e", pady=5, padx=5)
        self.cmb_categoria = ttk.Combobox(self.torneo_frame, state="readonly", width=25)
        self.cmb_categoria.grid(row=2, column=3, sticky="w", pady=5, padx=5)

        btn_torneo_box = ttk.Frame(self.torneo_frame)
        btn_torneo_box.grid(row=3, column=0, columnspan=4, pady=10)

        self.btn_confirmar_torneo = ttk.Button(btn_torneo_box, text="Confirmar Datos de Torneo", command=self.gestionar_bloqueo_torneo)
        self.btn_confirmar_torneo.pack(side="left", padx=5)

        self.btn_cancelar_torneo = ttk.Button(btn_torneo_box, text="Cancelar Edición", command=self.cancelar_edicion_torneo)

        # --- NUEVO BOTÓN DE DEBUG ---
        self.btn_cargar_torneo = ttk.Button(btn_torneo_box, text="Cargar Torneo (Debug)", command=self.abrir_ventana_cargar_torneo)
        self.btn_cargar_torneo.pack(side="right", padx=5)
        
        self.torneo_debug_id = None # Variable para controlar si estamos en modo debug

        # ================= FRAME 2: INSCRIPCIÓN =================
        self.form_frame = ttk.LabelFrame(self, text="2. Inscripción y Pesaje (Confirmar torneo para habilitar)", padding=10)
        self.form_frame.pack(fill="x", padx=20, pady=5)

        ttk.Label(self.form_frame, text="Atleta:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
        self.cmb_atleta = ttk.Combobox(self.form_frame, state="readonly", width=40)
        self.cmb_atleta.grid(row=0, column=1, sticky="w", pady=5, padx=5)
        self.cmb_atleta.bind("<<ComboboxSelected>>", self.al_seleccionar_atleta)

        self.btn_nuevo_atleta = ttk.Button(self.form_frame, text="+ Gestión BD Atletas", command=self.abrir_ventana_nuevo)
        self.btn_nuevo_atleta.grid(row=0, column=2, sticky="w", padx=10)

        # Validación que soporta decimales
        vcmd_peso = (self.register(self.validar_peso), '%P')
        ttk.Label(self.form_frame, text="Peso Exacto (kg):").grid(row=1, column=0, sticky="w", pady=5, padx=5)
        self.ent_peso = ttk.Entry(self.form_frame, width=15, validate='key', validatecommand=vcmd_peso)
        self.ent_peso.grid(row=1, column=1, sticky="w", pady=5, padx=5)

        estilos_frame = ttk.Frame(self.form_frame)
        estilos_frame.grid(row=2, column=0, columnspan=3, sticky="w", pady=5, padx=5)
        self.chk_libre = ttk.Checkbutton(estilos_frame, text="Estilo Libre", variable=self.var_estilo_libre)
        self.chk_libre.pack(side="left", padx=10)
        self.chk_greco = ttk.Checkbutton(estilos_frame, text="Grecorromana", variable=self.var_estilo_greco)
        self.chk_greco.pack(side="left", padx=10)
        self.chk_femenina = ttk.Checkbutton(estilos_frame, text="Femenina", variable=self.var_estilo_femenina)
        self.chk_femenina.pack(side="left", padx=10)

        botones_form_frame = ttk.Frame(self.form_frame)
        botones_form_frame.grid(row=3, column=0, columnspan=3, pady=10)

        self.btn_agregar = ttk.Button(botones_form_frame, text="Añadir a Memoria", command=self.agregar_a_memoria)
        self.btn_agregar.pack(side="left", padx=5)
        self.btn_cancelar_edicion = ttk.Button(botones_form_frame, text="Cancelar Edición", command=self.cancelar_edicion)

        # ================= FRAME 3: TABLA DE MEMORIA OPTIMIZADA =================
        tabla_frame = ttk.LabelFrame(self, text="3. Atletas en Memoria (Pendientes de Subir)", padding=10)
        tabla_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # Columna "peso_oficial" añadida
        columnas = ("id", "idx_local", "atleta", "sexo", "club", "ciudad", "peso", "peso_oficial", "estilos")
        self.tabla = ttk.Treeview(tabla_frame, columns=columnas, show="headings", height=6)
        
        self.tabla.heading("id", text="ID BD")
        self.tabla.heading("idx_local", text="Idx") 
        self.tabla.heading("atleta", text="Atleta")
        self.tabla.heading("sexo", text="Sexo")
        self.tabla.heading("club", text="Club")
        self.tabla.heading("ciudad", text="Ciudad")
        self.tabla.heading("peso", text="Peso Dado")
        self.tabla.heading("peso_oficial", text="Peso Oficial")
        self.tabla.heading("estilos", text="Estilos")
        
        self.tabla.column("id", width=45, anchor="center") 
        self.tabla.column("idx_local", width=0, stretch=tk.NO) 
        self.tabla.column("atleta", width=180, anchor="w")
        self.tabla.column("sexo", width=40, anchor="center")
        self.tabla.column("club", width=120, anchor="w")
        self.tabla.column("ciudad", width=90, anchor="w")
        self.tabla.column("peso", width=70, anchor="center")
        self.tabla.column("peso_oficial", width=110, anchor="center")
        self.tabla.column("estilos", width=140, anchor="w")
        
        self.tabla.pack(side="top", fill="both", expand=True)

        btn_box = ttk.Frame(tabla_frame)
        btn_box.pack(fill="x", pady=5)
        
        ttk.Button(btn_box, text="Eliminar Seleccionado", command=self.eliminar_de_memoria).pack(side="left", padx=5)
        ttk.Button(btn_box, text="Editar Seleccionado", command=self.cargar_para_editar).pack(side="left", padx=5)
        ttk.Button(btn_box, text="Confirmar y Subir a Base de Datos", command=self.subir_inscripciones_bd).pack(side="right")

        self.cambiar_estado_inscripcion("disabled")

    # ================= VALIDACIONES =================
    def validar_peso(self, P):
        """Permite borrar y admite números con hasta 2 decimales (ej. 74 o 74.55)."""
        if P == "": return True
        # RegEx: Máximo 3 enteros, un punto opcional, y máximo 2 decimales
        match = re.match(r'^\d{0,3}(\.\d{0,2})?$', P)
        return match is not None

    # ================= LÓGICA DE TORNEO =================
    def cambiar_estado_inscripcion(self, estado):
        estado_cmb = "readonly" if estado == "normal" else "disabled"
        self.cmb_atleta.config(state=estado_cmb)
        self.btn_nuevo_atleta.config(state=estado)
        self.ent_peso.config(state=estado)
        self.btn_agregar.config(state=estado)
        
        if estado == "disabled":
            self.chk_libre.config(state="disabled")
            self.chk_greco.config(state="disabled")
            self.chk_femenina.config(state="disabled")

    def gestionar_bloqueo_torneo(self):
        if self.btn_confirmar_torneo.cget("text") == "Modificar Torneo":
            self.ent_tor_nombre.config(state="normal")
            self.ent_tor_lugar.config(state="normal")
            self.cmb_categoria.config(state="readonly")
            self.btn_confirmar_torneo.config(text="Guardar Cambios")
            self.btn_cancelar_torneo.pack(side="left", padx=5)
            self.cambiar_estado_inscripcion("disabled")
            self.form_frame.config(text="2. Inscripción y Pesaje (Confirmar torneo para habilitar)")
            return

        nombre = self.ent_tor_nombre.get().strip()
        lugar = self.ent_tor_lugar.get().strip()
        cat = self.cmb_categoria.get()

        if not nombre or not lugar or not cat:
            return messagebox.showwarning("Incompleto", "Llene nombre, lugar y categoría.")

        if self.categoria_confirmada is not None and self.categoria_confirmada != cat:
            if self.inscripciones_memoria:
                respuesta = messagebox.askyesno("Cambio de Categoría", "Cambiar la categoría borrará las inscripciones actuales. ¿Desea continuar?")
                if not respuesta:
                    self.cmb_categoria.set(self.categoria_confirmada)
                    return
                else:
                    self.inscripciones_memoria.clear()
                    for item in self.tabla.get_children(): self.tabla.delete(item)

        self.torneo_nombre_conf = nombre
        self.torneo_lugar_conf = lugar
        self.categoria_confirmada = cat

        self.ent_tor_nombre.config(state="disabled")
        self.ent_tor_lugar.config(state="disabled")
        self.cmb_categoria.config(state="disabled")
        
        self.btn_confirmar_torneo.config(text="Modificar Torneo")
        self.btn_cancelar_torneo.pack_forget()

        self.form_frame.config(text="2. Inscripción y Pesaje (Habilitado)")
        self.filtrar_atletas_por_edad()
        self.cambiar_estado_inscripcion("normal")

    def cancelar_edicion_torneo(self):
        self.ent_tor_nombre.delete(0, tk.END); self.ent_tor_nombre.insert(0, self.torneo_nombre_conf)
        self.ent_tor_lugar.delete(0, tk.END); self.ent_tor_lugar.insert(0, self.torneo_lugar_conf)
        self.cmb_categoria.set(self.categoria_confirmada)

        self.ent_tor_nombre.config(state="disabled"); self.ent_tor_lugar.config(state="disabled"); self.cmb_categoria.config(state="disabled")
        self.btn_confirmar_torneo.config(text="Modificar Torneo")
        self.btn_cancelar_torneo.pack_forget()
        self.form_frame.config(text="2. Inscripción y Pesaje (Habilitado)")
        self.cambiar_estado_inscripcion("normal")

    # ================= LÓGICA DE INSCRIPCIONES Y PESOS OFICIALES =================
    def cargar_para_editar(self):
        item_sel = self.tabla.selection()
        if not item_sel: return messagebox.showwarning("Selección", "Seleccione un atleta de la tabla.")
        
        valores = self.tabla.item(item_sel[0], "values")
        self.id_atleta_editando = int(valores[0])
        self.item_tree_editando = item_sel[0]

        self.cmb_atleta.current(int(valores[1]))
        self.al_seleccionar_atleta(None)
        
        self.ent_peso.delete(0, tk.END)
        self.ent_peso.insert(0, valores[6]) # El peso dado está en índice 6

        # Los estilos están en el índice 8 ahora, porque el oficial ocupa el 7
        self.var_estilo_libre.set(True if "Libre" in valores[8] else False) 
        self.var_estilo_greco.set(True if "Grecorromana" in valores[8] else False)
        self.var_estilo_femenina.set(True if "Femenina" in valores[8] else False)

        self.btn_agregar.config(text="Actualizar Inscripción")
        self.btn_cancelar_edicion.pack(side="left", padx=5)
        self.cmb_atleta.config(state="disabled")

    def cancelar_edicion(self):
        self.id_atleta_editando = None
        self.item_tree_editando = None
        self.btn_agregar.config(text="Añadir a Memoria")
        self.btn_cancelar_edicion.pack_forget()
        self.cmb_atleta.config(state="readonly")
        self.cmb_atleta.set('')
        self.ent_peso.delete(0, tk.END)
        self.var_estilo_libre.set(False); self.var_estilo_greco.set(False); self.var_estilo_femenina.set(False)

    def agregar_a_memoria(self):
        idx = self.cmb_atleta.current()
        peso_str = self.ent_peso.get().strip()
        if idx == -1 or not peso_str: return messagebox.showwarning("Incompleto", "Seleccione atleta y peso.")
        try: peso_dado = float(peso_str)
        except ValueError: return messagebox.showwarning("Error", "Peso con formato inválido.")

        atleta = self.atletas_filtrados_objetos[idx]
        estilos_sel = []
        if self.var_estilo_libre.get(): estilos_sel.append(("Libre", 1))
        if self.var_estilo_greco.get(): estilos_sel.append(("Grecorromana", 2))
        if self.var_estilo_femenina.get(): estilos_sel.append(("Femenina", 3))

        if not estilos_sel: return messagebox.showwarning("Estilo Requerido", "Debe seleccionar al menos un estilo.")

        id_cat_torneo = next((c['id'] for c in self.categorias_db if c['nombre'] == self.categoria_confirmada), None)
        pesos_oficiales_text, estilos_memoria, ids_divisiones = [], [], [] # <- Modificado aquí

        for nombre_estilo, id_estilo in estilos_sel:
            bracket_encontrado = None
            for p in self.pesos_oficiales_db:
                if p['id_categoria_edad'] == id_cat_torneo and p['id_estilo_lucha'] == id_estilo:
                    if p['peso_minimo'] <= peso_dado <= p['peso_maximo']:
                        bracket_encontrado = p
                        break
            if not bracket_encontrado: return messagebox.showwarning("Fuera de Rango", f"Peso inválido para {nombre_estilo}.")
            
            pesos_oficiales_text.append(f"{nombre_estilo[:3]}: {bracket_encontrado['peso_maximo']}kg")
            estilos_memoria.append(nombre_estilo)
            ids_divisiones.append(bracket_encontrado['id']) # <- Guardamos el ID oficial

        texto_peso_oficial = " | ".join(pesos_oficiales_text)
        fila_valores = (atleta['id'], idx, f"{atleta['apellidos']}, {atleta['nombre']}", atleta['sexo'], atleta['club'], atleta['ciudad'], peso_str, texto_peso_oficial, " + ".join(estilos_memoria))

        if self.id_atleta_editando is not None:
            for ins in self.inscripciones_memoria:
                if ins['id_atleta'] == self.id_atleta_editando:
                    ins['peso'] = peso_str; ins['peso_oficial'] = texto_peso_oficial; ins['estilos'] = estilos_memoria; ins['ids_divisiones'] = ids_divisiones
                    break
            self.tabla.item(self.item_tree_editando, values=fila_valores)
            self.cancelar_edicion()
            return messagebox.showinfo("Actualizado", "Inscripción actualizada.")

        for ins in self.inscripciones_memoria:
            if ins['id_atleta'] == atleta['id']: return messagebox.showwarning("Duplicado", "Este atleta ya está en la lista.")

        self.inscripciones_memoria.append({"id_atleta": atleta['id'], "peso": peso_str, "peso_oficial": texto_peso_oficial, "estilos": estilos_memoria, "ids_divisiones": ids_divisiones}) # <- Añadido
        self.tabla.insert("", "end", values=fila_valores)
        self.ent_peso.delete(0, tk.END); self.cmb_atleta.set('')
        self.var_estilo_libre.set(False); self.var_estilo_greco.set(False); self.var_estilo_femenina.set(False)

    def eliminar_de_memoria(self):
        item_sel = self.tabla.selection()
        if not item_sel: return messagebox.showwarning("Selección", "Seleccione un atleta de la tabla.")
        
        item_a_borrar = item_sel[0]
        valores = self.tabla.item(item_a_borrar, "values")
        nombre_atleta = valores[2]
        
        respuesta = messagebox.askyesno("Confirmar Eliminación", f"¿Seguro que desea eliminar a '{nombre_atleta}' de las inscripciones?")
        if not respuesta: return
            
        if self.item_tree_editando == item_a_borrar: self.cancelar_edicion() 
            
        id_atleta = int(valores[0])
        self.inscripciones_memoria = [ins for ins in self.inscripciones_memoria if ins['id_atleta'] != id_atleta]
        self.tabla.delete(item_a_borrar)

    # ================= CARGA DE DATOS =================
    def cargar_datos_bd(self):
        self.categorias_db = self.db.obtener_categorias()
        if self.categorias_db:
            self.cmb_categoria['values'] = [cat['nombre'] for cat in self.categorias_db]
            
        self.pesos_oficiales_db = self.db.obtener_pesos_oficiales()
        self.atletas_db = self.db.obtener_atletas()
        
        if self.btn_confirmar_torneo.cget("text") == "Modificar Torneo":
            self.filtrar_atletas_por_edad()

    def filtrar_atletas_por_edad(self):
        idx_cat = self.cmb_categoria.current()
        if idx_cat == -1: return

        cat = self.categorias_db[idx_cat]
        anio_torneo = datetime.now().year
        self.atletas_filtrados_objetos = []
        atletas_permitidos = []

        for atleta in self.atletas_db:
            edad_uww = anio_torneo - atleta['fecha_nacimiento'].year
            if cat['edad_minima'] <= edad_uww <= cat['edad_maxima']:
                atletas_permitidos.append(f"{atleta['apellidos']}, {atleta['nombre']} (ID: {atleta['id']})")
                self.atletas_filtrados_objetos.append(atleta)

        self.cmb_atleta['values'] = atletas_permitidos
        self.cmb_atleta.set('')

    def al_seleccionar_atleta(self, event):
        idx = self.cmb_atleta.current()
        if idx == -1: return
        atleta = self.atletas_filtrados_objetos[idx]

        self.var_estilo_libre.set(False); self.var_estilo_greco.set(False); self.var_estilo_femenina.set(False)

        if atleta['sexo'] == 'M':
            self.chk_libre.config(state="normal"); self.chk_greco.config(state="normal"); self.chk_femenina.config(state="disabled")
            self.var_estilo_libre.set(True)
        else:
            self.chk_libre.config(state="disabled"); self.chk_greco.config(state="disabled"); self.chk_femenina.config(state="normal")
            self.var_estilo_femenina.set(True)

    def abrir_ventana_nuevo(self):
        VentanaNuevoRegistro(self)

    def subir_inscripciones_bd(self):
        if not self.inscripciones_memoria: 
            return messagebox.showwarning("Sin Atletas", "No hay atletas inscritos.")
        
        # --- NUEVO: SI ESTAMOS EN MODO DEBUG, SALTAR DIRECTO A PAREO ---
        if getattr(self, "torneo_debug_id", None) is not None:
            from pantalla_pareo import PantallaPareo
            p_pareo = self.controller.pantallas.get(PantallaPareo)
            if p_pareo:
                p_pareo.cargar_torneo(self.torneo_debug_id)
                self.controller.mostrar_pantalla(PantallaPareo)
            self.torneo_debug_id = None # Limpiamos por si el usuario vuelve atrás
            return
            
        # 1. Agrupar inscripciones por división (estilo y peso) para contar parejas
        divisiones = {}
        for ins in self.inscripciones_memoria:
            id_atleta = ins['id_atleta']
            # Buscar el nombre del atleta para mostrarlo en el mensaje
            nombre_atleta = next((f"{a['apellidos']}, {a['nombre']}" for a in self.atletas_db if a['id'] == id_atleta), "Atleta Desconocido")
            
            for i, id_div in enumerate(ins['ids_divisiones']):
                estilo = ins['estilos'][i]
                
                # Obtener el peso máximo oficial para mostrarlo en el mensaje
                peso_oficial_str = "Desconocido"
                for p in self.pesos_oficiales_db:
                    if p['id'] == id_div:
                        peso_oficial_str = f"{p['peso_maximo']}kg"
                        break
                        
                clave_div = (id_div, estilo, peso_oficial_str)
                if clave_div not in divisiones:
                    divisiones[clave_div] = []
                divisiones[clave_div].append(nombre_atleta)
                
        # 2. Validar si hay al menos una pareja y agrupar a los solitarios por nombre
        hay_pareja = False
        atletas_solitarios = {} # Diccionario: { "Perez, Juan": ["Libre - 74kg", "Greco - 74kg"] }
        
        for (id_div, estilo, peso_str), atletas in divisiones.items():
            if len(atletas) >= 2:
                hay_pareja = True
            elif len(atletas) == 1:
                nombre = atletas[0]
                div_str = f"{estilo} - {peso_str}"
                
                # Agrupamos por atleta
                if nombre not in atletas_solitarios:
                    atletas_solitarios[nombre] = []
                atletas_solitarios[nombre].append(div_str)
                
        # 3. Regla A: Debe haber al menos una pareja en todo el torneo
        if not hay_pareja:
            return messagebox.showwarning("Parejas Insuficientes", "Debe haber al menos 2 atletas en una misma división de peso y estilo para poder generar un torneo válido.")
            
        # 4. Regla B: Avisar si hay atletas sin pareja antes de confirmar (agrupados)
        if atletas_solitarios:
            solitarios_lista = []
            # Formatear el texto: Nombre (División 1, División 2)
            for nombre, divs in atletas_solitarios.items():
                solitarios_lista.append(f"• {nombre} ({', '.join(divs)})")
                
            mensaje = "Los siguientes atletas están solos en su división (sin oponente):\n\n"
            mensaje += "\n".join(solitarios_lista[:15])
            if len(solitarios_lista) > 15:
                mensaje += f"\n... y {len(solitarios_lista) - 15} más."
            mensaje += "\n\n¿Desea continuar y subir el torneo de todos modos?"
            
            respuesta = messagebox.askyesno("Atletas sin oponente", mensaje)
            if not respuesta:
                return # El usuario cancela la subida

        # --- Continuar con el guardado en BD ---
        id_cat = next((c['id'] for c in self.categorias_db if c['nombre'] == self.categoria_confirmada), None)
        try: fecha_db = datetime.strptime(self.ent_tor_fecha.get().strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
        except: fecha_db = datetime.now().strftime("%Y-%m-%d")

        datos_torneo = {"nombre": self.torneo_nombre_conf, "lugar": self.torneo_lugar_conf, "fecha": fecha_db, "id_categoria": id_cat}
        
        # Guardar en Base de Datos
        # (Asegúrate de que 'self.db.guardar_torneo_completo' esté correctamente implementado en conexion_db.py)
        id_torneo = self.db.guardar_torneo_completo(datos_torneo, self.inscripciones_memoria)
        
        if id_torneo:
            messagebox.showinfo("Éxito", "Torneo guardado en la Base de Datos. Pasando a Fase de Pareos.")
            from pantalla_pareo import PantallaPareo
            p_pareo = self.controller.pantallas.get(PantallaPareo)
            if p_pareo:
                p_pareo.cargar_torneo(id_torneo)
                self.controller.mostrar_pantalla(PantallaPareo)
        else:
            messagebox.showerror("Error", "Error al guardar en la base de datos.")

    def abrir_ventana_cargar_torneo(self):
        ventana = tk.Toplevel(self)
        ventana.title("Seleccionar Torneo (Debug)")
        ventana.geometry("600x300")
        ventana.transient(self)
        ventana.grab_set()

        columnas = ("id", "nombre", "fecha", "categoria")
        tabla_torneos = ttk.Treeview(ventana, columns=columnas, show="headings")
        tabla_torneos.heading("id", text="ID"); tabla_torneos.column("id", width=50, anchor="center")
        tabla_torneos.heading("nombre", text="Nombre"); tabla_torneos.column("nombre", width=250, anchor="w")
        tabla_torneos.heading("fecha", text="Fecha"); tabla_torneos.column("fecha", width=100, anchor="center")
        tabla_torneos.heading("categoria", text="Categoría Edad"); tabla_torneos.column("categoria", width=150, anchor="center")
        tabla_torneos.pack(fill="both", expand=True, padx=10, pady=10)

        torneos = self.db.obtener_lista_torneos_debug()
        for t in torneos:
            tabla_torneos.insert("", "end", values=(t['id'], t['nombre'], t['fecha'], t['categoria']))

        btn_cargar = ttk.Button(ventana, text="Cargar en Pantalla", command=lambda: self.ejecutar_carga_torneo(tabla_torneos, ventana))
        btn_cargar.pack(pady=10)

    def ejecutar_carga_torneo(self, tabla, ventana):
        item_sel = tabla.selection()
        if not item_sel: return messagebox.showwarning("Selección", "Seleccione un torneo.")
        
        id_torneo = int(tabla.item(item_sel[0], "values")[0])
        ventana.destroy()

        datos_torneo, inscripciones = self.db.obtener_torneo_completo_debug(id_torneo)
        if not datos_torneo: return

        # 1. Llenar los campos de torneo
        self.ent_tor_nombre.config(state="normal"); self.ent_tor_nombre.delete(0, tk.END); self.ent_tor_nombre.insert(0, datos_torneo['nombre'])
        self.ent_tor_lugar.config(state="normal"); self.ent_tor_lugar.delete(0, tk.END); self.ent_tor_lugar.insert(0, datos_torneo['lugar'])
        self.ent_tor_fecha.config(state="normal"); self.ent_tor_fecha.delete(0, tk.END); self.ent_tor_fecha.insert(0, datos_torneo['fecha']); self.ent_tor_fecha.config(state="readonly")
        self.cmb_categoria.config(state="normal"); self.cmb_categoria.set(datos_torneo['categoria'])

        # 2. Limpiar memoria y tabla
        self.inscripciones_memoria.clear()
        for item in self.tabla.get_children(): self.tabla.delete(item)

        # 3. Agrupar estilos por atleta (reconstrucción de memoria)
        atletas_agrupados = {}
        for ins in inscripciones:
            id_atl = ins['id_peleador']
            if id_atl not in atletas_agrupados:
                atletas_agrupados[id_atl] = {"datos_bd": ins, "estilos": [], "pesos_text": [], "ids_divisiones": []}
            atletas_agrupados[id_atl]["estilos"].append(ins['estilo'])
            atletas_agrupados[id_atl]["pesos_text"].append(f"{ins['estilo'][:3]}: {ins['peso_maximo']}kg")
            atletas_agrupados[id_atl]["ids_divisiones"].append(ins['id_division'])

        # 4. Llenar la tabla visual y la memoria local
        for id_atl, data in atletas_agrupados.items():
            info = data["datos_bd"]
            texto_peso_oficial = " | ".join(data["pesos_text"])
            
            self.inscripciones_memoria.append({
                "id_atleta": id_atl, "peso": str(info['peso_pesaje']),
                "peso_oficial": texto_peso_oficial, "estilos": data["estilos"], "ids_divisiones": data["ids_divisiones"]
            })
            
            fila_valores = (id_atl, 0, f"{info['apellidos']}, {info['nombre']}", info['sexo'], info['club'] or "Sin Club", info['ciudad'] or "Sin Ciudad", str(info['peso_pesaje']), texto_peso_oficial, " + ".join(data["estilos"]))
            self.tabla.insert("", "end", values=fila_valores)

        # 5. Bloquear pantalla y guardar estado debug
        self.torneo_debug_id = id_torneo
        self.gestionar_bloqueo_torneo()
        messagebox.showinfo("Cargado", "Torneo cargado en memoria. Dele a 'Confirmar y Subir a BD' para saltar directamente a la Fase de Pareos.")
