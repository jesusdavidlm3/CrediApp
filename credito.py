#!.venv/bin/python
from flask import (
    Flask,
    request,
    g,
    url_for,
    redirect,
    Response,
    session,
    render_template,
    abort,
    flash,
    get_flashed_messages,
)
from jinja2 import Environment, FileSystemLoader
import datetime

from functools import wraps, reduce
from hashlib import sha1
import sqlite3
import re
from urllib.parse import quote as urlencode
import os

import uuid
from pprint import pprint

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from html.parser import HTMLParser

app = Flask(__name__)
app.config.from_pyfile("config.py")

FLASH_ERROR = "error"
FLASH_INFO = "info"

REQUIRE_POSITIVE_NUMBER = "pattern='[1-9][0-9]*' required title='Ingrese un numero positivo.'"
REQUIRE_DECIMAL_NUMBER = "pattern='[1-9][0-9]*(.[0-9]+)?|0.[0-9]+' required title='Ingrese un número decimal postivo'"
SPANISH_LETTER = "[a-zA-ZÀ-ÿ\\u00f1\\u00d1]"
NAME_PATTERN = f"pattern='[A-Z]{SPANISH_LETTER}*(\s+[A-Z]{SPANISH_LETTER}*)*' title='Nombre debe estar apropiadamente capitalizado (por ejemplo: Nombre Apellido) y no contener números'"
PHONE_PATTERN = """
    pattern='((\\+58\\s+|0)?[0-9]{3}-?[0-9]{7})?'
    title='El número de teléfono puede empezar opcionalmente con +58 y espacio o 0, seguido de 3 números (por ejemplo 424), opcionalmente un guión (-) y los últimos 7 números'
"""

def exportar(title, header, table):
    style = ""
    with open("static/style.css") as f:
        style = f.read()
    content = render_template("export.html", title=title, header=header, table=table, style=style)
    return Response(
        content,
        mimetype="text/html",
        headers={"Content-Disposition": f"attachment;filename={title}.html"},
    )

class HTMLText(HTMLParser):
    text = ""
    in_body = False

    def __init__(self, html):
        HTMLParser.__init__(self)
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "body":
            self.in_body = True

    def handle_endtag(self, tag):
        if tag.lower() == "body":
            self.in_body = False

    def handle_data(self, data):
        if self.in_body:
            self.text += data
    
