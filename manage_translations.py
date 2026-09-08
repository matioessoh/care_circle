#!/usr/bin/env python
"""Gestion des traductions Care Circle (extraction + compilation) sans gettext.

Usage:
  python manage_translations.py extract   # scan tous les templates -> met a jour locale/proj/...
  python manage_translations.py compile   # compile .po -> .mo

Valable pour les templates et le code Python. Remplace makemessages + compilemessages
tout en utilisant Babel (aucun besoin de xgettext/msgfmt systeme).
"""
import os
import re
import sys
import io
from pathlib import Path

BASE = Path(__file__).parent
LOCALE = BASE / 'locale'
LANG = 'en'
DIR = LOCALE / LANG / 'LC_MESSAGES'
VARIANTS = ['templates']

TRAN = re.compile(r"\{%\s*trans\s+(['\"])(?P<msg>.+?)\1\s*%\}", re.S)
BLOCKTRAN = re.compile(
    r"\{%\s*blocktrans.*?%\}(?P<msg>.*?)\{%\s*endblocktrans\s*%\}", re.S)


def iter_templates():
    for root, _dirs, files in os.walk(BASE):
        if 'locale' in root or '.git' in root or 'node_modules' in root:
            continue
        for f in files:
            if f.endswith('.html'):
                yield Path(root) / f


def extract_messages():
    """Retourne un dict {msgid: set(locations)} à partir des templates."""
    found = {}
    for tf in iter_templates():
        try:
            content = tf.read_text(encoding='utf-8')
        except OSError:
            continue
        for m in TRAN.finditer(content):
            msg = m.group('msg').strip()
            if msg:
                found.setdefault(msg, set()).add(str(tf.relative_to(BASE)))
        for m in BLOCKTRAN.finditer(content):
            msg = ' '.join(line.strip() for line in m.group('msg').splitlines()).strip()
            if msg:
                found.setdefault(msg, set()).add(str(tf.relative_to(BASE)))
    return found


def make_po():
    """Écrit le .po à partir des messages extraits."""
    DIR.mkdir(parents=True, exist_ok=True)
    po_file = DIR / 'django.po'
    existing = {}
    if po_file.exists():
        existing = parse_existing_po(po_file.read_text(encoding='utf-8'))

    found = extract_messages()
    # Fusionner : conserver les traductions déjà faites, ajouter les nouvelles.
    merged = {}
    for msgid in found:
        loc = found[msgid]
        old = existing.get(msgid)
        source = '; '.join(sorted(loc))
        if old:
            merged[msgid] = (old, source)
        else:
            merged[msgid] = ('', source)

    lines = []
    lines.append('msgid ""')
    lines.append('msgstr ""')
    lines.append('"Project-Id-Version: Care Circle 1.0\\n"')
    lines.append('"Report-Msgid-Bugs-To: \\n"')
    lines.append('"POT-Creation-Date: 2026-09-08 00:00+0000\\n"')
    lines.append('"PO-Revision-Date: 2026-09-08 00:00+0000\\n"')
    lines.append('"Last-Translator: Care Circle\\n"')
    lines.append('"Language-Team: Care Circle <no@care.circle>\\n"')
    lines.append('"Language: en\\n"')
    lines.append('"MIME-Version: 1.0\\n"')
    lines.append('"Content-Type: text/plain; charset=UTF-8\\n"')
    lines.append('"Content-Transfer-Encoding: 8bit\\n"')
    lines.append('"Plural-Forms: nplurals=2; plural=(n != 1);\\n"')
    lines.append('')
    for msgid, (trans, source) in sorted(merged.items()):
        lines.append(f'# {source}')
        lines.append(f'msgid "{_escape(msgid)}"')
        lines.append(f'msgstr "{_escape(trans)}"')
        lines.append('')
    new_content = '\n'.join(lines)
    po_file.write_text(new_content, encoding='utf-8')
    print(f'PO écrit : {po_file} ({len(merged)} messages)')


def _escape(s):
    return (s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n'))


def parse_existing_po(text):
    """Relit un .po existant -> {msgid: msgstr}."""
    entries = {}
    msgid = None
    msgstr = ''
    reading_msgid = False
    reading_msgstr = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('msgid '):
            if msgid is not None:
                entries[msgid] = msgstr
            msgid = _dec_multi(line, 'msgid ')
            msgstr = ''
            reading_msgid = True
            reading_msgstr = False
        elif line.startswith('msgstr '):
            msgstr = _dec_multi(line, 'msgstr ')
            reading_msgid = False
            reading_msgstr = True
        elif line.startswith('"'):
            piece = _unescape(line[1:-1])
            if reading_msgid:
                msgid += piece
            elif reading_msgstr:
                msgstr += piece
        else:
            reading_msgid = False
            reading_msgstr = False
    if msgid is not None:
        entries[msgid] = msgstr
    return entries


def _dec_multi(line, prefix):
    value = line[len(prefix):].strip()
    if value.startswith('"') and value.endswith('"'):
        return _unescape(value[1:-1])
    return ''


def _unescape(s):
    return (s.replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n'))


def compile_mo():
    """Compile django.po -> django.mo via Babel (équivalent msgfmt)."""
    from babel.messages.mofile import write_mo
    from babel.messages.pofile import read_po

    DIR.mkdir(parents=True, exist_ok=True)
    po_file = DIR / 'django.po'
    if not po_file.exists():
        print('Pas de .po ; lancez d\'abord : extract')
        return
    po = read_po(po_file.open('rb'))
    mo_file = DIR / 'django.mo'
    with mo_file.open('wb') as f:
        write_mo(f, po)
    print(f'MO écrit : {mo_file} ({len(po)} entrées)')


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'compile'
    if cmd == 'extract':
        make_po()
    elif cmd == 'compile':
        compile_mo()
    else:
        print('Usage: python manage_translations.py [extract|compile]')
        sys.exit(1)


if __name__ == '__main__':
    main()