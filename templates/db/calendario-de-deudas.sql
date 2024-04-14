select 
	c.cliente, c.id, c.fecha_compra, c.fecha_limite, 
	coalesce(p_compra.monto, 0) as pagado,
	coalesce(productos.monto, 0) as monto_total
from compras as c

left join (
	select compra, sum(monto) as monto from pagos
	group by compra
) as p_compra on p_compra.compra = c.id

left join (
	select compra, sum(monto) as monto from compra_productos
	group by compra
) as productos on productos.compra = c.id

where pagado != monto_total
{% if cliente %}
and c.cliente = :cliente
{% endif %}

group by c.id
order by c.fecha_limite, c.id
