create table usuarios(
	cedula integer primary key check (cedula > 0),
	nombre text not null,
	correo text not null,
	hash_pass text not null,
	tipo text check(tipo in ('Empleado', 'Cliente')) default 'Cliente',
	imagen text,
	telefono text default '',
	direccion text default '',
	anulado boolean not null check (anulado in (0, 1)) default 0,
	limite_credito double default 0 check(limite_credito >= 0)
);

create table recuperaciones(
	uuid text,
	cedula integer
);

create table productos(
	id integer primary key,
	cantidad_disponible integer not null check (cantidad_disponible >= 0),
	precio double not null check (precio > 0),
	nombre text not null,
	imagen text,
	anulado boolean not null check (anulado in (0, 1)) default 0,
	id_de_proveedor text -- ID asignada por el proveedor a este producto
);

create table compras(
	id integer primary key,
	fecha_compra date not null,
	fecha_limite date not null check (fecha_limite >= fecha_compra),
	
	cliente integer not null,
	
	foreign key (cliente) references clientes(cedula)
);

create table compra_productos(
	id integer primary key,
	cantidad integer not null check (cantidad > 0),
	precio_producto double not null check (precio_producto > 0),
	-- Monto total es calculado automaticamente por la base de datos cada vez que se consigue
	monto integer generated always as (cantidad * precio_producto) virtual,
	
	producto integer not null,
	compra integer not null,
	
	foreign key (producto) references productos(id),
	foreign key (compra) references compras(id)
);

create table pagos(
	id integer primary key,
	monto integer not null check (monto > 0),
	fecha date default (date('now')),
	
	-- Si se paga por adelantado, compra es null y cliente tiene un valor
	-- En el caso de ser un pago a una compra cliente es null ya que es parte de la compra
	compra integer check (not (null not in (compra, cliente)) and null in (compra, cliente)),
	cliente integer check (not (null not in (compra, cliente)) and null in (compra, cliente)),
	
	foreign key (compra) references compras(id),
	foreign key (cliente) references usuarios(cedula)
);

insert into usuarios(cedula, nombre, hash_pass, tipo) values(1, 'Empleado', '356a192b7913b04c54574d18c28d46e6395428ab', 'Empleado'); 
insert into usuarios(cedula, nombre, hash_pass, tipo, limite_credito) values(2, 'Cliente', '356a192b7913b04c54574d18c28d46e6395428ab', 'Cliente', 100);
