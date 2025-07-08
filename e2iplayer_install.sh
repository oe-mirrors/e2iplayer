#!/bin/sh

## Variablen ##
SCRIPTVERSION=13
STARTDATE="$(date +%a.%d.%b.%Y-%H:%M:%S)"
BOXIP="http://127.0.0.1"
WGET=/usr/bin/wget
EXTRACT="tar -xvzf"
EXTRACT_ZIP=/usr/bin/7za
NICE=/bin/nice
NICE_ARGS="-n 19"
TARGET_PATH=/usr/lib/enigma2/python/Plugins/Extensions
TMP=/var/volatile/tmp
WORKDIR=/home/root/_workdir # Can be changed as desired, e.g. on HDD to /media/hdd/_workdir or just /media/hdd/dirname_as_desired.
LOGFILE=$WORKDIR/_e2iplayer_install.log

# If an E2iPlayer is already installed it will be backed up, if you don't want this, simply change it to BACKUP=no
BACKUP=yes
# Directory where the E2iPlayer Backup is stored (can be changed as desired, e.g. for HDD to E2IPLAYER_BACKUP_DIR=/media/hdd/dirname_as_desired).
E2IPLAYER_BACKUP_DIR=$WORKDIR/e2iplayer_backups

# Here you can select the E2iPlayer Version to be installed/updated e.g.: JBLEYEL_VERSION=yes
# (only one of the different possible Versions may be marked with yes, namely the desired Version).
# For jbleyel E2iPlayer Version (only works with python3, so from OpenATV-7.x upwards).
JBLEYEL_VERSION=yes
# For zadmario E2iPlayer Version (works for both python2 and python3, i.e. for all OpenATV Versions).
ZADMARIO_VERSION=no
# For Blindspot76 E2iPlayer 'python3' Version (only works with python3, so from OpenATV-7.x upwards).
BLINDSPOT76_PY3_VERSION=no
# For Blindspot76 E2iPlayer 'python2' Version (only works with python2, i.e. up to OpenATV-6.4).
BLINDSPOT76_PY2_VERSION=no


