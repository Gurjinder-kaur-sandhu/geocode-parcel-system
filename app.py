"""
app.py
------
Flask web application for the GeoCode Parcel Delivery System.

Key design point
-----------------
A receiver's location is captured ONCE, at registration time, by whoever
is physically standing at that address (the receiver themselves, or a
field agent doing a one-time doorstep visit). That location becomes a
permanent GeoCode for that address — exactly like a phone number is
permanent for a person. Every future parcel to that receiver just looks
up their saved GeoCode; nobody re-detects GPS at parcel-creation time,
because the person creating the parcel (the sender / a courier office
clerk) is very likely standing somewhere else entirely.

Routes
------
GET  /                    dashboard (stats + recent parcels)
GET  /addresses           list all registered receiver addresses
GET  /addresses/new       form to register a new receiver address (GPS capture)
POST /addresses/new       geocode the location, generate GeoCode + QR, save
GET  /add                 form to create a parcel (pick a saved receiver)
POST /add                 create parcel against the receiver's saved GeoCode
GET  /track                search a parcel by GeoCode / tracking ID
POST /track                same, via form submit
GET  /scan                 upload a QR code image to "scan" a parcel
POST /scan                 decode QR, look up parcel, allow status update
POST /update-status        advance a parcel's status
GET  /api/geocode-from-coords   AJAX: GeoCode preview from raw GPS coordinates
"""

import os

import qrcode
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from PIL import Image

import db
import geocode as geocode_engine

try:
    from pyzbar.pyzbar import decode as decode_qr_image
    PYZBAR_AVAILABLE = True
except Exception:
    PYZBAR_AVAILABLE = False

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

QR_DIR = os.path.join(app.static_folder, "qrcodes")
os.makedirs(QR_DIR, exist_ok=True)


def make_qr(code: str, filename_base: str) -> str:
    """Generate a QR code image encoding the GeoCode, save it, return the web path."""
    img = qrcode.make(code)
    filename = f"{filename_base}.png"
    path = os.path.join(QR_DIR, filename)
    img.save(path)
    return f"qrcodes/{filename}"


@app.route("/")
def dashboard():
    parcels = db.get_all_parcels()
    stats = db.get_stats()
    return render_template("dashboard.html", parcels=parcels[:15], stats=stats)


# ------------------------------------------------------------------
# Address book — register a receiver's location ONCE
# ------------------------------------------------------------------

@app.route("/addresses")
def addresses():
    return render_template("addresses.html", addresses=db.get_all_addresses())


@app.route("/addresses/new", methods=["GET", "POST"])
def add_address():
    if request.method == "GET":
        return render_template("add_address.html")

    receiver_name = request.form.get("receiver_name", "").strip()
    receiver_phone = request.form.get("receiver_phone", "").strip()
    label = request.form.get("label", "").strip()
    lat_raw = request.form.get("latitude", "").strip()
    lon_raw = request.form.get("longitude", "").strip()

    if not all([receiver_name, receiver_phone, label, lat_raw, lon_raw]):
        flash("Fill in every field and capture a location before submitting.", "error")
        return render_template("add_address.html", form=request.form)

    if db.get_address_by_phone(receiver_phone):
        flash("This phone number is already registered. Search for it on the "
              "Addresses page instead of registering again.", "error")
        return render_template("add_address.html", form=request.form)

    lat, lon = float(lat_raw), float(lon_raw)
    code = geocode_engine.encode(lat, lon)
    qr_path = make_qr(code, f"addr_{code}")
    address_id = db.create_address(receiver_name, receiver_phone, label, lat, lon, code, qr_path)

    return render_template("add_address.html", success=True, address={
        "receiver_name": receiver_name, "receiver_phone": receiver_phone, "label": label,
        "geocode": code, "lat": lat, "lon": lon, "qr_path": qr_path,
    })


# ------------------------------------------------------------------
# Parcels — always reference an already-registered address
# ------------------------------------------------------------------

