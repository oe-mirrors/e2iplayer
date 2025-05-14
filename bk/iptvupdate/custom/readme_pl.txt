Jeżeli chcesz, aby w trakcie aktualizacji pluginu wykonywane zostały dodatkowe skrypty wystarczy umieścić je w tym katalogu.
Dostępne są skrypty napisane w językach bash (powinny posiadać rozszeżenie ".sh") oraz python (rozszeżenie ".py").

Do każdego skryptu przekazywane są dwa parametry:
1) lokalizacja starej wersji pluginu np.:           "/usr/local/e2/lib/enigma2/python/Plugins/Extensions/IPTVPlayer"
2) tymczasowa lokalizacja nowej wersji pluginu np.: "/tmp/iptv_update/iptvplayer-for-e2-iptvplayer-for-e2/IPTVPlayer"

Parametry te mogą być przydatne jeśli np. chcemy skopiować nie które pliki ze starej wersji do nowej.
W szczególności każdy skrypt powinien kopiować samego siebie do tymczasowej lokalizacji z nową wersją.


W przypadku sukcesu skrypt powinien zwracać "0". 
W przypadku błędu krytycznego powinna to być wartość różna od "0" (spowoduje to fiasko całej aktualizacji).



Przykładowy kod skryptu napisany w bashu kopiujący grafiki markera ze starej wersji do nowej: 

-------------------------------------------------------------------------
#!/bin/sh

cp $1"/iptvupdate/custom/MyScriptUniqueName.sh" $2"/iptvupdate/custom/MyScriptUniqueName.sh"
status=$?
if [ $status -ne 0 ]; then
	echo "Błąd krytyczny. Plik MyScriptUniqueName.sh nie może zostać skopiowany, error[$status]."
	exit 1	
fi

cp $1"/icons/PlayerSelector/marker1*.png" $2"/icons/PlayerSelector/"
status=$?
if [ $status -ne 0 ]; then
	echo "Uwaga nie udało się skopiować grafiki markera ze starej wersji, error[$status]."
	exit 0
fi

echo "Wykonywanie MyScriptUniqueName.sh zakończone sukcesem."
exit 0
-------------------------------------------------------------------------