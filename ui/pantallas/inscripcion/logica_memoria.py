import tkinter as tk
from tkinter import ttk, messagebox
import re
from datetime import datetime
from utils.utilidades import aplicar_autocompletado
from ui.ventanas.ventana_nuevo_atleta import VentanaNuevoRegistro

class LogicaMemoriaMixin:
    """Contiene la lógica del formulario de pesaje, adición a memoria y actualización de la tabla central."""

    def cargar_para_editar(self):
        item_sel = self.tabla.selection()
        if not item_sel: return messagebox.showwarning("Selección", "Seleccione un atleta de la tabla.")
        
        valores = self.tabla.item(item_sel[0], "values")
        self.id_atleta_editando = int(valores[0])

        # --- CORRECCIÓN: Limpiar prefijos visuales (RED, NUEVO, etc.) del nombre ---
        nombre_crudo = valores[2].replace("🌐 [RED] ", "").replace("✨ [NUEVO] ", "").replace("✏️ [EDITAR] ", "").replace("❌ [ELIMINAR] ", "").replace("🔄 [EDITADO] ", "").replace("🗑️ [BORRADO] ", "")

        # Asignar el valor limpio para que el buscador interno lo encuentre a la perfección
        atleta_str = f"{nombre_crudo} (ID: {self.id_atleta_editando})"
        self.cmb_atleta.set(atleta_str)
        
        # Al ejecutar esto ahora, SÍ encontrará al atleta y desbloqueará las casillas según su sexo
        self.al_seleccionar_atleta(None)
        
        self.var_peso.set(valores[6])

        self.var_estilo_libre.set(True if "Libre" in valores[8] else False) 
        self.var_estilo_greco.set(True if "Grecorromana" in valores[8] else False)
        self.var_estilo_femenina.set(True if "Femenina" in valores[8] else False)

        self.btn_agregar.config(text="Actualizar Inscripción")
        if hasattr(self, 'btn_cancelar_edicion'):
            self.btn_cancelar_edicion.pack(side="left", padx=5)
        self.cmb_atleta.config(state="disabled")

    def cancelar_edicion(self):
        self.id_atleta_editando = None
        self.item_tree_editando = None
        self.btn_agregar.config(text="Añadir a Memoria")
        if hasattr(self, 'btn_cancelar_edicion'):
            self.btn_cancelar_edicion.pack_forget()
            
        # --- DESBLOQUEAR Y VACIAR CAMPOS ---
        self.cmb_atleta.config(state="normal") 
        self.cmb_atleta.set('')
        
        if hasattr(self, 'var_peso'):
            self.var_peso.set('') # Vaciamos el peso explícitamente
            
        self.al_seleccionar_atleta() # Esto apagará y vaciará los checkboxes de estilo

    def agregar_a_memoria(self):
        self.esta_editando_localmente = True
        if getattr(self, "_procesando_agregado", False): return
        self._procesando_agregado = True

        # MANDAR EL FOCO A LA TABLA PARA "MATAR" EL ENTER DEL BOTÓN
        self.tabla.focus_set()
        
        try:
            texto_atleta = self.cmb_atleta.get().strip()
            peso_str = self.ent_peso.get().strip()
            
            # --- CORTAFUEGOS 1: Prevenir "clic fantasma" tras limpiar el formulario ---
            if not texto_atleta and not peso_str: 
                return
                
            if not texto_atleta or not peso_str: 
                messagebox.showwarning("Incompleto", "Seleccione atleta y peso.")
                return

            try: peso_dado = float(peso_str)
            except ValueError: return messagebox.showwarning("Error", "Peso inválido.")

            atleta = next((a for a in getattr(self, "atletas_filtrados_objetos", []) if f"{a['apellidos']}, {a['nombre']} (ID: {a['id']})" == texto_atleta), None)
            if not atleta: return messagebox.showwarning("Error", "Atleta no válido.")

            id_cat_torneo = next((int(c['id']) for c in self.categorias_db if c['nombre'] == self.categoria_confirmada), None)
            
            estilos_sel = []
            if self.var_estilo_libre.get(): estilos_sel.append(("Estilo Libre", 1))
            if self.var_estilo_greco.get(): estilos_sel.append(("Grecorromana", 2))
            if self.var_estilo_femenina.get(): estilos_sel.append(("Femenina", 3))

            if not estilos_sel: return messagebox.showwarning("Estilo Requerido", "Seleccione un estilo.")

            pesos_oficiales_text, estilos_memoria, ids_divisiones = [], [], []

            for nombre_estilo, id_estilo in estilos_sel:
                bracket_encontrado = None
                for p in self.pesos_oficiales_db:
                    if int(p['id_categoria_edad']) == id_cat_torneo and int(p['id_estilo_lucha']) == int(id_estilo):
                        if float(p['peso_minimo']) <= peso_dado <= float(p['peso_maximo']):
                            bracket_encontrado = p
                            break
                
                if not bracket_encontrado: 
                    return messagebox.showwarning("Fuera de Rango", f"El peso {peso_dado}kg no existe para {nombre_estilo}.")
            
                abr = "Lib" if nombre_estilo == "Estilo Libre" else nombre_estilo[:3]
                pesos_oficiales_text.append(f"{abr}: {bracket_encontrado['peso_maximo']}kg")
                estilos_memoria.append(nombre_estilo)
                ids_divisiones.append(int(bracket_encontrado['id']))

            texto_peso_oficial = " | ".join(pesos_oficiales_text)
            peso_formateado = f"{peso_dado:.2f}"

            # --- RUTA 1: ACTUALIZANDO UN ATLETA EXISTENTE ---
            if self.id_atleta_editando is not None:
                for ins in self.inscripciones_memoria:
                    if ins['id_atleta'] == self.id_atleta_editando:
                        ins.update({'peso': peso_formateado, 'peso_oficial': texto_peso_oficial, 'estilos': estilos_memoria, 'ids_divisiones': ids_divisiones})
                        if ins.get('de_red'):
                            ins['estado_local'] = 'editado'
                        break
                self.actualizar_tabla_visual()
                
                # Reseleccionar en la tabla tras actualizar
                for item in self.tabla.get_children():
                    if int(self.tabla.item(item, "values")[0]) == self.id_atleta_editando:
                        self.tabla.selection_set(item)
                        self.al_seleccionar_tabla(None)
                        break
                        
                self.cancelar_edicion()
                return messagebox.showinfo("Actualizado", "Inscripción actualizada localmente.\nRecuerde presionar 'Sincronizar' para guardar.")

            if any(ins['id_atleta'] == atleta['id'] for ins in self.inscripciones_memoria):
                return messagebox.showwarning("Duplicado", "Este atleta ya está en la lista.")

            # --- RUTA 2: AGREGANDO UN ATLETA NUEVO ---
            self.inscripciones_memoria.append({
                "id_atleta": int(atleta['id']), "peso": peso_formateado, "peso_oficial": texto_peso_oficial, 
                "estilos": estilos_memoria, "ids_divisiones": ids_divisiones, "de_red": False
            })
            self.actualizar_tabla_visual()
            
            # --- CORTAFUEGOS 2: Seleccionar automáticamente al atleta recién añadido ---
            for item in self.tabla.get_children():
                if int(self.tabla.item(item, "values")[0]) == int(atleta['id']):
                    self.tabla.selection_set(item)
                    self.al_seleccionar_tabla(None)
                    break

            # Limpiar y bloquear campos tras agregar a memoria de forma segura
            self.cmb_atleta.set('')
            self.al_seleccionar_atleta() 

        finally:
            self.esta_editando_localmente = False
            self.after(500, lambda: setattr(self, "_procesando_agregado", False))

    def eliminar_de_memoria(self):
        self.esta_editando_localmente = True
        item_sel = self.tabla.selection()
        if not item_sel: return
        
        valores = self.tabla.item(item_sel[0], "values")
        nombre_atleta = valores[2].replace("🌐 [RED] ", "").replace("✨ [NUEVO] ", "").replace("✏️ [EDITAR] ", "").replace("🔄 [EDITADO] ", "").replace("🗑️ [BORRADO] ", "")
        id_atleta = int(valores[0])
        
        if not messagebox.askyesno("Marcar Eliminación", f"¿Marcar a '{nombre_atleta}' para ser eliminado?\n\nEl cambio se aplicará a la sala cuando presione 'Sincronizar'."): 
            self.esta_editando_localmente = False
            return
            
        if self.id_atleta_editando == id_atleta: 
            self.cancelar_edicion() 
            
        # --- LÓGICA DE ELIMINACIÓN INTELIGENTE ---
        for ins in self.inscripciones_memoria:
            if ins['id_atleta'] == id_atleta:
                if not ins.get('de_red'):
                    # Si era local (blanco) y lo borras, desaparece de inmediato porque no existía en la BD
                    self.inscripciones_memoria.remove(ins)
                else:
                    # Si ya estaba en la red, lo marcamos para que se pinte de rojo
                    ins['estado_local'] = 'eliminado'
                break

        self.actualizar_opciones_filtros()
        self.actualizar_tabla_visual()
        self.esta_editando_localmente = False

    def deshacer_cambios_locales(self):
        if not messagebox.askyesno("Deshacer Cambios", "¿Desea descartar todos los cambios locales (eliminaciones, ediciones y nuevos) y recargar la tabla original?"):
            return
            
        self.esta_editando_localmente = True
        self.cancelar_edicion() # Limpia los campos de texto
        
        # 1. Borramos los atletas que no se han subido (los blancos)
        self.inscripciones_memoria = [i for i in self.inscripciones_memoria if i.get('de_red')]
        
        # 2. Limpiamos los estados de edición/eliminación de los que vienen de la red
        for ins in self.inscripciones_memoria:
            if 'estado_local' in ins:
                del ins['estado_local']
                
        # 3. Obligamos al radar a refrescar la vista en el próximo latido
        self._ultima_firma_red = None
        self.actualizar_tabla_visual()
        self.esta_editando_localmente = False
        messagebox.showinfo("Restaurado", "Se han descartado los cambios locales.")

    def actualizar_tabla_visual(self, event=None):
        if not hasattr(self, 'tabla'): return 
        
        # --- NUEVO: Memorizar qué atleta estaba seleccionado ---
        ids_seleccionados = [str(self.tabla.item(i, "values")[0]) for i in self.tabla.selection()]
        
        for item in self.tabla.get_children(): self.tabla.delete(item)

        tipo_busq = getattr(self, 'cmb_tipo_busqueda', None)
        if not tipo_busq: return 
        tipo = tipo_busq.get()
        term = self.ent_busqueda.get().strip().lower()

        mostrar_m = self.var_filtro_m.get()
        mostrar_f = self.var_filtro_f.get()
        sel_pesos = [self.listbox_pesos.get(i) for i in self.listbox_pesos.curselection()]
        sel_estilos = [self.listbox_estilos.get(i) for i in self.listbox_estilos.curselection()]

        total_atletas = 0
        clubes_unicos = set()
        ciudades_unicas = set()

        for ins in self.inscripciones_memoria:
            id_atl = ins['id_atleta']
            info = next((a for a in self.atletas_db if a['id'] == id_atl), None)
            if not info: continue

            if info['sexo'] == 'M' and not mostrar_m: continue
            if info['sexo'] == 'F' and not mostrar_f: continue

            if sel_pesos:
                pesos_atl = ins['peso_oficial'].split(" | ")
                if not any(p in sel_pesos for p in pesos_atl): continue
            
            if sel_estilos and not any(e in sel_estilos for e in ins['estilos']): continue

            nombre_completo = f"{info['apellidos']}, {info['nombre']}"
            club = info['club'] or "Sin Club"
            ciudad = info['ciudad'] or "Sin Ciudad"
            
            if term:
                if tipo == "ID" and str(id_atl) != term: continue
                if tipo == "Nombre" and term not in nombre_completo.lower(): continue
                if tipo == "Club" and term not in club.lower(): continue
                if tipo == "Ciudad" and term not in ciudad.lower(): continue

            is_dsq = id_atl in getattr(self, "atletas_descalificados_ids", set())
            tags_list = ["dsq"] if is_dsq else []
            
            divisiones_atleta = ins.get('ids_divisiones', [])
            bloqueadas = getattr(self, "pesos_bloqueados_ids", set())
            todas_bloqueadas = all((d in bloqueadas) for d in divisiones_atleta) if divisiones_atleta else False
            
            prefijo = ""
            estado_local = ins.get('estado_local')
            
            if estado_local == 'eliminado':
                prefijo = "❌ [ELIMINAR] "
                tags_list.append("eliminado_local")
            elif estado_local == 'editado':
                prefijo = "✏️ [EDITAR] "
                tags_list.append("editado_local")
            elif todas_bloqueadas:
                if not is_dsq: tags_list.append("confirmado")
            elif ins.get("de_red", False):
                ciclos = ins.get("ciclos_red", 2)
                tipo_cambio = ins.get("tipo_cambio_red", "nuevo")
                
                # --- FIX: Prioridad absoluta al estado de borrado ---
                if tipo_cambio == 'eliminado':
                    prefijo = "🗑️ [BORRADO] "
                    tags_list.append("eliminado_red")
                elif ciclos < 2:
                    if tipo_cambio == 'editado':
                        prefijo = "🔄 [EDITADO] "
                        tags_list.append("editado_red")
                    else:
                        prefijo = "✨ [NUEVO] "
                        tags_list.append("red_nuevo")
                else:
                    prefijo = "🌐 [RED] "
                    tags_list.append("sync_red")
                    
            nombre_mostrar = prefijo + nombre_completo
            tags = tuple(tags_list)

            fila_valores = (id_atl, 0, nombre_mostrar, info['sexo'], club, ciudad, ins['peso'], ins['peso_oficial'], " + ".join(ins['estilos']))
            
            # --- NUEVO: Insertar y devolver la selección automáticamente ---
            nuevo_item = self.tabla.insert("", "end", values=fila_valores, tags=tags)
            if str(id_atl) in ids_seleccionados:
                self.tabla.selection_add(nuevo_item)
            
            total_atletas += 1
            if club != "Sin Club": clubes_unicos.add(club)
            if ciudad != "Sin Ciudad": ciudades_unicas.add(ciudad)

        if hasattr(self, 'lbl_estadisticas'):
            color_estado = "#6f42c1" if getattr(self, "todo_bloqueado", False) else "#28a745"
            self.lbl_estadisticas.config(text=f"Atletas: {total_atletas}  |  Clubes: {len(clubes_unicos)}  |  Ciudades: {len(ciudades_unicas)}", foreground=color_estado)
            
        # --- CORTAFUEGOS: Re-evaluar botones en lugar de apagarlos ciegamente ---
        if self.tabla.selection():
            self.al_seleccionar_tabla(None)
        else:
            if hasattr(self, 'btn_editar_memoria'):
                self.btn_editar_memoria.config(state="disabled")
                self.btn_eliminar_memoria.config(state="disabled")

        hay_cambios_pendientes = any(i.get('estado_local') or not i.get('de_red') for i in self.inscripciones_memoria)
        if hasattr(self, 'btn_deshacer_memoria'):
            self.btn_deshacer_memoria.config(state="normal" if hay_cambios_pendientes else "disabled")

    def filtrar_atletas_por_edad(self):
        # 1. DESCARGA EN VIVO: Siempre usar datos frescos de la BD
        if hasattr(self, 'db'):
            self.atletas_db = self.db.obtener_atletas()

        # Usar la variable de memoria porque el combobox bloqueado devuelve vacío
        nombre_cat = getattr(self, 'categoria_confirmada', None)
        if not nombre_cat:
            nombre_cat = self.cmb_categoria.get().strip()
            
        if not nombre_cat: 
            return

        # 2. MATCH TOLERANTE: Ignora mayúsculas y espacios extra
        cat = next((c for c in getattr(self, 'categorias_db', []) if str(c.get('nombre', '')).strip().lower() == nombre_cat.lower()), None)
        
        # Si no hay categoría válida, la lista queda estrictamente vacía
        if not cat: 
            if hasattr(self, 'cmb_atleta'):
                self.cmb_atleta.config(values=[])
                self.cmb_atleta.set('')
            return

        anio_torneo = datetime.now().year
        self.atletas_filtrados_objetos = []
        atletas_permitidos = []

        # 3. TOLERANCIA DE COLUMNAS
        try: e_min = int(cat.get('edad_minima', cat.get('edad_min', 0)))
        except: e_min = 0
        try: e_max = int(cat.get('edad_maxima', cat.get('edad_max', 99)))
        except: e_max = 99

        import re
        for atleta in getattr(self, 'atletas_db', []):
            fecha_nac = atleta.get('fecha_nacimiento', '')
            anio_nac = anio_torneo 
            
            # EXTRACCIÓN CON EXPRESIÓN REGULAR
            if hasattr(fecha_nac, 'year'):
                anio_nac = fecha_nac.year
            else:
                match = re.search(r'\d{4}', str(fecha_nac))
                if match:
                    anio_nac = int(match.group())
            
            edad_uww = anio_torneo - anio_nac
            
            # Filtro ESTRICTO de Edad UWW
            if e_min <= edad_uww <= e_max:
                texto_combo = f"{atleta.get('apellidos', '')}, {atleta.get('nombre', '')} (ID: {atleta.get('id', '')})"
                atletas_permitidos.append(texto_combo)
                self.atletas_filtrados_objetos.append(atleta)

        # 4. INYECCIÓN AL COMBOBOX
        if hasattr(self, 'cmb_atleta'):
            self.cmb_atleta.config(values=atletas_permitidos)
            try:
                aplicar_autocompletado(self.cmb_atleta, atletas_permitidos)
            except:
                pass
            self.cmb_atleta.set('')

    def al_seleccionar_atleta(self, event=None):
        if not hasattr(self, 'cmb_atleta'): return
        
        texto_atleta = self.cmb_atleta.get().strip()
        
        # Función interna rápida para apagar y bloquear
        def forzar_bloqueo():
            self.var_estilo_libre.set(False)
            self.var_estilo_greco.set(False)
            self.var_estilo_femenina.set(False)
            if hasattr(self, 'chk_libre'): self.chk_libre.config(state="disabled")
            if hasattr(self, 'chk_greco'): self.chk_greco.config(state="disabled")
            if hasattr(self, 'chk_femenina'): self.chk_femenina.config(state="disabled")
            self.actualizar_categoria_dinamica()
        
        if not texto_atleta: 
            return forzar_bloqueo()
            
        atleta = next((a for a in getattr(self, "atletas_filtrados_objetos", []) if f"{a.get('apellidos', '')}, {a.get('nombre', '')} (ID: {a.get('id', '')})" == texto_atleta), None)
        
        if not atleta: 
            return forzar_bloqueo()

        self.var_estilo_libre.set(False)
        self.var_estilo_greco.set(False)
        self.var_estilo_femenina.set(False)

        sexo = str(atleta.get('sexo', '')).upper()
        if sexo == 'M':
            if hasattr(self, 'chk_libre'): self.chk_libre.config(state="normal")
            if hasattr(self, 'chk_greco'): self.chk_greco.config(state="normal")
            if hasattr(self, 'chk_femenina'): self.chk_femenina.config(state="disabled")
            self.var_estilo_libre.set(True)
        else:
            if hasattr(self, 'chk_libre'): self.chk_libre.config(state="disabled")
            if hasattr(self, 'chk_greco'): self.chk_greco.config(state="disabled")
            if hasattr(self, 'chk_femenina'): self.chk_femenina.config(state="normal")
            self.var_estilo_femenina.set(True)

        self.actualizar_categoria_dinamica()

    def actualizar_categoria_dinamica(self, *args):
        # --- CORTAFUEGOS 1: Si el combobox de atleta está vacío, abortar silenciosamente ---
        # Esto evita el error emergente cuando acabas de añadir a alguien y el peso sigue ahí.
        if hasattr(self, 'cmb_atleta'):
            texto_atleta = self.cmb_atleta.get().strip()
            if not texto_atleta:
                if hasattr(self, 'lbl_cat_dinamica'):
                    self.lbl_cat_dinamica.config(text="Categoría: --", foreground="gray")
                return

            # --- REGLA DE NO DESELECCIONAR TODOS ---
            atleta = next((a for a in getattr(self, "atletas_filtrados_objetos", []) if f"{a.get('apellidos', '')}, {a.get('nombre', '')} (ID: {a.get('id', '')})" == texto_atleta), None)
            
            if atleta:
                if not (self.var_estilo_libre.get() or self.var_estilo_greco.get() or self.var_estilo_femenina.get()):
                    if str(atleta.get('sexo', '')).upper() == 'M': self.var_estilo_libre.set(True)
                    else: self.var_estilo_femenina.set(True)

        peso_str = getattr(self, 'var_peso', tk.StringVar()).get().strip()
        if not peso_str:
            if hasattr(self, 'lbl_cat_dinamica'):
                self.lbl_cat_dinamica.config(text="Categoría: --", foreground="gray")
            return
            
        try: peso_dado = float(peso_str)
        except ValueError:
            self.lbl_cat_dinamica.config(text="Categoría: Error", foreground="red")
            return
            
        if peso_dado <= 20: 
            self.lbl_cat_dinamica.config(text="Peso irreal", foreground="red")
            return

        if not getattr(self, 'categoria_confirmada', None):
            self.lbl_cat_dinamica.config(text="Confirme torneo primero", foreground="orange")
            return

        estilos_sel = []
        if self.var_estilo_libre.get(): estilos_sel.append(("Estilo Libre", 1)) 
        if self.var_estilo_greco.get(): estilos_sel.append(("Grecorromana", 2))
        if self.var_estilo_femenina.get(): estilos_sel.append(("Femenina", 3))

        # --- CORTAFUEGOS 2: Sustituimos el messagebox por un texto visual ---
        if not estilos_sel:
            if hasattr(self, 'lbl_cat_dinamica'):
                self.lbl_cat_dinamica.config(text="Categoría: Faltan Estilos", foreground="orange")
            return

        id_cat_torneo = next((c['id'] for c in self.categorias_db if c['nombre'] == self.categoria_confirmada), None)
        
        cats_encontradas = []
        for nombre_estilo, id_estilo in estilos_sel:
            bracket_encontrado = None
            for p in getattr(self, 'pesos_oficiales_db', []):
                if str(p['id_categoria_edad']) == str(id_cat_torneo) and str(p['id_estilo_lucha']) == str(id_estilo):
                    if float(p['peso_minimo']) <= peso_dado <= float(p['peso_maximo']):
                        bracket_encontrado = p
                        break
            
            abr = "Lib" if nombre_estilo == "Estilo Libre" else nombre_estilo[:3]
            
            if bracket_encontrado:
                cats_encontradas.append(f"{abr}: {bracket_encontrado['peso_maximo']}kg")
            else:
                cats_encontradas.append(f"{abr}: Fuera de Rango")
        
        texto_final = " | ".join(cats_encontradas)
        color = "red" if "Fuera" in texto_final else "#17a2b8"
        if hasattr(self, 'lbl_cat_dinamica'):
            self.lbl_cat_dinamica.config(text=f"Asignación: {texto_final}", foreground=color)

    def cargar_datos_bd(self):
        self.categorias_db = self.db.obtener_categorias()
        if self.categorias_db:
            aplicar_autocompletado(self.cmb_categoria, [cat['nombre'] for cat in self.categorias_db])
            
        self.pesos_oficiales_db = self.db.obtener_pesos_oficiales()
        self.atletas_db = self.db.obtener_atletas()
        
        if self.btn_confirmar_torneo.cget("text") == "Modificar Torneo":
            self.filtrar_atletas_por_edad()

        clubes = self.db.obtener_clubes()
        ciudades = self.db.obtener_ciudades()
        
        self.map_ciudades_torneo = {c['nombre']: c['id'] for c in ciudades}
        aplicar_autocompletado(self.cmb_tor_ciudad, sorted(list(self.map_ciudades_torneo.keys())))
        
    def al_seleccionar_tabla(self, event=None):
        # --- CORTAFUEGOS: Evitar deselección o cambio de fila con el teclado durante edición ---
        if getattr(self, "id_atleta_editando", None) is not None:
            # Forzar a mantener la selección en el atleta que se está editando
            for item in self.tabla.get_children():
                if self.tabla.item(item, "values") and int(self.tabla.item(item, "values")[0]) == self.id_atleta_editando:
                    if item not in self.tabla.selection():
                        self.tabla.selection_set(item)
                    break
            return

        # Resto de la lógica normal
        if getattr(self, "todo_bloqueado", False) or getattr(self, "bloquear_seleccion_tabla", False):
            if self.tabla.selection(): self.tabla.selection_remove(self.tabla.selection()[0])
            return
            
        item_sel = self.tabla.selection()
        if not item_sel: return
        valores = self.tabla.item(item_sel[0], "values")
        id_atleta = int(valores[0])
        
        ins_data = next((i for i in self.inscripciones_memoria if i['id_atleta'] == id_atleta), None)
        if not ins_data: return
        
        is_locked = any(div_id in getattr(self, "pesos_bloqueados_ids", set()) for div_id in ins_data['ids_divisiones'])
        
        is_deleted = ins_data.get('estado_local') == 'eliminado' or (ins_data.get('tipo_cambio_red') == 'eliminado' and ins_data.get('ciclos_red', 2) < 2)
        
        if is_locked or is_deleted:
            self.btn_editar_memoria.config(state="disabled")
            self.btn_eliminar_memoria.config(state="disabled")
        else:
            self.btn_editar_memoria.config(state="normal")
            self.btn_eliminar_memoria.config(state="normal")
        
    def cambiar_estado_inscripcion(self, estado):
        estado_cmb = "normal" if estado == "normal" else "disabled"
        self.cmb_atleta.config(state=estado_cmb)
        self.btn_nuevo_atleta.config(state=estado)
        self.ent_peso.config(state=estado)
        self.btn_agregar.config(state=estado)
        
        if estado == "disabled":
            self.chk_libre.config(state="disabled")
            self.chk_greco.config(state="disabled")
            self.chk_femenina.config(state="disabled")
        else:
            # Forzamos la validación para que los estilos nazcan apagados
            self.al_seleccionar_atleta()

    # -- Métodos de Filtros y Validadores (validar_peso, limpiar_filtros, etc.) --
    def validar_peso(self, P):
        """Permite borrar y admite números con hasta 2 decimales (ej. 74 o 74.55)."""
        if P == "": return True
        # RegEx: Máximo 3 enteros, un punto opcional, y máximo 2 decimales
        match = re.match(r'^\d{0,3}(\.\d{0,2})?$', P)
        return match is not None

    def validar_solo_numeros(self, P):
        if P == "": return True
        return P.isdigit()

    def cambiar_tipo_busqueda(self, event=None):
        # 1. Se limpia la barra automáticamente al cambiar de opción
        self.ent_busqueda.delete(0, tk.END)
        
        tipo = self.cmb_tipo_busqueda.get()
        
        # 2. Se activa o desactiva la validación de "Solo Números"
        if tipo == "ID": 
            self.ent_busqueda.config(validate='key', validatecommand=self.vcmd_id)
        else: 
            self.ent_busqueda.config(validate='none')
            
        self.actualizar_tabla_visual()

    def limpiar_filtros(self):
        """Restablece todos los parámetros de búsqueda a su estado inicial."""
        self.cmb_tipo_busqueda.set("Nombre")
        self.cambiar_tipo_busqueda() # Esto limpia el entry y ajusta validaciones
        
        self.var_filtro_m.set(True)
        self.var_filtro_f.set(True)
        
        self.listbox_pesos.selection_clear(0, tk.END)
        self.listbox_estilos.selection_clear(0, tk.END)
        
        self.actualizar_opciones_filtros()
        self.actualizar_tabla_visual()

    def limpiar_listbox(self, listbox):
        """Desmarca todas las opciones de un listbox y actualiza la tabla."""
        listbox.selection_clear(0, tk.END)
        # Si borramos estilos, debemos actualizar los pesos compatibles
        if listbox == getattr(self, 'listbox_estilos', None):
            self.actualizar_opciones_filtros()
        self.actualizar_tabla_visual()

    def filtrar_listbox(self, listbox, entry, lista_completa):
        """Filtra visualmente los elementos del Listbox según lo escrito."""
        texto = entry.get().lower()
        
        # Guardar qué estaba seleccionado antes de filtrar
        seleccionados_nombres = [listbox.get(i) for i in listbox.curselection()]
        
        listbox.delete(0, tk.END)
        for item in lista_completa:
            if texto in item.lower():
                listbox.insert(tk.END, item)
                # Volver a marcar si estaba seleccionado
                if item in seleccionados_nombres:
                    listbox.selection_set(listbox.size() - 1)

    def actualizar_opciones_filtros(self):
        """Actualiza las categorías de peso según los estilos seleccionados."""
        if not hasattr(self, 'listbox_pesos'): return

        sel_pesos = [self.listbox_pesos.get(i) for i in self.listbox_pesos.curselection()]
        sel_estilos = [self.listbox_estilos.get(i) for i in self.listbox_estilos.curselection()]
        
        pesos_compatibles = set()
        estilos_existentes = set()
        mapping = {"Lib": "Estilo Libre", "Gre": "Grecorromana", "Fem": "Femenina"}

        for ins in self.inscripciones_memoria:
            for est in ins['estilos']: estilos_existentes.add(est)
            
            individuales = ins['peso_oficial'].split(" | ")
            for w_str in individuales:
                prefijo = w_str.split(":")[0].strip()
                estilo_del_peso = mapping.get(prefijo)
                
                if not sel_estilos or estilo_del_peso in sel_estilos:
                    pesos_compatibles.add(w_str)

        # 1. Actualizar memoria y Listbox de Pesos
        self.pesos_memoria_completa = sorted(pesos_compatibles)
        self.listbox_pesos.delete(0, tk.END)
        for idx, p in enumerate(self.pesos_memoria_completa):
            self.listbox_pesos.insert(tk.END, p)
            if p in sel_pesos: self.listbox_pesos.selection_set(idx)

        # 2. Actualizar memoria y Listbox de Estilos (Solo crece, no se borra si quitas selección)
        self.estilos_memoria_completa = sorted(estilos_existentes)
        # Solo rellenar si está vacío o difiere, para no borrar la selección actual del usuario
        actuales = [self.listbox_estilos.get(i) for i in range(self.listbox_estilos.size())]
        if set(actuales) != estilos_existentes:
            self.listbox_estilos.delete(0, tk.END)
            for e in self.estilos_memoria_completa:
                self.listbox_estilos.insert(tk.END, e)
                # Restaurar selección
                if e in sel_estilos: 
                    self.listbox_estilos.selection_set(self.listbox_estilos.size() - 1)

    def limpiar_buscador(self, entry, listbox, lista_completa):
        """Borra el texto del buscador y restaura la lista visual original."""
        entry.delete(0, tk.END)
        self.filtrar_listbox(listbox, entry, lista_completa)
        # Retorna el foco a la tabla para evitar que el cursor se quede en el buscador
        self.tabla.focus_set()

    def abrir_ventana_nuevo(self):
        # Saber si soy un invitado
        es_master = getattr(self.controller, 'es_master', True)
        soy_guest = getattr(self, "torneo_debug_id", None) and not es_master
        
        VentanaNuevoRegistro(self, es_master=not soy_guest)