@app.route("/add", methods=["GET", "POST"])
def add_parcel():
    saved_addresses = db.get_all_addresses()

    if request.method == "GET":
        return render_template("add_parcel.html", addresses=saved_addresses)

    sender_name = request.form.get("sender_name", "").strip()
    address_id_raw = request.form.get("address_id", "").strip()
    note = request.form.get("note", "").strip()

    if not sender_name or not address_id_raw:
        flash("Pick a receiver and enter the sender's name.", "error")
        return render_template("add_parcel.html", addresses=saved_addresses)

    address = db.get_address_by_id(int(address_id_raw))
    if not address:
        flash("Couldn't find that receiver. Register their address first.", "error")
        return render_template("add_parcel.html", addresses=saved_addresses)

    tracking_id = db.generate_tracking_id()
    qr_path = make_qr(address["geocode"], f"parcel_{tracking_id}")
    parcel_id, tracking_id = db.create_parcel(
        address["id"], sender_name, address["receiver_name"], address["receiver_phone"],
        note or address["label"], address["latitude"], address["longitude"],
        address["geocode"], qr_path, tracking_id=tracking_id,
    )

    return render_template("add_parcel.html", addresses=saved_addresses, success=True, parcel={
        "tracking_id": tracking_id, "geocode": address["geocode"],
        "lat": address["latitude"], "lon": address["longitude"],
        "qr_path": qr_path, "receiver_name": address["receiver_name"],
        "label": address["label"],
    })


@app.route("/track", methods=["GET", "POST"])
def track():
    parcel = None
    searched = False
    if request.method == "POST":
        searched = True
        query = request.form.get("query", "").strip().upper()
        if geocode_engine.is_valid(query):
            parcel = db.get_parcel_by_geocode(query)
        else:
            parcel = db.get_parcel_by_tracking_id(query)
        if parcel is None:
            flash("No parcel found for that code. Double-check and try again.", "error")
    return render_template("track.html", parcel=parcel, searched=searched)


@app.route("/scan", methods=["GET", "POST"])
def scan():
    result = None
    if request.method == "POST":
        file = request.files.get("qr_image")
        manual_code = request.form.get("manual_code", "").strip()

        decoded_code = None
        if manual_code:
            decoded_code = manual_code.upper()
        elif file and file.filename and PYZBAR_AVAILABLE:
            try:
                img = Image.open(file.stream)
                decoded_objs = decode_qr_image(img)
                if decoded_objs:
                    decoded_code = decoded_objs[0].data.decode("utf-8").upper()
            except Exception:
                decoded_code = None
        elif file and file.filename and not PYZBAR_AVAILABLE:
            flash("QR image decoding isn't available in this environment "
                  "(install pyzbar + zbar). Use manual code entry instead.", "error")

        if decoded_code:
            parcel = db.get_parcel_by_geocode(decoded_code)
            if parcel:
                db.log_scan_event(parcel["id"], decoded_code, resolved=True)
                result = {"success": True, "parcel": parcel, "code": decoded_code}
            else:
                db.log_scan_event(-1, decoded_code, resolved=False, note="Unknown code")
                result = {"success": False, "code": decoded_code}
        elif not manual_code and not (file and file.filename):
            flash("Upload a QR image or type a GeoCode to scan.", "error")

    return render_template("scan.html", result=result, pyzbar_available=PYZBAR_AVAILABLE)


@app.route("/update-status", methods=["POST"])
def update_status():
    parcel_id = int(request.form["parcel_id"])
    new_status = request.form["status"]
    db.update_status(parcel_id, new_status)
    flash(f"Status updated to {new_status.replace('_', ' ').title()}.", "success")
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/api/geocode-from-coords")
def api_geocode_from_coords():
    """AJAX helper: given exact GPS coordinates, return the GeoCode preview."""
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_coords"}), 400
    code = geocode_engine.encode(lat, lon)
    return jsonify({"lat": lat, "lon": lon, "geocode": code})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
