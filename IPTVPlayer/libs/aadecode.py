        def aadecode(text):
            text = re.sub(r"\s+|/\*.*?\*/", "", text)
            data = text.split("+(???)[?o?]")[1]
            chars = data.split("+(???)[???]+")[1:]

            txt = ""
            for char in chars:
                char = char \
                    .replace("(o???o)","u") \
                    .replace("c", "0") \
                    .replace("(???)['0']", "c") \
                    .replace("???", "1") \
                    .replace("!+[]", "1") \
                    .replace("-~", "1+") \
                    .replace("o", "3") \
                    .replace("_", "3") \
                    .replace("???", "4") \
                    .replace("(+", "(")
                char = re.sub(r'\((\d)\)', r'\1', char)

                c = ""; subchar = ""
                for v in char:
                    c+= v
                    try: x = c; subchar+= str(eval(x)); c = ""
                    except: pass
                if subchar != '': txt+= subchar + "|"
            txt = txt[:-1].replace('+','')

            txt_result = "".join([ chr(int(n, 8)) for n in txt.split('|') ])
            return txt_result