# GTA Clipper op iPhone — gebaseerd op het originele GitHub-project

De mobiele webapp gebruikt zoveel mogelijk van de oorspronkelijke GTA VI Claude Code-scripts. Je HomeBoard staat in een andere repository en wordt niet aangeraakt.

## Dagelijkse werkwijze

1. **Betaalopdracht zoeken:** open de links naar Content Rewards, Whop en Clip.tech in het dashboard. Controleer of de opdracht nog open is en of jij vanuit jouw regio mag meedoen.
2. **Campagne opslaan:** neem de echte maker, toegestane bronvideo, verplichte credit, hashtags, formaat, duur en regels over. Laat onbekende tarieven en budgetten leeg: die worden nooit geschat.
3. **Videobron kiezen:** gebruik je eigen video of beeld waarvoor de rechthebbende expliciet toestemming geeft. De aanwezigheid van een video op YouTube geeft niet automatisch hergebruikrechten.
4. **Momenten vinden:** analyseer de video via de bestaande Whisper-/FFmpeg-/yt-dlp-scripts. Kies een voorgesteld hoogtepunt.
5. **Clip maken:** kies blur, fill, facecam of react, plus woord-voor-woord ondertitels, tekstbubbels of geen ondertitels. Schrijf of kies een pakkende openingszin. Bekijk het resultaat op je gsm.
6. **Optioneel vertalen:** er zijn knoppen voor ES, PT, DE en RU op basis van het oorspronkelijke vertaal-script. Controleer elke vertaling.
7. **Technische controle:** de oorspronkelijke check.py controleert 1080×1920, fps, audio, lengte, verboden woorden en eventueel de **handmatig overgenomen** hashtags/vermelding. Deze controle **kan niet** beeldrechten, campagne-eligibiliteit, alle overlays of betalingsgoedkeuring bevestigen.
8. **Publicatie:** jij beslist of je de clip publiceert en dient zelf de URL in bij het campagneplatform. De app publiceert of schrijft niet zelfstandig in.
9. **Metingen:** registreer echte views (bijvoorbeeld na 12, 24 of 72 uur), goedkeuring en uitsluitend bevestigde uitbetalingen. Een bestaand postadres wordt bijgewerkt, niet dubbel geteld.

## Extra live-modus

Bij expliciete toestemming kun je de originele live.py-module 3, 5, 10 of 15 minuten gebruiken om chatpieken te vinden. Deze module maakt **ruwe fragmenten**, geen volledige Shorts met campagnerechten. Hij is niet geschikt om onbeperkt 24/7 in een Codespace te draaien.

## Campagnezoeker — wat er nu automatisch gaat

De knop **Zoek betaalde GTA 6-campagnes** controleert bij een druk op de knop de openbare catalogus en campagnepagina's van Content Rewards. Het dashboard toont de originele campagne-URL, gevonden naam, publiek zichtbare betaalbedragen en publieke status, of **onbekend** wanneer gegevens niet duidelijk op de website staan. Resultaten krijgen een controletijdstip en blijven tot de volgende zoekopdracht als cache beschikbaar. Het is dus geen continue achtergrondmonitor.

Klik op **Bewaar als concept** om een gevonden campagneformulier vooraf in te vullen. De gebruiker controleert op de originele campagnepagina de volledige regels (maker, toegestaan bronmateriaal, verplichte overlays, hashtags, deelname uit België, uitbetalingsvoorwaarden) en vult die in. Aanmelding en publicatie zijn altijd handmatig.

De oorspronkelijke campaign-finder is een Claude Code-instructie aan een browsende AI, geen formele publieke betaal-API. Onze nieuwe ontdekker leest alleen vrij toegankelijke pagina's van Content Rewards. **Als die site zijn pagina's verandert, serververzoeken blokkeert of login vereist, kan de automatische zoekfunctie geen resultaten tonen.** Het dashboard geeft dan een foutmelding en de rechtstreekse links naar Content Rewards, Whop en Clip.tech blijven beschikbaar. Voor Whop en Clip.tech zijn de afgeschermde campagnevoorwaarden niet automatisch leesbaar.

Andere originele Claude Code skills zoals cheat-codes, secrets-map, questions-to-posts en playbook zijn nog niet allemaal als aparte knoppen in de webapp ingebouwd. De originele bestanden blijven gewoon aanwezig in de fork.

## Openen op iPhone

- Codespaces: https://github.com/codespaces
- Bestaande GTA Clipper Codespace: open de Codespace en kies in Ports/Poorten poort **8765** → Open in Browser.
- Hou poort 8765 op **Private**.
- Je kunt de dashboardlink als beginschermicoon toevoegen in Safari; hij werkt alleen zolang de Codespace draait en de aanmelding geldig is.

## Bijwerken zonder telkens code te plakken

Vanaf de nieuwe bootstrapversie controleert de Codespace bij een volgende editorverbinding of het lokale project op branch main **veilig fast-forward** geüpdatet kan worden. Alleen als er geen lokale tracked wijzigingen zijn. Hij forceert of overschrijft geen eigen bewerkingen. Wanneer de dashboardcode gewijzigd is, kan hij een **niet-bezig** dashboard herstarten. De eerste keer dat deze nieuwe bootstrap op een bestaande Codespace belandt, moet de nieuwe code wel eenmaal via GitHub synchronisatie binnenkomen. Daarna kan bijwerken op volgende aansluitingen automatisch.

Bij problemen:
- Dashboard status en installatielog in de webapp.
- Bij installatieproblemen: .dashboard/install.log en .dashboard/install.status.
- Bij webserverproblemen: .dashboard/server.log.
- Bij bijwerkproblemen: .dashboard/update.log.
- Sluit Codespaces af als je klaar bent om gebruikskosten te beperken.
- De data en clips staan lokaal in de Codespace. Bij verwijderen van de Codespace kun je die verliezen; exporteer belangrijke resultaten eerst.

## Verificatie

GitHub Actions test Python-syntax, de JavaScript-interface, lokale campagne- en post-API's en controles zonder live externe accounts. **Niet automatisch getest:** volledige YouTube/Twitch-videodownload, daadwerkelijke Whisper-transcriptie, betaalde campagnes, socialemediapublicatie en echte uitbetalingen.
