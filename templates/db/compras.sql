{% set filter_fields = ["u.cedula", "u.nombre"] %}

select c.id, u.cedula, u.nombre, c.fecha_compra, c.fecha_limite, productos.cantidad, productos.monto as monto_total, sum(p.monto) as pagado
from compras as c
join usuarios as u on u.cedula = c.cliente
join (
	select compra, sum(cantidad) as cantidad, sum(monto) as monto from compra_productos
	where true
	{% if key %}
		and compra = :key
	{% endif %}
	group by compra
) as productos on productos.compra = c.id
left join pagos as p on p.compra = c.id
where true
{% if key %}
	and c.id = :key
{% endif %}
{% if cliente %}
	and u.cedula = :cliente
{% endif %}
{% include 'db/filter.sql' %}
group by c.id
order by c.fecha_compra desc
