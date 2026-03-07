import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from utils.utilidades import aplicar_formato_fecha, aplicar_deseleccion_tabla

class LogicaTorneoMixin:
    """Contiene toda la lógica de gestión de Torneos, validaciones y guardado en BD."""
    
    def bloquear_datos_torneo(self, es_guest):
        """Bloquea o desbloquea el panel izquierdo y gestiona el botón Modificar Torneo."""
        estado_normal = "disabled" if es_guest else "normal"
        estado_combo = "disabled" if es_guest else "readonly"

        controles = [
            (getattr(self, 'ent_tor_nombre', None), estado_normal),
            (getattr(self, 'cmb_categoria', None), estado_combo),
            (getattr(self, 'ent_tor_lugar', None), estado_normal),
            (getattr(self, 'cmb_tor_ciudad', None), estado_combo),
            (getattr(self, 'cmb_tor_tapices', None), estado_combo),
            (getattr(self, 'ent_fecha_inicio', None), estado_normal),
            (getattr(self, 'ent_fecha_fin', None), estado_normal)
            # --- CORRECCIÓN: Se eliminaron los chk_libre, chk_greco y chk_femenina de aquí ---
        ]
        
        for widget, est in controles:
            if widget: 
                widget.config(state=est)

        # --- NUEVO: Mostrar botón para todos, pero bloqueado para invitados ---
        if es_guest:
            if hasattr(self, 'btn_confirmar_torneo'):
                if not self.btn_confirmar_torneo.winfo_ismapped():
                    self.btn_confirmar_torneo.pack(side="left", padx=5, before=self.btn_nuevo_limpiar)
                self.btn_confirmar_torneo.config(state="disabled", text="Modificar Torneo")
            if hasattr(self, 'btn_cancelar_torneo'): 
                self.btn_cancelar_torneo.pack_forget()
        else:
            if hasattr(self, 'btn_confirmar_torneo'):
                if not self.btn_confirmar_torneo.winfo_ismapped():
                    self.btn_confirmar_torneo.pack(side="left", padx=5, before=self.btn_nuevo_limpiar)
                self.btn_confirmar_torneo.config(state="normal")

    def gestionar_bloqueo_torneo(self):
        # --- BARRERA DE SEGURIDAD PARA TORNEOS FINALIZADOS ---
        if getattr(self, "torneo_finalizado", False):
            return messagebox.showwarning("Torneo Finalizado", "No se puede modificar la información de un torneo que ya ha sido cerrado.")

        if self.btn_confirmar_torneo.cget("text") == "Modificar Torneo":
            self.ent_tor_nombre.config(state="normal")
            self.ent_tor_lugar.config(state="normal")
            self.cmb_tor_ciudad.config(state="normal")
            
            # --- NUEVO: BLOQUEO ABSOLUTO DE CATEGORÍA ---
            # Si hay al menos un peso bloqueado/confirmado, la categoría no se puede tocar
            if getattr(self, "pesos_bloqueados_ids", set()):
                self.cmb_categoria.config(state="disabled")
            else:
                self.cmb_categoria.config(state="normal")
                
            self.btn_confirmar_torneo.config(text="Guardar Cambios")
            self.btn_cancelar_torneo.pack(side="left", padx=5)
            self.cambiar_estado_inscripcion("disabled")
            self.form_frame.config(text="2. Inscripción y Pesaje (Confirme datos para habilitar)")
            return

        nombre = self.ent_tor_nombre.get().strip()
        lugar = self.ent_tor_lugar.get().strip()
        cat = self.cmb_categoria.get()
        ciu = self.cmb_tor_ciudad.get()

        if not nombre or not lugar or not ciu or not cat:
            return messagebox.showwarning("Incompleto", "Llene nombre, lugar, ciudad y categoría.")

        if self.categoria_confirmada is not None and self.categoria_confirmada != cat:
            # --- NUEVO: Doble validación de seguridad contra cambios ilícitos ---
            if getattr(self, "pesos_bloqueados_ids", set()):
                self.cmb_categoria.set(self.categoria_confirmada)
                return messagebox.showwarning("Bloqueado", "No se puede cambiar la categoría porque ya existen llaves en curso.")
                
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
        self.torneo_ciudad_conf = ciu

        self.ent_tor_nombre.config(state="disabled")
        self.ent_tor_lugar.config(state="disabled")
        self.cmb_categoria.config(state="disabled")
        self.cmb_tor_ciudad.config(state="disabled") 
        
        self.btn_confirmar_torneo.config(text="Modificar Torneo")
        self.btn_cancelar_torneo.pack_forget()

        # --- AHORA SÍ: DESBLOQUEAMOS LAS INSCRIPCIONES ---
        self.form_frame.config(text="2. Inscripción y Pesaje (Habilitado)")
        self.cambiar_estado_inscripcion("normal")
        # Si los datos son válidos y se bloquea la edición de datos generales:
        self.btn_guardar_torneo.config(state="normal") # Se activa para permitir "Crear Sala"
        
        # Habilitar controles de red
        self.btn_confirmar_red.config(state="normal")
        self.btn_eliminar_red.config(state="normal")
        self.btn_intercambiar_tapiz.config(state="normal")
        
        # --- NUEVO: RECARGAMOS LOS ATLETAS AL CONFIRMAR LA CATEGORÍA ---
        self.filtrar_atletas_por_edad()

        self.actualizar_btn_nuevo_limpiar()

    def cancelar_edicion_torneo(self):
        # 1. Habilitar temporalmente para poder restaurar los datos
        self.ent_tor_nombre.config(state="normal")
        self.ent_tor_lugar.config(state="normal")
        self.cmb_tor_ciudad.config(state="normal")
        self.cmb_categoria.config(state="normal")

        # 2. Restaurar datos desde la memoria
        self.ent_tor_nombre.delete(0, tk.END)
        self.ent_tor_nombre.insert(0, self.torneo_nombre_conf)
        self.ent_tor_lugar.delete(0, tk.END)
        self.ent_tor_lugar.insert(0, self.torneo_lugar_conf)
        self.cmb_tor_ciudad.set(getattr(self, 'torneo_ciudad_conf', '')) 
        self.cmb_categoria.set(self.categoria_confirmada)

        # 3. Volver a bloquear la cabecera
        self.ent_tor_nombre.config(state="disabled")
        self.ent_tor_lugar.config(state="disabled")
        self.cmb_categoria.config(state="disabled")
        self.cmb_tor_ciudad.config(state="disabled") 
        
        self.btn_confirmar_torneo.config(text="Modificar Torneo")
        self.btn_cancelar_torneo.pack_forget()
        
        # --- NUEVO: PREGUNTAR ANTES DE HABILITAR LA INSCRIPCIÓN ---
        if getattr(self, "todo_bloqueado", False):
            self.form_frame.config(text="2. Inscripción y Pesaje (Torneo Bloqueado)")
            self.cambiar_estado_inscripcion("disabled")
        else:
            self.form_frame.config(text="2. Inscripción y Pesaje (Habilitado)")
            self.cambiar_estado_inscripcion("normal")

        self.actualizar_btn_nuevo_limpiar()

    def resetear_torneo(self, forzar=False):
        """Borra la memoria y resetea la pantalla a su estado inicial de fábrica."""
        # Si no es un reseteo forzado (ej. el usuario hizo clic en el botón), preguntamos
        if not forzar:
            respuesta = messagebox.askyesno("Confirmar", "¿Está seguro de limpiar todos los datos y empezar de cero? Se perderán las inscripciones no guardadas.")
            if not respuesta: return
        
        # --- SALIR DE LA SALA DE RED ACTUAL Y HEREDAR MÁSTER ---
        if hasattr(self.controller, 'id_conexion_red') and self.controller.id_conexion_red:
            self.db.eliminar_conexion_instancia(self.controller.id_conexion_red)
            self.controller.id_conexion_red = None
            self.controller.es_master = False
            self.controller.tapiz_asignado = None

        # 1. Resetear variables lógicas
        self.torneo_debug_id = None
        self.categoria_confirmada = None
        self.torneo_nombre_conf = ""
        self.torneo_lugar_conf = ""
        self.torneo_ciudad_conf = ""
        self.todo_bloqueado = False
        self.bloquear_seleccion_tabla = False # <--- NUEVA LÍNEA AÑADIDA
        self.pesos_bloqueados_ids = set()

        # 2. Resetear Campos de Texto
        self.ent_tor_nombre.config(state="normal")
        self.ent_tor_lugar.config(state="normal")
        self.cmb_categoria.config(state="normal")
        
        self.ent_tor_nombre.delete(0, tk.END)
        self.ent_tor_lugar.delete(0, tk.END)
        self.cmb_tor_ciudad.set('') # <-- NUEVO
        self.cmb_tor_ciudad.config(state="normal") # <-- NUEVO
        self.cmb_categoria.set('')
        
        self.ent_tor_fecha.config(state="normal")
        self.ent_tor_fecha.delete(0, tk.END)
        self.ent_tor_fecha.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.ent_tor_fecha.config(state="readonly")

        # 3. Resetear Botones
        self.btn_confirmar_torneo.config(text="Confirmar Datos de Torneo", state="normal")
        self.btn_cancelar_torneo.pack_forget()
        
        # Restaurar botones de la tabla por si estaban ocultos por un torneo cerrado
        if hasattr(self, 'frame_acciones_memoria') and not self.frame_acciones_memoria.winfo_ismapped():
            self.frame_acciones_memoria.pack(side="left", before=self.lbl_estadisticas)
        
        # Asegurarse de que regresen desactivados
        if hasattr(self, 'btn_editar_memoria'):
            self.btn_editar_memoria.config(state="disabled")
            self.btn_eliminar_memoria.config(state="disabled")
        
        # 4. Limpiar Inscripciones
        self.inscripciones_memoria.clear()
        
        # --- NUEVO: LIMPIAR FORMULARIO DE PESAJE ---
        self.cmb_atleta.set('')
        self.al_seleccionar_atleta()
        if hasattr(self, 'var_peso'): 
            self.var_peso.set('')
        self.al_seleccionar_atleta()
        if hasattr(self, 'lbl_cat_dinamica'):
            self.lbl_cat_dinamica.config(text="Categoría: --", foreground="gray")

        # --- NUEVO: LIMPIAR LISTBOX Y BUSCADORES DE FILTROS ---
        if hasattr(self, 'listbox_pesos'):
            self.listbox_pesos.delete(0, tk.END)
            self.listbox_estilos.delete(0, tk.END)
            self.ent_buscar_peso.delete(0, tk.END)
            self.ent_buscar_estilo.delete(0, tk.END)
            self.pesos_memoria_completa = []
            self.estilos_memoria_completa = []
        
        # --- CORRECCIÓN: Resetear el nuevo panel de búsqueda ---
        if hasattr(self, 'ent_busqueda'):
            self.limpiar_filtros()
        else:
            self.actualizar_opciones_filtros()
            self.actualizar_tabla_visual()
        
        self.cambiar_estado_inscripcion("disabled")
        self.form_frame.config(text="2. Inscripción y Pesaje (Confirmar torneo para habilitar)")

        # --- BLOQUEO DE GESTIÓN DE RED ---
        self.escuchando_red = False

        self.btn_guardar_torneo.config(
            state="disabled", 
            text="✅ Confirmar y Crear Sala",
            bg="#28a745"
        )
        self.btn_avanzar_pareo.config(state="disabled")
        
        self.btn_confirmar_red.config(state="disabled")
        self.btn_eliminar_red.config(state="disabled")
        self.btn_intercambiar_tapiz.config(state="disabled")
        self.btn_ceder_master.config(state="disabled")
        
        # Limpiar la tabla de red
        for item in self.tabla_red.get_children():
            self.tabla_red.delete(item)

        # --- NUEVO: RESTAURAR ETIQUETA DEL MÁSTER ---
        self.lbl_tapete_master.config(
            text="🥇 Tapete Máster: (Esperando creación de sala...)", 
            foreground="black" # Restauramos al color original (o el color por defecto de tu tema)
        )
        
        # --- NUEVO: Ocultar el botón tras limpiar ---
        self.actualizar_btn_nuevo_limpiar()
        
        # --- NUEVO: Ocultar el botón tras limpiar ---
        self.actualizar_btn_nuevo_limpiar()

        self.torneo_finalizado = False
        self.actualizar_botones_guardado()

    def actualizar_btn_nuevo_limpiar(self):
        """Mantiene el botón siempre visible y con el texto/estado correcto según la fase."""
        if not hasattr(self, 'btn_nuevo_limpiar'): return
        
        # Asegurarse de que el botón esté visible en la interfaz
        if not self.btn_nuevo_limpiar.winfo_ismapped():
            self.btn_nuevo_limpiar.pack(side="left", padx=5)

        # EVALUACIÓN DE REGLAS:
        if getattr(self, "torneo_debug_id", None) is not None:
            # Reglas 2, 3 y 4: Torneo en Base de Datos (Guardado, Cargado o en Edición Post-Guardado)
            self.btn_nuevo_limpiar.config(text="Nuevo Torneo (Salir)", state="normal")
            
        elif getattr(self, "categoria_confirmada", None) is not None:
            # Regla 1: Torneo Nuevo con datos confirmados localmente (Aún no subido a la BD)
            self.btn_nuevo_limpiar.config(text="Limpiar Torneo", state="normal")
            
        else:
            # Regla 5: Estado inicial, vacío o recién clickeado en "Nuevo/Limpiar"
            self.btn_nuevo_limpiar.config(text="Limpiar Torneo", state="disabled")

    def aplicar_interfaz_visitante(self):
        """Bloquea toda la edición y red, dejando solo la lectura y el avance a llaves."""
        self.todo_bloqueado = True
        self.cambiar_estado_inscripcion("disabled")
        
        # 1. Bloquear edición del Torneo
        if hasattr(self, 'btn_confirmar_torneo'):
            self.btn_confirmar_torneo.config(state="disabled")
        if hasattr(self, 'btn_guardar_torneo'):
            self.btn_guardar_torneo.config(state="disabled")
            
        # 2. Cambiar texto a Modo Visitante
        if hasattr(self, 'lbl_tapete_master'):
            self.lbl_tapete_master.config(text="🏁 Torneo Finalizado (Modo Visitante)", foreground="#17a2b8")
            
        # 3. Apagar controles de red permanentemente
        self.escuchando_red = False
        if hasattr(self, 'btn_confirmar_red'): self.btn_confirmar_red.config(state="disabled")
        if hasattr(self, 'btn_eliminar_red'): self.btn_eliminar_red.config(state="disabled")
        if hasattr(self, 'btn_intercambiar_tapiz'): self.btn_intercambiar_tapiz.config(state="disabled")
        if hasattr(self, 'btn_ceder_master'): self.btn_ceder_master.config(state="disabled")
        
        # --- NUEVO: VACIAR LA TABLA DE RED ---
        if hasattr(self, 'tabla_red'):
            for item in self.tabla_red.get_children():
                self.tabla_red.delete(item)
        
        # 4. Permitir SIEMPRE ir a las llaves
        if hasattr(self, 'btn_avanzar_pareo'):
            self.btn_avanzar_pareo.config(state="normal")

    def refrescar_estado_bloqueos(self):
        """Consulta la BD y actualiza la interfaz si hubo cambios en la pantalla de Pareo."""
        if getattr(self, "torneo_debug_id", None) is None: 
            return

        # Guardamos el estado anterior para no spamear el mensaje emergente
        ya_estaba_cerrado = getattr(self, "torneo_finalizado", False)

        # 1. Consultar si el torneo fue cerrado por completo (tiene fecha_fin)
        conexion = self.db.conectar()
        if conexion:
            try:
                with conexion.cursor() as cur:
                    cur.execute("SELECT fecha_fin FROM torneo WHERE id = %s", (self.torneo_debug_id,))
                    res = cur.fetchone()
                    self.torneo_finalizado = True if (res and res[0]) else False
            finally: 
                conexion.close()

        # --- NUEVO: SI ESTÁ FINALIZADO, APLICAR INTERFAZ VISITANTE Y CORTAR ---
        if getattr(self, "torneo_finalizado", False):
            self.aplicar_interfaz_visitante()
            self.actualizar_botones_guardado()
            self.actualizar_tabla_visual()
            
            # Lanzamos el mensaje SOLO a los invitados, el Máster no necesita este aviso extra
            if not ya_estaba_cerrado and not getattr(self.controller, 'es_master', False):
                messagebox.showinfo("Torneo Finalizado", "El Director ha cerrado oficialmente el torneo.\n\nEl sistema de red se ha desconectado y has pasado a modo de Solo Lectura (Visitante).")
            return

        # 2. Consultar qué llaves están bloqueadas ahora y quiénes fueron descalificados
        self.pesos_bloqueados_ids = self.db.obtener_divisiones_bloqueadas(self.torneo_debug_id)
        self.atletas_descalificados_ids = self.db.obtener_peleadores_descalificados(self.torneo_debug_id)

        # 3. Evaluar si TODAS las divisiones están bloqueadas
        all_locked = True
        if not self.inscripciones_memoria:
            all_locked = False
        else:
            for ins in self.inscripciones_memoria:
                for div_id in ins['ids_divisiones']:
                    if div_id not in self.pesos_bloqueados_ids:
                        all_locked = False
                        break
                if not all_locked: break

        # 4. Aplicar cambios visuales de bloqueo
        if all_locked and self.pesos_bloqueados_ids:
            self.todo_bloqueado = True
            self.cambiar_estado_inscripcion("disabled")
            if hasattr(self, 'frame_acciones_memoria'):
                self.frame_acciones_memoria.pack_forget()
        else:
            self.todo_bloqueado = False
            if hasattr(self, 'frame_acciones_memoria') and not self.frame_acciones_memoria.winfo_ismapped():
                self.frame_acciones_memoria.pack(side="left", before=self.lbl_estadisticas)

        # 5. Refrescar colores y botones
        self.actualizar_botones_guardado()
        self.actualizar_tabla_visual()

    def abrir_ventana_cargar_torneo(self):
        from ui.ventanas.ventana_cargar_torneo import VentanaCargarTorneo
        VentanaCargarTorneo(self)

    def ejecutar_carga_torneo(self, id_torneo):
        """Este método es llamado por la VentanaCargarTorneo cuando el usuario hace una selección."""
        
        # --- NUEVO: Bloqueo de seguridad para evitar el glitch de recarga ---
        if getattr(self, "torneo_debug_id", None) == id_torneo:
            return messagebox.showinfo("Torneo Activo", "Este torneo ya está cargado y activo actualmente.")

        # Desconectar de sala previa si aplica
        if hasattr(self.controller, 'id_conexion_red') and self.controller.id_conexion_red:
            if getattr(self, 'torneo_debug_id', None) != id_torneo:
                self.db.eliminar_conexion_instancia(self.controller.id_conexion_red)
                self.controller.id_conexion_red = None

        datos_torneo, inscripciones = self.db.obtener_torneo_completo_debug(id_torneo)
        if not datos_torneo: return

        # 1. Llenar los campos de torneo
        self.ent_tor_nombre.config(state="normal"); self.ent_tor_nombre.delete(0, tk.END); self.ent_tor_nombre.insert(0, datos_torneo['nombre'])
        self.ent_tor_lugar.config(state="normal"); self.ent_tor_lugar.delete(0, tk.END); self.ent_tor_lugar.insert(0, datos_torneo['lugar'])
        self.ent_tor_fecha.config(state="normal"); self.ent_tor_fecha.delete(0, tk.END); self.ent_tor_fecha.insert(0, datos_torneo['fecha']); self.ent_tor_fecha.config(state="readonly")

        self.cmb_tor_ciudad.config(state="normal")
        self.cmb_tor_ciudad.set(datos_torneo.get('ciudad_nombre', ''))
        self.cmb_tor_ciudad.config(state="disabled")
        
        # Seleccionar la categoría correctamente con set
        self.cmb_categoria.config(state="normal")
        self.cmb_categoria.set(datos_torneo['categoria'])

        # 2. Limpiar memoria y tabla
        self.inscripciones_memoria.clear()
        for item in self.tabla.get_children(): self.tabla.delete(item)

        # 3. Agrupar estilos por atleta (reconstrucción de memoria)
        atletas_agrupados = {}
        for ins in inscripciones:
            id_atl = ins['id_peleador']
            
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
                atletas_agrupados[id_atl] = {"datos_bd": ins, "estilos": [], "pesos_text": [], "ids_divisiones": [], "peso_exacto": peso_fila}
            else:
                peso_actual = atletas_agrupados[id_atl]["peso_exacto"]
                if peso_actual in ['0', '0.0'] and peso_fila not in ['0', '0.0']:
                    atletas_agrupados[id_atl]["peso_exacto"] = peso_fila
                elif val_p > 0:
                    try:
                        if val_p > float(peso_actual):
                            atletas_agrupados[id_atl]["peso_exacto"] = peso_fila
                    except: pass
            
            # NORMALIZAR ESTILOS DE LA BD
            est_db = str(ins.get('estilo', ''))
            if 'libre' in est_db.lower(): est_norm = 'Estilo Libre'
            elif 'greco' in est_db.lower(): est_norm = 'Grecorromana'
            elif 'fem' in est_db.lower(): est_norm = 'Femenina'
            else: est_norm = est_db

            abr = "Lib" if est_norm == "Estilo Libre" else est_norm[:3]
            atletas_agrupados[id_atl]["estilos"].append(est_norm)
            atletas_agrupados[id_atl]["pesos_text"].append(f"{abr}: {ins['peso_maximo']}kg")
            
            id_div = ins.get('id_division') or ins.get('id_peso_oficial_uww')
            if id_div is None:
                p_max = ins.get('peso_maximo') or ins.get('peso_cat')
                id_estilo = 1 if 'libre' in est_db.lower() else (2 if 'greco' in est_db.lower() else 3)
                for p in self.pesos_oficiales_db:
                    if float(p['peso_maximo']) == float(p_max) and int(p['id_estilo_lucha']) == id_estilo:
                        id_div = p['id']
                        break
                        
            if id_div is not None:
                atletas_agrupados[id_atl]["ids_divisiones"].append(int(id_div))

        # 4. Llenar la memoria local
        for id_atl, data in atletas_agrupados.items():
            texto_peso_oficial = " | ".join(data["pesos_text"])
            
            self.inscripciones_memoria.append({
                "id_atleta": id_atl, "peso": str(data["peso_exacto"]),
                "peso_oficial": texto_peso_oficial, "estilos": data["estilos"], "ids_divisiones": data["ids_divisiones"],
                "de_red": True 
            })
            
        self.actualizar_opciones_filtros()

        # 5. --- APLICACIÓN MANUAL DE ESTADO "CONFIRMADO" ---
        self.torneo_debug_id = id_torneo
        self.categoria_confirmada = datos_torneo['categoria']
        self.torneo_nombre_conf = datos_torneo['nombre']
        self.torneo_lugar_conf = datos_torneo['lugar']
        self.torneo_ciudad_conf = datos_torneo.get('ciudad_nombre', '')
        
        self.oficiales_db = self.db.obtener_oficiales()

        self.btn_confirmar_torneo.config(text="Modificar Torneo")
        self.btn_cancelar_torneo.pack_forget()
        self.form_frame.config(text="2. Inscripción y Pesaje (Habilitado)")
        self.cambiar_estado_inscripcion("normal")
        self.filtrar_atletas_por_edad()

        # --- GESTIÓN DE RED SEGURA ---
        import socket, os
        nombre_pc = f"{socket.gethostname()}-{os.getpid()}"
        id_oficial = getattr(self.controller, 'id_operador', None)
        master_activo = self.db.verificar_master_activo(id_torneo)
            
        if not master_activo or master_activo == nombre_pc:
            if not master_activo:
                id_conexion = self.db.registrar_conexion_instancia(id_torneo, id_oficial, nombre_pc, es_master=True)
            else:
                m_db = self.db.verificar_master_existente(id_torneo)
                id_conexion = m_db['id'] if m_db else None
                
            self.controller.id_conexion_red = id_conexion
            self.controller.es_master = True
            self.controller.tapiz_asignado = "Tapiz A"
            
            self.bloquear_datos_torneo(False) 
            self.ent_tor_nombre.config(state="disabled")
            self.ent_tor_lugar.config(state="disabled")
            self.cmb_categoria.config(state="disabled")
            if hasattr(self, 'cmb_tor_ciudad'): self.cmb_tor_ciudad.config(state="disabled")

            if hasattr(self, 'btn_avanzar_pareo'): self.btn_avanzar_pareo.config(state="normal")
            if hasattr(self, 'btn_guardar_torneo'):
                if not self.btn_guardar_torneo.winfo_ismapped():
                    self.btn_guardar_torneo.pack(side="left", fill="x", expand=True, padx=(0, 2))
                self.btn_guardar_torneo.config(state="normal", text="💾 Guardar Cambios")
                
        else:
            self.controller.es_master = False
            id_conexion = self.db.registrar_conexion_instancia(id_torneo, id_oficial, nombre_pc, es_master=False)
            self.controller.id_conexion_red = id_conexion
            
            self.bloquear_datos_torneo(True)
            if hasattr(self, 'btn_guardar_torneo'):
                if not self.btn_guardar_torneo.winfo_ismapped():
                    self.btn_guardar_torneo.pack(side="left", fill="x", expand=True, padx=(0, 2))
                self.btn_guardar_torneo.config(state="disabled", text="☁️ Sincronizar Atletas")
                
            self.comprobar_estado_guest(id_torneo, id_conexion)

        self.iniciar_escucha_red()
        self.actualizar_tabla_visual()
        self.refrescar_estado_bloqueos()
        self.actualizar_btn_nuevo_limpiar()

    def guardar_progreso(self):
        self._ejecutar_guardado(ir_a_pareo=False)

    def subir_inscripciones_bd(self):
        self._ejecutar_guardado(ir_a_pareo=True)

    def _ejecutar_guardado(self, ir_a_pareo=False):
        if not self.inscripciones_memoria: 
            return messagebox.showwarning("Sin Atletas", "No hay atletas inscritos.")
            
        # --- REGLA: SI ESTÁ TODO BLOQUEADO O FINALIZADO, SOLO AVANZAR ---
        if getattr(self, "torneo_finalizado", False) or getattr(self, "todo_bloqueado", False):
            if ir_a_pareo and getattr(self, "torneo_debug_id", None):
                from pantalla_pareo import PantallaPareo
                p_pareo = self.controller.pantallas.get(PantallaPareo)
                if p_pareo:
                    p_pareo.cargar_torneo(self.torneo_debug_id)
                    self.controller.mostrar_pantalla(PantallaPareo)
            return

        # 1. Agrupar y Validar Parejas
        divisiones = {}
        for ins in self.inscripciones_memoria:
            id_atleta = ins['id_atleta']
            nombre_atleta = next((f"{a['apellidos']}, {a['nombre']}" for a in self.atletas_db if a['id'] == id_atleta), "Atleta Desconocido")
            for i, id_div in enumerate(ins['ids_divisiones']):
                estilo = ins['estilos'][i]
                peso_oficial_str = "Desconocido"
                for p in self.pesos_oficiales_db:
                    if p['id'] == id_div:
                        peso_oficial_str = f"{p['peso_maximo']}kg"
                        break
                clave_div = (id_div, estilo, peso_oficial_str)
                if clave_div not in divisiones: divisiones[clave_div] = []
                divisiones[clave_div].append(nombre_atleta)
                
        hay_pareja = False
        atletas_solitarios = {} 
        for (id_div, estilo, peso_str), atletas in divisiones.items():
            if len(atletas) >= 2: 
                hay_pareja = True
            elif len(atletas) == 1:
                # --- NUEVA CONDICIÓN: Ignorar si la llave de esta división ya fue confirmada ---
                if id_div not in getattr(self, "pesos_bloqueados_ids", set()):
                    nombre = atletas[0]
                    if nombre not in atletas_solitarios: 
                        atletas_solitarios[nombre] = []
                    atletas_solitarios[nombre].append(f"{estilo} - {peso_str}")
                
        if not hay_pareja:
            return messagebox.showwarning("Parejas Insuficientes", "Debe haber al menos 2 atletas en una misma división.")
            
        if atletas_solitarios:
            mensaje = "Atletas solos en su división:\n\n" + "\n".join([f"• {n} ({', '.join(d)})" for n, d in list(atletas_solitarios.items())[:15]])
            if len(atletas_solitarios) > 15: mensaje += f"\n... y {len(atletas_solitarios) - 15} más."
            mensaje += "\n\n¿Desea continuar?"
            if not messagebox.askyesno("Atletas sin oponente", mensaje): return 

        # --- GUARDAR O SINCRONIZAR EN BD ---
        id_existente = getattr(self, "torneo_debug_id", None)
        
        if id_existente:
            # MODO: SINCRONIZAR ACTUALIZACIÓN
            if self.db.sincronizar_inscripciones(id_existente, self.inscripciones_memoria):
                self.actualizar_botones_guardado()
                if ir_a_pareo:
                    messagebox.showinfo("Éxito", "Cambios guardados. Pasando a Fase de Pareos.")
                    from pantalla_pareo import PantallaPareo
                    p_pareo = self.controller.pantallas.get(PantallaPareo)
                    if p_pareo:
                        p_pareo.cargar_torneo(id_existente)
                        self.controller.mostrar_pantalla(PantallaPareo)
                else:
                    messagebox.showinfo("Éxito", "Progreso sincronizado correctamente en la Base de Datos.")
            else:
                messagebox.showerror("Error", "No se pudo sincronizar la base de datos.")
        else:
            # MODO: CREAR NUEVO TORNEO
            id_cat = next((c['id'] for c in self.categorias_db if c['nombre'] == self.categoria_confirmada), None)
            try: fecha_db = datetime.strptime(self.ent_tor_fecha.get().strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
            except: fecha_db = datetime.now().strftime("%Y-%m-%d")
            id_ciu = self.map_ciudades_torneo.get(self.cmb_tor_ciudad.get())
            datos_torneo = {
                'nombre': self.var_nombre_torneo.get().strip(),
                'id_categoria': self.categoria_seleccionada_id,
                'lugar': self.var_lugar_torneo.get().strip(),
                'id_ciudad': self.id_ciudad_seleccionada,
                'fecha': self.var_fecha_torneo.get(),
                'num_tapices': int(self.cmb_num_tapices.get()) # <--- AÑADIR ESTA LÍNEA
            }
            
            nuevo_id = self.db.guardar_torneo_completo(datos_torneo, self.inscripciones_memoria)
            
            if nuevo_id:
                self.torneo_debug_id = nuevo_id
                self.ent_tor_nombre.config(state="disabled")
                self.ent_tor_lugar.config(state="disabled")
                self.cmb_categoria.config(state="disabled")
                if hasattr(self, 'cmb_tor_ciudad'): self.cmb_tor_ciudad.config(state="disabled")
                self.btn_confirmar_torneo.config(text="Modificar Torneo", state="disabled")
                self.btn_cancelar_torneo.pack_forget()
                self.actualizar_btn_nuevo_limpiar()
                self.actualizar_botones_guardado() # Se cambian los botones a modo "Guardado"
                
                if ir_a_pareo:
                    messagebox.showinfo("Éxito", "Torneo guardado en la BD. Pasando a Fase de Pareos.")
                    from pantalla_pareo import PantallaPareo
                    p_pareo = self.controller.pantallas.get(PantallaPareo)
                    if p_pareo:
                        p_pareo.cargar_torneo(nuevo_id)
                        self.controller.mostrar_pantalla(PantallaPareo)
                else:
                    messagebox.showinfo("Éxito", "Torneo inicial guardado correctamente.")
            else:
                messagebox.showerror("Error", "Error al crear el torneo en la base de datos.")

    def guardar_solo_torneo(self):
        """Sincroniza forzando el reemplazo de los atletas editados para que la BD no los ignore."""
        id_existente = getattr(self, 'torneo_debug_id', None)
        es_master = getattr(self.controller, 'es_master', False)
        soy_guest = bool(id_existente) and not es_master

        # --- ESCUDO ANTI-NULL Y ANTI-DUPLICADOS UNIVERSAL ---
        datos_limpios = []
        datos_pre_sync = [] # Lista temporal sin los atletas editados
        hay_editados = False
        divisiones = {} 
        
        for ins in self.inscripciones_memoria:
            # 1. Saltamos los que marcamos con el botón "Eliminar" O los que la red ya eliminó
            if ins.get('estado_local') == 'eliminado' or ins.get('tipo_cambio_red') == 'eliminado':
                continue
                
            ins_copia = ins.copy()
            ins_copia['peso_pesaje'] = ins.get('peso') 
            ins_copia['peso_dado'] = ins.get('peso')   
            
            divs_validas = []
            estilos_validos = []
            
            for idx, d in enumerate(ins.get('ids_divisiones', [])):
                if d is not None and int(d) not in divs_validas:
                    id_div = int(d)
                    divs_validas.append(id_div)
                    estilo = ins.get('estilos', [])[idx] if idx < len(ins.get('estilos', [])) else "Estilo Libre"
                    estilos_validos.append(estilo)
                    
                    if id_div not in divisiones: divisiones[id_div] = []
                    divisiones[id_div].append(ins['id_atleta'])
            
            if divs_validas:
                ins_copia['ids_divisiones'] = divs_validas
                ins_copia['estilos'] = estilos_validos
                
                # --- TRUCO DE MAGIA: Separamos a los editados ---
                if ins.get('estado_local') == 'editado':
                    ins_copia['de_red'] = False 
                    hay_editados = True
                    datos_limpios.append(ins_copia)
                    # NO lo agregamos a datos_pre_sync (Forzamos a la BD a creer que lo borramos)
                else:
                    datos_limpios.append(ins_copia)
                    datos_pre_sync.append(ins_copia)

        # --- VALIDACIÓN GLOBAL: AL MENOS 1 PAREJA ---
        hay_pareja = any(len(atletas) >= 2 for atletas in divisiones.values())
        if not hay_pareja:
            return messagebox.showerror("Error de Sincronización", "Debe haber al menos 2 atletas en una misma categoría.\n\nNo puedes sincronizar una lista vacía o sin parejas válidas.")

        # --- FILTRO PARA INVITADOS (GUEST) ---
        if soy_guest:
            if not messagebox.askyesno("Sincronizar", "¿Deseas enviar tus cambios a la base de datos?"):
                return
            self.esta_editando_localmente = True
            
            # 1. Engañar a la BD para que purgue la versión vieja del atleta
            if hay_editados:
                self.db.sincronizar_inscripciones(id_existente, datos_pre_sync)
                
            # 2. Insertar la versión nueva y editada del atleta
            exito = self.db.sincronizar_inscripciones(id_existente, datos_limpios)
            
            if exito:
                self.inscripciones_memoria = [i for i in self.inscripciones_memoria if i.get('estado_local') != 'eliminado']
                for ins in self.inscripciones_memoria:
                    ins['de_red'] = True
                    if 'estado_local' in ins: del ins['estado_local']
                    
                self._ultima_firma_red = None 
                messagebox.showinfo("Éxito", "Sincronización completada.")
                self.actualizar_tabla_visual()
            else:
                messagebox.showerror("Error", "No se pudo sincronizar.")
            self.esta_editando_localmente = False
            return

        # --- LÓGICA PARA EL MÁSTER ---
        if id_existente:
            self.esta_editando_localmente = True 
            
            # 1. Engañar a la BD para que purgue la versión vieja
            if hay_editados:
                self.db.sincronizar_inscripciones(id_existente, datos_pre_sync)
                
            # 2. Insertar la versión nueva
            if self.db.sincronizar_inscripciones(id_existente, datos_limpios):
                
                # --- FIX CRÍTICO: Limpiar estados locales para el Máster también ---
                self.inscripciones_memoria = [i for i in self.inscripciones_memoria if i.get('estado_local') != 'eliminado']
                for ins in self.inscripciones_memoria:
                    ins['de_red'] = True
                    if 'estado_local' in ins: del ins['estado_local']
                    
                self._ultima_firma_red = None 
                self.actualizar_tabla_visual() 
                messagebox.showinfo("Éxito", "Cambios sincronizados correctamente.")
                if hasattr(self, 'btn_avanzar_pareo'): self.btn_avanzar_pareo.config(state="normal")
            self.esta_editando_localmente = False
            return

        # --- LÓGICA DE CREACIÓN DEL TORNEO (NUNCA ANTES GUARDADO) ---
        if not self.inscripciones_memoria:
            return messagebox.showwarning("Sin Atletas", "Debe inscribir atletas antes de guardar.")

        # Re-construir divisiones para validación de sala
        divisiones_nuevas = {}
        for ins in datos_limpios:
            for i, id_div in enumerate(ins['ids_divisiones']):
                if id_div in getattr(self, "pesos_bloqueados_ids", set()):
                    continue
                estilo = ins['estilos'][i] if i < len(ins['estilos']) else "Estilo"
                nombre_atl = next((f"{a['apellidos']}, {a['nombre']}" for a in self.atletas_db if a['id'] == ins['id_atleta']), "Atleta")
            
                if id_div not in divisiones_nuevas:
                    divisiones_nuevas[id_div] = {"estilo": estilo, "atletas": []}
                divisiones_nuevas[id_div]["atletas"].append(nombre_atl)

        hay_pareja_nueva = any(len(d["atletas"]) >= 2 for d in divisiones_nuevas.values())
        if not hay_pareja_nueva:
            return messagebox.showerror("Error", "Debe haber al menos 2 atletas en una misma categoría para crear la sala.")

        id_cat = next((c['id'] for c in self.categorias_db if c['nombre'] == self.categoria_confirmada), None)
        id_ciu = self.map_ciudades_torneo.get(self.torneo_ciudad_conf, None)
        
        try: fecha_db = datetime.strptime(self.ent_tor_fecha.get().strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError: fecha_db = datetime.now().strftime("%Y-%m-%d")

        datos_torneo = {
            'nombre': self.torneo_nombre_conf,
            'id_categoria': id_cat,
            'lugar': self.torneo_lugar_conf,
            'id_ciudad': id_ciu,
            'fecha': fecha_db
        }
        
        id_torneo = self.db.guardar_torneo_completo(datos_torneo, datos_limpios)
        if not id_torneo:
            return messagebox.showerror("Error", "Fallo al conectar con la base de datos para crear el torneo.")
        
        self.torneo_debug_id = id_torneo

        import socket
        import os 
        nombre_pc = f"{socket.gethostname()}-{os.getpid()}"
        id_oficial = getattr(self.controller, 'id_operador', None) or (self.oficiales_db[0]['id'] if getattr(self, 'oficiales_db', None) else 1)
            
        id_conexion = self.db.registrar_conexion_instancia(id_torneo, id_oficial, nombre_pc, es_master=True)
        
        if id_conexion:
            self.controller.id_conexion_red = id_conexion
            self.controller.es_master = True
            self.controller.tapiz_asignado = "Tapiz A"
            
            for ins in self.inscripciones_memoria:
                ins['de_red'] = True
            self.actualizar_tabla_visual()
            
            id_oficial = getattr(self.controller, 'id_operador', None)
            oficial = next((o for o in self.oficiales_db if o['id'] == id_oficial), None)
            nombre_oficial = f"{oficial['nombre']} {oficial['apellidos']}" if oficial else "Desconocido"
            
            self.lbl_tapete_master.config(text=f"🥇 Tapiz A (Máster: {nombre_oficial}) - {nombre_pc}", foreground="#28a745")
            
            self.bloquear_datos_torneo(False) 
            self.ent_tor_nombre.config(state="disabled")
            self.ent_tor_lugar.config(state="disabled")
            self.cmb_categoria.config(state="disabled")
            if hasattr(self, 'cmb_tor_ciudad'): self.cmb_tor_ciudad.config(state="disabled")
            
            self.btn_guardar_torneo.config(state="normal", text="💾 Guardar Cambios")
            self.btn_avanzar_pareo.config(state="normal")
            
            self.actualizar_btn_nuevo_limpiar()
            messagebox.showinfo("Sala Creada", f"¡Éxito! Torneo creado.\n\nEres el MASTER desde '{nombre_pc}'.")
            self.iniciar_escucha_red()
        else:
            messagebox.showerror("Error de Red", "El torneo se guardó, pero falló la creación de la sala.")

    def avanzar_fase_dos(self):
        """Sincroniza y decide qué lógica de red aplicar al abrir la Cartelera."""
        if not getattr(self, 'torneo_debug_id', None):
            return messagebox.showwarning("Acceso Denegado", "Debes GUARDAR EL TORNEO en la BD primero.")
        
        if not self.inscripciones_memoria:
            return messagebox.showwarning("Sin Atletas", "Inscribe al menos un atleta antes de generar llaves.")

        # Sincroniza cualquier atleta nuevo antes de salir
        if not self.db.sincronizar_inscripciones(self.torneo_debug_id, self.inscripciones_memoria):
            return messagebox.showerror("Error", "Fallo al guardar los atletas en la base de datos.")

        from ui.pantallas.pareo.pantalla_pareo import PantallaPareo
        p_pareo = self.controller.pantallas.get(PantallaPareo)
        
        if p_pareo:
            # ---> Ahora ESTA ÚNICA línea carga el torneo e inicia la red silenciosamente
            p_pareo.cargar_torneo(self.torneo_debug_id)
            self.controller.mostrar_pantalla(PantallaPareo)
