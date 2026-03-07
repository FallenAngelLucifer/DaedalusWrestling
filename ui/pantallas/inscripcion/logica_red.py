import tkinter as tk
from tkinter import ttk, messagebox

class LogicaRedMixin:
    """Maneja la sincronización en vivo, roles de Máster/Invitado y asignación de tapices."""

    def gestionar_estado_botones_red(self, event=None):
        """Activa o desactiva los botones de red según las reglas exactas de selección y el rol."""
        
        # --- NUEVO: CORTAFUEGOS PARA TORNEO FINALIZADO (MODO VISITANTE) ---
        if getattr(self, "torneo_finalizado", False):
            if hasattr(self, 'tabla_red') and self.tabla_red.selection():
                self.tabla_red.selection_remove(self.tabla_red.selection())
            return

        # --- ESCUDO PARA INVITADOS ---
        if not getattr(self.controller, 'es_master', False):
            # Si un invitado intenta hacer clic, deseleccionamos la fila al instante
            if hasattr(self, 'tabla_red') and self.tabla_red.selection():
                self.tabla_red.selection_remove(self.tabla_red.selection())
            
            # Asegurar que todos los controles de red estén apagados
            if hasattr(self, 'btn_confirmar_red'): self.btn_confirmar_red.config(state="disabled")
            if hasattr(self, 'btn_eliminar_red'): self.btn_eliminar_red.config(state="disabled")
            if hasattr(self, 'btn_intercambiar_tapiz'): self.btn_intercambiar_tapiz.config(state="disabled")
            if hasattr(self, 'btn_ceder_master'): self.btn_ceder_master.config(state="disabled")
            return

        # --- LÓGICA PARA EL MÁSTER ---
        seleccionados = self.tabla_red.selection()
        cantidad = len(seleccionados)
        
        # Estado por defecto (Todo bloqueado)
        est_conf = "disabled"
        est_elim = "disabled"
        est_inter = "disabled"
        est_ceder = "disabled"
        
        if cantidad == 1:
            tags = self.tabla_red.item(seleccionados[0], "tags")
            es_yo = "yo_mismo" in tags
            es_confirmado = "confirmado" in tags
            es_pendiente = "pendiente" in tags
            
            if es_yo:
                pass # Regla 1: Se seleccionó a sí mismo. Todo bloqueado.
            elif es_confirmado:
                # Regla 2: Seleccionó a alguien confirmado.
                est_elim = "normal"
                est_ceder = "normal"
            elif es_pendiente:
                # Regla 3: Seleccionó a un pendiente.
                est_conf = "normal"
                est_elim = "normal"
                
        elif cantidad == 2:
            # Regla 4: Dos seleccionados para intercambio.
            tags1 = self.tabla_red.item(seleccionados[0], "tags")
            tags2 = self.tabla_red.item(seleccionados[1], "tags")
            
            valido1 = "confirmado" in tags1 or "yo_mismo" in tags1
            valido2 = "confirmado" in tags2 or "yo_mismo" in tags2
            
            if valido1 and valido2:
                est_inter = "normal"

        # Aplicamos los estados
        if hasattr(self, 'btn_confirmar_red'): self.btn_confirmar_red.config(state=est_conf)
        if hasattr(self, 'btn_eliminar_red'): self.btn_eliminar_red.config(state=est_elim)
        if hasattr(self, 'btn_intercambiar_tapiz'): self.btn_intercambiar_tapiz.config(state=est_inter)
        if hasattr(self, 'btn_ceder_master'): self.btn_ceder_master.config(state=est_ceder)

    def actualizar_botones_guardado(self):
        """Evalúa las reglas visuales de los botones inferiores y de edición."""
        if not hasattr(self, 'btn_guardar_torneo'): return

        is_finalizado = getattr(self, "torneo_finalizado", False)
        is_todo_bloqueado = getattr(self, "todo_bloqueado", False)
        has_id = getattr(self, "torneo_debug_id", None) is not None
        es_master = getattr(self.controller, 'es_master', False)

        # --- NUEVO: Validar si soy un invitado en espera ---
        texto_lbl = self.lbl_tapete_master.cget("text") if hasattr(self, 'lbl_tapete_master') else ""
        soy_guest_pendiente = (not es_master and "⏳" in texto_lbl)

        # 1. SI EL TORNEO ESTÁ CERRADO O TODAS LAS LLAVES CONFIRMADAS
        if is_finalizado or is_todo_bloqueado:
            self.btn_guardar_torneo.pack_forget() 
            if hasattr(self, 'frame_acciones_memoria'):
                self.frame_acciones_memoria.pack_forget() 
            if hasattr(self, 'btn_avanzar_pareo'):
                # BLOQUEO: Si el invitado no está aprobado, no puede avanzar aunque el torneo esté listo
                # EXCEPCIÓN: Si el torneo está FINALIZADO, TODOS pueden avanzar para ver el historial
                if soy_guest_pendiente and not is_finalizado:
                    self.btn_avanzar_pareo.config(state="disabled")
                else:
                    self.btn_avanzar_pareo.config(state="normal")
            return

        # 2. SI EL TORNEO ESTÁ ACTIVO
        if hasattr(self, 'frame_acciones_memoria') and not self.frame_acciones_memoria.winfo_ismapped():
            self.frame_acciones_memoria.pack(side="left", before=self.lbl_estadisticas)

        if has_id:
            if not self.btn_guardar_torneo.winfo_ismapped():
                self.btn_guardar_torneo.pack(side="left", fill="x", expand=True, padx=(0, 2))
                
            if es_master:
                self.btn_guardar_torneo.config(state="normal", text="💾 Guardar Cambios")
                estado_pareo = "normal" 
            else:
                estado = "normal" if "✅" in texto_lbl else "disabled"
                self.btn_guardar_torneo.config(state=estado, text="☁️ Sincronizar Atletas")
                estado_pareo = estado 
                
            if hasattr(self, 'btn_avanzar_pareo'):
                self.btn_avanzar_pareo.config(state=estado_pareo)
                
        else:
            if not self.btn_guardar_torneo.winfo_ismapped():
                self.btn_guardar_torneo.pack(side="left", fill="x", expand=True, padx=(0, 2))
                
            if getattr(self, 'categoria_confirmada', None):
                self.btn_guardar_torneo.config(state="normal", text="✅ Confirmar y Crear Sala")
            else:
                self.btn_guardar_torneo.config(state="disabled", text="✅ Confirmar y Crear Sala")
                
            if hasattr(self, 'btn_avanzar_pareo'):
                self.btn_avanzar_pareo.config(state="disabled")

    def confirmar_arbitro_red(self):
        item_sel = self.tabla_red.selection()
        if not item_sel: return messagebox.showwarning("Selección", "Seleccione un árbitro pendiente de la tabla.")
        
        # PROTECCIÓN: Evitar auto-confirmar al Máster
        tags = self.tabla_red.item(item_sel[0], "tags")
        if "yo_mismo" in tags and getattr(self.controller, 'es_master', False):
            return messagebox.showwarning("Aviso", "No puedes confirmarte a ti mismo, ya eres el administrador de la sala.")
            
        self.tabla_red.item(item_sel[0], tags=("confirmado",))
        self.actualizar_letras_tapices()
        self.sincronizar_tapices_db()

    def eliminar_arbitro_red(self):
        item_sel = self.tabla_red.selection()
        if not item_sel: return messagebox.showwarning("Selección", "Seleccione un árbitro de la tabla.")
        
        id_conexion = self.tabla_red.item(item_sel[0], "values")[0]
        
        # PROTECCIÓN: Evitar auto-eliminación
        if str(id_conexion) == str(self.controller.id_conexion_red):
            return messagebox.showwarning("Aviso", "No puedes eliminarte a ti mismo.\n\nSi deseas abandonar la sala, utiliza el botón de Cerrar Sesión o Cede el Máster.")
            
        if messagebox.askyesno("Confirmar", "¿Desea desconectar y eliminar a este árbitro de la sala?"):
            self.db.eliminar_conexion_instancia(id_conexion) 
            if getattr(self, 'torneo_debug_id', None):
                self.refrescar_tabla_red_master(self.torneo_debug_id)

    def intercambiar_tapiz(self):
        """Cruza los tapices asignados de los dos árbitros seleccionados."""
        seleccionados = self.tabla_red.selection()
        if len(seleccionados) != 2:
            return messagebox.showwarning("Aviso", "Seleccione exactamente dos árbitros confirmados para intercambiar.")
            
        # Extraemos los datos del Árbitro 1
        id1 = self.tabla_red.item(seleccionados[0], "values")[0]
        tapiz1 = self.tabla_red.item(seleccionados[0], "values")[3]
        
        # Extraemos los datos del Árbitro 2
        id2 = self.tabla_red.item(seleccionados[1], "values")[0]
        tapiz2 = self.tabla_red.item(seleccionados[1], "values")[3]
        
        # Hacemos el cruce directo en la Base de Datos
        if hasattr(self.db, 'asignar_tapiz_a_cliente'):
            self.db.asignar_tapiz_a_cliente(id1, tapiz2)
            self.db.asignar_tapiz_a_cliente(id2, tapiz1)
            
        # Si uno de los involucrados es el Máster, actualizamos su variable interna
        mi_id = str(self.controller.id_conexion_red)
        if str(id1) == mi_id:
            self.controller.tapiz_asignado = tapiz2
        elif str(id2) == mi_id:
            self.controller.tapiz_asignado = tapiz1
            
        # Forzamos refresco visual instantáneo
        self.refrescar_tabla_red_master(self.torneo_debug_id)

    # --- NUEVA FUNCIÓN A AGREGAR ---
    def sincronizar_tapices_db(self):
        for item in self.tabla_red.get_children():
            valores = self.tabla_red.item(item, "values")
            tags = self.tabla_red.item(item, "tags")
            
            es_master_local = ("yo_mismo" in tags and getattr(self.controller, 'es_master', False))
            if "confirmado" in tags or es_master_local:
                self.db.asignar_tapiz_a_cliente(valores[0], valores[3])

    def actualizar_letras_tapices(self):
        """Asigna las letras (Tapiz A, B, C) por orden de lista, incluyendo al Máster."""
        items = self.tabla_red.get_children()
        ascii_letra = 65 # Empezamos en la letra 'A'
        
        for item in items:
            valores_actuales = list(self.tabla_red.item(item, "values"))
            tags_actuales = self.tabla_red.item(item, "tags")
            
            # El Máster siempre cuenta como confirmado para la letra
            es_master_local = ("yo_mismo" in tags_actuales and getattr(self.controller, 'es_master', False))
            
            if "confirmado" in tags_actuales or es_master_local:
                valores_actuales[3] = f"Tapiz {chr(ascii_letra)}"
                ascii_letra += 1
                
                # Si es mi fila de Máster, actualizo mi variable interna para que mi computadora lo sepa
                if es_master_local:
                    self.controller.tapiz_asignado = valores_actuales[3]
            else:
                valores_actuales[3] = "Pendiente"
                
            self.tabla_red.item(item, values=valores_actuales)

    def ceder_master(self):
        """Transfiere los poderes de administrador a otro árbitro."""
        item_sel = self.tabla_red.selection()
        if not item_sel: return messagebox.showwarning("Selección", "Seleccione al árbitro al que desea transferir el mando.")
        
        id_conexion_sel = self.tabla_red.item(item_sel[0], "values")[0]
        nombre_sel = self.tabla_red.item(item_sel[0], "values")[1].replace("⭐ ", "") 
        
        if str(id_conexion_sel) == str(self.controller.id_conexion_red):
            return messagebox.showwarning("Aviso", "No puedes cederte el control a ti mismo.")
            
        tags = self.tabla_red.item(item_sel[0], "tags")
        if "pendiente" in tags:
            return messagebox.showwarning("Aviso", "El árbitro debe estar confirmado en la red antes de poder cederle el control.")

        mensaje = f"Está a punto de CEDER EL CONTROL de la sala a:\n\n{nombre_sel}\n\nSi cede el Máster, usted pasará a ser un invitado y perderá los privilegios.\nSólo podrá recuperar el control si el nuevo Máster se lo devuelve o se desconecta.\n\n¿Desea continuar?"
        
        if messagebox.askyesno("Ceder Máster", mensaje):
            if hasattr(self.db, 'transferir_master'):
                exito = self.db.transferir_master(self.torneo_debug_id, id_conexion_sel)
                if exito:
                    # 1. Degradación de rol
                    self.controller.es_master = False
                    
                    # 2. Deseleccionar todo para limpiar la interfaz
                    self.tabla_red.selection_remove(self.tabla_red.selection())
                    
                    # 3. Llamar al cerebro para que aplique el Escudo de Invitado
                    self.gestionar_estado_botones_red()
                    
                    # 4. --- NUEVO: Activar Escudo de Torneo y Botón Sincronizar ---
                    self.bloquear_datos_torneo(True)
                    if hasattr(self, 'btn_guardar_torneo'):
                        self.btn_guardar_torneo.config(state="normal", text="☁️ Sincronizar Atletas")
                    
                    messagebox.showinfo("Control Cedido", "Has cedido el control. Ahora eres un invitado en la sala.")
                    
                    # 5. Entrar en modo Invitado
                    self.comprobar_estado_guest(self.torneo_debug_id, self.controller.id_conexion_red)
            else:
                messagebox.showerror("Error", "La función no está implementada en la base de datos.")

    def iniciar_escucha_red(self):
        """Inicia el bucle que consulta la BD cada 3 segundos."""
        if not hasattr(self, 'escuchando_red') or not self.escuchando_red:
            self.escuchando_red = True
            self.ciclo_escucha_red()
            self.escuchar_nuevos_atletas_red() # <--- NUEVO MOTOR ACTIVADO

    def ciclo_escucha_red(self):
        if not getattr(self, "escuchando_red", False): return
        
        id_torneo = getattr(self, 'torneo_debug_id', None)
        id_mi_conexion = getattr(self.controller, 'id_conexion_red', None)
        if not id_torneo or not id_mi_conexion: return

        mi_estado = self.db.verificar_estado_mi_conexion(id_mi_conexion)
        if not mi_estado:
            self.escuchando_red = False
            self.controller.id_conexion_red = None
            self.controller.es_master = False
            messagebox.showwarning("Desconectado", "Has sido desconectado de la sala.")
            self.resetear_torneo(forzar=True)
            return

        if hasattr(self.db, 'mantener_latido_conexion'):
            self.db.mantener_latido_conexion(id_mi_conexion)

        is_master_db = mi_estado.get('es_master', False)
        was_master_local = getattr(self.controller, 'es_master', False)

        # 2. TRANSICIONES DE PODER PACÍFICAS
        if is_master_db and not was_master_local:
            # --- ASCENSO ---
            self.controller.es_master = True
            self.controller.tapiz_asignado = mi_estado.get('tapiz_asignado', 'Tapiz A')
            
            self.bloquear_datos_torneo(False) # Muestra botón Modificar
            
            # --- CORRECCIÓN: Inicia bloqueado, requiere clic en "Modificar" ---
            self.ent_tor_nombre.config(state="disabled")
            self.ent_tor_lugar.config(state="disabled")
            self.cmb_categoria.config(state="disabled")
            if hasattr(self, 'cmb_tor_ciudad'): self.cmb_tor_ciudad.config(state="disabled")
            
            if hasattr(self, 'btn_guardar_torneo'):
                self.btn_guardar_torneo.config(state="normal", text="💾 Guardar Cambios")
            
            messagebox.showinfo("Control de Sala", "¡Has recibido los privilegios de Máster!")

        elif not is_master_db and was_master_local:
            # --- DESCENSO ---
            self.controller.es_master = False
            
            self.bloquear_datos_torneo(True) # Activa el escudo
            if hasattr(self, 'tabla_red') and self.tabla_red.selection():
                self.tabla_red.selection_remove(self.tabla_red.selection())
            self.gestionar_estado_botones_red() 
            
            if hasattr(self, 'btn_guardar_torneo'):
                self.btn_guardar_torneo.config(state="normal", text="☁️ Sincronizar Atletas")

        # 3. HERENCIA POR DESCONEXIÓN ABRUPTA
        if not is_master_db:
            master_activo = self.db.verificar_master_activo(id_torneo)
            if not master_activo:
                if hasattr(self.db, 'heredar_master'):
                    heredado = self.db.heredar_master(id_torneo, id_mi_conexion)
                    if heredado:
                        messagebox.showwarning("Máster Caído", "El Máster anterior se desconectó.\nHas heredado automáticamente el control de la sala.")

        # 4. ACTUALIZAR VISUALES Y BLOQUEOS
        self.refrescar_estado_bloqueos()

        # --- CORTAFUEGOS: Si el torneo cerró, detener todo ---
        if getattr(self, "torneo_finalizado", False):
            return

        # Sincronización de atletas para TODOS (Master y Guest)
        self.escuchar_nuevos_atletas_red()

        if self.controller.es_master:
            if hasattr(self.db, 'limpiar_conexiones_muertas'):
                self.db.limpiar_conexiones_muertas(id_torneo)
            self.refrescar_tabla_red_master(id_torneo)
        else:
            self.comprobar_estado_guest(id_torneo, id_mi_conexion)

        # Repetir cada 3 segundos
        self.after(3000, self.ciclo_escucha_red)

    def escuchar_nuevos_atletas_red(self):
        """Sincroniza usando la consulta completa a la BD para no perder jamás el peso decimal."""
        if getattr(self, "esta_editando_localmente", False) or not getattr(self, 'escuchando_red', False):
            return
            
        try:
            # --- FIX DEFINITIVO: Usar la consulta COMPLETA en lugar de la consulta rápida ---
            # Esto obliga a PostgreSQL a devolver TODAS las columnas, incluyendo peso_pesaje y peso_dado reales.
            resultado_bd = self.db.obtener_torneo_completo_debug(self.torneo_debug_id)
            if not resultado_bd: return
            
            # Desempaquetamos la tupla (datos_torneo, inscripciones)
            _, inscripciones_bd = resultado_bd
            
            if inscripciones_bd is not None:
                atletas_agrupados = {}
                for ins in inscripciones_bd:
                    id_atl = ins.get('id_peleador')
                    if id_atl is None: continue
                    id_atl = int(id_atl)
                    
                    # Extracción agresiva del peso
                    p_bd = ins.get('peso_pesaje')
                    try: val_p = float(p_bd)
                    except: val_p = 0
                    
                    if val_p <= 0:
                        p_bd = ins.get('peso_dado')
                        try: val_p = float(p_bd)
                        except: val_p = 0
                        
                    if val_p <= 0:
                        p_bd = ins.get('peso')
                        try: val_p = float(p_bd)
                        except: val_p = 0
                        
                    peso_fila = str(p_bd) if val_p > 0 else '0'
                    
                    if id_atl not in atletas_agrupados:
                        atletas_agrupados[id_atl] = {"pesos_text": [], "ids_divs": [], "estilos": [], "peso_exacto": peso_fila}
                    else:
                        peso_actual = atletas_agrupados[id_atl]["peso_exacto"]
                        if peso_actual in ['0', '0.0'] and peso_fila not in ['0', '0.0']:
                            atletas_agrupados[id_atl]["peso_exacto"] = peso_fila
                        elif val_p > 0:
                            try:
                                if val_p > float(peso_actual):
                                    atletas_agrupados[id_atl]["peso_exacto"] = str(val_p)
                            except: pass
                    
                    est_db = str(ins.get('estilo', ''))
                    abr = "Lib" if 'libre' in est_db.lower() else est_db[:3]
                    p_max = ins.get('peso_maximo') or ins.get('peso_cat') or '?'
                    
                    p_str = f"{abr}: {p_max}kg"
                    if p_str not in atletas_agrupados[id_atl]["pesos_text"]:
                        atletas_agrupados[id_atl]["pesos_text"].append(p_str)
                        
                        id_div = ins.get('id_division') or ins.get('id_peso_oficial_uww')
                        if id_div is None and p_max != '?':
                            id_estilo = 1 if 'libre' in est_db.lower() else (2 if 'greco' in est_db.lower() else 3)
                            for p in self.pesos_oficiales_db:
                                if float(p['peso_maximo']) == float(p_max) and int(p['id_estilo_lucha']) == id_estilo:
                                    id_div = p['id']
                                    break
                                    
                        if id_div is not None:
                            atletas_agrupados[id_atl]["ids_divs"].append(int(id_div))

                    if est_db not in atletas_agrupados[id_atl]["estilos"]:
                        atletas_agrupados[id_atl]["estilos"].append(est_db)

                # --- COMPARACIÓN INTELIGENTE DIRECTA ---
                hubo_cambios = False
                nueva_memoria = []
                self.atletas_db = self.db.obtener_atletas()
                
                for id_atl, data in atletas_agrupados.items():
                    existente = next((i for i in self.inscripciones_memoria if int(i['id_atleta']) == id_atl), None)
                    peso_red = data["peso_exacto"]
                    
                    if existente:
                        if existente.get('estado_local') in ['eliminado', 'editado']:
                            nueva_memoria.append(existente)
                            continue
                        
                        if peso_red in ['0', '0.0'] and existente.get('peso', '0') not in ['0', '0.0']:
                            peso_red = existente.get('peso', '0')

                        texto_oficial = " | ".join(data["pesos_text"])
                        
                        try: cambio_peso = float(existente.get('peso', '0')) != float(peso_red)
                        except: cambio_peso = str(existente.get('peso', '0')) != str(peso_red)
                            
                        cambio_oficial = str(existente.get('peso_oficial')) != str(texto_oficial)
                        cambio_estilos = set(existente.get('estilos', [])) != set(data["estilos"])
                        
                        if cambio_peso or cambio_oficial or cambio_estilos:
                            existente['peso'] = str(peso_red)
                            existente['peso_oficial'] = texto_oficial
                            existente['estilos'] = data["estilos"]
                            existente['ids_divisiones'] = data["ids_divs"]
                            # --- NUEVO: Resetear ciclo y marcar como editado por la red ---
                            existente['ciclos_red'] = 0
                            existente['tipo_cambio_red'] = 'editado'
                            hubo_cambios = True
                            
                        if existente.get('de_red') and existente.get('ciclos_red', 2) < 2:
                            existente['ciclos_red'] = existente.get('ciclos_red', 0) + 1
                            hubo_cambios = True
                            
                        nueva_memoria.append(existente)
                    else:
                        nueva_memoria.append({
                            "id_atleta": id_atl, "peso": str(peso_red), "peso_oficial": " | ".join(data["pesos_text"]),
                            "estilos": data["estilos"], "ids_divisiones": data["ids_divs"],
                            "de_red": True, "ciclos_red": 0, "tipo_cambio_red": "nuevo" # <--- Etiqueta inicial
                        })
                        hubo_cambios = True
                        
                # --- NUEVO: DETECTAR Y MANTENER ELIMINADOS DE LA RED POR 2 CICLOS ---
                for loc in self.inscripciones_memoria:
                    id_loc = int(loc['id_atleta'])
                    if id_loc not in atletas_agrupados:
                        if not loc.get('de_red'):
                            # Local puro, se conserva en pantalla
                            nueva_memoria.append(loc)
                        else:
                            # Era de red, pero ya no está en BD (fue eliminado por alguien más)
                            ciclos = loc.get('ciclos_red', 2)
                            tipo = loc.get('tipo_cambio_red', '')
                            
                            if tipo != 'eliminado':
                                # Recién descubierto que lo borraron, iniciamos su velorio visual
                                loc['tipo_cambio_red'] = 'eliminado'
                                loc['ciclos_red'] = 0
                                nueva_memoria.append(loc)
                                hubo_cambios = True
                            elif ciclos < 1: # --- FIX: Reducimos de 2 a 1 para que desaparezca a los 3-6 segundos ---
                                loc['ciclos_red'] += 1
                                nueva_memoria.append(loc)
                                hubo_cambios = True
                            else:
                                hubo_cambios = True
                        
                ids_en_red = set(atletas_agrupados.keys())
                ids_azules_locales = set(int(i['id_atleta']) for i in self.inscripciones_memoria if i.get('de_red') and i.get('tipo_cambio_red') != 'eliminado')
                if ids_en_red != ids_azules_locales:
                    hubo_cambios = True

                if hubo_cambios:
                    self.inscripciones_memoria = nueva_memoria
                    self.actualizar_tabla_visual()
                    self.actualizar_opciones_filtros()
                    
        except Exception as e:
            print(f"Error en radar de red: {e}")

    def refrescar_tabla_red_master(self, id_torneo):
        """Actualiza la lista para el Admin, preservando selecciones múltiples."""
        
        # FIJAR SIEMPRE LA ETIQUETA VERDE DEL MÁSTER
        id_oficial = getattr(self.controller, 'id_operador', None)
        oficial = next((o for o in self.oficiales_db if o['id'] == id_oficial), None)
        nom_ofi = f"{oficial['nombre']} {oficial['apellidos']}" if oficial else "Desconocido"
        mi_tapiz = getattr(self.controller, 'tapiz_asignado', 'Tapiz A')
        self.lbl_tapete_master.config(text=f"🥇 {mi_tapiz} (Máster: {nom_ofi})", foreground="#28a745")

        # --- NUEVO CORTAFUEGOS: Si ya cerró, vaciar y no hacer nada más ---
        if getattr(self, "torneo_finalizado", False):
            for item in self.tabla_red.get_children(): 
                self.tabla_red.delete(item)
            return

        # 1. Guardar TODAS las selecciones actuales...
        ids_seleccionados = [str(self.tabla_red.item(i, "values")[0]) for i in self.tabla_red.selection()]

        conexiones = self.db.obtener_conexiones_torneo(id_torneo)
        for item in self.tabla_red.get_children(): 
            self.tabla_red.delete(item)

        if not conexiones: 
            self.gestionar_estado_botones_red()
            return

        for c in conexiones:
            es_master = c.get('es_master', False)
            mi_id = getattr(self.controller, 'id_conexion_red', None)
            
            tag = "yo_mismo" if str(c['id_conexion']) == str(mi_id) else ("confirmado" if c['estado_conexion'] == 'Aprobado' else "pendiente")
            nombre_visual = f"⭐ {c['nombre']} {c['apellidos']}" if es_master else f"{c['nombre']} {c['apellidos']}"
            tapiz_visual = c['tapiz_asignado'] or "N.A."
            
            valores = (c['id_conexion'], nombre_visual, c['nombre_dispositivo'], tapiz_visual, c['estado_conexion'])
            new_item = self.tabla_red.insert("", "end", values=valores, tags=(tag,))
            
            # 2. Restaurar selección múltiple
            if str(c['id_conexion']) in ids_seleccionados:
                self.tabla_red.selection_add(new_item)
                
        # 3. Re-evaluar los botones de seguridad tras refrescar
        self.gestionar_estado_botones_red()

    def comprobar_estado_guest(self, id_torneo, id_mi_conexion):
        """El Guest verifica su estado y actualiza la UI e invitados al instante."""
        estado_bd = self.db.verificar_estado_mi_conexion(id_mi_conexion)
        
        if not estado_bd: return # Seguridad por si se borra la conexión

        estado_conexion = estado_bd['estado_conexion']
        tapiz = estado_bd['tapiz_asignado']
        self.controller.tapiz_asignado = tapiz

        # Obtener a todos los presentes en la sala
        conexiones = self.db.obtener_conexiones_torneo(id_torneo)
        master_nombre = "Desconocido"

        for item in self.tabla_red.get_children(): self.tabla_red.delete(item)

        for c in conexiones:
            es_master = c.get('es_master', False)
            if es_master: master_nombre = f"{c['nombre']} {c['apellidos']}"
            
            es_yo = (str(c['id_conexion']) == str(id_mi_conexion))
            tag = "yo_mismo" if es_yo else ("confirmado" if c['estado_conexion'] == 'Aprobado' else "pendiente")
            
            nombre_visual = f"⭐ {c['nombre']} {c['apellidos']}" if es_master else f"{c['nombre']} {c['apellidos']}"
            tapiz_visual = c['tapiz_asignado'] or "N.A."
            
            self.tabla_red.insert("", "end", values=(c['id_conexion'], nombre_visual, c['nombre_dispositivo'], tapiz_visual, c['estado_conexion']), tags=(tag,))

        # Actualización de etiqueta basada en la realidad de la BD
        if estado_conexion == 'Aprobado':
            self.lbl_tapete_master.config(text=f"✅ {tapiz} (Máster: {master_nombre})", foreground="#17a2b8")
            if hasattr(self, 'btn_avanzar_pareo'): self.btn_avanzar_pareo.config(state="normal")
            
            # --- CORTAFUEGOS: Solo habilitar interfaz si NO estoy editando un atleta ---
            if str(self.cmb_atleta.cget("state")) == "disabled" and not getattr(self, "todo_bloqueado", False):
                if getattr(self, "id_atleta_editando", None) is None: # <--- CONDICIÓN DE BLOQUEO
                    self.cambiar_estado_inscripcion("normal")
            self.bloquear_seleccion_tabla = False
        else:
            # Invitado Pendiente: Todo congelado
            self.lbl_tapete_master.config(text=f"⏳ Esperando aprobación (Máster: {master_nombre})", foreground="#fd7e14")
            if hasattr(self, 'btn_avanzar_pareo'): self.btn_avanzar_pareo.config(state="disabled")
            
            self.cambiar_estado_inscripcion("disabled")
            self.bloquear_seleccion_tabla = True

        self.actualizar_botones_guardado()
