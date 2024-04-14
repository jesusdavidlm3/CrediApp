{% set filter_fields = ["cl.cedula", "cl.nombre", "cl_compra.cedula", "cl_compra.nombre"] %}

select p.id, p.monto, p.fecha, p.compra,
       coalesce(cl.cedula, cl_compra.cedula),
       coalesce(cl.nombre, cl_compra.nombre)
from pagos as p
left join usuarios as cl on p.cliente = cl.cedula
left join compras as c on p.compra = c.id
left join usuarios as cl_compra on cl_compra.cedula = c.cliente
where true
{% if key %}
	and p.id = :key
{% endif %}
{% include 'db/filter.sql' %}
