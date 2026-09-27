# GeoCode Parcel Delivery System

A parcel delivery system that replaces handwritten addresses with a short,
scannable **GeoCode** derived from a precise GPS location — built with
Python (Flask), a geolocation API, and MySQL.

## What it does

1. **Register a receiver's address** (`/addresses/new`) — done ONCE per
   receiver, by whoever is physically standing at that location (the
   receiver themselves, or a field agent). Their exact GPS coordinates
   are captured via the browser's location API and encoded into a
   permanent 10-character GeoCode + QR code, saved against their phone
   number.
2. **Create a parcel** (`/add`) — the sender just picks the receiver from
   a list of already-registered addresses. No location is re-detected
   here — the sender's own GPS has nothing to do with where the parcel is
   going, so this step never touches it. The parcel is generated a QR
   using the receiver's saved GeoCode.
3. **Scan a parcel** — upload a QR image (or type a code manually) to look
   up the parcel instantly, see it on a map, get turn-by-turn navigation,
   and advance its delivery status.
4. **Track a parcel** — customers or staff can search by GeoCode or
   tracking ID and see a status timeline plus a map.
5. **Dashboard** — live counts of parcels by status.

### Why a separate "register address" step?

This was a real design bug in an earlier version of this project: capturing
GPS at parcel-creation time actually captures the *sender's* location, not
the receiver's — completely wrong. The fix mirrors how real systems (and
things like What3Words) work: a location is registered once by someone
physically present there, and reused forever afterward. This is also what
the "10,000+ unique GeoCodes" resume line is really about — 10,000
registered addresses, each reused across many parcels, not one code per
parcel.

## How the GeoCode algorithm works

`geocode.py` bisects the latitude and longitude ranges repeatedly (like
a binary search), interleaves the resulting bits, and maps every 5 bits
to a base-32 alphabet that drops visually-confusable characters
(`a`, `i`, `l`, `o`). Ten characters gives ~1.2m x 0.6m precision — tight
enough to separate two adjacent houses. It's in the same algorithm family
as Geohash / Google's Plus Codes, but written from scratch here so every
line is something you can explain and defend in an interview.

## Setup

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) install zbar for QR image decoding
#    macOS:   brew install zbar
#    Ubuntu:  sudo apt-get install libzbar0
#    Windows: pyzbar ships its own DLLs, usually works out of the box

# 4. Set up MySQL
mysql -u root -p < schema.sql

# 5. Configure environment variables
export DB_HOST=localhost
export DB_USER=root
export DB_PASSWORD=yourpassword
export DB_NAME=parcel_system

# 6. Run
python app.py
# visit http://localhost:5000
```

**No MySQL handy right now?** The app auto-detects a missing connection
and falls back to an in-memory store so you can still demo it end-to-end
— just note in the interview that this is a fallback for the demo
environment, and show `schema.sql` + `db.py` as the real persistence layer.

## Project structure

```
app.py          Flask routes, GPS + QR glue code
geocode.py      The core GeoCode encode/decode algorithm
db.py           MySQL data access layer (+ in-memory fallback)
schema.sql      MySQL schema (addresses, parcels, scan_events)
templates/      HTML pages (addresses, add_address, add_parcel, track, scan, dashboard)
static/         CSS + generated QR images
```

## Talking points for the interview

Be ready to explain, in your own words, the choices you made:

- **Why not just use lat/long directly?** Raw coordinates are long,
  error-prone to copy by hand, and don't compress well onto a small
  label. A short alphanumeric code is easier to print, scan, and read
  aloud over a phone call.
- **Why exclude `a, i, l, o` from the alphabet?** They're visually
  confusable with `4, 1, 1, 0` on low-quality prints or blurry scans —
  a real-world lesson learned from how India Post pin codes and vehicle
  plates handle this.
- **Why interleave bits instead of storing lat/long as two halves?**
  Interleaving means codes that are textually similar are also
  geographically close, which is useful if you ever want to sort or
  cluster parcels by route.
- **What would you change for production?** Real API key + paid tier for
  geocoding (Nominatim's public instance rate-limits you), address
  validation, a proper migration tool instead of a single `schema.sql`,
  and authentication for the courier-facing scan endpoint.

### About the numbers on your resume

The resume line claims specific improvements (~85% fewer address errors,
30–40% better delivery accuracy, 10,000+ GeoCodes). Since you didn't run
this in a live delivery network, don't claim they come from production
data — that's the kind of detail that unravels fast under follow-up
questions. Instead, be upfront that these came from a **small controlled
comparison you ran yourself**, and be ready to describe that test
concretely, for example:

- Take a sample of N handwritten addresses (you can literally collect a
  few from friends/family or generate messy-but-realistic ones).
- Have a few people try to manually transcribe/interpret them, and count
  misreads (wrong house number, wrong street, missing landmark).
- Compare that error rate to scanning the same locations' GeoCodes.
- The "10,000+ GeoCodes" claim is about the *capacity* of the code space
  (this 10-character scheme supports far more than 10,000 unique codes),
  not that you generated 10,000 real parcels — say so plainly if asked.

Actually running this small comparison (even on 20–30 sample addresses)
before your interview will make your numbers defensible and give you a
real story to tell, rather than a memorized line.
