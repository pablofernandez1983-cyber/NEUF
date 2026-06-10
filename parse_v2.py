"""
Parser v2 para NEUFMSG.DAT - Btrieve database del lector offline NEUF (MP Online, 1997)

Estructura descubierta:
- Registros de metadatos: [from]\n[to]\n[extra_2chars]\0[30 bytes binarios]
  - binary[0-1]: página overflow donde está el body (uint16 LE)
  - binary[2]: índice de slot 0-based dentro de la página (si hay continuación en slot anterior, se incluye)
  - binary[14-17]: Unix timestamp (uint32 LE)
- Páginas overflow: contienen N cuerpos de mensajes
  - Header de 16 bytes con num_slots en bytes 10-11
  - Slot directory al FINAL de la página (2 bytes por slot, leyendo desde byte 3582 hacia atrás)
  - slots[i] = offset del record i+1 dentro de la página
  - Slot con bit alto (0x8000) = continuación de otra página
"""
import re, struct, json, datetime

DAT = r'C:\NEUF\NEUFMSG.DAT'
ARE = r'C:\NEUF\NEUFARE.DAT'
OUT = r'C:\NEUF\app\messages_v2.json'

PAGE_SIZE = 3584
HEADER    = 16

with open(DAT, 'rb') as f:
    raw = f.read()
print(f"Archivo: {len(raw):,} bytes, {len(raw)//PAGE_SIZE} páginas")

# ── Mapa área_id (binary[3]) → nombre de área ────────────────────────────────
# Extraído de NEUFARE.DAT: el byte en (name_offset-2) de cada record = area_id
areas = {
    2: 'correo/recibidos', 7: 'correo/enviados',
    8: 'neuf/info', 9: 'neuf/personal', 10: 'neuf/salida',
    15: 'avisos/trabajos', 17: 'bbs/mejoras', 20: 'idioma/varios',
    23: 'deportes/futbol', 24: 'espect/tv/varios', 26: 'libre/humor',
    32: 'bbs/soft', 34: 'sist/win95', 35: 'soft/internet',
    38: 'soft/multimedia', 39: 'votos/bbs', 40: 'votos/under',
    46: 'votos/general', 48: 'avisos/segundama', 57: 'espect/cine',
    60: 'sist/windows', 66: 'bbs/info', 67: 'revistas/varios',
    68: 'bbs/soft', 73: 'idioma/ingles', 79: 'libre/ingenio',
    83: 'soft/anim', 87: 'demos/hola', 88: 'demos/preguntas',
    93: 'juegos/3d', 94: 'juegos/consolas', 95: 'juegos/demos',
    96: 'juegos/varios', 97: 'avisos/mujeres', 99: 'juegos/simula',
    100: 'juegos/torneos', 102: 'deportes/varios', 106: 'juegos/online',
    108: 'libre/social', 111: 'juegos/arcade', 112: 'juegos/avent',
    115: 'artes/musica/digital', 116: 'espect/tv/simpsons', 125: 'soft/graf',
    130: 'deportes/grandt', 134: 'artes/musica/digital', 137: 'bbs/rankings',
    138: 'idioma/castellano', 142: 'avisos/publicidad', 144: 'votos/oficiales',
    160: 'sist/debate', 164: 'hardware', 167: 'idioma/varios',
    177: 'prog/java', 178: 'soft/bases', 179: 'soft/comunic',
    180: 'ciencias/fisica', 181: 'hogar/mascotas', 182: 'libre/social',
    183: 'mundo/debates', 187: 'sist/unix', 188: 'soft/compre',
    190: 'soft/virus', 192: 'libre/under', 193: 'deportes/bowling',
    194: 'libre/perfiles', 195: 'libre/under', 196: 'mundo/turismo',
    197: 'sist/dos', 198: 'soft/redes', 199: 'espect/recitales',
    200: 'hogar/cocina', 201: 'libre/nostalgia', 202: 'libre/reuniones',
    203: 'mundo/derechos', 204: 'mundo/politica', 205: 'artes/liter/poesia',
    206: 'ciencias/matematica', 207: 'prog/varios', 208: 'hobbies/electro',
    209: 'prog/visual', 210: 'artes/musica/clasica', 211: 'ciencias/historia',
    213: 'libre/anuncios', 214: 'hobbies/radio', 215: 'prog/pascal',
    216: 'libre/payada', 217: 'ciencias/quimica', 218: 'hobbies/autos',
    219: 'sist/os2', 220: 'espect/varios', 221: 'prog/c++',
    223: 'prog/xbase', 224: 'revistas/axxon', 225: 'soft/herram',
    226: 'mundo/filosofia', 227: 'artes/musica/varios', 228: 'mundo/religion',
    229: 'sist/varios', 231: 'hobbies/peces', 232: 'mundo/ecologia',
    233: 'deportes/ajedrez', 234: 'hobbies/comics', 235: 'prof/medicina',
    236: 'artes/foto', 237: 'prog/basic', 240: 'espect/tv/xfiles',
}
print(f"Áreas cargadas: {len(areas)}")

