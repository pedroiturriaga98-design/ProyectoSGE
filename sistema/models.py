# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
import unicodedata
from django.db import models


def normalizar_texto(texto: str) -> str:
    """Quita tildes, eñes y caracteres especiales, dejando solo caracteres a-z."""
    if not texto:
        return ""
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
    return "".join(c for c in texto.lower() if c.isalnum())


class Alumno(models.Model):
    rut_alumno = models.CharField(primary_key=True, max_length=12)
    nombre_completo = models.CharField(max_length=100)
    estado_matricula = models.CharField(max_length=20)
    curso_id_curso = models.ForeignKey('Curso', models.DO_NOTHING, db_column='CURSO_id_curso') # Field name made lowercase.
    
    # Aquí está el nuevo puente hacia el apoderado
    usuario_rut = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='USUARIO_rut', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'alumno'


class Asignatura(models.Model):
    id_asignatura = models.IntegerField(primary_key=True)
    nombre_asignatura = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'asignatura'


class AsignaturaCurso(models.Model):
    id_asig_curso = models.IntegerField(primary_key=True)
    curso_id_curso = models.ForeignKey('Curso', models.DO_NOTHING, db_column='CURSO_id_curso')  # Field name made lowercase.
    asignatura_id_asignatura = models.ForeignKey(Asignatura, models.DO_NOTHING, db_column='ASIGNATURA_id_asignatura')  # Field name made lowercase.
    usuario_rut = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='USUARIO_rut')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'asignatura_curso'


class Evaluacion(models.Model):
    id_evaluacion = models.AutoField(primary_key=True)

    asignatura_curso_id_asig_curso = models.ForeignKey(
        'AsignaturaCurso',
        models.DO_NOTHING,
        db_column='ASIGNATURA_CURSO_id_asig_curso'
    )

    numero_evaluacion = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'evaluacion'
        unique_together = (
            ('asignatura_curso_id_asig_curso', 'numero_evaluacion'),
        )

    def __str__(self):
        return f"Nota {self.numero_evaluacion}"


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.IntegerField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.IntegerField()
    is_active = models.IntegerField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'


class AuthUserGroups(models.Model):
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user', 'group'),)


class AuthUserUserPermissions(models.Model):
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user', 'permission'),)



class Calificacion(models.Model):
    id_calificacion = models.IntegerField(primary_key=True)

    valor_nota = models.FloatField()

    fecha_ingreso = models.DateField()

    alumno_rut_alumno = models.ForeignKey(
        Alumno,
        models.DO_NOTHING,
        db_column='ALUMNO_rut_alumno'
    )

    asignatura_curso_id_asig_curso = models.ForeignKey(
        AsignaturaCurso,
        models.DO_NOTHING,
        db_column='ASIGNATURA_CURSO_id_asig_curso'
    )

    evaluacion_id_evaluacion = models.ForeignKey(
        Evaluacion,
        models.DO_NOTHING,
        db_column='EVALUACION_id_evaluacion',
        blank=True,
        null=True
    )

    class Meta:
        managed = False
        db_table = 'calificacion'

    def __str__(self):
        return (
            f"{self.alumno_rut_alumno_id} - "
            f"Nota: {self.valor_nota}"
        )


class Curso(models.Model):
    id_curso = models.IntegerField(primary_key=True)
    nombre_curso = models.CharField(max_length=50)
    usuario_rut = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='USUARIO_rut')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'curso'


class DetalleInsumo(models.Model):
    id_detalle = models.IntegerField(primary_key=True)
    cant_insumo = models.IntegerField()
    insumo_id_insumo = models.ForeignKey('Insumo', models.DO_NOTHING, db_column='INSUMO_id_insumo')  # Field name made lowercase.
    solicitud_insumo_id_solicitud = models.ForeignKey('SolicitudInsumo', models.DO_NOTHING, db_column='SOLICITUD_INSUMO_id_solicitud')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'detalle_insumo'


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.PositiveSmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class DjangoMigrations(models.Model):
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'


class EquipoTi(models.Model):
    codigo_inventario = models.CharField(primary_key=True, max_length=50)
    tipo_equipo = models.CharField(max_length=100, blank=True, null=True, db_column='tipo_equipo') # <--- Clave para que Django lo lea y guarde
    estado = models.CharField(max_length=20)
    ubicacion = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'equipo_ti'


class Insumo(models.Model):
    id_insumo = models.IntegerField(primary_key=True)
    nombre_item = models.CharField(max_length=100)
    stock_actual = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'insumo'


class RegistroAsistencia(models.Model):
    id_asistencia = models.IntegerField(primary_key=True)
    fecha = models.DateField()
    presente = models.IntegerField()
    alumno_rut_alumno = models.ForeignKey(Alumno, models.DO_NOTHING, db_column='ALUMNO_rut_alumno')  # Field name made lowercase.
    asignatura_curso_id_asig_curso = models.ForeignKey(AsignaturaCurso, models.DO_NOTHING, db_column='ASIGNATURA_CURSO_id_asig_curso')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'registro_asistencia'


class Rol(models.Model):
    id_rol = models.IntegerField(primary_key=True)
    nombre_rol = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = 'rol'




