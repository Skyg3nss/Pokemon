# Chaos Chaser Scanner API

Gratis test-backend voor de Chaos Chaser Pokémon-kaartscanner.

## Wat deze server doet

`POST /recognize` ontvangt één foto en gebruikt `pokemon-card-recognizer` in `SINGLE_IMAGE` + `master` mode.

Voorbeeld response:

```json
{
  "ok": true,
  "card": {
    "set": "base1",
    "name": "Charizard",
    "number": "4"
  }
}
```

## Render deploy

Deze repo bevat al `render.yaml`.

1. Maak een nieuwe GitHub repository.
2. Upload alle bestanden uit deze map naar de root van de repo.
3. Ga naar Render.
4. Kies **New → Blueprint**.
5. Connect je GitHub repo.
6. Render leest automatisch `render.yaml`.
7. Controleer dat **plan = Free** staat.
8. Deploy.

De API krijgt daarna een URL zoals:

`https://chaos-chaser-scanner.onrender.com`

Test:

- `GET /health`
- `POST /warmup`
- `POST /recognize` met form-data veld `image`

## Belangrijk

De package zelf waarschuwt dat CPU veel trager is dan NVIDIA GPU.
Render Free is CPU-only. Dit is daarom eerst een echte haalbaarheidstest:
we testen snelheid + RAM + herkenningskwaliteit voordat we hem aan Chaos Chaser koppelen.

## CORS

Standaard staat CORS open voor de testfase. Later zetten we `ALLOWED_ORIGINS`
op alleen je Netlify-site.