# ── Slot directory de una página ──────────────────────────────────────────────
def page_slots(page_num):
    page = raw[page_num*PAGE_SIZE:(page_num+1)*PAGE_SIZE]
    n = struct.unpack_from('<H', page, 10)[0]
    if n == 0 or n > 500:
        return []
    slots = []
    for i in range(n):
        off = PAGE_SIZE - 2 - i * 2
        if off < HEADER:
            break
        slots.append(struct.unpack_from('<H', page, off)[0])
    return slots  # slots[0]=primer record (menor offset), ..., slots[-1]=último

# ── Leer texto de un slot ────────────────────────────────────────────────────
def slot_text(page_num, slot_val, next_val=None):
    real_off = slot_val & 0x7FFF          # quitar flag de continuación
    if real_off == 0 or real_off >= PAGE_SIZE - 10:
        return ''
    abs_start = page_num * PAGE_SIZE + real_off
    # Si tiene flag de continuación (high bit), hay un header de 4 bytes antes del texto
    text_start = abs_start + (4 if slot_val & 0x8000 else 0)
    if next_val is not None:
        abs_end = page_num * PAGE_SIZE + (next_val & 0x7FFF)
    else:
        # Último slot: el uint16 en PAGE_SIZE-2*(n+1) (justo antes del slot
        # directory) es el offset de fin de datos de la página. Verificado en
        # 775/775 páginas: last_slot < free_ptr <= dir_start. Si no es válido,
        # caer al inicio del directory para no leer la tabla como texto.
        n = struct.unpack_from('<H', raw, page_num * PAGE_SIZE + 10)[0]
        if 0 < n <= 500:
            dir_start = PAGE_SIZE - 2 * (n + 1)
            free_ptr = struct.unpack_from('<H', raw, page_num * PAGE_SIZE + dir_start)[0]
            end_off = free_ptr if real_off < free_ptr <= dir_start else dir_start
        else:
            end_off = PAGE_SIZE - 2
        abs_end = page_num * PAGE_SIZE + end_off
    chunk = raw[text_start:abs_end]
    # Limpiar basura binaria del inicio
    text = chunk.decode('cp850', errors='replace')
    text = re.sub(r'^[\x00-\x1f\x7f-\x9f]+', '', text)
    text = text.rstrip('\x00')
    # Truncar en el separador de NEUF entre mensajes (indica inicio de otro slot)
    for sep in ('[ Mensaje no votado ]', '[ Mensaje votado', '\x00\x00\x00\x00\x00\x00\x00\x00'):
        idx = text.find(sep)
        if idx > 0:
            text = text[:idx].rstrip()
            break
    # Quitar bytes de control sueltos al final (p.ej. terminador \x16 del record)
    text = re.sub(r'[\x00-\x1f\x7f]+$', '', text)
    return text

# ── Obtener body completo: slot_idx + posible continuación anterior ────────────
def get_body(page_num, slot_idx):
    if page_num <= 0 or page_num >= len(raw) // PAGE_SIZE:
        return ''
    slots = page_slots(page_num)
    if not slots or slot_idx >= len(slots):
        # Fallback: leer desde inicio de datos
        start = page_num * PAGE_SIZE + HEADER
        chunk = raw[start:start + 4096]
        text = chunk.decode('cp850', errors='replace')
        return re.split(r'\x00{4,}', text)[0][:3000]

    # Slot principal únicamente.
    # La continuación (slot con bit alto = 0x8000) pertenece al registro de la
    # página anterior — no al registro actual. Incluirla mezclaría cuerpos de
    # mensajes distintos y rompería la extracción del tema.
    main_val = slots[slot_idx]
    # Fin del record: el MENOR offset de slot válido mayor que el inicio.
    # El directory puede estar desordenado y tener entradas borradas (0xFFFF),
    # así que slots[slot_idx+1] no sirve: en pág 3638 el slot 2 tenía 0xFFFF
    # como "siguiente" y se leían 32KB cruzando páginas (mezclaba mensajes).
    real_off = main_val & 0x7FFF
    nexts = [s & 0x7FFF for s in slots
             if real_off < (s & 0x7FFF) < PAGE_SIZE - 10]
    next_val = min(nexts) if nexts else None
    return slot_text(page_num, main_val, next_val)

# ── Parser de registros de metadatos ────────────────────────────────────────
# Patrón A (no-leídos): [from]\n[to]\n[extra_0-20chars]\0[binary 30 bytes]
PAT_UNREAD = re.compile(
    rb'([a-zA-Z0-9@._\-]{2,30})'
    rb'\n'
    rb'([a-zA-Z0-9@._\-]{1,30})'
    rb'\n'
    rb'([^\x00]{0,20})'
    rb'\x00'
    rb'(.{30})',
    re.DOTALL
)
# Patrón B (leídos): [from]\n[to]\0[binary 30 bytes]  — sin campo extra
PAT_READ = re.compile(
    rb'([a-zA-Z0-9@._\-]{2,30})'
    rb'\n'
    rb'([a-zA-Z0-9@._\-]{1,30})'
    rb'\x00'
    rb'(.{30})',
    re.DOTALL
)

