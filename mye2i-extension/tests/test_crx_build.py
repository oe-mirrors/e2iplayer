import base64
import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import zipfile

import pytest

sys.path.insert(0, "mye2i-extension")

import build_release as br  # noqa: E402

OPENSSL = shutil.which("openssl")
pytestmark = pytest.mark.skipif(OPENSSL is None, reason="openssl not available")


def read_varint(buf, pos):
    shift = result = 0
    while True:
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7


def fields(buf):
    out, pos = [], 0
    while pos < len(buf):
        tag, pos = read_varint(buf, pos)
        assert tag & 7 == 2, "only length-delimited fields expected"
        size, pos = read_varint(buf, pos)
        out.append((tag >> 3, buf[pos:pos + size]))
        pos += size
    return out


def parse(path):
    data = open(path, "rb").read()
    assert data[:4] == b"Cr24"
    version, header_len = struct.unpack("<II", data[4:12])
    header, zip_bytes = data[12:12 + header_len], data[12 + header_len:]
    top = fields(header)
    proof = fields([v for n, v in top if n == 2][0])
    signed = [v for n, v in top if n == 10000][0]
    return {
        "version": version,
        "top_fields": [n for n, _ in top],
        "pub": [v for n, v in proof if n == 1][0],
        "sig": [v for n, v in proof if n == 2][0],
        "signed": signed,
        "zip": zip_bytes,
    }


def signature_ok(info, tmp_path):
    payload = b"CRX3 SignedData\x00" + struct.pack("<I", len(info["signed"])) + info["signed"] + info["zip"]
    pub_pem = tmp_path / "pub.pem"
    subprocess.run([OPENSSL, "pkey", "-pubin", "-inform", "DER", "-outform", "PEM", "-out", str(pub_pem)], input=info["pub"], check=True)
    (tmp_path / "sig").write_bytes(info["sig"])
    (tmp_path / "payload").write_bytes(payload)
    result = subprocess.run([OPENSSL, "dgst", "-sha256", "-verify", str(pub_pem), "-signature", str(tmp_path / "sig"), str(tmp_path / "payload")], capture_output=True, text=True)
    return "Verified OK" in result.stdout


def make_extension(tmp_path, key=None):
    src = tmp_path / "ext"
    src.mkdir()
    manifest = {"name": "t", "version": "1.0", "manifest_version": 3}
    if key:
        manifest["key"] = key
    (src / "manifest.json").write_text(json.dumps(manifest))
    (src / "a.js").write_text("1")
    return src


def test_crx_with_throwaway_key_is_valid_and_has_no_manifest_key(tmp_path):
    src = make_extension(tmp_path, key="AAAA")  # a key that cannot match the throw-away one
    out = tmp_path / "t.crx"
    ext_id, throwaway = br.build_crx(str(src), str(tmp_path), None, str(out))
    info = parse(str(out))
    assert throwaway is True
    assert info["version"] == 3
    assert info["top_fields"] == [2, 10000]
    assert signature_ok(info, tmp_path)
    assert fields(info["signed"])[0][1] == hashlib.sha256(info["pub"]).digest()[:16]
    assert ext_id == br.extension_id(info["pub"])
    assert len(ext_id) == 32
    assert set(ext_id) <= set("abcdefghijklmnop")
    packed = json.loads(zipfile.ZipFile(io.BytesIO(info["zip"])).read("manifest.json"))
    assert "key" not in packed


def test_crx_with_own_key_keeps_matching_manifest_key(tmp_path):
    pem = tmp_path / "k.pem"
    pem.write_bytes(subprocess.run([OPENSSL, "genrsa", "2048"], stdout=subprocess.PIPE, check=True).stdout)
    pub_b64 = base64.b64encode(br.public_key_der(str(pem))).decode()
    src = make_extension(tmp_path, key=pub_b64)
    out = tmp_path / "o.crx"
    ext_id, throwaway = br.build_crx(str(src), str(tmp_path), str(pem), str(out))
    info = parse(str(out))
    assert throwaway is False
    assert signature_ok(info, tmp_path)
    assert json.loads(zipfile.ZipFile(io.BytesIO(info["zip"])).read("manifest.json"))["key"] == pub_b64
    assert ext_id == br.extension_id(base64.b64decode(pub_b64))


def test_two_throwaway_builds_get_different_ids(tmp_path):
    src = make_extension(tmp_path)
    ids = []
    for name in ("a", "b"):
        work = tmp_path / name
        work.mkdir()
        ids.append(br.build_crx(str(src), str(work), None, str(tmp_path / (name + ".crx")))[0])
    assert ids[0] != ids[1]


def test_extension_id_of_the_shipped_key():
    manifest = json.load(open(os.path.join("mye2i-extension", "manifest.json")))
    assert br.extension_id(base64.b64decode(manifest["key"])) == "cdommeolkoiklmmlnmcommlfbljbelac"


def test_earlier_build_output_is_not_packed_into_the_next_build(tmp_path):
    dist = os.path.join(br.HERE, "dist")
    made = not os.path.isdir(dist)
    os.makedirs(dist, exist_ok=True)
    marker = os.path.join(dist, "leftover-from-earlier-build.zip")
    open(marker, "wb").close()
    try:
        target = tmp_path / "copy"
        target.mkdir()
        br.copy_tree(str(target))
        assert "dist" not in os.listdir(str(target))
    finally:
        os.remove(marker)
        if made:
            os.rmdir(dist)
