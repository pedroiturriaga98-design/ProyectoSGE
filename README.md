# Sistema de Gestión Escolar (SGE) - Santa Juliana

Plataforma web desarrollada en **Django**, **Bootstrap 5** y **MySQL** para la administración académica, control de asistencia, gestión de incidencias e inventario de insumos.

## Requisitos
* Python 3.11+
* Servidor MySQL activo ( Workbench )

## Instalación y Despliegue

1. **Clonar el repositorio:**

   git clone https://github.com/pedroiturriaga98-design/ProyectoSGE
   cd ProyectoSGE

2. **Crear y activar entorno virtual (Windows)**:
     python -m venv venv
    .\venv\Scripts\activate
3. **Instalar dependencias:*
    pip install -r requirements.txt
4. **Configurar Base de Datos:**
   * Crea una base de datos vacía en MySQL llamada `mydb`.
   * Verifica `USER` y `PASSWORD` en `sge_core/settings.py` según tu configuración local.
5. **Migraciones y carga de datos**
    python manage.py migrate
   .\sistema\importar_bd.bat (si no se cargan datos)
6. ** Ejecutar Servidor**
    python manage.py runserver
7.  **Datos de prueba**
    Admin        :  fgonzalez@santajuliana.cl
    Profesor     :  jcontreras@santajuliana.cl
    Apoderado    :  acontreras@santajuliana.cl
    TI           :  ppaleta@santajuliana.cl
    Aseo         :  rgomez@santajuliana.cl

**CONTRASEÑA**   :  A123456789.


