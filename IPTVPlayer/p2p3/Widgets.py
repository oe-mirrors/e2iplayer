#from Plugins.Extensions.IPTVPlayer.p2p3.Widgets import getWidgetText, innerWidgetTextRight

def getWidgetText(widgetPointer):
    try:
        return(widgetPointer.Text)
    except Exception:
        try:
            return(widgetPointer.textU)
        except Exception:
            return(widgetPointer.text)
            
def innerWidgetTextRight(widgetPointer):
    try:
        return(widgetPointer.innerright())
    except Exception:
        return(widgetPointer.innerRight())
