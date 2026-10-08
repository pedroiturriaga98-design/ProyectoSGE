# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


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
    alumno_rut_alumno = models.ForeignKey(Alumno, models.DO_NOTHING, db_column='ALUMNO_rut_alumno')  # Field name made lowercase.
    asignatura_curso_id_asig_curso = models.ForeignKey(AsignaturaCurso, models.DO_NOTHING, db_column='ASIGNATURA_CURSO_id_asig_curso')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'calificacion'


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


class SolicitudInsumo(models.Model):
    id_solicitud = models.IntegerField(primary_key=True)
    fecha = models.DateField()
    estado_solicitud = models.CharField(max_length=20)
    usuario_rut = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='USUARIO_rut')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'solicitud_insumo'


class TicketSoporte(models.Model):
    id_ticket = models.IntegerField(primary_key=True)
    fecha_reporte = models.DateField()
    prioridad = models.CharField(max_length=20)
    usuario_rut = models.ForeignKey('Usuario', models.DO_NOTHING, db_column='USUARIO_rut')  # Field name made lowercase.
    equipo_ti_codigo_inventario = models.ForeignKey(EquipoTi, models.DO_NOTHING, db_column='EQUIPO_TI_codigo_inventario')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'ticket_soporte'


class Usuario(models.Model):
    rut = models.CharField(primary_key=True, max_length=12)
    password_hash = models.CharField(max_length=255)
    rol_id_rol = models.ForeignKey(Rol, models.DO_NOTHING, db_column='ROL_id_rol')  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'usuario'
