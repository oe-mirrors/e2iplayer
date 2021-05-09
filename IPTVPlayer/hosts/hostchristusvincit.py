# -*- coding: utf-8 -*-
###################################################
# LOCAL import
###################################################
from Components.config import config, ConfigSelection, ConfigYesNo, getConfigListEntry
from Plugins.Extensions.IPTVPlayer.components.iptvplayerinit import TranslateTXT as _
from Plugins.Extensions.IPTVPlayer.components.ihost import CHostBase, CBaseHostClass
from Plugins.Extensions.IPTVPlayer.tools.iptvtools import printDBG, printExc, MergeDicts, rm, formatBytes, CSelOneLink
from Plugins.Extensions.IPTVPlayer.tools.iptvtypes import strwithmeta
from Plugins.Extensions.IPTVPlayer.libs.urlparserhelper import getDirectM3U8Playlist
from Plugins.Extensions.IPTVPlayer.libs import ph
from Plugins.Extensions.IPTVPlayer.libs.e2ijson import loads as json_loads
###################################################

###################################################
# FOREIGN import
###################################################
import re
import time
import urllib
from datetime import timedelta
###################################################

config.plugins.iptvplayer.christusvincit_preferred_bitrate = ConfigSelection(default="99999999", choices=[("0", _("the lowest")),
                                                                                                    ("360000", "360000"),
                                                                                                    ("590000", "590000"),
                                                                                                    ("820000", "820000"),
                                                                                                    ("1250000", "1250000"),
                                                                                                    ("1750000", "1750000"),
                                                                                                    ("2850000", "2850000"),
                                                                                                    ("5420000", "5420000"),
                                                                                                    ("6500000", "6500000"),
                                                                                                    ("9100000", "9100000"),
                                                                                                    ("99999999", _("the highest")),
                                                                                                    ])
config.plugins.iptvplayer.christusvincit_use_preferred_bitrate = ConfigYesNo(default=True)

###################################################
# Config options for HOST
###################################################


def GetConfigList():
    optionList = []
    optionList.append(getConfigListEntry("Preferred video bitrate", config.plugins.iptvplayer.christusvincit_preferred_bitrate))
    optionList.append(getConfigListEntry("Use preferred video bitrate", config.plugins.iptvplayer.christusvincit_use_preferred_bitrate))
    return optionList
###################################################


def gettytul():
    return 'http://christusvincit-tv.pl/'