{
# If it does not exist create the Working Directory (this is where the Log file and the Fixes are stored).
mkdir -p $WORKDIR


# To avoid too many E2iPlayer Backups lying around on the Box with (variable BACKUP=yes), delete older Backups.
# The last Backup created always remains, but the script also creates a new Backup each time it is executed a new
# Backup so you always have two E2iPlayer Backups on the Box and never more.
ls -t $E2IPLAYER_BACKUP_DIR/*[0-9][0-9].tar.gz 2>> /dev/null | tail -n +2 | xargs -r rm -f


# Automatically close the Console (OSD Window on the TV) so that you do not
# have to do this yourself when executing this script directly on the Box via Hotkey.
sleep 1
$WGET -q -O - $BOXIP/web/remotecontrol?command=174 > /dev/null


# script Path + script Name + script Version Output + E2iPlayer Installation Start Message.
echo -e "\nScript-Path/Name/Version -> ${0}\t  Version_$SCRIPTVERSION\n"
echo -e "\nInstall/Update E2iPlayer ... -> $STARTDATE\n\n"
$WGET -O - -q "$BOXIP/web/message?text=Start%20Installation%20or%20Update%0AE2iPlayer \
%20%2E%2E%2E%20->%20$STARTDATE&type=1&timeout=10" > /dev/null && sleep 12


# OSD Error Output.
osd_error_message() {
	$WGET -O - -q "$BOXIP/web/message?text=ABORT%20---%20(%20More%20Details%20in%20$LOGFILE%20)&type=3" > /dev/null
}


# If the script was already running but ended with an Error, delete any remains.
$NICE $NICE_ARGS rm -rf $TMP/e2iplayer-* $TMP/e2iPlayer-* $TMP/iptv-host-xxx* $TMP/python*.gz $TMP/master.zip


# If necessary, install required Plugins/Programmes such as e2iplayer-deps, ppanel, p7zip/7zip, python-pycurl, duktape.
E2IPLAYER_DEPS=enigma2-plugin-extensions-e2iplayer-deps
PPANEL=enigma2-plugin-extensions-ppanel
if opkg list | grep -q p7zip ; then
	P7ZIP=p7zip && echo -e "P7ZIP=$P7ZIP\n"
elif opkg list | grep -q 7zip ; then
	P7ZIP=7zip && echo -e "P7ZIP=$P7ZIP\n"
fi
PY2_PYCURL=python-pycurl
PY3_PYCURL=python3-pycurl
if opkg list | grep -q $PY2_PYCURL ; then
	PYCURL=$PY2_PYCURL && echo -e "PYCURL=$PY2_PYCURL\n"
elif opkg list | grep -q $PY3_PYCURL ; then
	PYCURL=$PY3_PYCURL && echo -e "PYCURL=$PY3_PYCURL\n"
fi
DUKTAPE="$(opkg list | grep -w '^duktape[^\*]' | cut -d ' ' -f 1)"

OPKG_UPDATE=no
for i in $E2IPLAYER_DEPS $PPANEL $P7ZIP $PYCURL $DUKTAPE ; do
	if ! opkg list-installed | grep -q $i ; then

		if [ "$OPKG_UPDATE" = "no" ] ; then
			OPKG_UPDATE=yes ; echo -e "\nStart opkg update ...\n"
			opkg update ; echo -e "\n"
		fi

		echo -e "$i missing.\nInstall $i  ...\n"
		opkg install $i 2> /dev/null

		if [ "$?" = "0" ] ; then
			echo -e "\n$i successfully installed.\n\n"
		else
			echo -e "\n... ERROR ...\n$i Install failed !"
			echo -e "Install $i manually with Command;\nopkg install $i\nand/or start again $0.\n\n"
			osd_error_message && exit 1
		fi
	fi
done

# Check the Image Distro (e.g: whether OpenATV or OpenPLI) because in OpenPLI when using the E2iPlayer Version
# of zadmario there can be a problem with ‘not found OpenSSL’, which can be fixed by installing libcrypto-compat.
DISTROVERSION="$($WGET -O - -q $BOXIP/web/deviceinfo | grep "\(<\|</\)e2distroversion" \
 | tr -d '\n' | sed "s/.*<e2distroversion>\(.*\)<\/e2distroversion>.*/\\1\n/")"
LIBCRYPTO_COMPAT="$(opkg info libcrypto-compat* | grep "Package:" | grep -v '\(-dbg\|-dev\|-staticdev\)' | awk {'print $NF'})"

# If the Image Distro is an OpenPLI, install the libcrypto-compat Package if required.
if [ "$DISTROVERSION" = "openpli" ] ; then
	if ! opkg list-installed | grep -q "$LIBCRYPTO_COMPAT" ; then
		echo -e "Image Distro = \"$DISTROVERSION\",\n$LIBCRYPTO_COMPAT is missing.\nInstall $LIBCRYPTO_COMPAT ...\n\n"

		if [ "$OPKG_UPDATE" = "yes" ] ; then
			opkg install $LIBCRYPTO_COMPAT
		else
			opkg update && opkg install $LIBCRYPTO_COMPAT
		fi

		if [ "$?" = "0" ] ; then
			echo -e "\n$LIBCRYPTO_COMPAT successfully installed.\n\n"
		else
			echo -e "\n... ERROR ...\n$LIBCRYPTO_COMPAT Install failed !"
			echo -e "Install $LIBCRYPTO_COMPAT manually with Command;\nopkg install $LIBCRYPTO_COMPAT\nand/or start again $0.\n\n"
			osd_error_message && exit 1
		fi
	fi
fi


# Check the Python Version (to distinguish between OpenATV-6.4 and OpenATV-7.0 for the Install/Update).
PYTHON_VERSION_COMPLETE=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
echo -e "Python Version = $PYTHON_VERSION_COMPLETE\n\n"
PYTHON_VERSION=$(python -c "import sys; print(sys.version_info.major)")


# Determine file Address for Download using the Variables above in lines 25, 27, 29, and 31.
# Also check whether the selected E2iPlayer Version matches the Image (python2/python3).
case "yes" in
	"$JBLEYEL_VERSION")
		echo "Selected -> E2iPlayer Version of jbleyel for python3."
		if [ $PYTHON_VERSION -ne 3 ] ; then
			echo -e "\n... ERROR ...\nE2iPlayer Version does not match a python$PYTHON_VERSION Image.\n\n"
			osd_error_message && exit 1
		fi
		#FILE_ADRESS=https://github.com/oe-mirrors/e2iplayer/archive/refs/heads/python3.zip
		FILE_ADRESS=https://github.com/oe-mirrors/e2iplayer/archive/refs/heads/python3.tar.gz
	;;
	"$ZADMARIO_VERSION")
		echo "Selected -> E2iPlayer of zadmario."
		#FILE_ADRESS=https://gitlab.com/zadmario/e2iplayer/-/archive/master/e2iplayer-master.zip
		FILE_ADRESS=https://gitlab.com/zadmario/e2iplayer/-/archive/master/e2iplayer-master.tar.gz
	;;
	"$BLINDSPOT76_PY3_VERSION")
		echo "Selected -> E2iPlayer Version of blindspot76 for python3."
		if [ $PYTHON_VERSION -ne 3 ] ; then
			echo -e "\n... ERROR ...\nE2iPlayer Version does not match a python$PYTHON_VERSION Image.\n\n"
			osd_error_message && exit 1
		fi
		FILE_ADRESS=https://github.com/Blindspot76/e2iPlayer-Python3/archive/refs/heads/master.zip
	;;
	"$BLINDSPOT76_PY2_VERSION")
		echo "Selected -> E2iPlayer of blindspot76 for python2."
		if [ $PYTHON_VERSION -eq 3 ] ; then
			echo -e "\n... ERROR ...\nE2iPlayer Version does not match a python$PYTHON_VERSION Image.\n\n"
			osd_error_message && exit 1
		fi
		FILE_ADRESS=https://github.com/Blindspot76/e2iPlayer/archive/refs/heads/master.zip
	;;
		*) echo -e "\n... ERROR ...\nNo E2iPlayer Version selected.\n\n"; osd_error_message && exit 1;;
