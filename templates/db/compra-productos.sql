select p.id, p.nombre, cp.cantidad, cp.precio_producto, cp.monto, p.imagen
from compras as c
join compra_productos as cp on c.id = cp.compra
join productos as p on cp.producto = p.id
where c.id = :key
group by p.id
