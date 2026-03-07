import tkinter as tk
from tkinter import ttk, messagebox

class LogicaRedPareoMixin:
    """Maneja el latido de red durante el torneo, el panel flotante del Máster y la asignación de tapices."""

    def iniciar_torneo_red(self, id_conexion, es_master, tapiz):
        self.id_conexion_red = id_conexion
        self.es_master = es_master
        self.tapiz_asignado = tapiz

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

        self.idx_busqueda = -1

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

        # --- NUEVO: 3.5 Descargar cantidad de llaves confirmadas por el Máster ---
        ids_bloqueados = self.db.obtener_divisiones_bloqueadas(self.id_torneo) if hasattr(self.db, 'obtener_divisiones_bloqueadas') else []
        cantidad_bloqueadas_actual = len(ids_bloqueados)

        # 4. Detectar si hubo cambios en progreso, ganadores O confirmaciones
        estado_anterior_curso = getattr(self, 'combates_en_curso_red', {})
        estado_anterior_resultados = getattr(self, 'resultados_combates', {})
        cantidad_bloqueadas_anterior = getattr(self, 'cantidad_bloqueadas_red', len(self.divisiones_bloqueadas))
        
        hubo_cambios = (nuevos_combates != estado_anterior_curso) or \
                       (nuevos_resultados != estado_anterior_resultados) or \
                       (cantidad_bloqueadas_actual != cantidad_bloqueadas_anterior)
        
        self.combates_en_curso_red = nuevos_combates
        self.cantidad_bloqueadas_red = cantidad_bloqueadas_actual
        
        # Si hubo nuevos ganadores O NUEVAS LLAVES CONFIRMADAS, reconstruimos la matriz lógica
        if (nuevos_resultados != estado_anterior_resultados) or (cantidad_bloqueadas_actual != cantidad_bloqueadas_anterior):
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

