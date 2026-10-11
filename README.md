# NHL-stats – NHL-yöraportti

Hakee joka aamu edellisyön NHL-otteluiden tulokset ja syvädatan, tallentaa ne ja
tekee suomenkielisen HTML-raportin, joka nostaa esiin kiinnostavia yksityiskohtia:

- **Putket:** jatkuvat piste- ja maaliputket, katkenneet pitkät pisteputket,
  päättyneet maalittomat jaksot
- **Huono tuuri:** pelaaja jäi ilman maalia, vaikka laukausten odotettu maalimäärä (ixG) oli yli 1
- **Viimeistelijät:** monta maalia pienestä ixG:stä
- **xG vs. tulos:** joukkue hävisi, vaikka hallitsi odotettuja maaleja
- **Maalivahdit:** GSAx (päästetyt maalit vs. odotettu) yli ±2
- **Isot illat ja hattutemput, poikkeava peliaika**
- **Kausitaulukot:** käynnissä olevat pisteputket, xG-ali- ja ylisuoriutujat
- **Suomalaisnurkkaus:** yön suomalaiset kenttäpelaajat ja maalivahdit, heitä koskevat nostot
  sekä suomalaisten pistepörssi ja maalivahtitilastot
- **Loukkaantumiset:** yöllä pelanneet, joista tuli pelin jälkeen loukkaantumisilmoitus
  (esim. poikkeuksellisen lyhyt peliaika) sekä sivussa olevat suomalaiset ja tähtipelaajat
  arvioituine paluupäivineen. Tähti = edellisellä kaudella joukkueensa kolmen parhaan
  pistemiehen joukossa ja väh. 50 p, vähintään 65 p (puolustaja 50 p) tai joukkueen ykkösvahti

Raportti julkaistaan GitHub Pagesissa: <https://juhaopesonen.github.io/NHL-stats/>

## Datalähteet

| Lähde | Käyttö |
|---|---|
| [NHL:n avoin rajapinta](https://api-web.nhle.com) | Ottelut, tulokset, boxscoret, pelaajien nimet ja syntymämaat |
| [ESPN](https://www.espn.com/nhl/injuries) (tiedot RotoWirelta) | Loukkaantumiset: tila, vamman tyyppi, arvioitu paluupäivä |
| [MoneyPuck.com](https://moneypuck.com/data.htm) | Laukaustason data ja xG-malli → ixG, joukkueiden xG, 5v5-xG, vaaralliset paikat, GSAx |

MoneyPuckin data on vapaasti käytettävissä ei-kaupalliseen käyttöön, kun MoneyPuck.com
mainitaan lähteenä – raportin alatunnisteessa on maininta.

**Natural Stat Trick** jätettiin pois: sivusto on bottisuojauksen takana eikä salli
automaattista hakua. Vastaavat luvut (xG, 5v5, vaaralliset paikat) lasketaan MoneyPuckin laukausdatasta.

## Käyttö omalla koneella

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt

python -m nhlstats                      # yön pelit (Suomen aikaa eilinen päivä)
python -m nhlstats --date 2026-10-10    # tietty pelipäivä
python -m nhlstats --no-fetch           # vain raportti tallennetusta datasta
```

Ensimmäinen ajo hakee koko kauden siihen asti (muutama minuutti), sen jälkeen vain uudet päivät.

## Rakenne

```
nhlstats/
  nhl_api.py    NHL-rajapinta: ottelut ja boxscoret
  moneypuck.py  MoneyPuckin laukausdata ja xG-koosteet
  storage.py    CSV-tallennus kausittain
  insights.py   nostojen säännöt ja kausitaulukot
  report.py     HTML-raportti
  config.py     raja-arvot (esim. pisteputken pituus, ixG-raja)
data/2026-27/   tallennettu data (games, skaters, goalies, xg_*)
data/players.csv  pelaajien syntymämaat (suomalaiset = FIN)
data/2026-27/injuries.csv  loukkaantumislistan päivittäiset tilannekuvat
data/2026-27/stars.csv     tähtipelaajat (edellisen kauden tilastoista)
docs/           GitHub Pages: index.html = uusin raportti, raportit/ = arkisto
```

Loukkaantumisista tallennetaan vain faktatiedot, ei uutistekstejä. Paluupäivät ovat
arvioita, ja ESPN:n rajapinta on epävirallinen, joten sen muuttuminen voi katkaista haun –
muu raportti tehdään silloinkin normaalisti.

Nostojen herkkyyttä säädetään tiedostossa `nhlstats/config.py`.

Suomalaiset tunnistetaan NHL:n ilmoittamasta syntymämaasta. Ulkomailla syntynyt
suomalainen jää siis pois – sen voi korjata muuttamalla pelaajan maaksi `FIN`
tiedostossa `data/players.csv`.

## Automaatio

`.github/workflows/yoraportti.yml` ajaa raportin joka aamu (06.30 UTC) ja päivittää sen
iltapäivällä (12.00 UTC), kun MoneyPuckin data on varmasti täydentynyt. Data ja raportti
commitoidaan repoon. Ajon voi käynnistää käsin GitHubin Actions-välilehdeltä
(*Run workflow*), myös tietylle päivälle.

GitHub Pagesin käyttöönotto: *Settings → Pages → Build and deployment →
Deploy from a branch → `main` / `/docs`*.
