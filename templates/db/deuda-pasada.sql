select cliente, count(*) as pasadas from ({% include 'db/calendario-de-deudas.sql' %})
where fecha_limite < date('now') and pagado < monto_total
group by cliente
