{% set filter_fields = ["cedula", "nombre", "correo"] %}

select cedula, nombre, correo, imagen
from usuarios
where tipo = 'Empleado'
{% if key %}
	and cedula = :key
{% endif %}
{% include 'db/filter.sql' %}
