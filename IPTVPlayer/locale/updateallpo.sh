#!/bin/bash
# Script to generate po files outside of the normal build process
#  
# Pre-requisite:
# The following tools must be installed on your system and accessible from path
# gawk, find, xgettext, gsed, python, msguniq, msgmerge, msgattrib, msgfmt, msginit
#
# Run this script from within the locale folder.
#
# Author: Pr2
# Version: 1.1 - check for the gettext tools up front; drop the dead xml2po.py
#                step; skip the po/mo rewrite when only the POT-Creation-Date
#                header changed (avoids empty git diffs)
#          1.2 - msgmerge --no-fuzzy-matching: no guessed (fuzzy) translations
#
localgsed="sed"
findoptions=""

if [[ "$OSTYPE" == "darwin"* ]]
	then
		# Mac OSX
		printf "Script running on Mac OSX [%s]\n" "$OSTYPE"
    	findoptions=" -s -X "
        localgsed="gsed"
fi

# fail early with a clear message instead of a cryptic "command not found"
for tool in xgettext msguniq msgmerge msgattrib msgfmt msginit; do
	if ! command -v $tool > /dev/null 2>&1; then
		printf "Error: '%s' not found in PATH - install the gettext tools first.\n" "$tool" >&2
		exit 1
	fi
done

Plugin=IPTVPlayer
FilePath=/LC_MESSAGES/
printf "Po files update/creation from script starting.\n"
languages=($(ls -d ./*/ | $localgsed 's/\/$//g; s/.*\///g'))

#
# Arguments to generate the pot and po files are not retrieved from the Makefile.
# So if parameters are changed in Makefile please report the same changes in this script.
#

# keep the current pot around so we can tell a real string change from a
# pure POT-Creation-Date bump once the new one is built
if [[ -f $Plugin.pot ]]; then
	cp $Plugin.pot $Plugin.pot.bak
fi

printf "Creating temporary file $Plugin-py.pot\n"
find $findoptions .. -name "*.py" -exec xgettext --no-wrap -L Python --from-code=UTF-8 -kpgettext:1c,2 --add-comments="TRANSLATORS:" -d $Plugin -s -o $Plugin-py.pot {} \+
$localgsed --in-place $Plugin-py.pot --expression=s/CHARSET/UTF-8/
printf "Merging to create: $Plugin.pot\n"
msguniq --no-wrap --no-location -o $Plugin.pot $Plugin-py.pot
rm $Plugin-py.pot

# if nothing but the auto-generated POT-Creation-Date line differs from the
# previous pot, restore it and stop - no merge needed, po/mo (and git) stay clean
if [[ -f $Plugin.pot.bak ]]; then
	grep -v '^"POT-Creation-Date:' $Plugin.pot     > $Plugin.pot.new
	grep -v '^"POT-Creation-Date:' $Plugin.pot.bak > $Plugin.pot.old
	if diff -q $Plugin.pot.old $Plugin.pot.new > /dev/null; then
		printf "No string changes (only POT-Creation-Date) - leaving all files as they are.\n"
		mv $Plugin.pot.bak $Plugin.pot
		rm -f $Plugin.pot.old $Plugin.pot.new
		printf "Po files update/creation from script finished!\n"
		exit 0
	fi
	rm -f $Plugin.pot.bak $Plugin.pot.old $Plugin.pot.new
fi

OLDIFS=$IFS
IFS=" "
for lang in "${languages[@]}" ; do
	if [[ -f $lang$FilePath$Plugin.po ]]; then 
		printf "Updating existing translation file %s.po\n" $lang
		msgmerge --backup=none --no-wrap --no-fuzzy-matching -s -U $lang$FilePath$Plugin.po $Plugin.pot && touch $lang$FilePath$Plugin.po
		msgattrib --no-wrap --no-obsolete $lang$FilePath$Plugin.po -o $lang$FilePath$Plugin.po
		msgfmt -o $lang$FilePath$Plugin.mo $lang$FilePath$Plugin.po
	else
		if [[ ! -d $lang$FilePath ]]; then
			mkdir -p $lang$FilePath
		fi
		printf "New file created: %s, please add it to github before commit\n" $lang$FilePath$Plugin.po
		msginit -l $lang -o $lang$FilePath$Plugin.po -i $Plugin.pot --no-translator
		msgfmt -o $lang$FilePath$Plugin.mo $lang$FilePath$Plugin.po
	fi
done
IFS=$OLDIFS
printf "Po files update/creation from script finished!\n"


