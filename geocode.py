"""
geocode.py
-----------
Core encoding engine for the GeoCode Parcel Delivery System.

Design idea
===========
India's postal addresses are handwritten, inconsistent, and prone to
misreads (missing landmarks, wrong pin codes, ambiguous spellings). This
module converts a precise (latitude, longitude) pair into a short,
human-shareable, scannable alphanumeric code — a "GeoCode" — and back.

The algorithm is a base-32 interleaved bit encoding (in the same family
as Geohash), but written from scratch for this project so the bit
budget, alphabet, and code length are tuned specifically for
parcel-delivery precision (~1.2m x 0.6m cells at 10 characters) and so
it can be explained end-to-end in an interview.

How it works
============
1. Latitude range [-90, 90] and longitude range [-180, 180] are each
   repeatedly bisected. At each bisection we ask "is the point in the
   upper or lower half?" and emit a 1 or 0 accordingly.
2. Bits from longitude and latitude are interleaved (lon bit, lat bit,
   lon bit, lat bit, ...) so that codes which are *close in text* are
   also close in *physical space* — nearby parcels get similar-looking
   codes, which is useful for sorting/routing.
3. Every 5 bits are grouped and mapped to a base-32 alphabet that
   excludes visually-confusable characters (a, i, l, o are dropped) so
   the code is easy to read off a printed label or a low-quality scan.
"""

# Custom base32 alphabet - visually unambiguous characters only
# (excludes a, i, l, o to avoid confusion with 4, 1, 1, 0)
_ALPHABET = "0123456789bcdefghjkmnpqrstuvwxyz"
_ALPHABET_INDEX = {ch: idx for idx, ch in enumerate(_ALPHABET)}

# Code length in characters. 10 chars = 50 bits = 25 bits lat + 25 bits lon,
# which resolves to roughly 1.2m x 0.6m on the ground - tight enough to
# separate neighbouring houses/shops.
CODE_LENGTH = 10


def encode(lat: float, lon: float, precision: int = CODE_LENGTH) -> str:
    """Encode a (lat, lon) pair into a GeoCode string."""
    if not (-90.0 <= lat <= 90.0):
        raise ValueError("Latitude must be between -90 and 90")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError("Longitude must be between -180 and 180")

    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]

    bits = []
    bit_toggle = 0  # 0 -> encode longitude bit, 1 -> encode latitude bit
    total_bits = precision * 5

    while len(bits) < total_bits:
        if bit_toggle == 0:
            mid = (lon_range[0] + lon_range[1]) / 2
            if lon >= mid:
                bits.append(1)
                lon_range[0] = mid
            else:
                bits.append(0)
                lon_range[1] = mid
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat >= mid:
                bits.append(1)
                lat_range[0] = mid
            else:
                bits.append(0)
                lat_range[1] = mid
        bit_toggle ^= 1

    # Pack bits into base32 characters, 5 bits at a time
    chars = []
    for i in range(0, total_bits, 5):
        chunk = bits[i:i + 5]
        value = 0
        for b in chunk:
            value = (value << 1) | b
        chars.append(_ALPHABET[value])

    return "".join(chars).upper()


def decode(code: str):
    """Decode a GeoCode string back into an approximate (lat, lon, error_margin)."""
    code = code.strip().lower()
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    bit_toggle = 0

    for ch in code:
        if ch not in _ALPHABET_INDEX:
            raise ValueError(f"Invalid GeoCode character: {ch!r}")
        value = _ALPHABET_INDEX[ch]
        for shift in range(4, -1, -1):
            bit = (value >> shift) & 1
            if bit_toggle == 0:
                mid = (lon_range[0] + lon_range[1]) / 2
                if bit:
                    lon_range[0] = mid
                else:
                    lon_range[1] = mid
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                if bit:
                    lat_range[0] = mid
                else:
                    lat_range[1] = mid
            bit_toggle ^= 1

    lat = (lat_range[0] + lat_range[1]) / 2
    lon = (lon_range[0] + lon_range[1]) / 2
    lat_error = (lat_range[1] - lat_range[0]) / 2
    lon_error = (lon_range[1] - lon_range[0]) / 2

    return {
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "lat_error_m": round(lat_error * 111320, 2),
        "lon_error_m": round(lon_error * 111320, 2),
    }


def is_valid(code: str) -> bool:
    code = code.strip().lower()
    if len(code) != CODE_LENGTH:
        return False
    return all(ch in _ALPHABET_INDEX for ch in code)


if __name__ == "__main__":
    # Quick self-test - Connaught Place, New Delhi
    test_lat, test_lon = 28.6315, 77.2167
    code = encode(test_lat, test_lon)
    result = decode(code)
    print(f"Original : {test_lat}, {test_lon}")
    print(f"GeoCode  : {code}")
    print(f"Decoded  : {result}")
