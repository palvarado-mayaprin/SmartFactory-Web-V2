import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import mysql.connector
import pyodbc


class dtbSmartFactory:
    def __init__(self, query):
        self.query = query

    def consultaSmartFactory(self):
        
        
        config = {
            'user': 'smartfactory',
            'password': 'Mayaguatemala',
            'host': '192.168.1.48',
            'port': 3306,
            'database': 'smartfactory'
        }

        
        conn = None
        cursor = None
        
        try:
            conn = mysql.connector.connect(**config)
            cursor = conn.cursor()
            cursor.execute(self.query)

            
            if self.query.strip().lower().startswith(("insert", "update", "delete")):
                conn.commit()
                print("Consulta ejecutada con éxito")
                return "Operación exitosa"

            return cursor.fetchall()

        except mysql.connector.Error as err:
            print(f"Error al ejecutar consulta: {self.query}")
            print(f"Error: {err}")
            return None

        finally:
            if cursor is not None:
                cursor.close()
            if conn is not None:
                conn.close()


class dtbOptimus:
    def __init__(self, query):
        self.query = query

    def consultaOptimus(self):
        config = {
            'user': 'reports',
            'password': 'cognos',
            'host': '10.0.1.2',
            'database': 'mayaprin',
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_general_ci'
        }

        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        cursor.execute(self.query)
        resultados = cursor.fetchall()
        cursor.close()
        conn.close()
        return resultados


class dtbOptimus1:
    def __init__(self, query, params=None):
        self.query = query
        self.params = params

    def consultaOptimus(self):
        config = {
            'user': 'reports',
            'password': 'cognos',
            'host': '10.0.1.2',
            'database': 'mayaprin',
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_general_ci'
        }

        conn = None
        cursor = None
        try:
            conn = mysql.connector.connect(**config)
            conn.set_charset_collation('utf8mb4', 'utf8mb4_general_ci')
            cursor = conn.cursor()

            cursor.execute(self.query, self.params) if self.params else cursor.execute(self.query)
            resultados = cursor.fetchall()

        except mysql.connector.Error as err:
            print(f"Error en la consulta: {err}")
            resultados = None

        finally:
            if cursor: cursor.close()
            if conn: conn.close()

        return resultados


class dtbEntregasDiarias:
    def __init__(self, query):
        self.query = query

    def consultaEntregasDiarias(self):
        server = '10.0.1.2'
        database = 'entregasDiarias'
        username = 'BI'
        password = 'VWg59b5<F7:e'

        connection_string = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'

        try:
            conn = pyodbc.connect(connection_string)
            cursor = conn.cursor()
            cursor.execute(self.query)
            resultado = cursor.fetchall()
        except pyodbc.Error as e:
            print(f"Error al conectar: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

        return resultado
    

    

