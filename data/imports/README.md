# Importable Sources

Drop additional source feeds in this folder to merge them into the app automatically.

Supported files:

- `realtor_listings.csv`
- `airbnb_listings.csv`

Expected columns:

```text
id,source_key,source_label,title,description,borough,neighborhood,address,price,beds,baths,sqft,property_type,available_from,lease_term,image_url,listing_url,latitude,longitude,pet_friendly,furnished,has_doorman,has_laundry,near_subway,allows_guarantors,featured
```

Notes:

- `source_key` can be `realtor` or `airbnb`
- `source_label` is optional; if blank the app will infer it
- rows with missing/zero price are ignored
- rows with missing `listing_url` are ignored
