#!/bin/sh

#e2iplayer install script - Pike_Bishop from oATV

## Variables ##
SCRIPTVERSION=16.0.3_git-oemirrors
STARTDATE="$(date +%a.%d.%b.%Y-%H:%M:%S)"
BOXIP="http://127.0.0.1"
WGET=/usr/bin/wget
EXTRACT="tar -xvzf"
NICE=/bin/nice
NICE_ARGS="-n 19"
TARGET_PATH=/usr/lib/enigma2/python/Plugins/Extensions
TMP=/var/volatile/tmp
WORKDIR=/home/root/_workdir # Can be changed as desired, e.g. on HDD to /media/hdd/_workdir or just /media/hdd/dirname_as_desired.
LOGFILE=$WORKDIR/_e2iplayer_install.log

# If an E2iPlayer is already installed it will be backed up, if you don't want this, simply change it to BACKUP=no
BACKUP=no	# parameters yes/no
# Directory where the E2iPlayer Backup is stored (can be changed as desired, e.g. for HDD to E2IPLAYER_BACKUP_DIR=/media/hdd/dirname_as_desired).
E2IPLAYER_BACKUP_DIR=$WORKDIR/e2iplayer_backups


{
# If it does not exist create the Working Directory (this is where the Log file are stored).
mkdir -p $WORKDIR


# To avoid too many E2iPlayer Backups lying around on the Box with (variable BACKUP=yes), delete older Backups.
# The last Backup created always remains, but the script also creates a new Backup each time it is executed a new
# Backup so you always have two E2iPlayer Backups on the Box and never more.
ls -t $E2IPLAYER_BACKUP_DIR/*[0-9][0-9].tar.gz 2>> /dev/null | tail -n +2 | xargs -r rm -f


# script Name + script Version Output + E2iPlayer Installation Start Message.
echo -e "\nScript-Name/Version -> e2iplayer_install.sh\t  Version_$SCRIPTVERSION\n"
echo -e "\nInstall/Update E2iPlayer ... -> $STARTDATE\n\n"


# If the script was already running but ended with an Error, delete any remains.
$NICE $NICE_ARGS rm -rf $TMP/e2iplayer-* $TMP/python*.gz $TMP/master.* $TMP/opkg-*


# If necessary, install required Plugins/Programmes such as e2iplayer-deps, ppanel, python-pycurl, duktape.
E2IPLAYER_DEPS=enigma2-plugin-extensions-e2iplayer-deps
PPANEL=enigma2-plugin-extensions-ppanel
PY2_PYCURL=python-pycurl
PY3_PYCURL=python3-pycurl
if opkg list | grep -q $PY2_PYCURL ; then
	PYCURL=$PY2_PYCURL && echo -e "PYCURL=$PY2_PYCURL\n"
elif opkg list | grep -q $PY3_PYCURL ; then
	PYCURL=$PY3_PYCURL && echo -e "PYCURL=$PY3_PYCURL\n"
fi
DUKTAPE="$(opkg list | grep -w '^duktape[^\*]' | cut -d ' ' -f 1)"

OPKG_UPDATE=no
for i in $E2IPLAYER_DEPS $PPANEL $PYCURL $DUKTAPE ; do
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
			echo -e "Install $i manually with Command;\nopkg install $i\nand/or start again e2iplayer_install.sh.\n\n"
			exit 1
		fi
	fi
done

# Check the Image Distro (e.g: whether OpenATV or OpenPLI) because in OpenPLI when using the E2iPlayer
# there can be a problem with ‘not found OpenSSL’, which can be fixed by installing libcrypto-compat.
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
			echo -e "Install $LIBCRYPTO_COMPAT manually with Command;\nopkg install $LIBCRYPTO_COMPAT\nand/or start again e2iplayer_install.sh.\n\n"
			exit 1
		fi
	fi
fi


# Check the Python Version (to distinguish between OpenATV-6.4 and OpenATV-7.0 for the Install/Update).
PYTHON_VERSION_COMPLETE=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
echo -e "Python Version = $PYTHON_VERSION_COMPLETE\n\n"
PYTHON_VERSION=$(python -c "import sys; print(sys.version_info.major)")


# Check whether the E2iPlayer oemirrors Version matches the Image (python2/python3).
echo "Install/Update -> E2iPlayer Version of oemirrors for python3 only."
if [ $PYTHON_VERSION -ne 3 ] ; then
	echo -e "\n... ERROR ...\nE2iPlayer Version does not match a python$PYTHON_VERSION Image.\n\n"
	exit 1
else
	FILE_ADRESS=https://github.com/oe-mirrors/e2iplayer/archive/refs/heads/python3.tar.gz
fi

# Download the E2iPlayer Source Package into the Directory (Variable TMP).
echo -e "\n\nDownload E2iPlayer Source Package (*.tar.gz) to;\n$TMP ...\n"
if ! $WGET -P $TMP $FILE_ADRESS ; then
	if ! $WGET "--no-check-certificate" $FILE_ADRESS -P $TMP ; then
		echo -e "\n... ERROR ...\nDownload E2iPlayer Source Package failed ! \nCheck your Internet Connection\nand restart e2iplayer_install.sh.\n\n"
		exit 1
	fi
fi

# Unpack the E2iPlayer Source Package in the Directory (Variable TMP).
echo -e "\nUnpack E2iPlayer Source Package to;\n$TMP ..."
if [ -e $TMP/python3.tar.gz ] ; then
	$EXTRACT $TMP/python3.tar.gz -C $TMP > /dev/null

	if [ "$?" != "0" ] ; then
		echo -e "\n... ERROR ...\nUnpack E2iPlayer Source Package failed ! \nrestart e2iplayer_install.sh.\n\n"
		exit 1
	fi
fi

# Read the Path to the unpacked E2iPlayer Source Package and assign it to a Variable.
EXTRACTED_SOURCE_PATH="$($NICE $NICE_ARGS find $TMP -maxdepth 2 -name IPTVPlayer)"

# Delete an already installed E2iPlayer, If BACKUP=yes is set in line 19, a Backup (*.tar.gz) of the
# already installed E2iPlayer is first created and stored in the Directory (Variable E2IPLAYER_BACKUP_DIR).
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
	$NICE $NICE_ARGS rm -rf  $TARGET_PATH/IPTVPlayer

	if [ "$?" != "0" ] ; then
		echo -e "\n... INFORMATION ...\nDelete the already installed E2iPlayer failed ! \nHowever, this may not be a tragedy."
		echo -e "The new E2iPlayer is then simply copied over.\n"
	fi
fi

# Copy Directory (Variable TMP)/e2iplayer-*/IPTVPlayer or (Variable EXTRACTED_SOURCE_PATH) recursively into the Directory (Variable TARGET_PATH).
echo -e "\n\nCopy;\n$EXTRACTED_SOURCE_PATH\nto;\n$TARGET_PATH ...\n"
if ! $NICE $NICE_ARGS cp -rf $EXTRACTED_SOURCE_PATH $TARGET_PATH ; then
	echo -e "\n... ERROR ...\nCopy;\n$EXTRACTED_SOURCE_PATH failed ! \n\n"
	exit 1
fi

# link duktape, only if duk (duktape binary) exists in /usr/bin and not in the .../IPTVPlayer/bin directory, link it there.
if [ -e /usr/bin/duk -a ! -e $TARGET_PATH/IPTVPlayer/bin/duk ] ; then
	ln -s /usr/bin/duk $TARGET_PATH/IPTVPlayer/bin
fi


# E2iPlayer Installation/Update success Message.
ENDDATE="$(date +%a.%d.%b.%Y-%H:%M:%S)"
echo -e "\nE2iPlayer installed/updated successfully. -> $ENDDATE\n"


# Delete the remains.
echo -e "\nDelete remains (*.tar.gz/*.zip and Directory e2iplayer-*) ...\n"
$NICE $NICE_ARGS rm -rf $TMP/e2iplayer-* $TMP/python*.gz $TMP/master.* $TMP/opkg-*


# Enigma2 GUI restart, yes or no ?, it's your decision (if there are currently no timer recordings running the answer would be yes).
while true; do
	read -p "$(echo -e "\nWould you like to restart the Enigma2 GUI? y/n (Default = yes) ?")" -n 1 yn
	case $yn in
		[yY]* )	echo -e "\n\nEnigma2 GUI restart is executed ...\n"
				$WGET -q -O - $BOXIP/web/powerstate?newstate=3
				echo -e "\n" && break ;;
		[nN]* ) echo -e "\n" && break ;;
			* ) if [ -z "$yn" ] ; then
					echo -e "\n\nEnigma2 GUI restart is executed ...\n"
					$WGET -q -O - $BOXIP/web/powerstate?newstate=3
					echo -e "\n" && break
				fi
				echo -e "\n\nPlease answer with y for (yes) or n for (no).\n" ;;
	esac
done
} 2>&1 | tee $LOGFILE

exit