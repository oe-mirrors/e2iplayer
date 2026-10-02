# -*- coding: utf-8 -*-
# Config entries for credentials: passwords / API keys never show in a config list (like the PIN), empty
# login and secret fields show a placeholder. Only the display changes - the value is stored and read like any
# ConfigText, so hosts and providers keep using .value. OK opens the virtual keyboard with the clear text.
from Components.config import ConfigText, ConfigPassword

LOGIN_PLACEHOLDER = 'xxxxx'
SECRET_PLACEHOLDER = '*****'


def _shown(multi, text):
    # ConfigText.getMulti: (type, text, marks) - and (type, text) for a read-only entry on some images
    multi = list(multi)
    multi[1] = text
    if len(multi) > 2:
        multi[2] = []  # no cursor mark inside the masked text
    return tuple(multi)


class ConfigSecret(ConfigPassword):
    """password, API key, token: '*' per character in every config list, also in the selected row (the
    images show it there); '*****' when empty. A ConfigPassword, so the web interface never sends it out."""

    def __init__(self, default='', fixed_size=False, visible_width=False):
        ConfigPassword.__init__(self, default=default, fixed_size=fixed_size, visible_width=visible_width)

    def getMulti(self, selected):
        # ConfigPassword.getMulti shows the text while the row is selected - this one never does
        multi = ConfigText.getMulti(self, selected)
        return _shown(multi, '*' * len(self.value) if self.value else SECRET_PLACEHOLDER)


class ConfigLogin(ConfigText):
    """login / user name / e-mail: shown as it is, 'xxxxx' while nothing is entered"""

    def __init__(self, default='', fixed_size=False, visible_width=False):
        ConfigText.__init__(self, default=default, fixed_size=fixed_size, visible_width=visible_width)

    def getMulti(self, selected):
        multi = ConfigText.getMulti(self, selected)
        if self.value:
            return multi
        return _shown(multi, LOGIN_PLACEHOLDER)
