import tkinter as tk
from tkinter import ttk

class ComboBuscador(ttk.Frame):
    def __init__(self, parent, values=None, state="normal", width=20, **kwargs):
        super().__init__(parent)
        self.lista_valores = list(values) if values else []
        
        # --- WIDGETS INTERNOS ---
        self.entry = ttk.Entry(self, width=width)
        self.entry.pack(side="left", fill="both", expand=True)
        
        self.btn = tk.Label(self, text="▼", bg="#e1e1e1", width=3, relief="groove", cursor="hand2")
        self.btn.pack(side="right", fill="y")
        
        self.panel = tk.Toplevel(self)
        self.panel.wm_overrideredirect(True)
        self.panel.withdraw()
        self.panel.attributes("-topmost", True)
        
        self.listbox = tk.Listbox(self.panel, font=self.entry.cget("font"), bg="#2d2d2d", 
                                  fg="white", selectbackground="#17a2b8", highlightthickness=1)
        self.listbox.pack(fill="both", expand=True)
        
        self.config(state=state)
        
        # --- EVENTOS ---
        self.entry.bind("<KeyRelease>", self.filtrar)
        self.entry.bind("<KeyPress>", self.manejar_teclas)
        self.btn.bind("<Button-1>", self.alternar)
        self.entry.bind("<FocusOut>", self.ocultar_panel)
        self.listbox.bind("<Double-Button-1>", self.seleccionar)
        self.listbox.bind("<Return>", self.seleccionar)
        self.listbox.bind("<FocusOut>", self.ocultar_panel)
        
        # NUEVO: Escuchar clics globales en la ventana principal
        # Usamos after_idle para asegurar que la interfaz ya esté cargada al hacer esto
        self.after_idle(self.vincular_clic_global)

        # --- NUEVO: Escudo para estado Disabled ---
        self.bind("<Button-1>", self._respetar_candado, add="+")
        self.bind("<ButtonPress-1>", self._respetar_candado, add="+")
        self.bind("<Key>", self._respetar_candado, add="+")

    def _respetar_candado(self, event):
        """Bloquea cualquier interacción física si el Combobox está deshabilitado."""
        if self.cget("state") == "disabled":
            return "break"

    # --- NUEVA LÓGICA DE CIERRE GLOBAL (CON SEGURO DE VIDA) ---
    def vincular_clic_global(self):
        try:
            # Validar que el widget siga existiendo antes de vincular
            if not self.winfo_exists(): return
            raiz = self.winfo_toplevel()
            raiz.bind("<Button-1>", self.clic_fuera, add="+")
        except Exception:
            pass
        
    def clic_fuera(self, event):
        try:
            # SEGURO 1: Si se destruyó por cambio de pantalla, abortar
            if not self.winfo_exists() or not self.panel.winfo_exists(): 
                return
                
            if self.panel.winfo_ismapped():
                if event.widget not in (self.entry, self.btn, self.listbox, self.panel):
                    self.panel.withdraw() 
                    self.validar_texto()  
        except Exception:
            # Ignorar cualquier error residual de Tkinter
            pass
                
    def validar_texto(self):
        txt = self.get()
        if txt and txt not in [str(x) for x in self.lista_valores]:
            self.set('')

    # --- SIMULACIÓN DE MÉTODOS NATIVOS ---
    def __setitem__(self, key, value):
        if key == 'values': self.lista_valores = list(value)
        else: self.entry[key] = value
            
    def __getitem__(self, key):
        if key == 'values': return self.lista_valores
        return self.entry[key]
        
    def get(self): return self.entry.get()
    
    def set(self, text):
        est = self.entry.cget("state")
        self.entry.config(state="normal")
        self.entry.delete(0, tk.END)
        self.entry.insert(0, text)
        self.entry.config(state=est)
        
    def current(self, index=None):
        if index is None:
            txt = self.get()
            return self.lista_valores.index(txt) if txt in self.lista_valores else -1
        self.set(self.lista_valores[index])
        
    def config(self, **kwargs):
        if 'state' in kwargs:
            st = kwargs['state']
            if st == "disabled":
                self.entry.config(state="disabled")
                self.btn.config(bg="#f0f0f0", fg="#a0a0a0")
                self.entry.unbind("<Button-1>") # <- DESENCHUFA EL CLIC
            elif st == "readonly":
                self.entry.config(state="readonly")
                self.btn.config(bg="#e1e1e1", fg="black")
                self.entry.bind("<Button-1>", lambda e: self.alternar(e))
            else:
                self.entry.config(state="normal")
                self.btn.config(bg="#e1e1e1", fg="black")
                self.entry.unbind("<Button-1>")
        if 'values' in kwargs:
            self.lista_valores = list(kwargs['values'])
            
    def configure(self, **kwargs): self.config(**kwargs)
            
    def cget(self, key):
        if key == "state": return str(self.entry.cget("state"))
        if key == "values": return self.lista_valores
        return super().cget(key)
        
    def bind(self, seq, func, add=None):
        if seq == "<<ComboboxSelected>>":
            self.entry.bind("<<ComboSeleccionado>>", func, add)
        else:
            self.entry.bind(seq, func, add)

    def focus_set(self):
        self.entry.focus_set()
            
    # --- LÓGICA DE BÚSQUEDA ---
    def filtrar(self, event):
        if str(self.entry.cget("state")) == "disabled": return "break"
        if event.keysym in ('Up', 'Down', 'Return', 'Escape', 'Tab'): return
        
        texto = self.get().lower()
        self.listbox.delete(0, tk.END)
        
        if texto == '':
            elementos = self.lista_valores
        else:
            elementos = [item for item in self.lista_valores if texto in str(item).lower()]

        for item in elementos: 
            self.listbox.insert(tk.END, item)
        
        self.mostrar_panel()
        
    def mostrar_panel(self):
        self.panel.deiconify()
        self.panel.lift()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        w = self.winfo_width()
        h = min(150, max(25, self.listbox.size() * 20))
        self.panel.geometry(f"{w}x{h}+{x}+{y}")
        
    def alternar(self, event):
        # Escudo impenetrable con conversión a string
        if str(self.entry.cget("state")) == "disabled": 
            return "break"
        
        try:
            if not self.winfo_exists() or not self.panel.winfo_exists(): return
            
            if self.panel.winfo_ismapped():
                self.panel.withdraw()
                self.validar_texto() 
            else:
                self.listbox.delete(0, tk.END)
                for item in self.lista_valores: 
                    self.listbox.insert(tk.END, item)
                
                self.mostrar_panel()
                self.entry.focus_set()
                
                txt_actual = self.get()
                if txt_actual in self.lista_valores:
                    idx = self.lista_valores.index(txt_actual)
                    self.listbox.selection_clear(0, tk.END)
                    self.listbox.selection_set(idx)
                    self.listbox.see(idx)
        except Exception:
            pass
            
    def seleccionar(self, event):
        if self.listbox.curselection():
            val = self.listbox.get(self.listbox.curselection())
            self.set(val)
            self.panel.withdraw()
            self.entry.event_generate("<<ComboSeleccionado>>")
            self.entry.focus_set()
            
    def manejar_teclas(self, event):
        if str(self.entry.cget("state")) == "disabled": return "break"
        
        if event.keysym == 'Down':
            if not self.panel.winfo_ismapped():
                self.alternar(event)
            elif self.listbox.size() > 0:
                self.listbox.focus_set()
                self.listbox.selection_set(0)
        elif event.keysym == 'Escape':
            self.panel.withdraw()
            self.validar_texto()
            
    def ocultar_panel(self, event):
        def revisar():
            try:
                # SEGURO 2: Validar existencia antes de ejecutar el retraso
                if not self.winfo_exists() or not self.panel.winfo_exists(): 
                    return
                    
                foco = self.focus_get()
                if foco != self.entry and foco != self.listbox:
                    self.panel.withdraw()
                    self.validar_texto()
            except Exception:
                pass
                
        self.after(100, revisar)

