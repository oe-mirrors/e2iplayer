from future.utils import raise_
from setuptools import Command
from setuptools.command.build import build as _build
import os


class build_trans(Command):
	description = 'Compile .po files into .mo files'

	def initialize_options(self):
		pass

	def finalize_options(self):
		pass

	def run(self):
		s = os.path.join('IPTVPlayer', 'locale')
		for lang in os.listdir(s):
			lc = os.path.join(s, lang, 'LC_MESSAGES')
			if os.path.isdir(lc):
				for f in os.listdir(lc):
					if f.endswith('.po'):
						src = os.path.join(lc, f)
						dest = os.path.join(lc, f[:-2] + 'mo')
						print("Language compile %s -> %s" % (src, dest))
						if os.system("msgfmt '%s' -o '%s'" % (src, dest)) != 0:
							raise_(Exception, "Failed to compile: " + src)



class build(_build):
	sub_commands = _build.sub_commands + [('build_trans', None)]

	def run(self):
		_build.run(self)


cmdclass = {
	'build': build,
	'build_trans': build_trans,
}
