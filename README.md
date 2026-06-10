# NEUF — Archivo histórico de MP Online BBS (1997)

Lector web de **50.489 mensajes** de los foros de **MP Online**, un BBS de Buenos Aires,
escritos entre abril y diciembre de 1997.

Los mensajes fueron rescatados de una copia de **NEUF**, el lector offline del BBS
("No Estás Usando el Fono"): los usuarios se conectaban por módem, descargaban los
mensajes nuevos, cortaban la llamada y leían/respondían sin ocupar la línea de teléfono.
La base de datos original estaba en formato **Btrieve** (`NEUFMSG.DAT`), y casi 30 años
después fue parseada byte a byte para recuperar los mensajes.

## Cómo usarlo

```
python server.py
```

Abre http://localhost:8585 con una interfaz tipo terminal DOS, fiel a la estética del
NEUF original. Comandos:

| Comando | Acción |
|---|---|
| `DIR` | listar directorio actual |
| `CD <nombre>` / `CD..` | navegar foros |
| `<número>` | leer un mensaje · `N`/`P` siguiente/anterior |
| `SORT DE\|PARA\|FECHA\|TEMA` | ordenar la lista |
| `BUSCAR <texto>` | búsqueda full-text (`/de:`, `/para:`, `/area:`) |
| `VER` · `CLS` · `?` | info · limpiar · ayuda |

Ejemplo: `CD foros` → `CD deportes` → `CD futbol` → `1`

## Qué hay adentro

Los foros más activos: `hardware` (10.455 mensajes), `deportes/futbol` (8.641),
`sist/win95` (3.190), `soft/internet` (2.721), `juegos/*` (7.000+), `votos/*` (3.700+,
el sistema de votaciones del BBS), `libre/nostalgia`, `idioma/ingles`, y unas 100 áreas más.
Discusiones sobre el Torneo Apertura '97, el Gran DT, módems de 33.6k, Windows 95 vs OS/2,
los primeros pasos de internet en Argentina, MP3, emuladores, y la vida cotidiana de una
comunidad online pre-web.

## Archivos

- `index.html` — la app (HTML/JS sin dependencias, fuente VT323)
- `messages.json` — los 50.489 mensajes (30MB)
- `server.py` — servidor estático mínimo
- `parse_v2.py` — el parser de Btrieve que extrajo los mensajes de `NEUFMSG.DAT`

## Privacidad

Este archivo contiene **solo los foros públicos** del BBS, que cualquier usuario podía
leer en 1997. El correo privado fue excluido del dataset. Si participaste de MP Online
y querés que se elimine algún mensaje tuyo, abrí un issue.
