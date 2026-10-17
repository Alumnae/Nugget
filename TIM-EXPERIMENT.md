# Esperimento TIM 22201 / SKU_CU

Basato su Nugget v7.4.1. Non modifica CommCenter e non dimostra l'esistenza
né la durata di una finestra di accettazione dell'overlay su iOS 26.1.
Non è stato provato su un iPhone: i test verificano solo la preparazione dei file.

## Cosa serve

- iPhone con iOS **26.1**, relativo UDID e linea attiva TIM_Italy.bundle / 22201.
- Copia originale dell'overlay effettivamente usato da quella linea e il suo
  percorso risolto `/var/mobile/Library/Carrier Bundles/Overlay/device-….plist`.
  Non usare il percorso del symlink `com.apple.carrier_1.plist`.
- Conferma che il Watch da attivare richieda SKU_CU.

Questo prototipo **non esporta automaticamente l'overlay protetto**. Se non hai
un modo per ottenere l'originale, manca ancora un prerequisito per provarlo.
Il nome del bundle e il codice 22201 sono confermati dall'utente, non dedotti
né verificati sul dispositivo. Non usare overlay presi da altri dispositivi.

## Utilizzo

Avvia da sorgente con le dipendenze previste dal README upstream.
In SpringBoard Options seleziona **TIM 22201: experimental Watch SKU…**.
Importa l'originale e indica percorso completo e UDID. Il prototipo conserva
una copia sotto `~/Nugget-TIM-backups/<UDID>/<SHA256>/`, con manifest e plist
modificato. L'unica modifica semantica è l'aggiunta di SKU_CU a SupportedSKUs,
conservando SKU_EU e gli altri valori originali.

Chiudi la finestra e usa Apply con le altre modifiche disabilitate. Il trasferimento
usa BookRestore di Nugget. Questa versione non aggiunge riavvii di CommCenter,
reload forzati o garanzie temporali; conserva il comportamento di applicazione
upstream, che può richiedere riavvii. Ciò potrebbe rendere inutilizzabile la
finestra ipotizzata: va misurato sul dispositivo, non dedotto dal trasferimento.

Apri Watch > Cellulare. Un trasferimento completato non prova che iOS abbia
accettato il valore né che TIM completerà il provisioning. Dopo un trasferimento
riuscito il job viene cancellato per evitare riapplicazioni involontarie.
Dopo un errore, ispeziona lo stato del dispositivo prima di ritentare.

## Ripristino

Nella stessa finestra scegli **Stage original from backup**, seleziona il
manifest salvato e usa Apply sullo stesso iPhone con iOS 26.1. Il checksum
dell'originale viene controllato prima del ripristino. Questo ripristina il file
salvato; non garantisce l'annullamento di eventuali operazioni eSIM completate
presso TIM. Non usare un vecchio backup dopo aggiornamenti del carrier o
cambiamenti della linea, e non unpairare/cancellare il Watch per questo test.

Conserva questi backup privatamente: possono contenere dati della linea.
Non commetterli né caricarli su GitHub.

## Verifica locale

`python3 -m unittest discover -s tests -p 'test_tim_overlay.py' -v`

Non sono stati eseguiti trasferimenti, attivazioni o test della finestra temporale.

## Selezione modello e BoardConfig

Il menu a tendina contiene le dieci serie della tabella fornita dall'utente
(Air, 17, 16e, 16, 15, 14, SE 3, 13, 12, 11). Mostra il nome esatto
`overrides_….plist` e gli identifier IPSW associati. La tabella è usata come
riferimento fornito dall'utente, non come rilevamento dei file installati.

La serie scelta viene salvata nel manifest; Apply verifica che il ProductType
dell'iPhone collegato appartenga alla serie. Il ripristino recupera la selezione
dal manifest. I vecchi backup privi di selezione restano utilizzabili con i
controlli UDID e versione già previsti.

Il file `TIM_Italy.bundle/overrides_….plist` è un override del bundle. Non è
il file runtime `Overlay/device-….plist`: il menu non può dedurre il percorso
di quest'ultimo. Il prototipo continua a importare l'overlay attivo completo
e a richiedere il suo percorso esatto; non scrive il file override del bundle
al posto dell'overlay.
