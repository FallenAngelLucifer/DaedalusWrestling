import psycopg2
from psycopg2.extras import RealDictCursor

from database.queries_atletas import QueriesAtletasMixin
from database.queries_torneo import QueriesTorneoMixin
from database.queries_pareo import QueriesPareoMixin
from database.queries_red import QueriesRedMixin

class ConexionDB(QueriesAtletasMixin, QueriesTorneoMixin, QueriesPareoMixin, QueriesRedMixin):
    def __init__(self):
        self.host = "localhost"
        self.database = "DaedalusWrestling"
        self.user = "postgres"
        self.password = "sk8erace1mortadela1@"
        self.port = "5432"

    def conectar(self):
        try:
            conexion = psycopg2.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password,
                port=self.port,
                options="-c search_path=lucha_olimpica" 
            )
            return conexion
        except psycopg2.Error as e:
            print(f"Error conectando a PostgreSQL: {e}")
            return None

    def _ejecutar_select(self, query, params=None):
        """Función base para obtener datos como diccionario."""
        conexion = self.conectar()
        if not conexion: return []
        try:
            with conexion.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
        except psycopg2.Error as e:
            print(f"Error ejecutando consulta: {e}")
            return []
        finally:
            conexion.close()

    def _ejecutar_insert(self, query, params):
        """Función genérica para ejecutar INSERTS/UPDATES/DELETES y hacer commit."""
        conexion = self.conectar()
        if not conexion: return False
        try:
            with conexion.cursor() as cursor:
                cursor.execute(query, params)
                conexion.commit()
                return True
        except psycopg2.Error as e:
            print(f"Error en modificación de BD: {e}")
            conexion.rollback()
            return False
        finally:
            conexion.close()