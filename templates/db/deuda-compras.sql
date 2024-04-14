select c.id, productos.monto - coalesce(sum(p.monto), 0) as deuda 
from compras as c
left join pagos as p on p.compra = c.id
join (
	select compra, sum(monto) as monto 
	from compra_productos
	group by compra
) as productos on productos.compra = c.id
where c.cliente = :cliente
group by c.id
having deuda > 0
