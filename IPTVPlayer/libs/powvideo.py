# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################

from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc 
from Plugins.Extensions.IPTVPlayer.tools.e2ijs import js_execute, js_execute_ext
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads, dumps as json_dumps

###################################################
# FOREIGN import
###################################################

import re

def swapUrl(html_data, strToSwap):
    printDBG("Powvideo swapUrl library")

    # get javascript code
    m = re.search("(?P<code1>var _0x[a-e0-9]{4,6}=\[.*?)(?P<code2>Array\[.*?;\};)", html_data)

    if not m:
        return strToSwap

    code1 = m.groupdict().get('code1','')
    code2 = m.groupdict().get('code2','')

    if code1=='' or code2=='':
        return strToSwap
        
    printDBG("-------------- swap code part 1 -------------")
    printDBG(code1)
    printDBG("-------------- swap code part 2 -------------") 
    printDBG(code2)

    #look for all string codes to replace in code2
    m = re.search("(?P<varName>_0x[a-f0-9]{3,6})", code2)
    
    if not m:
        return strToSwap
    
    varName = m.group('varName')
    strings = re.findall("(?P<varName>" + varName + ")\('(?P<varNumber>0x[a-f0-9]{1,2})','(?P<varCode>[^']+?)'\)", code2)

    if strings:
        
        # it creates a new code for writing decoded string values    
        code3 = "console.log(\"ss={}\");\n"
        for s in strings:
            code3 = code3 + "console.log(\"ss.update({'" + s[1] +"' : '\" + "+ s[0]+"('"+ s[1]+ "','"+s[2] + "') + \"'})\");\n"

        js_code = code1 +  "\n" + "\n" + code3 
        
        printDBG("-------- javascript for decoding strings ------ ")
        printDBG(js_code)
    
        # exec with duktape
        ret = js_execute( js_code )
        if ret['sts'] and 0 == ret['code']:
            response = ret['data']
            printDBG("-------- duktape answer ------ ")
            printDBG(response)
            
            # run python code to populate string dict
            exec(response)
            
            # make changes in code2
            for x in ss:
                code2 = re.sub( varName +"\('" + x +"','[^']+?'\)" ,"'" + ss[x] + "'", code2)

            printDBG("-------- code2 after substitutions ------ ")
            printDBG(code2)

            varT = re.findall("(_0x[0-9a-z]{4,7})\[['\"]file['\"]\]", code2)
            if varT:
                code2 = code2.replace(varT[0],"t")
                code2= re.findall("(t\[['\"]file['\"]\].*?)return t", code2)
                if code2:
                    code2 = code2[0]
                    code2 = code2.replace("eval(","console.log(")
                    
                    # exec with duktape to show swap javascript code
                    js_code = "var t={file:\"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\"}\n" + code2 

                    printDBG("-------- javascript to show swap function ------ ")
                    printDBG(js_code)

                    # exec with duktape
                    ret = js_execute( js_code )
                    if ret['sts'] and 0 == ret['code']:
                        response = ret['data']
                        printDBG("-------- duktape answer ------ ")
                        printDBG(response)
                        
                        code2 = re.sub("console.log\(_0x[0-9a-f]{4,7}\);", response + "\n", code2)
                        code2 = re.sub("\$\([^\)]+?\)", "xxx" , code2)

                        printDBG("-------- code2 after substitutions ------ ")
                        printDBG(code2)
                        
                        js_code = "var navigator={ userAgent : \"Mozilla\"}; var xxx={ thing : {}, data : function(a, b ){ if (typeof b == 'undefined'){ return this.thing[a]; } else { this.thing[a]=b;} } }; \n"
                        js_code = js_code + "var t = { file : \"%s\" }\n" % strToSwap + code2 + "console.log(t[\"file\"]);"

                        printDBG("-------- final javascript code ------ ")
                        printDBG(js_code)

                        # exec with duktape
                        ret = js_execute( js_code )
                        if ret['sts'] and 0 == ret['code']:
                            response = ret['data']
                            printDBG("-------- duktape answer ------ ")
                            printDBG(response)
                            
                            return response.replace('\n','')
                            
                        else:
                            printDBG("Duktape execution failed! check code")
                        
                    else:
                        printDBG("Duktape execution failed! check code")

        else:
            printDBG("Duktape execution failed! check code")

    return strToSwap