esac

# Download the E2iPlayer Source Package into the Directory (Variable TMP).
echo -e "\n\nDownload E2iPlayer Source Package (*.tar.gz/*.zip) to;\n$TMP ...\n"
if ! $WGET -P $TMP $FILE_ADRESS ; then
	if ! $WGET "--no-check-certificate" $FILE_ADRESS -P $TMP ; then
		echo -e "\n... ERROR ...\nDownload E2iPlayer Source Package failed ! \nCheck your Internet Connection\nand restart $0.\n\n"
		osd_error_message && exit 1
	fi
fi

# Unzip the E2iPlayer Source Package in the Directory (Variable TMP).
echo -e "\nUnzip E2iPlayer Source Package to;\n$TMP ..."
if [ -e $TMP/python3.tar.gz ] ; then
	$EXTRACT $TMP/python3.tar.gz -C /$TMP > /dev/null
elif [ -e $TMP/e2iplayer-master.tar.gz ] ; then
	$EXTRACT $TMP/e2iplayer-master.tar.gz -C /$TMP > /dev/null
elif [ -e $TMP/master.zip ] ; then
	$EXTRACT_ZIP x $TMP/master.zip -o$TMP > /dev/null
fi

if [ "$?" != "0" ] ; then
	echo -e "\n... ERROR ...\nUnzip E2iPlayer Source Package failed ! \nrestart $0.\n\n"
	osd_error_message && exit 1
fi

# Read the Path to the unpacked E2iPlayer Source Package and assign it to a Variable.
EXTRACTED_SOURCE_PATH="$($NICE $NICE_ARGS find $TMP -maxdepth 2 -name IPTVPlayer)"

