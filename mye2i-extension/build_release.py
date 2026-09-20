# Builds the release files for the MyE2i extension:
#   mye2iv3-latest.zip   unpacked folder (mye2iv3/) for "Load unpacked"; this is
#                        what UPDATE_URL in scripts/mye2iserver.py points to
#   mye2iv3-latest.crx   Chrome package, with --crx (or --pem). Chrome/Edge do not
#                        install it outside policies or developer mode. Signed with
#                        --pem if given (fixed extension ID, keeps the "key" of the
#                        manifest), otherwise with a throw-away key generated for
#                        this run - then the .crx gets a new extension ID every
#                        build and its manifest is written WITHOUT "key". Written by
#                        the code below (CRX3), needs only `openssl`, no browser.
#   mye2iv3-firefox-unsigned.xpi
#                        Firefox build (same sources, generated manifest),
#                        with --firefox. Firefox release/beta only installs it
#                        after Mozilla signed it, see README ("Firefox").
# Usage: python build_release.py [--crx] [--pem path/to/mye2i-extension.pem]
#                                [--firefox] [--out dir]
import argparse
import base64
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKIP = {'build_release.py', '__pycache__', 'tests', 'dist'}

FIREFOX_ADDON_ID = 'mye2iv3@e2iplayer'


def firefox_manifest(manifest):
    """Chrome manifest -> Firefox manifest (MV3 with an event page)."""
    m = dict(manifest)
    m.pop('key', None)  # Chrome-only, fixes the Chrome extension ID
    m['background'] = {'scripts': ['scripts/background.js']}
    # Firefox ignores the fragment in include_globs; background.js injects the
    # fragment-triggered scripts itself there (see IS_FIREFOX in background.js)
    m['content_scripts'] = [c for c in m['content_scripts'] if 'contentscripts/e2it.js' in c['js']]
    m['browser_specific_settings'] = {'gecko': {
        'id': FIREFOX_ADDON_ID,
        # 128: scripting/content_scripts "world": "MAIN"
        'strict_min_version': '128.0',
        'data_collection_permissions': {'required': ['none']},
    }}
    return m


def copy_tree(dst):
    for name in os.listdir(HERE):
        if name in SKIP or name.endswith(('.zip', '.crx')):
            continue
        src = os.path.join(HERE, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dst, name), ignore=shutil.ignore_patterns('__pycache__'))
        else:
            shutil.copy2(src, os.path.join(dst, name))


def zip_dir(directory, zip_path, top=''):
    """Zip `directory`; entries are placed below `top` (empty = archive root)."""
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(directory):
            for name in sorted(files):
                full = os.path.join(root, name)
                arcname = os.path.relpath(full, directory).replace(os.sep, '/')
                z.write(full, (top + '/' + arcname) if top else arcname)


# ---------------------------------------------------------------------------
# CRX3 (Chrome package format 3): "Cr24", version 3, header length, protobuf header,
# then the zip. The header carries the public key + an RSA-SHA256 signature over
# "CRX3 SignedData\0" + len(signed_header_data) + signed_header_data + zip, and
# signed_header_data holds crx_id = first 16 bytes of sha256(public key), which is
# what the extension ID is made of.
def _openssl(*args, data=None):
    exe = shutil.which('openssl')
    if not exe:
        sys.exit('openssl not found - it is needed to sign the .crx')
    return subprocess.run([exe] + list(args), input=data, stdout=subprocess.PIPE, check=True).stdout


def _varint(number):
    out = bytearray()
    while True:
        byte = number & 0x7f
        number >>= 7
        out.append(byte | (0x80 if number else 0))
        if not number:
            return bytes(out)


def _field(number, payload):
    """Protobuf length-delimited field."""
    return _varint((number << 3) | 2) + _varint(len(payload)) + payload


def public_key_der(pem_path):
    return _openssl('rsa', '-in', pem_path, '-pubout', '-outform', 'DER')


