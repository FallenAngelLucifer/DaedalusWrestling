import tkinter as tk
from tkinter import ttk

from database.conexion_db import ConexionDB
# Importación de los nuevos módulos lógicos
from ui.pantallas.pareo.logica_red_pareo import LogicaRedPareoMixin
from ui.pantallas.pareo.logica_llaves import LogicaLlavesMixin
from ui.pantallas.pareo.logica_cartelera import LogicaCarteleraMixin
from ui.pantallas.pareo.logica_exportacion import LogicaExportacionMixin

class PantallaPareo(ttk.Frame, LogicaRedPareoMixin, LogicaLlavesMixin, LogicaCarteleraMixin, LogicaExportacionMixin):
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

        self.crear_interfaz_global()

    def crear_interfaz_global(self):
        """Construye los contenedores principales y los encabezados de la pantalla de Pareo."""
        # --- Frame de encabezado para navegación y título ---
        header_frame = ttk.Frame(self)
        header_frame.pack(fill="x", pady=(10, 5))

        self.btn_regresar = ttk.Button(header_frame, text="⬅ Regresar a Inscripción", command=self.regresar_a_inscripcion)
        self.btn_regresar.pack(side="left", padx=20)

        lbl_titulo = ttk.Label(header_frame, text="Fase 2: Desarrollo de Pareo (Brackets)", font=("Helvetica", 16, "bold"))
        lbl_titulo.pack(side="left", padx=(0, 20))

        # Etiqueta de mi Tapiz Actual
        self.lbl_mi_tapiz_header = ttk.Label(header_frame, text="📍 Tapiz Asignado: Pendiente", font=("Helvetica", 12, "bold"), foreground="#007bff")
        self.lbl_mi_tapiz_header.pack(side="left", expand=True, anchor="w")
        
        self.btn_gestion_red = tk.Button(header_frame, text="👥 Gestionar Red", font=("Helvetica", 9, "bold"), bg="#17a2b8", fg="white", cursor="hand2", command=self.abrir_panel_red)

        # --- Frame exclusivo para exportaciones masivas ---
        self.export_frame = ttk.Frame(self)
        self.export_frame.pack(fill="x", padx=20, pady=(0, 0)) 

        self.lbl_estado_torneo = ttk.Label(self.export_frame, text="", font=("Helvetica", 10, "bold"))
        self.lbl_estado_torneo.pack(side="right", padx=10, anchor="s")

        self.btn_exportar_todas_img = tk.Button(self.export_frame, text="🖼 Exportar Todas (IMG)", bg="#17a2b8", fg="white", command=self.exportar_todas_las_imagenes)
        self.btn_exportar_fichas_pdf = tk.Button(self.export_frame, text="📄 Exportar Fichas (PDF)", bg="#d9534f", fg="white", command=self.exportar_todas_las_fichas_pdf)

        self.after(100, self.gestionar_botones_globales)

        # Contenedor dinámico central
        self.contenedor_principal = ttk.Frame(self)
        self.contenedor_principal.pack(fill="both", expand=True)

    def regresar_a_inscripcion(self):
        """Regresa a la pantalla de inscripción manteniendo la conexión de red activa."""
        self.cerrar_panel_combate()
            
        from ui.pantallas.inscripcion.pantalla_inscripcion import PantallaInscripcion
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
