#define UNICODE
#include <windows.h>

typedef struct menu {
	const wchar_t* name;
	struct menu* rest;
} menu_t;

menu_t menu[] = {
	{L"Clientes", (menu_t[]) {
		{
			L"Consultar",
			(menu_t[]) {
				{L"Infomación de Producto"},
				{L"Estado del Cliente"},
				{L"Calendario de Deudas"},
				{L"Historial de Compras"},
				{NULL}
			}
		},
		{NULL}
	}},
	{L"Empleados", (menu_t[]) {
		{L"Cliente", (menu_t[]) {
			{L"Registrar"},
			{L"Actualizar"},
			{L"Consultar estado"},
			{L"Consultar calendario de deudas"},
			{NULL}
		}},
		{L"Empleado", (menu_t[]) {
			{L"Agregar"},
			{L"Modificar"},
			{L"Eliminar"},
			{NULL},
		}},
		{NULL}
	}},
	{L"Inventario", (menu_t[]) {
		{L"Consultar", (menu_t[]) { {L"Infomación del Producto"}, {NULL} } },
		{L"Administrar", (menu_t[]) {
			{L"Agregar"},
			{L"Modificar"},
			{L"Eliminar"},
			{NULL},
		}},
		{NULL}
	}},
	{L"Pagos", (menu_t[]) {
		{L"Compras", (menu_t[]) {
			{L"Agregar"},
			{L"Anular"},
			{NULL},
		}},
		{L"Abonos", (menu_t[]) {
			{L"Realizar"},
			{L"Consultar"},
			{L"Revertir"},
			{NULL}
		}},
		{NULL}
	}},
	{L"Reporte", (menu_t[]) {
		{L"Cliente", (menu_t[]) {
			{L"Calendario de Deudas"},
			{L"Historial de Compra"},
			{NULL},
		}},
		{L"Empleado", (menu_t[]) {
			{L"Inventario Actual"},
			{L"Calendario de Deudas"},
			{NULL}
		}},
		{NULL}
	}},
	{L"Ayuda", (menu_t[]) { {L"Manual de Usuario"}, {NULL} } },
	{L"Salida", (menu_t[]) { {L"Desconexión del Usuario"}, {NULL} } },
	{NULL}
};

HMENU create_menu(HMENU parent, menu_t* menu)
{
	if(!parent)
		parent = CreateMenu();
	while(menu->name) {
		if(menu->rest) {
			HMENU item = create_menu(NULL, menu->rest);
			AppendMenu(parent, MF_POPUP, (UINT_PTR)item, menu->name);
		}
		else
			AppendMenu(parent, MF_STRING, 0, menu->name);
		menu++;
	}
	return parent;
}

LRESULT CALLBACK event_loop(HWND hwnd, UINT uMsg, WPARAM wParam, LPARAM lParam)
{
	switch (uMsg) {
	case WM_DESTROY: PostQuitMessage(0); return 0;
	case WM_PAINT: {
		PAINTSTRUCT ps;
		HDC hdc = BeginPaint(hwnd, &ps);
		FillRect(hdc, &ps.rcPaint, (HBRUSH)(COLOR_WINDOW + 1));
		EndPaint(hwnd, &ps);
	}
	}
	return DefWindowProc(hwnd, uMsg, wParam, lParam);
}

int main(void)
{
	HINSTANCE instance = GetModuleHandle(NULL);
	
	const wchar_t class_name[] = L"Menu Window";
	WNDCLASS wc = { .lpfnWndProc = event_loop,
					.hInstance = GetModuleHandle(NULL),
					.lpszClassName = class_name };
	RegisterClass(&wc);
	
	HMENU bar = create_menu(NULL, menu);
	HWND win = CreateWindowEx(0, class_name, L"Menu", WS_OVERLAPPED, 0, 0, 800, 100, NULL, bar, instance, NULL);
	if(!win) 
		return 1;
	ShowWindow(win, SW_SHOW);
	
	MSG msg;
	while (GetMessage(&msg, NULL, 0, 0)) {
		TranslateMessage(&msg);
		DispatchMessage(&msg);
	}
	return 0;
}