class TicketSoporte(models.Model):
    id_ticket = models.IntegerField(primary_key=True)
    fecha_reporte = models.DateField()
    prioridad = models.CharField(max_length=20)
    observacion = models.TextField(blank=True, null=True)

    estado_ticket = models.CharField(
        max_length=50,
        default='Pendiente'
    )

    usuario_rut = models.ForeignKey(
        'Usuario',
        models.DO_NOTHING,
        db_column='USUARIO_rut'
    )

    equipo_ti_codigo_inventario = models.ForeignKey(
        'EquipoTi',
        models.DO_NOTHING,
        db_column='EQUIPO_TI_codigo_inventario'
    )

    descripcion = models.TextField(blank=True, null=True)
    tipo_incidencia = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    class Meta:
        managed = False
        db_table = 'ticket_soporte'

    
class Usuario(models.Model):
    cambiar_password = models.BooleanField(default=True)
    rut = models.CharField(primary_key=True, max_length=12)
    password_hash = models.CharField(max_length=255)
    rol_id_rol = models.ForeignKey('Rol', models.DO_NOTHING, db_column='rol_id_rol')
    
    nombre = models.CharField(max_length=100, blank=True, null=True)
    apellido_paterno = models.CharField(max_length=100, blank=True, null=True)
    apellido_materno = models.CharField(max_length=100, blank=True, null=True)
    correo = models.CharField(max_length=150, blank=True, null=True)
    correo_recuperacion = models.CharField(max_length=150, blank=True, null=True) # 📌 El Gmail personal de rescate
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    activo = models.IntegerField(default=1)

    def generar_correo_institucional(self) -> str:
        dominio = "santajuliana.cl"
        nom = normalizar_texto(self.nombre)
        ape_pat = normalizar_texto(self.apellido_paterno)
        ape_mat = normalizar_texto(self.apellido_materno)
        if not nom or not ape_pat:
            return self.correo or ""
        inicial_nom = nom[0]
        sugerencia = f"{inicial_nom}{ape_pat}@{dominio}"
        if not Usuario.objects.filter(correo=sugerencia).exclude(rut=self.rut).exists():
            return sugerencia
        if ape_mat:
            sugerencia_mat = f"{inicial_nom}{ape_pat}{ape_mat[0]}@{dominio}"
            if not Usuario.objects.filter(correo=sugerencia_mat).exclude(rut=self.rut).exists():
                return sugerencia_mat
        contador = 2
        base = f"{inicial_nom}{ape_pat}{ape_mat[0] if ape_mat else ''}"
        while Usuario.objects.filter(correo=f"{base}{contador}@{dominio}").exclude(rut=self.rut).exists():
            contador += 1
        return f"{base}{contador}@{dominio}"

    def save(self, *args, **kwargs):
        if self.rut:
            limpio = str(self.rut).replace(".", "").replace("-", "").strip().upper()
            if len(limpio) >= 2:
                cuerpo = limpio[:-1]
                dv = limpio[-1]
                try:
                    cuerpo_con_puntos = f"{int(cuerpo):,}".replace(",", ".")
                    self.rut = f"{cuerpo_con_puntos}-{dv}"
                except ValueError:
                    self.rut = f"{cuerpo}-{dv}"
        if self.nombre:
            self.nombre = self.nombre.strip().title()
        if self.apellido_paterno:
            self.apellido_paterno = self.apellido_paterno.strip().title()
        if self.apellido_materno:
            self.apellido_materno = self.apellido_materno.strip().title()
        if not self.correo:
            self.correo = self.generar_correo_institucional()
        else:
            self.correo = self.correo.strip().lower()
        if self.correo_recuperacion:
            self.correo_recuperacion = self.correo_recuperacion.strip().lower()
        super().save(*args, **kwargs)

    class Meta:
        managed = False
        db_table = 'usuario'

class SolicitudInsumo(models.Model):
    id_solicitud = models.IntegerField(primary_key=True)
    fecha = models.DateField()
    estado_solicitud = models.CharField(max_length=20)
    # Cambia max_length a 20 (o si es ForeignKey, asegúrate que no restrinja)
    usuario_rut = models.ForeignKey(Usuario, models.DO_NOTHING, db_column='USUARIO_rut')
    descripcion = models.TextField(blank=True, null=True)
    tipo_solicitud = models.CharField(max_length=50, blank=True, null=True)
    observaciones = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'solicitud_insumo'

class EventoCalendario(models.Model):
    id_evento = models.AutoField(primary_key=True)

    titulo = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)

    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()

    tipo_evento = models.CharField(max_length=30)
    alcance = models.CharField(max_length=20)

    id_asig_curso = models.ForeignKey(
        'AsignaturaCurso',
        models.DO_NOTHING,
        db_column='id_asig_curso',
        blank=True,
        null=True
    )

    id_curso = models.ForeignKey(
        'Curso',
        models.DO_NOTHING,
        db_column='id_curso',
        blank=True,
        null=True
    )

    usuario_rut = models.ForeignKey(
        'Usuario',
        models.DO_NOTHING,
        db_column='usuario_rut'
    )

    lugar = models.CharField(
        max_length=150,
        blank=True,
        null=True
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'evento_calendario'

    def __str__(self):
        return self.titulo