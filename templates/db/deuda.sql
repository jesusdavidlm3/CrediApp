select 
	cl.cedula, 
	coalesce(productos.monto, 0) as deuda,
	coalesce(pagado_cliente.monto, 0) + coalesce(p_compra.monto, 0) as pagado 
from usuarios as cl

left join (
	select c.cliente, coalesce(sum(monto), 0) as monto from compras as c
	left join pagos as p on p.compra = c.id
	group by c.cliente
) as p_compra on p_compra.cliente = cl.cedula

left join (
	select c.cliente, coalesce(sum(monto), 0) as monto from compras as c
	left join compra_productos as p on p.compra = c.id
	group by c.cliente
) as productos on productos.cliente = cl.cedula

left join (
	select cliente, coalesce(sum(monto), 0) as monto from pagos
	where cliente is not null
	group by cliente
) as pagado_cliente on pagado_cliente.cliente = cl.cedula

where cl.anulado != 1 and cl.tipo = 'Cliente'
group by cl.cedula
