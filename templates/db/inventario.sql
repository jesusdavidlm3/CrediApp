{% set filter_fields = ["nombre", "id_de_proveedor"] %}
select id, nombre, precio, cantidad_disponible, id_de_proveedor, imagen
from productos
where anulado = 0
{% if key %}
	and id = :key
{% endif %}
{% include 'db/filter.sql' %}
