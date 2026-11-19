# GTA Clipper op je iPhone (GitHub Codespaces)

Dit is de mobiele uitbreiding boven op de oorspronkelijke, geforkte GTA VI-scripts.

## Eén keer instellen (zonder terminal)

1. Open https://github.com/codespaces/new?repo=1464192994
2. Selecteer de standaardbranch main en maak een **nieuwe Codespace** aan.
3. De installatie voert vanzelf het installatiescript uit. Python, FFmpeg en de pakketten worden ingericht.
4. Bij het openen van de Codespace start de webapp op poort **8765**.
5. Klik in de Codespaces-editor onderaan op **Ports / Poorten**, zoek **GTA Clipper mobiel dashboard (8765)** en kies **Open in Browser**. De poort moet op **Private** staan.
6. Gebruik de knoppen op het dashboard. Je hoeft geen terminalcommando's te plakken.

**Belangrijk:** een bestaande Codespace bevat mogelijk nog de oude bestanden. Een nieuwe Codespace haalt de meest recente versie op. Stop oude Codespaces via https://github.com/codespaces om onnodig verbruik te vermijden.

## Het dashboard

- **Systeemstatus:** toont of de automatische installatie klaar is of mislukte, en de installatielog.
- **Trends en streams:** zoekt video-/livestreammetadata via de originele scripts, zonder downloads van video.
- **Fragmentanalyse:** je geeft een toegestane YouTube/Twitch-URL op; de originele analyzer downloadt de video en zoekt kandidaten. Verwerking kan langer duren en gebruikt opslag.
- **Clip maken:** genereert een verticaal MP4-bestand met het originele knipscript. Je bekijkt het resultaat in de iPhone-browser.

Er wordt **nooit automatisch gepost**, geen sociaal account gekoppeld en geen inkomsten gegarandeerd. Gebruik alleen je eigen video of materiaal waarvoor je gebruiksrechten hebt. Een betaalcampagne heeft haar eigen regels en moet afzonderlijk worden gecontroleerd.

## Probleemoplossing

- Als er een melding over een ontbrekend Python-interpreterpad verschijnt, controleer in het dashboard de installatiestatus. De Python-omgeving kan nog niet klaar zijn of de installatie kan gefaald hebben.
- Als het dashboard niet opent: controleer of de Codespace actief is, of poort **8765** in het tabblad **Ports** verschijnt en of de laatste GitHub-versie gebruikt wordt.
- Logs staan in de map .dashboard en worden niet naar Git geüpload.
- Als de installatie is mislukt, gebruik **Codespaces: Rebuild Container** vanuit de Command Palette of start een verse Codespace.
- Codespaces verbruikt quotum zolang de machine aan staat. Stop de Codespace wanneer je klaar bent.

Dit is een eerste versie. De werkelijke YouTube-/Twitch-koppelingen en videoweergave moeten in Codespaces met echte toegestane content getest worden.