class Christusvincit(CBaseHostClass):

    def __init__(self):
        CBaseHostClass.__init__(self, {'history': 'christusvincit-tv.pl', 'cookie': 'christusvincit-tv.pl.cookie'})

        self.HTTP_HEADER = self.cm.getDefaultHeader(browser='chrome')
        self.defaultParams = {'header': self.HTTP_HEADER}

        self.MAIN_URL = 'http://christusvincit-tv.pl/'
        self.DEFAULT_ICON_URL = 'http://christusvincit-tv.pl/images/christusbg.jpg'
        self.reImgObj = re.compile(r'''<img[^>]+?src=(['"])([^>]*?)(?:\1)''', re.I)
        self.titlesMap = {'wspolodkupicielka': 'Współodkupicielka i Pośredniczka Wszelkich Łask',
                          'rekolkap': 'Rekolekcje kap\xc5\x82a\xc5\x84skie',
                          'medalionbogaojca': 'Medalion Boga Ojca',
                          'mojkosciele': 'M\xc3\xb3j Ko\xc5\x9bciele co oni Tobie uczynili',
                          'redemptorismater': 'Redemptoris Mater',
                          'luter': 'Luter \xc5\x9bwiadkiem Chrystusa ?',
                          'bn2017': 'Bo\xc5\xbce Narodzenie w tajemnicy Tr\xc3\xb3jcy Przenaj\xc5\x9bwi\xc4\x99tszej',
                          'synowielaski': 'Synowie \xc5\x82aski przywo\xc5\x82ajcie narody i miasta',
                          'witajoblubienico': 'Witaj Oblubienico Ducha \xc5\x9awi\xc4\x99tego',
                          'mowaboga': 'Or\xc4\x99dzia-Mowa Boga',
                          'chwalaboga': 'Chwa\xc5\x82a Boga-doszli\xc5\x9bmy do absurdu',
                          'maciewybor': 'Macie wyb\xc3\xb3r mi\xc4\x99dzy Niebem a Piek\xc5\x82em',
                          'kontds': 'Kontemplacja Ducha \xc5\x9awi\xc4\x99tego',
                          'listyp': 'Kontemplacja Ducha \xc5\x9awi\xc4\x99tego w listach \xc5\x9bw. Paw\xc5\x82a',
                          'prosby': 'Pro\xc5\x9bby Matki Bo\xc5\xbcej',
                          'zyciesak': '\xc5\xbbycie sakramentalne wg. \xc5\x9bw. Agnieszki',
                          'objquito': 'Objawienia w Quito',
                          'poznajmy': 'Poznajmy Wroga',
                          'tajemnicabn': 'Tajemnica Bo\xc5\xbcego Narodzenia',
                          'lag2016': 'Ma\xc5\x82a Intronizacja 2016',
                          'dsroz': 'Duchu \xc5\x9awi\xc4\x99ty Rozpal',
                          'kontemplacjajch': 'Kontemplacja Jezusa Chrystusa',
                          'cierpienieo': 'Cierpienie Oblubienicy',
                          'rekokap': 'Rekolekcje o kap\xc5\x82a\xc5\x84stwie',
                          'intronizacja': 'Intronizacja-mo\xc5\xbce si\xc4\x99 zegn\xc4\x85',
                          'quito_nowe': 'Objawienia Matki Bo\xc5\xbcej z Quito',
                          'bogmowi': 'B\xc3\xb3g m\xc3\xb3wi do swego kap\xc5\x82ana',
                          'kazanieslowa1': 'S\xc5\x82owa ks.P.Natanka do ks.kard.S.Dziwisza',
                          'rekolekcje': 'Rekolekcje o Mszy \xc5\x9bw.',
                          'glebiamodlitwy': 'G\xc5\x82\xc4\x99bia modlitwy Ojcze nasz',
                          'tatojestem': 'Tato jestem',
                          '30-lecieksp': '30-lecie kap\xc5\x82a\xc5\x84stwa ks.P.M.Natanka',
                          'gazetym': 'Gazety m\xc3\xb3wi\xc4\x85 o ksi\xc4\x99dzu',
                          'regulam': 'Regu\xc5\x82a Maria\xc5\x84ska',
                          'bozatajemnica': 'Bo\xc5\xbca Tajemnica Maryja',
                          'kochamkaplana': 'Kocham polskiego katolickiego kap\xc5\x82ana',
                          'bitwa_o_post': 'Bitwa o post',
                          'tajemnice_glowny': 'Tajemnica r\xc3\xb3\xc5\xbca\xc5\x84ca \xc5\x9bwi\xc4\x99tego',
                          'bog_umacnia': 'B\xc3\xb3g umacnia',
                          'bajka_sprawozdanie_komisarzy': 'Bajka sprawozdanie komisarzy',
                          'dlaczego_rok_1960': 'Dlaczego rok 1960? \xc5\xbb\xc4\x85dania Matki Bo\xc5\xbcej Fatimskiej',
                          'Polsko_Bog_jeszcze_czeka_na_Ciebie': 'Polsko, B\xc3\xb3g jeszcze czeka na Ciebie',
                          'istota_ojcostwa_boga': 'Istota Ojcostwa Boga',
                          'polsko_ciebie_maryja_uratuje': 'Polsko,Ciebie tylko Maryja uratuje',
                          'katechezy_boga': 'Katechezy Boga Ojca',
                          'potega_slowa': 'Pot\xc4\x99ga S\xc5\x82owa Bo\xc5\xbcego',
                          'rozwazania_drogi_krzyzowej': 'Rozwa\xc5\xbcania drogi krzy\xc5\xbcowej',
                          'uczynmnieniewolnikiemtwojejmilosci': 'Uczy\xc5\x84 Mnie niewolnikiem Twojej mi\xc5\x82o\xc5\x9bci',
                          'drogapojednania': 'Droga pojednania',
                          'leniwiwwierze': 'Leniwi w wierze',
                          'kazaniapogrzebowe': 'Kazania pogrzebowe',
                          'czysciec': 'Tajemnica czy\xc5\x9b\xc4\x87ca',
                          'cierpienieboga': 'Cierpienie Boga',
                          'czynie': 'Czyni\xc4\x99 nieprzyja\xc5\xba\xc5\x84 mi\xc4\x99dzy \xc5\xbcywio\xc5\x82ami',
                          'swiatduchaiswiatciala': '\xc5\x9awiat ducha i \xc5\x9bwiat cia\xc5\x82a',
                          'medalik_benedykta': 'Medalik \xc5\x9bw. Benedykta',
                          'triduum2012': '\xc5\x9awi\xc4\x99te Triduum',
                          'grzechy': 'Cztery grzechy g\xc5\x82\xc3\xb3wne ks. Piotra Natanka',
                          'plomien': 'Ko\xc5\x9bci\xc3\xb3\xc5\x82 p\xc5\x82onie',
                          'pokuta': 'Sakrament pokuty - niezmierzona Mi\xc5\x82o\xc5\x9b\xc4\x87 Boga',
                          'droga2': 'Droga Czas\xc3\xb3w Ostatecznych',
                          'niebianskie': 'B\xc3\xb3g powala z n\xc3\xb3g - katechezy niebia\xc5\x84skie',
                          'objawienia': 'Objawienia w Montichiari - Godzina \xc5\x81aski',
                          'zertka': 'Polacy, B\xc3\xb3g chce si\xc4\x99 podeprze\xc4\x87 o Wasz\xc4\x85 ofiar\xc4\x99',
                          'krol_b': 'Polsko, oto Kr\xc3\xb3l nadchodzi!',
                          'kaplani1': 'Kap\xc5\x82ani Chrystusowi czemu \xc5\x9bpicie?',
                          'polska1': 'Kocham Polsk\xc4\x99',
                          'modernizm': 'Rozsadzenie Ko\xc5\x9bcio\xc5\x82a od wewn\xc4\x85trz',
                          'msza_sw': 'O Mszy \xc5\x9awi\xc4\x99tej',
                          'encykliki': 'Encykliki papieskie',
                          'kaplan': 'Tylko kap\xc5\x82an katolicki uratuje \xc5\x9bwiat',
                          'dollar_s': 'Lucyferyczny plan zniszczenia Ko\xc5\x9bcio\xc5\x82a \xc5\x9awi\xc4\x99tego',
                          'list_kaplani': 'List Otwarty do Kap\xc5\x82an\xc3\xb3w Ko\xc5\x9bcio\xc5\x82a Katolickiego',
                          'gietrzwald': 'Katechezy gietrzwa\xc5\x82dzkie',
                          'kongresmaryjny': 'Kongres Maryjny',
                          'czestochowa_kategoria': 'Pielgrzymki do Cz\xc4\x99stochowy',
                          'czest102015': 'Cz\xc4\x99stochowa 2015',
                          'jasna_gora': 'Jasna G\xc3\xb3ra ',
                          'krolowa2018': 'Kr\xc3\xb3lowa idzie do Sejmu 2018 ',
                          'wars2017': 'Kr\xc3\xb3lowa idzie do Sejmu 2017 ',
                          'marsz2016': 'Kr\xc3\xb3lowa idzie do Sejmu 2016 ',
                          'kategoria_niepokalane_poczecie_nmp': 'Niepokalane Pocz\xc4\x99cie NMP',
                          'kategoria_chrystus_krol': 'Chrystus Kr\xc3\xb3l - S\xc5\x82owa do Rycerzy',
                          'kategoria_bog_ojciec': 'B\xc3\xb3g Ojciec',
                          'kategoria_dwa_serca': 'Dwa Serca',
                          'kategoria_najdrozsza_krew': 'Najdro\xc5\xbcsza Krew Pana Jezusa',
                          'slowodorycerzy1': 'S\xc5\x82owa do Rycerzy Chrystusa Kr\xc3\xb3la',
                          'reformalit': 'Reforma liturgiczna',
                          'dwaserca2018': 'Dwa Serca 2018',
                          'dwojgaserc2018': 'Uroczysto\xc5\x9b\xc4\x87 Dwojga Serc 29.09.2018r.',
                          'sekretlasal': 'Sekret La Salette i kompleks ksi\xc4\x99\xc5\xbcy saletyn\xc3\xb3w',
                          'kazkrew2018': 'O Krwi Najdro\xc5\xbcsza 2018',
                          'koronacjamb2018': 'Koronacja Matki Bo\xc5\xbcej z Quito',
                          'quito2018': 'Objawienia Matki Bo\xc5\xbcej w Quito',
                          'cierboga': 'Cierpienie Boga w Tr\xc3\xb3jcy Jedynego',
                          'encyklikimaryjne': 'Encykliki Maryjne',
                          'uczpm': 'Uczymy si\xc4\x99 Pie\xc5\x9bni Maryjnych',
                          'manifestacjazbiorcze': 'Kr\xc3\xb3lowa idzie do Sejmu',
                          'kazschol': 'Pierwsze kazanie scholastyczne',
                          'krolowanie': 'Kr\xc3\xb3lowanie Pana Jezusa i Kr\xc3\xb3lowanie Maryi',
                          'postzbiorcze': 'Posty - Pomagamy Matce Bo\xc5\xbcej',
                          'zesrocz': 'Zestawienie roczne',
                          'domychk': 'Domy Chrystusa Kr\xc3\xb3la',
                          'zesl4062017': 'Zes\xc5\x82anie Ducha \xc5\x9awi\xc4\x99tego 04.06.2017r.',
                          'kazaniawielkanocy': 'Kazanie Czasu Wielkanocy',
                          'kfront': 'Kazanie frontowe',
                          '24meki': '24 godziny M\xc4\x99ki naszego Pana Jezusa Chrystusa',
                          'kontsj': 'Kontemplacja Naj\xc5\x9bwi\xc4\x99tszego Serca Jezusa',
                          'boguzdrawia': 'B\xc3\xb3g czyni cuda i uzdrawia',
                          'wdsnabw': 'Wieczernik Ducha \xc5\x9awi\xc4\x99tego nabo\xc5\xbce\xc5\x84stwo wieczorne',
                          'rozwazaniacz': 'Rozwa\xc5\xbcania czerwcowe',
                          'adwokat': 'Naj\xc4\x85\xc5\x82em Adwokata na godzin\xc4\x99 \xc5\x9bmierci',
                          'inner': 'Inne retransmisje',
                          'adwentglowne': 'Liturgiczne inicjacje adwentowe',
                          'objawieniawakita1': 'Objawienia w Akita',
                          'wieczornice': 'Wieczornice',
                          'burzanadp': 'Burza nad pustelni\xc4\x85',
                          'paninarodow': 'Pani Wszystkich Narod\xc3\xb3w',
                          'blogjest': 'B\xc5\x82ogos\xc5\x82awiony jestem',
                          'oduchuswietym': 'O Duchu \xc5\x9awi\xc4\x99tym',
                          'miloscspraw': 'Mi\xc5\x82o\xc5\x9b\xc4\x87 wype\xc5\x82nia si\xc4\x99 w sprawiedliwo\xc5\x9bci',
                          'refleksje': 'Refleksje betlejemskie',
                          'nasza_matka-garabandal': 'Nasza Matka - Garabandal',
                          'kazania_pasyjne_glowny': 'Kazania Pasyjne',
                          'kazania_nabozenstwa_patriotyczne': 'Kazania i nabo\xc5\xbce\xc5\x84stwa patriotyczne',
                          'w_obronie_garabandal': 'W obronie Garabandal',
                          'nabozenstwouzdrawianiaiuwalniania': 'Nabo\xc5\xbce\xc5\x84stwa uzdrawiania i uwalniania',
                          'tajemnicamszywgojcapio': 'Tajemnica Mszy \xc5\x9aw. wg \xc5\x9bw. Ojca Pio',
                          '25lecie_pustelni': '25-lecie Pustelni',
                          'ratujcie_dusze': 'Ratujcie dusze',
                          'bog_trwa_zawsze': 'B\xc3\xb3g trwa zawsze. Czas kt\xc3\xb3ry jest przeminie',
                          'quovadis': 'Quo Vadis',
                          'bitwa_pod_wiedniem': 'Bitwa pod Wiedniem',
                          'detronizacjakrola': 'Detronizacja Kr\xc3\xb3la. Oni Mnie nie chc\xc4\x85',
                          'kosciele': 'Ko\xc5\x9bciele obud\xc5\xba si\xc4\x99!',
                          'czestochowa06102012': 'Cz\xc4\x99stochowa - 06.10.2012r Rok Wiary',
                          'bruksela': 'Bruksela - wsp\xc3\xb3\xc5\x82czesny Jeroboam',
                          'wykrot': 'S\xc5\x82owa do pielgrzym\xc3\xb3w z Wykrotu',
                          'galeria_bobola_prawy': 'Rotunda \xc5\x9bw.Boboli',
                          'kimnaprawdejesteskaplanie': 'Kim naprawd\xc4\x99 jeste\xc5\x9b kap\xc5\x82anie?',
                          'objawienia_prywatne': 'Objawienia prywatne',
                          'przebaczenie': 'O naturze przebaczenia',
                          'ktokrolem': 'Kogo wybierzemy Kr\xc3\xb3lem - 01.04.2012r.',
                          'droga': 'Droga kt\xc3\xb3r\xc4\x85 id\xc4\x99, jest...',
                          'swjan': 'Wspomnienie \xc5\x9bw. Jana Ewangelisty',
                          'przyspiesze': 'Przy\xc5\x9bpiesz\xc4\x99 Dzie\xc5\x84 Mojego Przyj\xc5\x9bcia',
                          'hold1': 'Rocznica Ho\xc5\x82du Ruskiego - Msza \xc5\x9bwi\xc4\x99ta z 5.11.2011r.',
                          'uwiedzony': 'Uwiedzony \xc5\x9bwiat i ludzko\xc5\x9b\xc4\x87 - kazanie z 2 pa\xc5\xbadziernika 2011r.',
                          'oni_nie_zrobia': 'Oni nie zrobi\xc4\x85 Intronizacji',
                          'heretyk': 'Prawdziwe oblicze HERETYK\xc3\x93W i SEKCIARZY w Ko\xc5\x9bciele',
                          'baal': "Wzywam prorok\xc3\xb3w Baal'a na konfrontacj\xc4\x99",
                          'natanek1': 'ks.Natanek niepos\xc5\x82uszny?',
                          'katechezy': 'Katechezy czas\xc3\xb3w ostatecznych',
                          'ogloszenia_biezace': 'Og\xc5\x82oszenia bie\xc5\xbc\xc4\x85ce',
                          'slowodorycerzy1': 'Pilne! S\xc5\x82owa do Rycerzy Chrystusa Kr\xc3\xb3la',
                          'nowennabogojciec': 'Nowenna ku czci Boga Ojca',
                          'zakon': 'Powstaje zakon',
                          'banner_oferty_parafii': 'Oferty Parafii Internetowej',
                          'wykrot_banner': 'Nocna Pielgrzymka do Wykrotu (1-2/03/2014)',
                          'slowobozenacodzien': 'S\xc5\x82owo Bo\xc5\xbce na co dzie\xc5\x84',
                          'oredzianaczasyostateczne': 'Or\xc4\x99dzia na Czasy Ostateczne - czyta ks. Piotr',
                          'zywoty_swietych_panskich': '\xc5\xbbywoty \xc5\x9awi\xc4\x99tych Pa\xc5\x84skich',
                          'msze_swiete': 'Ca\xc5\x82e msze \xc5\x9bwi\xc4\x99te - nowe okienko',
                          'ewangeliawspol': 'Ewangelia wsp\xc3\xb3\xc5\x82cze\xc5\x9bnie',
                          'matka_swietych_polska': 'Matka \xc5\x9awi\xc4\x99tych Polska',
                          'filozofiamyslenia': 'Filozofia my\xc5\x9blenia',
                          'slowobozevaltorta': 'S\xc5\x82owo Bo\xc5\xbce na co dzie\xc5\x84 - M. Valtorta',
                          'dni_wiernych_parafii': 'Dni wiernych parafii',
                          'medugorje2018': 'Medugorje 9-17.10.2018r.',
                          'kongres2016': 'III-ci Kongres Maryjny 2016r.',
                          'iikongresmaryjny': 'II-gi Kongres Maryjny 2015r.',
                          '1kongresma': 'I-szy Kongres Maryjny 2014r.',
                          '1roczek_ks_piotra': '1-szy Roczek ks. Piotra',
                          '50teurodziny_ks_piotra': '50-te Urodziny ks. Piotra',
                          'bogojciec2018': 'Uroczysto\xc5\x9b\xc4\x87 Boga Ojca 2018',
                          'ubogojciec2017': 'Uroczysto\xc5\x9b\xc4\x87 Boga Ojca 2017',
                          'bojciec2016': 'Uroczysto\xc5\x9b\xc4\x87 Boga Ojca 2016',
                          'bogojciec2015': 'Uroczysto\xc5\x9b\xc4\x87 Boga Ojca 2015',
                          'bogojciec2014': 'Uroczysto\xc5\x9b\xc4\x87 Boga Ojca 2014',
                          'ojcostwoboga2014': 'Ojcostwo Boga 2014',
                          'boga_ojca_04082013': 'Uroczysto\xc5\x9b\xc4\x87 Boga Ojca 2013',
                          'bogaojca2012': 'Uroczysto\xc5\x9b\xc4\x87 Boga Ojca 2012',
                          '20110807': 'Uroczysto\xc5\x9b\xc4\x87 Boga Ojca 2011',
                          'milosc_boga': 'Mi\xc5\x82o\xc5\x9b\xc4\x87 Boga',
                          'dwojgaserc2017': 'Uroczysto\xc5\x9b\xc4\x87 Dwojga Serc 2017',
                          'ds2016': 'Uroczysto\xc5\x9b\xc4\x87 Dwojga Serc 2016',
                          'dwojgaserc2015': 'Uroczysto\xc5\x9b\xc4\x87 Dwojga Serc 2015',
                          'dwojgaserc2014': 'Uroczysto\xc5\x9b\xc4\x87 Dwojga Serc 2014',
                          'niepokalaneserce2014': 'Niepokalane Serce NMP 2014',
                          'dwojgaserc_28092013': 'Uroczysto\xc5\x9b\xc4\x87 Dwojga Serc 2013',
                          'uroczkrwi2017': 'Uroczysto\xc5\x9b\xc4\x87 Najdro\xc5\xbcszej Krwi Pana Jezusa 2017',
                          'krew2016': 'Uroczysto\xc5\x9b\xc4\x87 Najdro\xc5\xbcszej Krwi Pana Jezusa 2016',
                          'najkrew2015': 'Uroczysto\xc5\x9b\xc4\x87 Najdro\xc5\xbcszej Krwi Pana Jezusa 2015',
                          'najdrozszakrew2014': 'Uroczysto\xc5\x9b\xc4\x87 Najdro\xc5\xbcszej Krwi Pana Jezusa 2014',
                          'najdrozszejkrwi_07072013': 'Uroczysto\xc5\x9b\xc4\x87 Najdro\xc5\xbcszej Krwi Pana Jezusa 2013',
                          'npocz2017': 'Uroczysto\xc5\x9b\xc4\x87 Niepokalanego Pocz\xc4\x99cia NMP 2017',
                          'np2016': 'Uroczysto\xc5\x9b\xc4\x87 Niepokalanego Pocz\xc4\x99cia NMP 2016',
                          'npnmp2015': 'Uroczysto\xc5\x9b\xc4\x87 Niepokalanego Pocz\xc4\x99cia NMP 2015',
                          'npnmp2014': 'Uroczysto\xc5\x9b\xc4\x87 Niepokalanego Pocz\xc4\x99cia NMP 2014',
                          'niepokalanego_poczecia_08122013': 'Uroczysto\xc5\x9b\xc4\x87 Niepokalanego Pocz\xc4\x99cia NMP 2013',
                          'godzina_laski': 'Godzina \xc5\x82aski',
                          'odpust2012': 'Odpust Parafialny 2012',
                          'pielgrzymki_550x120': 'Pielgrzymki Odbijamy Europ\xc4\x99',
                          'chrystuskrol2018': 'Uroczysto\xc5\x9b\xc4\x87 Jezusa Chrystusa Kr\xc3\xb3la Polski 2018',
                          'podmianka': 'Podmianka - Atrapa Ko\xc5\x9bcio\xc5\x82a', }

    def listMain(self, cItem, nextCategory):
        printDBG("Christusvincit.listMain")

        sts, data = self.getPage(self.getMainUrl())
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        data = re.sub("<!--[\s\S]*?-->", "", data)
        sections = ph.rfindall(data, '</table>', ('<td', '>', 'capmain-left'), flags=0)
        for section in sections:
            self.handleSection(cItem, nextCategory, section)

        rtmpUrl = ph.search(data, '''netConnectionUrl['"\s]*?:\s*?['"](rtmp://[^'^"]+?)['"]''')[0]
        # move live to the top
        prevlist = self.currList
        self.currList = []
        for item in prevlist:
            if "na żywo" in item['title']:
                if rtmpUrl:
                    try:
                        rtmpUrl = strwithmeta(rtmpUrl, {'iptv_proto': 'rtmp', 'iptv_livestream': True})
                        params = {'title': '%s [RTMP]' % item['title'], 'url': rtmpUrl, 'type': 'video'}
                        if 'sub_items' in item:
                            item['sub_items'].append(params)
                        else:
                            item['rtmp_item'] = params
                    except Exception:
                        printExc()
                self.currList.insert(0, item)
            else:
                self.currList.append(item)

        MAIN_CAT_TAB = [{'category': 'search', 'title': _('Search'), 'search_item': True},
                        {'category': 'search_history', 'title': _('Search history'), }]
        self.listsTab(MAIN_CAT_TAB, cItem)

    def handleSection(self, cItem, nextCategory, section):
        printDBG("Christusvincit.handleSection")
        section = ph.STRIP_HTML_COMMENT_RE.sub("", section)

        tmp = section.split('</table>', 1)
        sTitle = self.cleanHtmlStr(tmp[0])
        if sTitle.lower() in ('linki',): #'kategorie'
            return
        sIcon = self.getFullUrl(ph.search(section, ph.IMAGE_SRC_URI_RE)[1])

        subItems = []
        uniques = set()
        iframes = ph.findall(section, '<center>', '</iframe>')
        if iframes:
            for iframe in iframes:
                title = self.cleanHtmlStr(iframe).split('Video Platform', 1)[0].strip()
                iframe = ph.search(iframe, ph.IFRAME_SRC_URI_RE)[1]
                if iframe in uniques:
                    continue
                uniques.add(iframe)
                if not title:
                    title = sTitle
                subItems.append(MergeDicts(cItem, {'category': nextCategory, 'title': title, 'url': iframe}))

        iframes = ph.IFRAME_SRC_URI_RE.findall(section)
        if iframes:
            for iframe in iframes:
                iframe = iframe[1]
                if iframe in uniques:
                    continue
                uniques.add(iframe)
                subItems.append(MergeDicts(cItem, {'category': nextCategory, 'title': sTitle, 'url': iframe}))
        section = ph.findall(section, ('<a', '>', ph.check(ph.any, ('articles.php', 'readarticle.php'))), '</a>')
        for item in section:
            url = self.getFullUrl(ph.search(item, ph.A_HREF_URI_RE)[1])
            icon = self.getFullUrl(ph.search(item, self.reImgObj)[1])
            title = self.cleanHtmlStr(item)
            if not title:
                title = icon.rsplit('/', 1)[-1].rsplit('.', 1)[0]
                title = self.titlesMap.get(title, title.upper())
            subItems.append(MergeDicts(cItem, {'good_for_fav': True, 'category': nextCategory, 'title': title, 'url': url, 'icon': icon}))

        if len(subItems) > 1:
            self.addDir(MergeDicts(cItem, {'category': 'sub_items', 'title': sTitle, 'icon': sIcon, 'sub_items': subItems}))
        elif len(subItems) == 1:
            params = subItems[0]
            params.update({'title': sTitle})
            self.addDir(params)

    def getPage(self, baseUrl, addParams={}, post_data=None):
        if addParams == {}:
            addParams = dict(self.defaultParams)
        return self.cm.getPage(baseUrl, addParams, post_data)

    def getFullUrl(self, url, currUrl=None):
        return CBaseHostClass.getFullUrl(self, url.replace('&amp;', '&'), currUrl)

    def listSubItems(self, cItem):
        printDBG("Christusvincit.listSubItems")
        self.currList = cItem['sub_items']

    def exploreItem(self, cItem):
        printDBG("Christusvincit.exploreItem")
        playerConfig = None

        sts, data = self.getPage(cItem['url'])
        if sts:
            cUrl = self.cm.meta['url']
            self.setMainUrl(cUrl)

            if 'articles.php' in cUrl:
                iframe = ph.search(data, ph.IFRAME_SRC_URI_RE)[1]
                if not iframe:
                    iframe = ph.find(data, ('<script', '>', 'embedIframeJs'))[1]
                    iframe = ph.getattr(iframe, 'src')

                if iframe and '?' in iframe:
                    sts, tmp = self.getPage(self.getFullUrl(iframe.replace('?', '?iframeembed=true&')))
                    if not sts:
                        return
                    playerConfig = ph.find(tmp, '{"playerConfig"', '};')[1][:-1]
                else:
                    sections = ph.find(data, '<noscript', 'scapmain-left')[1]
                    sections = ph.rfindall(sections, '</table>', ('<td', '>', 'capmain-left'), flags=0)
                    for section in sections:
                        self.handleSection(cItem, cItem['category'], section)
            else:
                playerConfig = ph.find(data, '{"playerConfig"', '};')[1][:-1]

            if playerConfig:
                try:
                    playerConfig = json_loads(playerConfig)
                    playlistResult = playerConfig.get('playlistResult', {})
                    if not playlistResult:
                        playlistResult['0'] = {'items': [playerConfig['entryResult']['meta']]}
                    for key, section in playlistResult.iteritems():
                        for item in section['items']:
                            icon = self.getFullUrl(item['thumbnailUrl'])
                            title = item['name']
                            desc = '%s | %s' % (str(timedelta(seconds=item['duration'])), item['description'])
                            params = {'title': title, 'icon': icon, 'desc': desc, 'f_id': item['id']}
                            if item.get('hlsStreamUrl'):
                                params['url'] = item['hlsStreamUrl']
                            self.addVideo(params)
                except Exception:
                    printExc()

        rtmpItem = dict(cItem).pop('rtmp_item', None)
        if rtmpItem:
            self.addVideo(rtmpItem)

    def listSearchResult(self, cItem, searchPattern, searchType):

        url = self.getFullUrl('/search.php?stext=%s&search=Szukaj&method=AND&stype=articles&forum_id=0&datelimit=0&fields=2&sort=datestamp&order=0&chars=50' % urllib.quote_plus(searchPattern))
        cItem = MergeDicts(cItem, {'category': 'list_search', 'url': url})
        self.listSearchItems(cItem)

    def listSearchItems(self, cItem):
        printDBG("Christusvincit.listSearchItems")
        page = cItem.get('page', 1)

        sts, data = self.getPage(cItem['url'])
        if not sts:
            return
        self.setMainUrl(self.cm.meta['url'])

        data = ph.find(data, 'search_result', '</table>', flags=0)[1]
        data = re.compile('''<div[^>]+?pagenav[^>]*?>''').split(data, 1)
        if len(data) == 2:
            nextPage = ph.find(data[-1], ('<a', '>%s<' % (page + 1)))[1]
            nextPage = self.getFullUrl(ph.getattr(nextPage, 'href'))
        else:
            nextPage = ''

        data = ph.findall(data[0], ('<a', '>', ph.check(ph.any, ('articles.php', 'readarticle.php'))), '</span>')
        for item in data:
            url = self.getFullUrl(ph.search(item, ph.A_HREF_URI_RE)[1])
            icon = self.getFullUrl(ph.search(item, self.reImgObj)[1])
            item = item.split('</a>', 1)
            title = self.cleanHtmlStr(item[0])
            desc = self.cleanHtmlStr(item[-1])

            self.addDir(MergeDicts(cItem, {'good_for_fav': True, 'category': 'explore_item', 'title': title, 'url': url, 'icon': icon, 'desc': desc}))
        if nextPage:
            self.addDir(MergeDicts(cItem, {'good_for_fav': False, 'title': _('Next page'), 'page': page + 1, 'url': nextPage}))

    def getLinksForVideo(self, cItem):
        urlsTab = []

        if 'url' in cItem and cItem['url'].startswith('rtmp://'):
            urlsTab = [{'name': 'rtmp', 'url': cItem['url'], 'need_resolve':0}]
        elif 'url' in cItem:
            urlsTab = getDirectM3U8Playlist(cItem['url'])
        else:
            url = 'http://mediaserwer3.christusvincit-tv.pl/api_v3/index.php?service=multirequest&apiVersion=3.1&expiry=86400&clientTag=kwidget%3Av2.41&format=1&ignoreNull=1&action=null&1:service=session&1:action=startWidgetSession&1:widgetId=_100&2:ks=%7B1%3Aresult%3Aks%7D&2:service=baseentry&2:action=list&2:filter:objectType=KalturaBaseEntryFilter&2:filter:redirectFromEntryId='
            url += cItem['f_id']
            url += '&3:ks=%7B1%3Aresult%3Aks%7D&3:contextDataParams:referrer=http%3A%2F%2Fmediaserwer3.christusvincit-tv.pl&3:contextDataParams:objectType=KalturaEntryContextDataParams&3:contextDataParams:flavorTags=all&3:contextDataParams:streamerType=auto&3:service=baseentry&3:entryId=%7B2%3Aresult%3Aobjects%3A0%3Aid%7D&3:action=getContextData&4:ks=%7B1%3Aresult%3Aks%7D&4:service=metadata_metadata&4:action=list&4:version=-1&4:filter:metadataObjectTypeEqual=1&4:filter:orderBy=%2BcreatedAt&4:filter:objectIdEqual=%7B2%3Aresult%3Aobjects%3A0%3Aid%7D&4:pager:pageSize=1&5:ks=%7B1%3Aresult%3Aks%7D&5:service=cuepoint_cuepoint&5:action=list&5:filter:objectType=KalturaCuePointFilter&5:filter:orderBy=%2BstartTime&5:filter:statusEqual=1&5:filter:entryIdEqual=%7B2%3Aresult%3Aobjects%3A0%3Aid%7D&kalsig=404d9c08e114ce91328cd739e5151b80'
            sts, data = self.getPage(url)
            if not sts:
                return []

            try:
                data = json_loads(data)
                baseUrl = data[1]['objects'][0]['dataUrl']
                for item in data[2]['flavorAssets']:
                    if item['fileExt'] != 'mp4' or not item['isWeb']:
                        continue
                    item['bitrate'] *= 1024
                    name = '%sx%s %s, bitrate: %s' % (item['width'], item['height'], formatBytes(item['size'] * 1024), item['bitrate'])
                    url = baseUrl.replace('/format/', '/flavorId/%s/format/' % item['id'])
                    urlsTab.append({'name': name, 'url': url, 'need_resolve': 0, 'bitrate': item['bitrate'], 'original': item['isOriginal']})
                urlsTab.sort(key=lambda x: x['bitrate'], reverse=True)
            except Exception:
                printExc()
        if len(urlsTab):
            max_bitrate = int(config.plugins.iptvplayer.christusvincit_preferred_bitrate.value)
            urlsTab = CSelOneLink(urlsTab, lambda x: int(x['bitrate']), max_bitrate).getSortedLinks()
            if config.plugins.iptvplayer.christusvincit_use_preferred_bitrate.value:
                urlsTab = [urlsTab[0]]
        return urlsTab

    def handleService(self, index, refresh=0, searchPattern='', searchType=''):
        printDBG('handleService start')

        CBaseHostClass.handleService(self, index, refresh, searchPattern, searchType)

        name = self.currItem.get("name", '')
        category = self.currItem.get("category", '')
        printDBG("handleService: ||| name[%s], category[%s] " % (name, category))
        self.currList = []

    #MAIN MENU
        if name == None:
            self.listMain({'name': 'category', 'type': 'category'}, 'explore_item')

        elif category == 'explore_item':
            self.exploreItem(self.currItem)

        elif category == 'sub_items':
            self.listSubItems(self.currItem)

    #SEARCH
        elif category == 'list_search':
            self.listSearchItems(self.currItem)
        elif category in ["search", "search_next_page"]:
            cItem = dict(self.currItem)
            cItem.update({'search_item': False, 'name': 'category'})
            self.listSearchResult(cItem, searchPattern, searchType)
    #HISTORIA SEARCH
        elif category == "search_history":
            self.listsHistory({'name': 'history', 'category': 'search'}, 'desc', _("Type: "))
        else:
            printExc()

        CBaseHostClass.endHandleService(self, index, refresh)


class IPTVHost(CHostBase):

    def __init__(self):
        CHostBase.__init__(self, Christusvincit(), True, [])
