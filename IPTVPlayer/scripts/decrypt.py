# -*- coding: utf-8 -*-

import sys


def printDBG(strDat):
    print("%s" % strDat)
    #print("%s" % strDat, file=sys.stderr)


def decrypt_file(file, key):
    from crypto.cipher.aes import AES
    from crypto.cipher.base import noPadding

    cipher = AES(key, keySize=len(key), padding=noPadding())

    data = ''
    with open(file, "rb") as f:
        data = f.read()

    with open(file, "wb") as f:
        offset = 0
        while True:
            for enc in [True, False]:
                if enc:
                    chunk = data[offset:offset + len(key)]
                    offset += len(key)
                else:
                    chunk = data[offset:offset + len(key) * 1000]
                    offset += len(key) * 1000

                if len(chunk) == len(key):
                    chunk = cipher.decrypt(chunk)

                f.write(chunk)
            if not chunk:
                break
    f.close()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        printDBG('Please provide libsPath, filePath, keyPath')
        sys.exit(1)

    libsPath = sys.argv[1]
    file = sys.argv[2]
    keyPath = sys.argv[3]
    with open(keyPath, "rb") as f:
        key = f.read()

    sys.path.insert(1, libsPath)
    if sys.version_info[0] >= 3: #PY3
        sys.path.append('/usr/lib/enigma2/python/Plugins/Extensions/IPTVPlayer/libs/crypto/cipher')

    decrypt_file(file, key)
    sys.exit(0)