def send_mail(to, subject, html):
    msg = MIMEMultipart("alternative")

    msg["Subject"] = subject
    msg["From"] = app.config["EMAIL"]
    msg["To"] = to

    msg.attach(MIMEText(HTMLText(html).text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        smtp = smtplib.SMTP(app.config["EMAIL_SERVER"], 587)
    except Exception as e:
        smtp = smtplib.SMTP_SSL(app.config["EMAIL_SERVER"], 465)
        print(e)

    smtp.ehlo()
    smtp.starttls()
    smtp.login(app.config["EMAIL"], app.config["EMAIL_PASSWORD"])
    smtp.send_message(msg)
    smtp.quit()

# Antes de cada request abrimos la base de datos
@app.before_request
def open_db():
    g.db = sqlite3.connect("db/credito.db")

# Y despues de cada request la cerramos
@app.after_request
def close_db(response):
    g.db.commit()
    g.db.close()
    return response


def has_errored():
    return (
        len(
            list(
                filter(
                    lambda x: x[0] == FLASH_ERROR,
                    get_flashed_messages(with_categories=True),
                )
            )
        )
        > 0
    )


# Añade los parametros a una url, y si ya existe lo cambia
@app.template_filter("url_add")
def filter_url_add(args):
    url = args[0]
    for key in args[1]:
        value = urlencode(str(args[1][key]).encode("utf-8"))
        if url.find("?") == -1:
            url += f"?{key}={value}"
            continue
        pos = url.find(f"{key}=")
        if pos != -1:
            end = url.find("&", pos)
            if end == -1:
                end = len(url)
            url = url[:pos] + f"{key}={value}" + url[end:]
            continue
        url += f"&{key}={value}"
    return url


@app.template_filter("type")
def filter_type(field):
    return field["type"] if "type" in field else "text"


@app.template_filter("name")
def filter_type(field):
    return field["name"] if "name" in field else field["label"].lower()


@app.template_filter("show")
def filter_show_fields(args):
    fields = args[0]
    show = args[1]
    return filter(lambda x: "show" in x and x["show"] == show, fields)

@app.template_filter("limit_decimal")
def filter_limit_decimal(x):
    if type(x) != float:
        return x
    return f"{x:.2f}"

@app.template_filter("index")
def filter_field_index(args):
    fields = args[0]
    field = args[1]
    return field["index"] if "index" in field else fields.index(field)


@app.template_filter("format")
def filter_format_fields(args):
    values = args[0]
    field = args[1]
    fields = args[2]
    index = filter_field_index([fields, field])
    value = values[index]
    return field["format"](value) if "format" in field else value

# Devuelve el nombre de un campo para formulario html
@app.template_filter("external_url")
def filter_external_url(url):
    return f'{app.config["PROTOCOL"]}://{app.config["HOST"]}:{str(app.config["PORT"])}{url}'

def string_insert(string, idx, val):
    return string[0:idx] + val + string[idx : len(string)]


def format_cedula(cedula):
    cedula = str(cedula)
    for i in range(len(cedula) - 3, 0, -3):
        cedula = string_insert(cedula, i, ".")
    return f"C.V. {cedula}"


def default_args_sql(query, args):
    if query == "result" and request.args.get("filter_value"):
        args["template"]["filter_value"] = request.args["filter_value"]
        args["sql"]["filter_value"] = "%" + request.args["filter_value"] + "%"

def get_query_columns(cursor):
    return { cursor.description[i][0]: i for i in range(len(cursor.description)) }

def execute_query(name, query, args):
    c = g.db.cursor()
    final_args = {"sql": args["sql"].copy(), "template": args["template"].copy()}
    default_args_sql(name, final_args)
    if type(query) == str:
        sql_file = query
    elif type(query) == list:
        sql_file = query[0]
        for arg in ["template", "sql"]:
            if arg in query[1]:
                final_args[arg].update(query[1][arg])

    sql = render_template("db/" + sql_file, **final_args["template"])
    print("SQL Template Arguments")
    pprint(final_args["template"])
    print("SQL Arguments")
    pprint(final_args["sql"])
    print(sql)
    c.execute(sql, final_args["sql"])
    
    columns = get_query_columns(c)
    result = c.fetchall()
    c.close()
    pprint(columns)
    pprint(result)
    return (result, columns)

def execute_queries(queries, args):
    c = g.db.cursor()
    print("SQL Queries")
    for query in queries:
        print("Query: ", query)
        result, columns = execute_query(query, queries[query], args)
        setattr(g, query, result)
        setattr(g, query + "_columns", columns)


default_pages = {
    "list": "list.html",
    "detail": "detail.html",
    "register": "register.html",
}

page_to_verb = {
    "list": "Listado de ",
    "detail": "Vista Detallada de ",
    "register": "Registrar ",
}


def render_page(title, pages=default_pages, queries="", args=None):
    if args is None:
        args = {}
    if not "template" in args:
        args["template"] = {}
    if not "sql" in args:
        args["sql"] = {}
    
    page_type = None
    if type(pages) == dict:
        page_type = request.args.get("page", "list")
        args["page_type"] = page_type
        g.title = page_to_verb[page_type] + title
        page = pages[page_type]
    else:
        page = pages
    if page_type == "detail":
        if not request.args.get("key", None):
            return abort(403)
        args["template"]["key"] = True
        args["sql"]["key"] = request.args["key"]

    if queries:
        if type(queries) == str:
            execute_queries({"result": queries}, args)
        elif type(queries) == dict:
            for key in queries:
                if key == page_type:
                    query = queries[key]
                    if type(query) == str:
                        query = {"result": query}
                    execute_queries(query, args)
    g.title = title

    return render_template(page, **args["template"])


def hashpass(p: str) -> str:
    return sha1(p.encode("utf-8")).hexdigest()


def distribuir_pagos_por_adelantado(cliente):
    c = g.db.cursor()
    c.execute(
        "select id, monto, fecha from pagos where cliente = :cliente",
        {"cliente": cliente},
    )
    pagos = c.fetchall()
    c.execute(render_template("db/deuda-compras.sql"), {"cliente": cliente})
    compras = c.fetchall()
    while pagos:
        pago = list(pagos[0])
        while compras:
            compra = list(compras[0])
            if pago[1] >= compra[1]:
                compras.pop(0)
            if compra[1] >= pago[1]:
                c.execute(
                    "update pagos set cliente = null, compra = ? where id = ?",
                    (compra[0], pago[0]),
                )
                pago[1] = 0
            else:
                c.execute(
                    "insert into pagos(compra, monto, fecha) values(?, ?, ?)",
                    (compra[0], compra[1], pago[2]),
                )
                pago[1] -= compra[1]
                c.execute("update pagos set monto = ? where id = ?", (pago[1], pago[0]))
            if not pago[1]:
                pagos.pop(0)
                break

        if not compras:
            break
    c.close()


def comprar():
    form = request.form
    c = g.db.cursor()

    productos = form.getlist("producto")
    cantidades = form.getlist("cantidad")
    assert len(productos) == len(cantidades)

    if len(productos) > len(set(productos)):
        flash("Los productos no deben repetirse", FLASH_ERROR)
        return

    precios = []
    for i in range(len(productos)):
        c.execute(
            "select nombre, cantidad_disponible, precio from productos where id = ? and anulado = 0",
            (productos[i],),
        )
        result = c.fetchone()
        if result is None:
            flash(f"El producto con el ID {productos[i]} no existe.", FLASH_ERROR)
            return
        if int(cantidades[i]) > result[1]:
            flash(
                f"{f'Solo quedan {result[1]}' if result[1] else 'No quedan'} unidades del producto con ID {productos[i]} y se pidieron {cantidades[i]}.",
                FLASH_ERROR,
            )
            return
        precios.append(result[2])

    monto_total = reduce(
        lambda value, x: value + x[0] * int(x[1]), zip(precios, cantidades), 0
    )

    cliente_sql = render_template("db/clientes.sql", key=True)
    c.execute(cliente_sql, {"key": form["cliente"]})
    cliente = c.fetchone()
    names = {c.description[i][0]: i for i in range(len(c.description))}

    if cliente is None:
        flash(f'El cliente con la cédula {form["cliente"]} no existe.', FLASH_ERROR)
        return
    if cliente[names["pasadas"]] or 0 > 0:
        flash(
            f'El cliente tiene {cliente[names["pasadas"]]} deudas las cuales pasaron el límite',
            FLASH_ERROR,
        )
        return
    if (cliente[names["deuda"]] or 0) + monto_total > cliente[names["limite_credito"]]:
        flash(f"La compra excede el límite de crédito del usuario.", FLASH_ERROR)
        return

    # Se ingresa la compra en si
    c.execute(
        "insert into compras(cliente, fecha_limite, fecha_compra) values(?, ?, DATE('now'))",
        (form["cliente"], form["fecha_limite"]),
    )
    # Agarramos el id que se le asigno a la compra
    compra = c.lastrowid
    # Por cada producto lo ingresamos en la tabla de compra_productos y disminuimos la cantidad disponible
    for i in range(len(productos)):
        c.execute(
            "insert into compra_productos(cantidad, precio_producto, producto, compra) values(?, ?, ?, ?)",
            (cantidades[i], precios[i], productos[i], compra),
        )
        c.execute(
            "update productos set cantidad_disponible = cantidad_disponible - ? where id = ?",
            (cantidades[i], productos[i]),
        )

    c.close()
    # Si tenemos pagos por adelantado, los asignamos automaticamente a esta compra (hasta que este pagado por completo)
    distribuir_pagos_por_adelantado(form["cliente"])


def revertir_compra():
    id = request.args["key"]
    c = g.db.cursor()
    c.execute("select cliente from compras where id = ?", (id,))
    cliente = c.fetchone()[0]
    c.execute("update pagos set compra = null, cliente = ?", (cliente,))
    c.execute("select cantidad, producto from compra_productos where compra = ?", (id,))
    for row in c.fetchall():
        c.execute(
            "update productos set cantidad_disponible = cantidad_disponible + ? where id = ?",
            row,
        )
    c.execute("delete from compra_productos where compra = ?", (id,))
    c.execute("delete from compras where id = ?", (id,))
    c.close()
    distribuir_pagos_por_adelantado(cliente)


def pagar():
    c = g.db.cursor()
    form = dict(request.form)
    monto = float(form["monto"])
    if monto <= 0:
        flash("El monto del pago tiene que ser positivo.", FLASH_ERROR)
        return
    c.execute(
        "select * from usuarios where cedula = ? and tipo = 'Cliente'",
        (form["cliente"],),
    )
    if not c.fetchall():
        flash(f'El cliente con la cédula {form["cliente"]} no existe.', FLASH_ERROR)
        return
    c.execute(
        "insert into pagos(cliente, monto) values(?, ?)", (form["cliente"], monto)
    )
    c.close()
    distribuir_pagos_por_adelantado(form["cliente"])


def check_usertype(check, action):
    def required(function):
        @wraps(function)
        def wrap(*args, **kwargs):
            if not check(session.get("type")):
                return action()
            return function(*args, **kwargs)

        return wrap

    return required


def forbbiden():
    abort(403)


login_required = check_usertype(lambda x: x != None, lambda: redirect(url_for("login")))
employee_required = check_usertype(lambda x: x == "Empleado", forbbiden)
client_required = check_usertype(lambda x: x == "Cliente", forbbiden)


# Login page and routine
@app.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        cursor = g.db.cursor()
        cursor.execute(
            "select hash_pass, nombre, tipo from usuarios where cedula = ? and anulado = 0",
            (request.form["cedula"],),
        )
        data = cursor.fetchone()
        cursor.close()

        if data != None:
            if hashpass(request.form["pass"]) == data[0]:
                session["user"] = request.form["cedula"]
                session["name"] = data[1]
                session["type"] = data[2]
                return redirect(url_for("index"))
            else:
                flash("La contraseña es incorrecta", FLASH_ERROR)
        else:
            flash(
                f'No se encontró el usuario con la cédula {request.form["cedula"]}',
                FLASH_ERROR,
            )
    return render_template("login.html")

def handle_password(form):
    if (not "pass" in form):
        return True
    if not form["pass"]:
        del form["pass"]
        if "pass_repeat" in form:
            del form["pass_repeat"]
        return True
    if not "pass_repeat" in form:
        del form["pass_repeat"]
        return True

    if form["pass"] != form["pass_repeat"]:
        flash("Las contraseñas no eran iguales.", FLASH_ERROR)
        return False

    form["hash_pass"] = hashpass(form["pass"])
    del form["pass"]
    del form["pass_repeat"]
    return True
    
@app.route("/recover", methods=("GET", "POST"))
def recover():
    if request.method == "POST":
        form = dict(request.form)
        if "uuid" in form:
            if not handle_password(form):
                return render_template("recover.html")
                
            c = g.db.cursor()
            c.execute("""
                update usuarios set hash_pass = ? where anulado = 0 and cedula = (select cedula from recuperaciones where uuid = ?)
                """, (form["hash_pass"], form["uuid"]))
            if not c.rowcount:
                flash("La solicitud de recuperar contraseña expiro, es invalida o el usuario fue eliminado", FLASH_ERROR)
                c.close()
            else:
                c.execute("delete from recuperaciones where uuid = ?", (form["uuid"],))
                flash("La contraseña fue recuperada exitosamente", FLASH_INFO)
                c.close()
                g.db.commit()
                return redirect(url_for('login'))
        else:
            c = g.db.cursor()
            c.execute("select correo, nombre from usuarios where cedula = ?", (form["cedula"],))
            result = c.fetchone()
            if result is None:
                flash(f'No se encontró el usuario con la cédula {form["cedula"]}', FLASH_ERROR)
            else:
                id = str(uuid.uuid4())
                email = result[0]
                try: 
                    send_mail(email, "CrediApp - Recuperación de Contraseña", render_template("email/recover.html", nombres=result[1], uuid=id))
                    c = g.db.cursor()
                    c.execute("insert into recuperaciones(cedula, uuid) values(?, ?)", (form["cedula"], id))
                    c.close()
                    g.db.commit()
                    flash("Se ha enviado exitosamente la petición de recuperación de contraseña a su correo electrónico", FLASH_INFO)
                except Exception as e:
                    print(e)
                    flash(f"No se pudo enviar el email al correo del cliente! Revise que su email sea valido, consulte con un empleado para modificarlo.", FLASH_ERROR)
    return render_template("recover.html")

def save_image():
    static_path = None
    if request.files.get("imagen", None):
        if ext := re.search("\.(png|jpg|gif)+$", request.files["imagen"].filename):
            data = request.files["imagen"].read()

            name = sha1(data).hexdigest()

            static_path = "images/" + name + ext.group(0)
            path = "static/" + static_path

            dest = open(path, "wb")
            dest.write(data)
            dest.close()
        else:
            flash("Archivo enviado tiene que ser una imagen!", FLASH_ERROR)
    return static_path


def create(table, args):
    columns = ", ".join([x for x in args])
    values = ", ".join([":" + x for x in args])

    command = f"insert into {table}({columns}) values({values})"
    print(command, args)
    g.db.execute(command, args)


def update(table, id_column, args):
    update_args = ", ".join([f"{x} = :{x}" for x in args if x != id_column])
    command = f"update {table} set {update_args} where {id_column} = :{id_column}"
    print(command, args)
    if request.args.get("key"):
        args[id_column] = request.args["key"]
    g.db.execute(command, args)


def delete(table, id_column, id):
    g.db.execute(f"delete from {table} where {id_column} = ?", (id,))


def crud(name, table, id_column, form):
    action = form["action"]
    del form["action"]
    if action == "create":
        try:
            create(table, form)
        except sqlite3.Error as err:
            print(err)
            flash(
                f"Ya había un {name} con la llave {id_column} o hay un error en los datos enviados.",
                FLASH_ERROR,
            )
            return
        flash(f"Se registró exitosamente el {name}", FLASH_INFO)
        return redirect(request.path)
    if action == "delete":
        delete(table, id_column, request.args["key"])
        flash(f"Se eliminó exitosamente el {name}", FLASH_INFO)
        return redirect(request.path)
    if action == "update":
        update(table, id_column, form)




def user_post(form, files):
    if "show_pass" in form:
        del form["show_pass"]

    if not handle_password(form):
        return

    image = save_image()
    if image is not None:
        form["imagen"] = image
    # Cuando se trata de crear un cliente que esta anulado se desanula
    if form["action"] == "create" and form["tipo"] == "Cliente":
        c = g.db.cursor()
        c.execute("select cedula from usuarios where tipo = 'Cliente' and cedula = ? and anulado = 1", (form["cedula"],))
        if c.fetchall():
            del form["action"]
            form["anulado"] = 0
            update("usuarios", "cedula", form)
            flash(f"Se registró exitosamente el cliente", FLASH_INFO)
            return redirect(request.path)
           
    if form["action"] == "delete":
        # Validar que no se eliminen todos los empleados
        if form["tipo"] == "Empleado":
            c = g.db.cursor()
            c.execute("select count(cedula) from usuarios where tipo = 'Empleado'")
            r = c.fetchone()
            c.close()
            if r[0] == 1:
                flash("No se pueden eliminar todos los empleados.", FLASH_ERROR)
                return
        # Los clientes no se eliminan, se anulan
        elif form["tipo"] == "Cliente":
            del form["action"]
            update("usuarios", "cedula", {"anulado": 1})
            flash(f"Se eliminó exitosamente el cliente", FLASH_INFO)
            return redirect(request.path)

    return crud("usuario", "usuarios", "cedula", form)


@app.route("/clientes", methods=("GET", "POST"))
@login_required
def clientes():
    args = {}
    args["template"] = {
        "table": "Cliente",
        "default_image": "profile.svg",
        "image_index": 6,
        "password": True,
        "fields": [
            {
                "label": "Cédula",
                "name": "cedula",
                "key": True,
                "show": "secondary",
                "format": format_cedula,
                "attributes": REQUIRE_POSITIVE_NUMBER,
            },
            {"label": "Nombre", "show": "main", "attributes": f"required {NAME_PATTERN}"},
            {"label": "Correo", "name": "correo", "type": "email", "attributes": "required placeholder='ejemplo@dominio.com'"},
            {"label": "Teléfono*", "name": "telefono", "attributes": PHONE_PATTERN},
            {"label": "Dirección*", "name": "direccion"},
            {
                "name": "limite_credito",
                "label": "Límite de Credito",
                "attributes": REQUIRE_DECIMAL_NUMBER,
            },
            {
                "index": 7,
                "info": True,
                "show": "secondary",
                "format": lambda x: "No tiene deuda"
                if (x or 0) == 0
                else f"Tiene {-x:.2f}$ en abonos"
                if x < 0
                else f"Debe {(x or 0):.2f}$",
            },
            {
                "index": 8,
                "info": True,
                "show": "secondary",
                "format": lambda x: f"Deuda del cliente ha pasado su fecha límite" if x == 1 else f"{x} deudas del cliente han pasado su fecha límite" if x > 1 else ""
            },
        ],
    }
    
    if session["type"] == "Cliente":
        if (request.method == "POST" or
            request.args.get("page", None) != "detail" or
            request.args.get("key", None) != session["user"]):
            return abort(403)
        args["template"]["non_editable"] = True
        args["template"]["non_erasable"] = True
    
    if request.method == "POST":
        form = dict(request.form)
        form["tipo"] = "Cliente"
        if page := user_post(form, request.files):
            return page

    pages = default_pages.copy()
    pages["detail"] = "client-detail.html"

    return render_page("Clientes", pages, "clientes.sql", args)


@app.route("/empleados", methods=("GET", "POST"))
@employee_required
def empleados():
    args = {}
    args["template"] = {
        "table": "Empleado",
        "default_image": "profile.svg",
        "image_index": 3,
        "password": True,
        "fields": [
            {
                "label": "Cédula",
                "name": "cedula",
                "key": True,
                "show": "secondary",
                "format": format_cedula,
                "attributes": REQUIRE_POSITIVE_NUMBER,
            },
            {"label": "Nombre", "show": "main", "attributes": f"required {NAME_PATTERN}"},
            {"label": "Correo", "name": "correo", "type": "email", "attributes": "required placeholder='ejemplo@dominio.com'"},
        ],
        "filter_fields": ["cedula", "nombre", "correo"],
    }
    if request.method == "POST":
        form = dict(request.form)
        form["tipo"] = "Empleado"
        if page := user_post(form, request.files):
            return page

    return render_page("Empleados", default_pages, "empleados.sql", args)

def export_inventario(args):
    result, cols = execute_query("result", "inventario.sql", args)
    table = []
    columns = {"id": "ID", "nombre": "Nombre", "cantidad_disponible": "Cantidad Disponible", "id_de_proveedor": "ID de Proveedor"}
    for row in result:
        table.append([])
        for key in columns:
            table[-1].append(row[cols[key]])
    return exportar("Inventario", columns.values(), table)

@app.route("/inventario", methods=("GET", "POST"))
@login_required
def inventario():
    args = { "sql": {} }
    args["template"] = {
        "table": "Producto",
        "default_image": "product.svg",
        "image_index": 5,
        "fields": [
            {
                "key": True,
                "show": "secondary",
                "info": True,
                "format": lambda x: f"ID de Sistema: {x}",
            },
            {"label": "Nombre", "show": "main", "attributes": "required"},
            {
                "label": "Precio",
                "show": "secondary",
                "format": lambda x: f"Cuesta {x:.2f}$",
                "attributes": REQUIRE_DECIMAL_NUMBER,
            },
            {
                "label": "Cantidad Disponible",
                "name": "cantidad_disponible",
                "show": "secondary",
                "format": lambda x: f"Hay {x} disponibles",
                "attributes": "pattern='[0-9]+' required",
            },
            {"label": "ID de proveedor*", "name": "id_de_proveedor"},
        ]
    }
    if session["type"] == "Cliente":
        args["template"]["non_editable"] = True
        args["template"]["non_mutable"] = True
        args["template"]["non_erasable"] = True
    if request.method == "POST":
        if session["type"] == "Cliente":
            return abort(403)
        form = dict(request.form)
        if form["action"] == "delete":
            c = g.db.cursor()
            c.execute("update productos set anulado = 1 where id = ?", (request.args["key"],))
            c.close()
            g.db.commit()
            flash(f"Se eliminó exitosamente el producto", FLASH_INFO)
            return redirect(request.path)
        else:
            image = save_image()
            if image is not None:
                form["imagen"] = image
            if page := crud("producto", "productos", "id", form):
                return page
    if request.args.get("export"):
        return export_inventario(args)
    return render_page("Productos", default_pages, "inventario.sql", args)

# TODO: Should return every product and the price when it was bought?
def export_compras(args):
    result, cols = execute_query("result", "compras.sql", args)
    table = []
    columns = {"cantidad": "Cantidad de productos", "fecha_compra": "Fecha de Compra", "fecha_limite": "Fecha Límite de Deuda", "pagado": "Monto Pagado", "monto_total": "Monto Total"}
    if session["type"] == "Empleado":
        columns["cedula"] = "Cédula Cliente"
        columns["nombre"] = "Nombres Cliente"
    for row in result:
        table.append([])
        for key in columns:
            table[-1].append(row[cols[key]])
    return exportar("Historial de Compras", columns.values(), table)

@app.route("/compras", methods=("GET", "POST"))
@login_required
def compras():
    queries = {
        "list": "compras.sql",
        "register": {
            "result": "inventario.sql",
            "clientes": "clientes.sql",
        },
        "detail": {
            "result": "compras.sql",
            "productos": "compra-productos.sql",
            "pagos": "compra-pagos.sql",
        },
    }
    pages = {
        "list": "list.html",
        "register": "register-compra.html",
        "detail": "detail-compra.html",
    }
    args = {}
    args["template"] = {
        "fields": [
            {
                "index": 5,
                "show": "main",
                "format": lambda x: f"Compra de {x} productos",
            },
            {"index": 2, "show": "main", "format": lambda x: f"Por cliente {x}"},
            {"index": 3, "show": "secondary", "format": lambda x: f"El {x}"},
            {"index": 6, "show": "secondary", "format": lambda x: f"Monto Total {x:.2f}$"},
            {"index": 7, "show": "secondary", "format": lambda x: f"Pagado {(x or 0):.2f}$"},
        ],
        "table": "Compra",
        "default_image": "buy.svg",
        "erase_verb": "Revertir",
    }
    args["sql"] = {"key": request.args.get("key")}

    if session["type"] == "Cliente":
        if request.method == "POST":
            return abort(403)
        args["template"]["non_editable"] = True
        args["template"]["non_mutable"] = True
        args["template"]["non_searchable"] = True
        args["template"]["non_erasable"] = True
        args["template"]["cliente"] = True
        args["sql"]["cliente"] = session["user"]
    
    if request.method == "POST":
        form = request.form
        action = form["action"]
        if action == "create":
            comprar()
            if not has_errored():
                flash("La compra fue realizada exitosamente.", FLASH_INFO)
                return redirect(request.path)
        if action == "delete":
            revertir_compra()
            flash(
                "La compra fue revertida exitosamente. Los pagos de la compra han sido liberados.",
                FLASH_INFO,
            )
            return redirect(request.path)

    if request.args.get("export") and not request.args.get("page"):
        return export_compras(args)
    return render_page("Compras", pages, queries, args)

def export_deudas(args):
    if args is None:
        args = {"sql": {}, "template": {}}
    result, cols = execute_query("result", "calendario-de-deudas.sql", args)
    table = []
    columns = {"fecha_compra": "Fecha de Compra", "fecha_limite": "Fecha Límite de Deuda", "pagado": "Monto Pagado", "monto_total": "Monto Total"}
    if session["type"] == "Empleado":
        columns["cliente"] = "Cédula Cliente"
    for row in result:
        table.append([])
        for key in columns:
            table[-1].append(row[cols[key]])
    return exportar("Calendario de Deudas", columns.values(), table)

@app.route("/deudas")
@login_required
def deudas():
    args = None
    if request.args.get("cliente", None):
        if session["type"] == 'Cliente' and request.args["cliente"] != session["user"]:
            return abort(403)
        c = g.db.cursor()
        c.execute("select nombre from usuarios where cedula = ?", (request.args["cliente"],))
        result = c.fetchone()
        if result == None:
            return abort(403)
        args = {
            "sql": {"cliente": request.args["cliente"]}, 
            "template": {"cliente": request.args["cliente"], "name": result[0]}
        }
    elif session["type"] == 'Cliente':
        return abort(403)
    if request.args.get("export"):
        return export_deudas(args)
    return render_page("Calendario de Deudas", "calendario-de-deudas.html", "calendario-de-deudas.sql", args)


@app.route("/abonos", methods=("GET", "POST"))
@employee_required
def abonos():
    args = {}
    args["template"] = {
        "erase_verb": "Revertir",
        "table": "Abono",
        "default_image": "payment.svg",
        "fields": [
            {
                "index": 4,
                "label": "Cédula Cliente",
                "name": "cliente",
                "type": "number",
                "attributes": "required",
            },
            {
                "index": 1,
                "label": "Monto",
                "show": "main",
                "format": lambda x: f"Pago con monto de {x:.2f}$",
                "attributes": REQUIRE_DECIMAL_NUMBER,
            },
            {
                "index": 2,
                "info": True,
                "show": "main",
                "format": lambda x: f"Realizado el {x}",
            },
            {
                "index": 3,
                "info": True,
                "show": "secondary",
                "format": lambda x: "Es un pago por adelantado" if not x else "",
            },
            {
                "index": 5,
                "info": True,
                "show": "secondary",
                "format": lambda x: f"Realizado por el cliente {x}",
            },
        ],
        "non_editable": True,
    }

    if request.method == "POST":
        form = dict(request.form)
        if form["action"] == "create":
            pagar()
            if not has_errored():
                flash("Se realizo el pago exitosamente", FLASH_INFO)
                return redirect(request.path)
        elif form["action"] == "delete":
            if not request.args.get("key", None):
                return abort(403)
            form["id"] = request.args["key"]
            c = g.db.cursor()
            c.execute("select compra from pagos where id = :id", form)
            if c.fetchone()[0] is not None:
                c.close()
                flash(
                    "Solo se pueden revertir pagos que no esten asignados a alguna compra",
                    FLASH_ERROR,
                )
            else:
                c.execute("delete from pagos where id = :id", form)
                c.close()
                flash("Se revertio el pago exitosamente", FLASH_INFO)
                return redirect(request.path)

    return render_page("Abonos", default_pages, "pagos.sql", args)


@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/")
@login_required
def index():
    return render_template("base.html")


@app.route("/help")
@login_required
def help():
    content = None
    name = None
    tipo = request.args.get("type")
    
    if tipo == "user":
        name = "Manual de Usuario.pdf"
    elif tipo == "admin":
        if session["type"] == "Cliente":
            return abort(403)
        name = "Manual de Analista.pdf"
    else:
        return abort(403)
        
    with open("static/" + name, "rb") as manual:
        content = manual.read()
    return Response(
        content,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment;filename={name}"},
    )

if __name__ == "__main__":
    app.run(debug=True, port=10000, host="0.0.0.0")
