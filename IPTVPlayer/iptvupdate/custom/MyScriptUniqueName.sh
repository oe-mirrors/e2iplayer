#!/bin/sh

cp "$1/iptvupdate/custom/MyScriptUniqueName.sh" "$2/iptvupdate/custom/MyScriptUniqueName.sh"
status=$?
if [ $status -ne 0 ]; then
	echo "Błąd krytyczny. Plik MyScriptUniqueName.sh nie może zostać skopiowany, error[$status]."
	exit 1
fi

cp "$1/icons/PlayerSelector/marker1"*".png" "$2/icons/PlayerSelector/"
status=$?
if [ $status -ne 0 ]; then
	echo "Uwaga nie udało się skopiować grafiki markera ze starej wersji, error[$status]."
	exit 0
fi

echo "Wykonywanie MyScriptUniqueName.sh zakończone sukcesem."
exit 0