def crx3(zip_bytes, pem_path):
    pub_der = public_key_der(pem_path)
    crx_id = hashlib.sha256(pub_der).digest()[:16]
    signed_header_data = _field(1, crx_id)
    payload = b'CRX3 SignedData\x00' + struct.pack('<I', len(signed_header_data)) + signed_header_data + zip_bytes
    signature = _openssl('dgst', '-sha256', '-sign', pem_path, data=payload)
    header = _field(2, _field(1, pub_der) + _field(2, signature)) + _field(10000, signed_header_data)
    return b'Cr24' + struct.pack('<II', 3, len(header)) + header + zip_bytes


def extension_id(pub_der):
    """Chrome extension ID: first 16 bytes of sha256(public key), hex digits mapped to a-p."""
    return ''.join(chr(ord('a') + int(c, 16)) for c in hashlib.sha256(pub_der).hexdigest()[:32])


def build_crx(build_dir, tmp, pem, out_path):
    key_path = pem
    if not key_path:
        key_path = os.path.join(tmp, 'throwaway.pem')
        with open(key_path, 'wb') as f:
            f.write(_openssl('genrsa', '2048'))
    pub_b64 = base64.b64encode(public_key_der(key_path)).decode('ascii')

    crx_dir = os.path.join(tmp, 'crx')
    if os.path.exists(crx_dir):
        shutil.rmtree(crx_dir)
    shutil.copytree(build_dir, crx_dir)
    manifest_path = os.path.join(crx_dir, 'manifest.json')
    with open(manifest_path, encoding='utf-8') as f:
        manifest = json.load(f)
    if manifest.get('key') and manifest['key'] != pub_b64:
        # signed with another key than the manifest pins: Chrome would reject the
        # mismatch, so the package takes the ID of the key that signed it
        del manifest['key']
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    zip_path = os.path.join(tmp, 'crx.zip')
    zip_dir(crx_dir, zip_path)
    with open(zip_path, 'rb') as f:
        data = crx3(f.read(), key_path)
    with open(out_path, 'wb') as f:
        f.write(data)
    return extension_id(base64.b64decode(pub_b64)), not pem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--crx', action='store_true', help='also build the .crx (throw-away key unless --pem is given)')
    ap.add_argument('--pem', help='signing key for the .crx (implies --crx)')
    ap.add_argument('--firefox', action='store_true', help='also build the unsigned Firefox .xpi')
    ap.add_argument('--out', default=os.path.join(HERE, 'dist'))
    args = ap.parse_args()

    with open(os.path.join(HERE, 'manifest.json'), encoding='utf-8') as f:
        chrome_manifest = json.load(f)
    version = chrome_manifest['version']
    os.makedirs(args.out, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        build = os.path.join(tmp, 'mye2iv3')
        os.makedirs(build)
        copy_tree(build)

        zip_path = os.path.join(args.out, 'mye2iv3-latest.zip')
        zip_dir(build, zip_path, top='mye2iv3')
        print('zip: %s (v%s)' % (zip_path, version))

        if args.firefox:
            ff = os.path.join(tmp, 'firefox')
            os.makedirs(ff)
            copy_tree(ff)
            with open(os.path.join(ff, 'manifest.json'), 'w', encoding='utf-8') as f:
                json.dump(firefox_manifest(chrome_manifest), f, indent=2, ensure_ascii=False)
            xpi_path = os.path.join(args.out, 'mye2iv3-firefox-unsigned.xpi')
            zip_dir(ff, xpi_path)
            print('xpi: %s (v%s, unsigned)' % (xpi_path, version))

        if args.crx or args.pem:
            crx_path = os.path.join(args.out, 'mye2iv3-latest.crx')
            ext_id, throwaway = build_crx(build, tmp, args.pem, crx_path)
            print('crx: %s (extension ID %s%s)' % (crx_path, ext_id, ', throw-away key - new ID every build' if throwaway else ''))


if __name__ == '__main__':
    main()
