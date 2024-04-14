{% set filter_fields = ["cl.cedula", "cl.nombre", "cl.correo"] %}

select 
	cl.cedula, nombre, correo, telefono, direccion, limite_credito, imagen, 
	d.deuda - d.pagado as deuda,
	coalesce(pasada.pasadas, 0) as pasadas
from usuarios as cl
left join ({% include 'db/deuda.sql' %}) as d on d.cedula = cl.cedula
left join ({% include 'db/deuda-pasada.sql' %}) as pasada on pasada.cliente = cl.cedula
where tipo = 'Cliente' and anulado = 0
{% if key %}
	and cl.cedula = :key
{% endif %}
{% include 'db/filter.sql' %}
group by cl.cedula
