"""
db.py
-----
Thin data-access layer over MySQL (via PyMySQL).

If a live MySQL connection isn't available (e.g. running the project
on a laptop without MySQL installed, for a quick demo), the module
falls back to an in-memory store automatically so the app still runs
end-to-end. Swap DEMO_MODE off once MySQL is configured (see .env / README).
"""

import os
import random
import string
from datetime import datetime

try:
    import pymysql
    import pymysql.cursors
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "parcel_system"),
    "cursorclass": pymysql.cursors.DictCursor if PYMYSQL_AVAILABLE else None,
    "autocommit": True,
}

_memory_store = {"parcels": {}, "addresses": {}, "scan_events": [], "next_id": 1, "next_addr_id": 1}


def _get_connection():
    return pymysql.connect(**DB_CONFIG)


def _using_mysql():
    if not PYMYSQL_AVAILABLE:
        return False
    try:
        conn = _get_connection()
        conn.close()
        return True
    except Exception:
        return False


USE_MYSQL = _using_mysql()


def generate_tracking_id():
    return "PD" + "".join(random.choices(string.digits, k=8))


# ---------------------------------------------------------------------
# Address book — a receiver's location is captured ONCE (they must be at
# that spot when it's registered) and reused for every future parcel.
# This mirrors how a real system would work: you don't re-detect GPS for
# every parcel, because the sender's location has nothing to do with
# where the parcel needs to go.
# ---------------------------------------------------------------------

def create_address(receiver_name, receiver_phone, label, lat, lon, geocode, qr_path):
    if USE_MYSQL:
        conn = _get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO addresses
                       (receiver_name, receiver_phone, label, geocode, latitude, longitude, qr_path)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (receiver_name, receiver_phone, label, geocode, lat, lon, qr_path),
                )
                return cur.lastrowid
        finally:
            conn.close()
    else:
        aid = _memory_store["next_addr_id"]
        _memory_store["next_addr_id"] += 1
        _memory_store["addresses"][aid] = {
            "id": aid, "receiver_name": receiver_name, "receiver_phone": receiver_phone,
            "label": label, "geocode": geocode, "latitude": lat, "longitude": lon,
            "qr_path": qr_path, "created_at": datetime.now(),
        }
        return aid


def get_address_by_phone(phone):
    phone = phone.strip()
    if USE_MYSQL:
        conn = _get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM addresses WHERE receiver_phone=%s", (phone,))
                return cur.fetchone()
        finally:
            conn.close()
    else:
        for addr in _memory_store["addresses"].values():
            if addr["receiver_phone"] == phone:
                return addr
        return None


def get_address_by_id(address_id):
    if USE_MYSQL:
        conn = _get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM addresses WHERE id=%s", (address_id,))
                return cur.fetchone()
        finally:
            conn.close()
    else:
        return _memory_store["addresses"].get(address_id)


def get_all_addresses():
    if USE_MYSQL:
        conn = _get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM addresses ORDER BY created_at DESC")
                return cur.fetchall()
        finally:
            conn.close()
    else:
        return sorted(_memory_store["addresses"].values(),
                       key=lambda a: a["created_at"], reverse=True)


def create_parcel(address_id, sender_name, receiver_name, receiver_phone, raw_address,
                   lat, lon, geocode, qr_path, tracking_id=None):
    tracking_id = tracking_id or generate_tracking_id()

    if USE_MYSQL:
        conn = _get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO parcels
                       (tracking_id, address_id, geocode, sender_name, receiver_name,
                        receiver_phone, raw_address, latitude, longitude, qr_path)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (tracking_id, address_id, geocode, sender_name, receiver_name,
                     receiver_phone, raw_address, lat, lon, qr_path),
                )
                return cur.lastrowid, tracking_id
        finally:
            conn.close()
    else:
        pid = _memory_store["next_id"]
        _memory_store["next_id"] += 1
        _memory_store["parcels"][pid] = {
            "id": pid, "tracking_id": tracking_id, "address_id": address_id, "geocode": geocode,
            "sender_name": sender_name, "receiver_name": receiver_name,
            "receiver_phone": receiver_phone, "raw_address": raw_address,
            "latitude": lat, "longitude": lon, "status": "CREATED",
            "qr_path": qr_path, "created_at": datetime.now(),
        }
        return pid, tracking_id


def get_all_parcels():
    if USE_MYSQL:
        conn = _get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM parcels ORDER BY created_at DESC")
                return cur.fetchall()
        finally:
            conn.close()
    else:
        return sorted(_memory_store["parcels"].values(),
                       key=lambda p: p["created_at"], reverse=True)


def get_parcel_by_geocode(geocode):
    geocode = geocode.upper().strip()
    if USE_MYSQL:
        conn = _get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM parcels WHERE geocode=%s", (geocode,))
                return cur.fetchone()
        finally:
            conn.close()
    else:
        for p in _memory_store["parcels"].values():
            if p["geocode"] == geocode:
                return p
        return None


def get_parcel_by_tracking_id(tracking_id):
    if USE_MYSQL:
        conn = _get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM parcels WHERE tracking_id=%s", (tracking_id,))
                return cur.fetchone()
        finally:
            conn.close()
    else:
        for p in _memory_store["parcels"].values():
            if p["tracking_id"] == tracking_id:
                return p
        return None


def update_status(parcel_id, new_status):
    if USE_MYSQL:
        conn = _get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE parcels SET status=%s WHERE id=%s",
                            (new_status, parcel_id))
        finally:
            conn.close()
    else:
        if parcel_id in _memory_store["parcels"]:
            _memory_store["parcels"][parcel_id]["status"] = new_status


def log_scan_event(parcel_id, scanned_geocode, resolved=True, note=""):
    if USE_MYSQL:
        conn = _get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO scan_events (parcel_id, scanned_geocode, resolved, note)
                       VALUES (%s,%s,%s,%s)""",
                    (parcel_id, scanned_geocode, resolved, note),
                )
        finally:
            conn.close()
    else:
        _memory_store["scan_events"].append({
            "parcel_id": parcel_id, "scanned_geocode": scanned_geocode,
            "resolved": resolved, "note": note, "scanned_at": datetime.now(),
        })


def get_stats():
    parcels = get_all_parcels()
    total = len(parcels)
    delivered = sum(1 for p in parcels if p["status"] == "DELIVERED")
    in_transit = sum(1 for p in parcels if p["status"] in ("IN_TRANSIT", "OUT_FOR_DELIVERY"))
    failed = sum(1 for p in parcels if p["status"] == "FAILED")
    return {
        "total": total, "delivered": delivered,
        "in_transit": in_transit, "failed": failed,
        "created": sum(1 for p in parcels if p["status"] == "CREATED"),
    }