# Rango Unix para mensajes de 1997 (ene 1997 – dic 1997)
TS_MIN = 852_076_800   # 1997-01-01
TS_MAX = 883_612_799   # 1997-12-31

messages = []
seen_page_slot = set()

def process_match(from_u, to_u, extra, binary):
    page_ref = struct.unpack_from('<H', binary, 0)[0]
    slot_idx = binary[2]

    ts = struct.unpack_from('<I', binary, 14)[0]
    if TS_MIN <= ts <= TS_MAX:
        date_str = datetime.datetime.utcfromtimestamp(ts).strftime('%d/%m/%Y %H:%M:%S')
    elif 800_000_000 < ts < 1_050_000_000:
        date_str = datetime.datetime.utcfromtimestamp(ts).strftime('%d/%m/%Y %H:%M:%S')
    else:
        date_str = ''

    area_name = areas.get(binary[3], '')
    key = (page_ref, slot_idx)
    if key in seen_page_slot or page_ref <= 0 or page_ref > 7000:
        return None
    seen_page_slot.add(key)

    body = get_body(page_ref, slot_idx)

    tema = extra
    body_clean = body
    if body:
        first_break = body.find('\n\n')
        if 0 < first_break < 150:
            tema_rest = body[:first_break].strip()
            if '\n' not in tema_rest and tema_rest:
                tema = extra + tema_rest
                body_clean = body[first_break:].strip()
        if not tema:
            tema = extra

    return {
        'from_user': from_u,
        'to_user':   to_u,
        'area':      area_name,
        'subject':   tema.strip(),
        'date':      date_str,
        'body':      body_clean[:6000],
        'page':      page_ref,
        'slot':      slot_idx,
    }

# Paso A: mensajes no-leídos (patrón con extra field)
for m in PAT_UNREAD.finditer(raw):
    from_u = m.group(1).decode('ascii', errors='replace')
    to_u   = m.group(2).decode('ascii', errors='replace')
    extra  = m.group(3).decode('cp850', errors='replace')
    binary = m.group(4)
    msg = process_match(from_u, to_u, extra, binary)
    if msg:
        messages.append(msg)

print(f"Paso A (no-leídos): {len(messages)} mensajes")
cnt_a = len(messages)

# Paso B: mensajes leídos (patrón sin extra field)
# Filtros extra para evitar falsos positivos en páginas de body:
#   - timestamp ESTRICTAMENTE en rango 1997
#   - from != 'Todos' (nadie envía DESDE Todos)
#   - area_id conocido (binary[3] en dict de areas)
#   - body no vacío
cnt_b_raw = 0
for m in PAT_READ.finditer(raw):
    from_u = m.group(1).decode('ascii', errors='replace')
    to_u   = m.group(2).decode('ascii', errors='replace')
    binary = m.group(3)

    # Filtro anti-falso-positivo
    if from_u.lower() == 'todos':
        continue
    ts = struct.unpack_from('<I', binary, 14)[0]
    if not (TS_MIN <= ts <= TS_MAX):
        continue
    if binary[3] not in areas:
        continue

    msg = process_match(from_u, to_u, '', binary)
    if msg and msg['body']:  # solo si tiene body real
        # El tema viene del body (primer bloque antes de \n\n)
        cnt_b_raw += 1
        messages.append(msg)

print(f"Paso B (leídos): {len(messages) - cnt_a} mensajes nuevos (de {cnt_b_raw} candidatos)")

print(f"Mensajes parseados: {len(messages)}")

# ── Limpiar prefijo de voto en from_user ─────────────────────────────────────
# En las áreas de votos, el byte 29 del registro binario ANTERIOR guarda el voto
# (S/N/B). El regex lo absorbe como primera letra del from ("Npaz" → "paz").
# Solo se quita si el resto es un usuario conocido (verificado: cero falsos
# positivos — ningún usuario real arranca con mayúscula).
known_users = {m['from_user'] for m in messages if m['from_user'][:1].islower()}
known_users |= {m['to_user'] for m in messages}
fixed_votes = 0
for m in messages:
    f_u = m['from_user']
    if len(f_u) > 2 and f_u[0] in 'SNB' and f_u[1:] in known_users:
        m['from_user'] = f_u[1:]
        fixed_votes += 1
print(f"Prefijos de voto corregidos: {fixed_votes}")

# Ordenar por fecha
messages.sort(key=lambda x: x['date'] or '99/99/9999')

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(messages, f, ensure_ascii=False, indent=2)
print(f"Guardado en {OUT}")

# Muestra de los primeros mensajes
for i, msg in enumerate(messages[:5]):
    print(f"\n--- {i+1} ---")
    print(f"  De: {msg['from_user']}  →  {msg['to_user']}")
    print(f"  Fecha: {msg['date']}")
    print(f"  Tema: {msg['subject'][:60]}")
    print(f"  Body: {msg['body'][:100]}")
