# NYC Rentals Platform

A fresh from-scratch NYC apartment rentals web app with:

- FastAPI backend
- Responsive Airbnb-style split layout
- Search, borough, neighborhood, price, beds, baths, amenity, and sort filters
- Interactive map with listing markers
- Scrapy project that exports data in the same schema used by the app

## Project layout

```text
nyc_rentals_platform/
├── app/
│   ├── main.py
│   ├── models.py
│   ├── repository.py
│   ├── static/
│   └── templates/
├── data/
│   └── listings.csv
├── scraper/
│   ├── scrapy.cfg
│   └── nyc_rentals_scraper/
└── tests/
```

## Run the web app

```bash
cd nyc_rentals_platform
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## API examples

```bash
curl "http://127.0.0.1:8000/api/listings?borough=Manhattan,Brooklyn&max_price=4500&pet_friendly=true"
curl "http://127.0.0.1:8000/api/filter-options"
```

## Run the Scrapy spider

The spider is set up for public NYC apartment result pages and exports normalized CSV data.

```bash
cd nyc_rentals_platform\scraper
scrapy crawl nyc_rentals -a max_pages=3
```

Output is written to `nyc_rentals_platform/data/scraped_listings.csv`.

## Deploy online

This project is ready for container deployment.

### Render

1. Push this folder to GitHub.
2. In Render, create a new `Blueprint` or `Web Service`.
3. Point it at the repo containing `nyc_rentals_platform/`.
4. Render will use:
   - [render.yaml](./render.yaml)
   - [Dockerfile](./Dockerfile)
5. After deploy, open `/health` to confirm the service is live.

The app binds to `0.0.0.0` and uses the platform `PORT` automatically.

## Notes

- The app ships with sample seed data in `data/listings.csv` so it works immediately.
- The scraper keeps `ROBOTSTXT_OBEY = True`; only scrape sources you are allowed to use.