# Delete an already installed E2iPlayer, but keep an already installed E2iPlayer +18 Addon, If BACKUP=yes is set in line 18
# , a Backup (*.tar.gz) of the already installed E2iPlayer is first created and stored in the Directory (Variable E2IPLAYER_BACKUP_DIR).
if [ -d $TARGET_PATH/IPTVPlayer ] ; then

	if [ "$BACKUP" = "yes" ] ; then
		BACKUP_DATE=$(date +%d.%m.%Y-%H:%M:%S)
		echo -e "\n\nBackup the already installed E2iPlayer in;\n$E2IPLAYER_BACKUP_DIR\nas Package;\ne2iplayer-$BACKUP_DATE.tar.gz ..."
		mkdir -p $E2IPLAYER_BACKUP_DIR
		#$NICE $NICE_ARGS tar cfvzp e2iplayer-$BACKUP_DATE.tar.gz -C $E2IPLAYER_BACKUP_DIR $TARGET_PATH/IPTVPlayer > /dev/null 2>&1
		$NICE $NICE_ARGS tar -czpf $E2IPLAYER_BACKUP_DIR/e2iplayer-$BACKUP_DATE.tar.gz $TARGET_PATH/IPTVPlayer > /dev/null 2>&1

		if [ "$?" != "0" ] ; then
			echo -e "\n... INFORMATION ...\nBackup of the already installed E2iPlayer failed ! \nBut it's not a tragedy.\n"
		fi
	fi

	echo -e "\n\nDelete the already installed E2iPlayer in;\n$TARGET_PATH/IPTVPlayer ..."
	echo -e "However, an already installed E2iPlayer +18 Addon is retained.\n"
	#$NICE $NICE_ARGS find $TARGET_PATH/IPTVPlayer -type f ! -iname "*xxx*" -exec rm {} +
	$NICE $NICE_ARGS find $TARGET_PATH/IPTVPlayer -type f -iname "*xxx*" -o -delete

	if [ "$?" != "0" ] ; then
		echo -e "\n... INFORMATION ...\nDelete the already installed E2iPlayer failed ! \nHowever, this may not be a tragedy."
		echo -e "The new E2iPlayer is then simply copied over.\n"
	fi

	# Only if the +18 Addon is included in the already installed E2iPlayer (i.e. it is already installed) the +18 Addon files
	# in the unpacked E2iPlayer Source Package are deleted so that an already installed +18 Addon is not overwritten.
	if [ "$($NICE $NICE_ARGS find $TARGET_PATH/IPTVPlayer -type f -iname "*xxx*" 2>/dev/null)" ] ; then
		echo -e "\n\nDelete +18 Addon files from;\n$EXTRACTED_SOURCE_PATH"
		echo -e "so as not to overwrite an already installed +18 Addon when copying ..."
		#$NICE $NICE_ARGS find $TMP/*/IPTVPlayer -maxdepth 3 -iname "*xxx*" -exec rm {} \;
		# Better, as the exact Path is specified and -type f also only deletes files, the above also deletes Folders with xxx in their name.
		#$NICE $NICE_ARGS find $EXTRACTED_SOURCE_PATH -maxdepth 3 -type f -iname "*xxx*" -exec rm {} \;
		# More efficient than the above command and portable (so should work in any Linux).
		#$NICE $NICE_ARGS find $EXTRACTED_SOURCE_PATH -maxdepth 3 -type f -iname "*xxx*" -exec rm {} + 
		# Most efficient if the find with delete works (i think there are also Versions of find where delete does not exist, so not so portable). 
		$NICE $NICE_ARGS find $EXTRACTED_SOURCE_PATH -maxdepth 3 -type f -iname "*xxx*" -delete
	fi
fi

# Copy Directory (Variable TMP)/e2iplayer-*/IPTVPlayer or (Variable EXTRACTED_SOURCE_PATH) recursively into the Directory (Variable TARGET_PATH).
echo -e "\n\nCopy;\n$EXTRACTED_SOURCE_PATH\nto;\n$TARGET_PATH ...\n"
if ! $NICE $NICE_ARGS cp -rf $EXTRACTED_SOURCE_PATH $TARGET_PATH ; then
	echo -e "\n... ERROR ...\nCopy;\n$EXTRACTED_SOURCE_PATH failed ! \n\n"
	osd_error_message && exit 1
fi


# link duktape, only if duk (duktape binary) exists in /usr/bin and not in the .../IPTVPlayer/bin directory, link it there.
if [ -e /usr/bin/duk -a ! -e $TARGET_PATH/IPTVPlayer/bin/duk ] ; then
	ln -s /usr/bin/duk $TARGET_PATH/IPTVPlayer/bin
fi

