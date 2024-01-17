from setuptools import setup
import setup_translate

pkg = 'Extensions.IPTVPlayer'
setup(name='enigma2-plugin-extensions-iptvplayer',
       version='1.0',
       description='IPTV Player for E2',
       package_dir={pkg: 'IPTVPlayer'},
       packages=[pkg],
       package_data={pkg: ['*.*', '*/*.*', '*/*/*.*', '*/*/*/*.*', '*/*/*/*/*.*']},
       cmdclass=setup_translate.cmdclass, # for translation
      )