# --- COMPATIBILIDAD ---
def aplicar_autocompletado(combobox, lista_valores):
    combobox['values'] = lista_valores

def aplicar_formato_fecha(entry):
    """Aplica una máscara estricta de formato DD/MM/YYYY a un Entry de Tkinter."""
    
    def on_key_release(event):
        # Ignoramos teclas de navegación y comandos
        teclas_ignorar = ('Left', 'Right', 'Up', 'Down', 'Tab', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R')
        if event.keysym in teclas_ignorar:
            return

        texto_actual = entry.get()
        pos = entry.index(tk.INSERT)
        
        # Guardar cuántos números hay antes del cursor para no perder la posición
        numeros_antes = len("".join(filter(str.isdigit, texto_actual[:pos])))
        
        # Extraer solo números y limitar a 8 dígitos (DDMMYYYY)
        numeros = "".join(filter(str.isdigit, texto_actual))[:8]
        
        # Reconstruir la máscara
        resultado = ""
        for i, d in enumerate(numeros):
            if i in (2, 4):
                resultado += "/"
            resultado += d
        
        entry.delete(0, tk.END)
        entry.insert(0, resultado)
        
        # Recalcular la posición correcta del cursor
        nueva_pos = 0
        nums_vistos = 0
        for i, c in enumerate(resultado):
            if nums_vistos == numeros_antes:
                nueva_pos = i
                break
            if c.isdigit():
                nums_vistos += 1
        else:
            nueva_pos = len(resultado)
            
        # Si el cursor cae justo sobre la barra, saltarla
        if nueva_pos in (2, 5) and len(resultado) > nueva_pos:
            nueva_pos += 1
            
        entry.icursor(nueva_pos)

    def on_backspace(event):
        # Si hay texto seleccionado, dejamos que el borrado normal actúe
        if entry.select_present(): return
        
        pos = entry.index(tk.INSERT)
        # Si estamos borrando justo después de una barra, borramos el número anterior a ella
        if pos in (3, 6):
            entry.delete(pos - 2)

    def corregir_cursor(event=None):
        pos = entry.index(tk.INSERT)
        # Evita que al hacer clic o usar flechas te quedes atascado antes de la barra
        if pos in (2, 5) and len(entry.get()) > pos:
            entry.icursor(pos + 1)

    # Asignar todos los eventos al Entry
    entry.bind('<KeyRelease>', on_key_release)
    entry.bind('<BackSpace>', on_backspace)
    entry.bind('<ButtonRelease-1>', corregir_cursor)
    entry.bind('<Key-Left>', lambda e: entry.after(1, corregir_cursor))
    entry.bind('<Key-Right>', lambda e: entry.after(1, corregir_cursor))

def aplicar_formato_cedula(entry):
    """Aplica formato XXX-XXXXXX-XXXXL y auto-calcula la letra final (Nicaragua)."""
    
    # Algoritmo Módulo 23 oficial de Nicaragua
    LETRAS = "ABCDEFGHJKLMNPQRSTUVWXY"
    
    def on_key_release(event):
        teclas_ignorar = ('Left', 'Right', 'Up', 'Down', 'Tab', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R')
        if event.keysym in teclas_ignorar:
            return

        texto_actual = entry.get()
        pos = entry.index(tk.INSERT)
        
        # Contar cuántos números hay antes del cursor
        numeros_antes = len("".join(filter(str.isdigit, texto_actual[:pos])))
        
        # Extraer solo los números y limitar a un máximo de 13 dígitos
        numeros = "".join(filter(str.isdigit, texto_actual))[:13]
        
        resultado = ""
        for i, d in enumerate(numeros):
            if i in (3, 9):
                resultado += "-"
            resultado += d
            
        # AUTO-CALCULAR LA LETRA FINAL
        if len(numeros) == 13:
            num_calc = int(numeros)
            letra = LETRAS[num_calc % 23]
            resultado += letra
            
        entry.delete(0, tk.END)
        entry.insert(0, resultado)
        
        # Restaurar la posición del cursor de forma fluida
        nueva_pos = 0
        nums_vistos = 0
        for i, c in enumerate(resultado):
            if nums_vistos == numeros_antes:
                nueva_pos = i
                break
            if c.isdigit():
                nums_vistos += 1
        else:
            nueva_pos = len(resultado)
            
        # Evitar que el cursor se quede atascado antes del guion o antes de la letra final
        if nueva_pos in (3, 10) and len(resultado) > nueva_pos:
            nueva_pos += 1
        # Si acabamos de poner la letra, colocar el cursor al final de todo
        elif len(numeros) == 13 and nueva_pos == 15:
            nueva_pos = 16
            
        entry.icursor(nueva_pos)

    def on_backspace(event):
        if entry.select_present(): return
        
        pos = entry.index(tk.INSERT)
        # Si estamos al final (después de la letra), borramos el último NÚMERO
        if pos == 16:
            entry.delete(14)
        # Si borramos justo después de un guion, borramos el número anterior a él
        elif pos in (4, 11):
            entry.delete(pos - 2)

    def corregir_cursor(event=None):
        pos = entry.index(tk.INSERT)
        if pos in (3, 10) and len(entry.get()) > pos:
            entry.icursor(pos + 1)
        # No permitir hacer clic entre el último número y la letra auto-generada
        elif len(entry.get()) == 16 and pos == 15:
            entry.icursor(16)

    entry.bind('<KeyRelease>', on_key_release)
    entry.bind('<BackSpace>', on_backspace)
    entry.bind('<ButtonRelease-1>', corregir_cursor)
    entry.bind('<Key-Left>', lambda e: entry.after(1, corregir_cursor))
    entry.bind('<Key-Right>', lambda e: entry.after(1, corregir_cursor))

def aplicar_deseleccion_tabla(arbol):
    """Otorga a una tabla el poder de deseleccionar con clics en blanco, toggles o clics fuera de ella."""
    
    def al_clic_izquierdo(event):
        item_clickeado = arbol.identify_row(event.y)
        
        # Escenario 1: Clic en espacio blanco dentro de la tabla
        if not item_clickeado:
            arbol.selection_remove(arbol.selection())
            arbol.event_generate("<<TreeviewSelect>>")
            return "break"
            
        # Escenario 2: Clic sobre un elemento ya seleccionado (Deselección tipo Ctrl+Clic)
        if item_clickeado in arbol.selection():
            arbol.selection_remove(item_clickeado)
            arbol.event_generate("<<TreeviewSelect>>")
            return "break" # Detiene el clic para que Tkinter no lo vuelva a marcar

    def clic_afuera(event):
        try:
            clase = event.widget.winfo_class()
            # Escenario 3: Clic fuera de la tabla. Ignoramos botones de acción y barras de scroll.
            if event.widget != arbol and clase not in ('Treeview', 'Scrollbar', 'TScrollbar', 'Button', 'TButton'):
                if arbol.selection():
                    arbol.selection_remove(arbol.selection())
                    arbol.event_generate("<<TreeviewSelect>>")
        except Exception:
            pass

    # Enlazar eventos
    arbol.bind("<Button-1>", al_clic_izquierdo, add="+")
    # Enlazar el detector global a la ventana principal de esta tabla
    arbol.winfo_toplevel().bind("<Button-1>", clic_afuera, add="+")