# Download and copy special keymap.xml (for @Papi2000 (but is also good for all other users)).
mv $TARGET_PATH/IPTVPlayer/keymap.xml $TARGET_PATH/IPTVPlayer/keymap.xml.org
$WGET -q -O "$TARGET_PATH/IPTVPlayer/keymap.xml" "https://drive.usercontent.google.com/download?id=1T9bS_NQC-z7YE-UQfm3b3V-mY2KY9css&export=download&confirm=yes"



# The following (Install Fixes is only valid until @zadmario takes over the Fixes) !
# Install Fixes 2025 from Mister X for savefiles, Vidhide, vidoza, supervideo.cc, VOE, hdfilmetv and much more, only
# in the ZADMARIO_VERSION and in the BLINDSPOT76_VERSIONS as already included in the JBLEYEL_VERSION.
echo -e "\n\nInstall Fixes 2025 by Mister X ..."
if [ "$JBLEYEL_VERSION" != "yes" ] ; then
	FDIR=$WORKDIR/e2iplayer_fixes && mkdir -p $FDIR

	rm -f $FDIR/e2iplayer_fixes.tar.gz

	# Download the Fixes (Package "e2iplayer_fixes.tar.gz") from Google Drive.
	$WGET -q -O "$FDIR/e2iplayer_fixes.tar.gz" "https://drive.usercontent.google.com/download?id=1-kgV9OUBMyrR3TTXQinGk1pwOneTOF5c&export=download&confirm=yes" && sleep 1

	# Unzip the Fixes to the correct Directories of the E2iPlayer (files with the same name there are overwritten).
	$EXTRACT $FDIR/e2iplayer_fixes.tar.gz -C $TARGET_PATH > /dev/null

	if [ "$?" != "0" ] ; then
		echo -e '\n... ERROR ...\nFixes unzip or copy failed !\n\n'
		osd_error_message && exit 1
	fi
fi
echo -e "Fixes Installation successfully completed.\n\n"
# End Install Fixes.



# E2iPlayer Installation/Update success Message.
ENDDATE="$(date +%a.%d.%b.%Y-%H:%M:%S)"
echo -e "\nE2iPlayer installed/updated successfully. -> $ENDDATE\n"
$WGET -O - -q "$BOXIP/web/message?text=E2iPlayer%20installed%2Fupdated%20successfully%2E&type=1&timeout=10" > /dev/null


# Delete the remains.
echo -e "\nDelete remains (*.tar.gz/*.zip and Directory e2iplayer-*) ...\n"
$NICE $NICE_ARGS rm -rf $TMP/e2iplayer-* $TMP/e2iPlayer-* $TMP/python*.gz $TMP/master.zip


# Check whether recording(s) is/are running, if not initiate Enigma2-GUI Restart, if so postpone
# Enigma2-GUI Restart by TIMEOUT minutes and repeat this until no more recording(s) is/are running.
echo ""
sleep 11
TIMEOUT=10
z=1
REC=yes
while [ "$REC" = "yes" ] ; do
	if [ $($WGET -O- -q $BOXIP/web/timerlist | grep "<e2state>2</e2state>" | grep -cm 1 "2") = 1 ] ; then
		REC=yes
		echo -e "No Enigma2 GUI Restart possible because a recording is running -> Wait $TIMEOUT Minutes ...\n"

		if [ "$z" = "1" ] ; then
			MSG="$(echo -e "No Enigma2-Gui Restart possible because a recording\nis running -> try it all $TIMEOUT Minutes again ...")"
			$WGET -O - -q "$BOXIP/web/message?type=1&timeout=10&text=$MSG" > /dev/null
		fi

		z=$((z+1)) && sleep ${TIMEOUT}m
		echo -e "\nInitiate Enigma2-GUI Restart (Attempt $z) ...\n"
	else
		REC=no
		echo -e "No recording in progress -> Restart Enigma2 GUI ...\n"
		$WGET -O - -q "$BOXIP/web/message?text=No%20recording%20in%20progress%0ARestart%20Enigma2%2DGUI%20%2E%2E%2E&type=1&timeout=10" > /dev/null && sleep 12
	fi
done

$WGET -q -O - $BOXIP/web/powerstate?newstate=3 > /dev/null 2>&1
} 2>&1 | tee $LOGFILE


exit
#