import random
from datetime import date, datetime, time, timedelta

import streamlit as st

st.set_page_config(page_title="SkyBook", page_icon="✈️", layout="wide")

# ---------- Data ----------
CITIES = ["Kochi", "Delhi", "Mumbai", "Bengaluru", "Chennai", "Hyderabad",
          "Kolkata", "Goa", "Thiruvananthapuram", "Dubai", "Singapore"]
CODES = {"Kochi": "COK", "Delhi": "DEL", "Mumbai": "BOM", "Bengaluru": "BLR",
         "Chennai": "MAA", "Hyderabad": "HYD", "Kolkata": "CCU", "Goa": "GOI",
         "Thiruvananthapuram": "TRV", "Dubai": "DXB", "Singapore": "SIN"}
AIRLINES = [("Air India", "AI"), ("IndiGo", "6E"), ("Emirates", "EK"),
            ("Vistara", "UK"), ("SpiceJet", "SG"), ("Akasa Air", "QP")]
CLASS_MULT = {"Economy": 1.0, "Premium Economy": 1.4, "Business": 2.2}
MEALS = {"No meal": 0, "Veg meal": 250, "Non-veg meal": 300}
BAG_PRICE = 1200
STEPS = ["Search", "Flights", "Passengers", "Seats", "Payment", "Ticket"]
SEAT_LIST = [f"{r}{c}" for r in range(1, 11) for c in "ABCDEF"]

# ---------- State ----------
defaults = {"page": "Home", "bookings": [], "flight": None, "passengers": [],
            "booking": None, "seats": {}, "from_city": "Kochi",
            "to_city": "Delhi", "date": date.today(), "people": 1}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------- Styling ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;800&display=swap');
.stApp{background:linear-gradient(160deg,#35b6ff,#6a5cff,#ff5fa2,#ffb347);
 background-size:300% 300%;animation:sky 18s ease infinite}
@keyframes sky{0%,100%{background-position:0% 0%}50%{background-position:100% 100%}}
[data-testid="stHeader"]{background:transparent}
.block-container{position:relative;z-index:2;max-width:1100px;margin-top:1rem;
 background:rgba(255,255,255,.94);border-radius:26px;padding:1.5rem 2rem 2rem!important;
 box-shadow:0 20px 60px rgba(40,20,120,.35)}
h1,h2,h3{font-family:'Baloo 2',cursive!important;color:#3a1c8f}
.cloud{position:fixed;z-index:-1;pointer-events:none;background:rgba(255,255,255,.55);
 border-radius:100px;animation:drift linear infinite}
.cloud::before,.cloud::after{content:"";position:absolute;background:inherit;border-radius:50%}
.cloud::before{width:50%;height:160%;top:-70%;left:15%}
.cloud::after{width:35%;height:130%;top:-45%;right:15%}
.c1{width:160px;height:40px;top:12%;left:-200px;animation-duration:38s}
.c2{width:240px;height:55px;top:45%;left:-300px;animation-duration:55s;animation-delay:-20s}
.c3{width:120px;height:32px;top:75%;left:-200px;animation-duration:30s;animation-delay:-8s}
@keyframes drift{to{transform:translateX(calc(100vw + 400px))}}
.hero{position:relative;overflow:hidden;color:#fff;padding:1.4rem 2rem 2.6rem;border-radius:20px;
 margin-bottom:1rem;background:linear-gradient(120deg,#ff5f6d,#ff9a44 50%,#ffd36b);
 box-shadow:0 10px 24px rgba(255,95,109,.4)}
.hero h1{margin:0;padding:0;font-size:2.8rem!important;color:#fff!important;
 font-family:'Baloo 2',cursive;text-shadow:0 3px 0 rgba(0,0,0,.12)}
.hero p{margin:.2rem 0 0;color:#fff!important;font-size:1.1rem}
.hero::after{content:"";position:absolute;left:0;right:0;bottom:16px;
 border-top:3px dashed rgba(255,255,255,.6)}
.plane{position:absolute;bottom:2px;left:-80px;font-size:2.2rem;animation:fly 8s linear infinite}
@keyframes fly{0%{left:-80px;transform:translateY(0)}50%{transform:translateY(-10px)}
 100%{left:105%;transform:translateY(0)}}
.stButton>button,.stDownloadButton>button{border:0;border-radius:999px;font-weight:700;
 background:linear-gradient(90deg,#6a5cff,#ff5fa2);box-shadow:0 6px 16px rgba(106,92,255,.35);
 transition:transform .15s,box-shadow .15s}
.stButton>button *,.stDownloadButton>button *{color:#fff!important}
[data-testid="stBaseButton-primary"]{background:linear-gradient(90deg,#ff9a44,#ff5f6d)!important}
.stButton>button:hover,.stDownloadButton>button:hover{transform:translateY(-3px) scale(1.03);
 box-shadow:0 10px 22px rgba(255,95,162,.45)}
.stButton>button:active{transform:scale(.97)}
.steps{display:flex;gap:6px;margin:.5rem 0 1rem;flex-wrap:wrap}
.step{flex:1;min-width:80px;text-align:center;padding:7px 4px;border-radius:999px;
 font-size:.85rem;background:#ece8ff;color:#5b4bb8}
.step.done{background:linear-gradient(90deg,#00c9a7,#3ad6b5);color:#fff}
.step.now{background:linear-gradient(90deg,#ff9a44,#ff5f6d);color:#fff;font-weight:700;
 animation:pulse 1.6s infinite}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(255,95,109,.55)}50%{box-shadow:0 0 0 8px rgba(255,95,109,0)}}
.fcard{background:#fff;color:#1b1650;border-left:8px solid #ff5fa2;border-radius:16px;
 padding:14px 18px;margin-bottom:6px;box-shadow:0 6px 18px rgba(58,28,143,.18);
 animation:rise .5s ease both;transition:transform .2s}
.fcard:hover{transform:translateX(6px)}
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
.fcard .air{font-weight:700;font-size:1.1rem}
.fcard .route{display:flex;align-items:center;gap:14px;margin:8px 0;font-size:1.3rem;font-weight:600}
.fcard .line{flex:1;position:relative;border-top:2px dashed #b7a8ff;text-align:center;
 font-size:.75rem;font-weight:400;padding-top:6px}
.fcard .line::after{content:"✈";position:absolute;left:0;top:-15px;font-size:1.1rem;
 color:#6a5cff;animation:along 3s linear infinite}
@keyframes along{to{left:calc(100% - 1rem)}}
.tag{display:inline-block;padding:2px 10px;border-radius:20px;font-size:.78rem;
 background:#ffe2ee;color:#c2185b;margin-right:6px}
.price{font-size:1.4rem;font-weight:800;color:#ff5f6d}
.seatrow{display:flex;gap:5px;justify-content:center;margin-bottom:5px;align-items:center}
.seat{width:34px;height:30px;border-radius:9px 9px 3px 3px;font-size:.7rem;display:flex;
 align-items:center;justify-content:center;background:#bfe3ff;color:#16306b;
 transition:transform .15s}
.seat:hover{transform:translateY(-3px) scale(1.12)}
.seat.taken{background:#9aa0b4;color:#fff;opacity:.6}
.seat.mine{background:linear-gradient(#ffb347,#ff5f6d);color:#fff;font-weight:700;
 animation:pulse 1.6s infinite}
.aisle{width:22px}.rownum{width:22px;font-size:.7rem;text-align:center;opacity:.7}
.bp{background:#fff;color:#1b1650;border-radius:16px;margin:14px 0;overflow:hidden;
 box-shadow:0 10px 26px rgba(58,28,143,.25);display:flex;flex-wrap:wrap;
 animation:slide .7s cubic-bezier(.2,.9,.3,1.2) both}
@keyframes slide{from{opacity:0;transform:translateX(-60px)}to{opacity:1;transform:none}}
.bp .main{flex:3;min-width:260px;padding:0 0 18px}
.bp .stub{flex:1;min-width:170px;padding:18px;border-left:2px dashed #b7a8ff;background:#fff3d6}
.bp .head{background:linear-gradient(90deg,#6a5cff,#ff5fa2);color:#fff;padding:9px 22px;
 font-weight:700;letter-spacing:.5px}
.bp .big{font-size:2.2rem;font-weight:800;line-height:1;color:#3a1c8f}
.bp .small{font-size:.75rem;color:#6b7280}
.bp .row{display:flex;gap:22px;margin:14px 22px 0;flex-wrap:wrap;align-items:center}
.bp .bar{height:34px;margin-top:10px;background:repeating-linear-gradient(90deg,#3a1c8f 0 2px,
 transparent 2px 5px,#3a1c8f 5px 6px,transparent 6px 10px)}
.flyby{position:fixed;inset:0;z-index:9999;pointer-events:none;overflow:hidden;
 animation:fadeout 1.7s forwards}
.flyplane{position:absolute;top:42%;left:-150px;font-size:5rem;
 filter:drop-shadow(0 10px 8px rgba(0,0,0,.3));animation:flyacross 1.5s ease-in forwards}
.flyplane::before{content:"";position:absolute;right:85%;top:55%;width:320px;height:8px;
 border-radius:8px;background:linear-gradient(90deg,transparent,rgba(255,255,255,.95))}
@keyframes flyacross{from{left:-150px;transform:translateY(60px)}
 to{left:105%;transform:translateY(-140px)}}
@keyframes fadeout{0%,85%{opacity:1}100%{opacity:0}}
@media(max-width:640px){.block-container{padding:1rem!important}.hero h1{font-size:2rem!important}}
@media(prefers-reduced-motion:reduce){.flyby{display:none}*{animation:none!important;transition:none!important}}
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="cloud c1"></div><div class="cloud c2"></div><div class="cloud c3"></div>'
    '<div class="hero"><h1>SkyBook</h1><p>Your Journey, Our Responsibility</p>'
    '<div class="plane">✈️</div></div>',
    unsafe_allow_html=True)

# ---------- Navigation ----------
a, b, c = st.columns(3)
for col, label, pg in [(a, "🏠 Home", "Home"), (b, "🔎 Search Flights", "Search"),
                       (c, "📚 My Bookings", "Bookings")]:
    if col.button(label, use_container_width=True, key="nav_" + pg):
        st.session_state.page = pg
        st.session_state.fly = True
        st.rerun()

page = st.session_state.page

# Plane flies across the screen after a page-changing button click
if st.session_state.pop("fly", False):
    st.markdown('<div class="flyby"><span class="flyplane">✈️</span></div>',
                unsafe_allow_html=True)


def go(p):
    st.session_state.page = p
    st.session_state.fly = True
    st.rerun()


def progress(current):
    html = '<div class="steps">'
    idx = STEPS.index(current)
    for i, s in enumerate(STEPS):
        cls = "now" if i == idx else ("done" if i < idx else "")
        html += f'<div class="step {cls}">{s}</div>'
    st.markdown(html + "</div>", unsafe_allow_html=True)


def make_flights(src, dst, d):
    rng = random.Random(f"{src}{dst}{d}".lower())
    base = rng.randint(3200, 6500)
    out = []
    for name, code in rng.sample(AIRLINES, 5):
        dep = datetime.combine(d, time(rng.choice([5, 7, 9, 12, 15, 18, 21]),
                                       rng.choice([0, 15, 30, 45])))
        stops = rng.choice([0, 0, 1])
        mins = rng.randint(100, 260) + (70 if stops else 0)
        cls = rng.choice(["Economy", "Economy", "Premium Economy", "Business"])
        price = int(base * CLASS_MULT[cls] * (0.9 if stops else 1) / 50) * 50
        out.append({"airline": name, "number": f"{code}-{rng.randint(100, 999)}",
                    "dep": dep.strftime("%I:%M %p"),
                    "arr": (dep + timedelta(minutes=mins)).strftime("%I:%M %p"),
                    "mins": mins, "stops": stops, "class": cls, "price": price})
    return out


def taken_seats(flight):
    rng = random.Random(flight["number"] + str(st.session_state.date))
    return set(rng.sample(SEAT_LIST, 20))


def seat_map(taken, mine):
    html = ""
    for r in range(1, 11):
        html += f'<div class="seatrow"><div class="rownum">{r}</div>'
        for letter in "ABCDEF":
            s = f"{r}{letter}"
            cls = "taken" if s in taken else ("mine" if s in mine else "")
            html += f'<div class="seat {cls}">{s}</div>'
            if letter == "C":
                html += '<div class="aisle"></div>'
        html += "</div>"
    legend = ('<div class="seatrow"><span class="seat">Free</span>'
              '<span class="seat mine">You</span><span class="seat taken">Taken</span></div>')
    st.markdown(legend + html, unsafe_allow_html=True)


def boarding_pass(b, p):
    return (
        f'<div class="bp"><div class="main"><div class="head">SKYBOOK BOARDING PASS</div>'
        f'<div class="row"><div><div class="big">{CODES.get(b["from"], b["from"][:3].upper())}</div>'
        f'<div class="small">{b["from"]}</div></div><div class="big">✈</div>'
        f'<div><div class="big">{CODES.get(b["to"], b["to"][:3].upper())}</div>'
        f'<div class="small">{b["to"]}</div></div></div>'
        f'<div class="row"><div><div class="small">Passenger</div><b>{p["name"]}</b></div>'
        f'<div><div class="small">Flight</div><b>{b["flight"]}</b></div>'
        f'<div><div class="small">Date</div><b>{b["date"]}</b></div>'
        f'<div><div class="small">Time</div><b>{b["time"]}</b></div></div></div>'
        f'<div class="stub"><div class="small">Seat</div><div class="big">{p["seat"]}</div>'
        f'<div class="small" style="margin-top:8px">Class</div><b>{b["class"]}</b>'
        f'<div class="small" style="margin-top:8px">Booking</div><b>{b["id"]}</b>'
        f'<div class="bar"></div></div></div>')


# ---------- Home ----------
if page == "Home":
    st.header("Welcome to SkyBook! 👋")
    st.write("Search flights, pick your seat on a live seat map, and get a boarding pass.")
    x, y, z = st.columns(3)
    x.subheader("🔎 Search")
    x.write("Choose cities and compare 5 flights by price, speed or time.")
    y.subheader("💺 Pick Seats")
    y.write("See which seats are taken and choose your own.")
    z.subheader("🎫 Boarding Pass")
    z.write("Add meals and baggage, apply a promo, and download your ticket.")
    st.info("Try the promo code **SKY10** at payment for 10% off the base fare.")
    if st.button("Start Booking", key="start", type="primary"):
        go("Search")

# ---------- Search ----------
elif page == "Search":
    progress("Search")
    st.header("🔎 Search Flights")
    x, y = st.columns(2)
    source = x.selectbox("From", CITIES, index=CITIES.index(st.session_state.from_city))
    destination = y.selectbox("To", CITIES, index=CITIES.index(st.session_state.to_city))
    d = st.date_input("Travel Date", value=max(st.session_state.date, date.today()),
                      min_value=date.today())
    people = st.number_input("Passengers", 1, 9, st.session_state.people)

    if st.button("Search Flights", key="submit_search", type="primary"):
        if source == destination:
            st.warning("Departure and destination must differ.")
        else:
            st.session_state.update(from_city=source, to_city=destination,
                                    date=d, people=int(people))
            go("Flights")

# ---------- Flights ----------
elif page == "Flights":
    progress("Flights")
    ss = st.session_state
    st.header(f"✈️ {ss.from_city} → {ss.to_city}")
    st.caption(f"{ss.date.strftime('%A, %d %B %Y')} · {ss.people} passenger(s)")

    x, y = st.columns(2)
    sort = x.radio("Sort by", ["Cheapest", "Fastest", "Earliest"], horizontal=True)
    cls_filter = y.multiselect("Class", list(CLASS_MULT), default=list(CLASS_MULT))

    flights = [f for f in make_flights(ss.from_city, ss.to_city, ss.date)
               if f["class"] in cls_filter]
    key = {"Cheapest": lambda f: f["price"], "Fastest": lambda f: f["mins"],
           "Earliest": lambda f: datetime.strptime(f["dep"], "%I:%M %p")}[sort]
    flights.sort(key=key)

    if not flights:
        st.info("No flights match these filters. Select more classes.")
    for i, f in enumerate(flights):
        stop_txt = "Non-stop" if f["stops"] == 0 else "1 stop"
        st.markdown(
            f'<div class="fcard"><div class="air">{f["airline"]} '
            f'<span style="font-weight:400">{f["number"]}</span></div>'
            f'<div class="route"><span>{f["dep"]}</span>'
            f'<span class="line">{f["mins"] // 60}h {f["mins"] % 60}m · {stop_txt}</span>'
            f'<span>{f["arr"]}</span></div>'
            f'<span class="tag">{f["class"]}</span>'
            f'<span class="price">₹{f["price"]:,}</span> per passenger</div>',
            unsafe_allow_html=True)
        if st.button("Select " + f["airline"], key=f"flight_{i}"):
            for k in [k for k in ss.keys() if k.startswith(("seat_", "meal_", "bag_"))]:
                del ss[k]
            ss.flight = {"airline": f["airline"], "number": f["number"],
                         "time": f"{f['dep']} - {f['arr']}", "class": f["class"],
                         "price": f["price"]}
            ss.passengers, ss.seats = [], {}
            go("Passengers")

    if st.button("← Change search"):
        go("Search")

# ---------- Passengers ----------
elif page == "Passengers":
    progress("Passengers")
    st.header("👤 Passenger Details")
    data = []
    for i in range(st.session_state.people):
        st.subheader(f"Passenger {i + 1}")
        name = st.text_input("Full Name", key=f"name_{i}")
        x, y = st.columns(2)
        age = x.number_input("Age", 1, 100, 18, key=f"age_{i}")
        kind = y.selectbox("Type", ["Adult", "Child"], key=f"type_{i}")
        phone = st.text_input("Phone (10 digits)", key=f"phone_{i}")
        email = st.text_input("Email", key=f"email_{i}")
        data.append({"name": name.strip(), "age": age, "type": kind,
                     "phone": phone.strip(), "email": email.strip()})

    if st.button("Continue to Seat Selection", type="primary"):
        bad_phone = any(not (p["phone"].isdigit() and len(p["phone"]) == 10) for p in data)
        if any(not p["name"] or "@" not in p["email"] for p in data) or bad_phone:
            st.warning("Fill in every name, a 10-digit phone number and a valid email.")
        else:
            st.session_state.passengers = data
            go("Seats")
    if st.button("Back to Flights"):
        go("Flights")

# ---------- Seats ----------
elif page == "Seats":
    progress("Seats")
    st.header("💺 Seat Selection")
    st.caption("Grey seats are already taken. Each passenger needs a different seat.")
    taken = taken_seats(st.session_state.flight)
    free = [s for s in SEAT_LIST if s not in taken]

    chosen = {}
    for i, p in enumerate(st.session_state.passengers):
        chosen[str(i)] = st.selectbox(f"{p['name']} — Seat", free,
                                      index=min(i, len(free) - 1), key=f"seat_{i}")
    seat_map(taken, set(chosen.values()))

    if st.button("Continue to Payment", type="primary"):
        if len(set(chosen.values())) != len(chosen):
            st.error("Two passengers cannot share the same seat.")
        else:
            st.session_state.seats = chosen
            for i, p in enumerate(st.session_state.passengers):
                p["seat"] = chosen[str(i)]
            go("Payment")
    if st.button("Back to Passenger Details"):
        go("Passengers")

# ---------- Payment ----------
elif page == "Payment":
    progress("Payment")
    ss = st.session_state
    f, passengers = ss.flight, ss.passengers

    st.header("💳 Payment")
    st.write(f"**{f['airline']} ({f['number']})** · {ss.from_city} → {ss.to_city} · {ss.date}")

    st.subheader("Extras")
    extras = 0
    for i, p in enumerate(passengers):
        x, y = st.columns(2)
        meal = x.selectbox(f"{p['name']} — Meal", list(MEALS), key=f"meal_{i}")
        bag = y.checkbox(f"Extra 15 kg baggage (+₹{BAG_PRICE:,})", key=f"bag_{i}")
        p["meal"] = meal
        p["bag"] = bag
        extras += MEALS[meal] + (BAG_PRICE if bag else 0)

    promo = st.text_input("Promo code").strip().upper()
    base = f["price"] * len(passengers)
    discount = base * 0.10 if promo == "SKY10" else 0
    if promo and not discount:
        st.warning("That promo code is not valid.")
    elif discount:
        st.success("SKY10 applied: 10% off the base fare.")
    gst = (base + extras - discount) * 0.05
    total = base + extras - discount + gst

    st.divider()
    st.write(f"Base Fare: ₹{base:,.2f}")
    st.write(f"Extras: ₹{extras:,.2f}")
    if discount:
        st.write(f"Discount: -₹{discount:,.2f}")
    st.write(f"GST (5%): ₹{gst:,.2f}")
    st.subheader(f"Total: ₹{total:,.2f}")

    method = st.radio("Payment Method", ["Credit / Debit Card", "UPI"])
    if method == "Credit / Debit Card":
        card = st.text_input("Card Number (16 digits)")
        x, y = st.columns(2)
        x.text_input("Expiry Date (MM/YY)")
        cvv = y.text_input("CVV", type="password")
        valid = card.replace(" ", "").isdigit() and len(card.replace(" ", "")) == 16 \
            and cvv.isdigit() and len(cvv) == 3
        problem = "Enter a 16-digit card number and a 3-digit CVV."
    else:
        upi = st.text_input("UPI ID", placeholder="example@upi")
        valid = "@" in upi
        problem = "Enter a valid UPI ID, like name@upi."

    if st.button("← Back to Seats"):
        go("Seats")

    if st.button("Confirm Payment", type="primary"):
        if not valid:
            st.error(problem)
        else:
            booking = {
                "id": "SB" + str(random.randint(10000, 99999)),
                "airline": f["airline"], "flight": f["number"], "time": f["time"],
                "class": f["class"], "from": ss.from_city, "to": ss.to_city,
                "date": str(ss.date), "passengers": [p.copy() for p in passengers],
                "base": base, "extras": extras, "discount": discount,
                "gst": gst, "total": total, "method": method}
            ss.bookings.append(booking)
            ss.booking = booking
            ss.celebrate = True
            go("Ticket")

# ---------- Ticket ----------
elif page == "Ticket":
    b = st.session_state.booking
    if b is None:
        st.warning("No booking found.")
    else:
        progress("Ticket")
        if st.session_state.pop("celebrate", False):
            st.balloons()
        st.header("🎫 Booking Confirmed!")
        st.success(f"Booking ID: {b['id']} (simulated booking)")

        for p in b["passengers"]:
            st.markdown(boarding_pass(b, p), unsafe_allow_html=True)

        st.subheader("💰 Payment Summary")
        st.write(f"Base Fare: ₹{b['base']:,.2f}")
        st.write(f"Extras: ₹{b['extras']:,.2f}")
        if b["discount"]:
            st.write(f"Discount: -₹{b['discount']:,.2f}")
        st.write(f"GST: ₹{b['gst']:,.2f}")
        st.write(f"**Total: ₹{b['total']:,.2f}** · {b['method']}")

        ticket = (f"SKYBOOK FLIGHT TICKET\nBooking ID: {b['id']}\n"
                  f"Airline: {b['airline']}\nFlight: {b['flight']}\n"
                  f"From: {b['from']}\nTo: {b['to']}\nDate: {b['date']}\n"
                  f"Time: {b['time']}\nClass: {b['class']}\n\n")
        for i, p in enumerate(b["passengers"]):
            ticket += (f"Passenger {i + 1}: {p['name']}\nAge: {p['age']} | Type: {p['type']}\n"
                       f"Seat: {p['seat']}\nMeal: {p['meal']}\n"
                       f"Extra baggage: {'Yes' if p['bag'] else 'No'}\n"
                       f"Phone: {p['phone']}\nEmail: {p['email']}\n\n")
        ticket += (f"Base Fare: Rs. {b['base']:.2f}\nExtras: Rs. {b['extras']:.2f}\n"
                   f"Discount: Rs. {b['discount']:.2f}\nGST: Rs. {b['gst']:.2f}\n"
                   f"Total: Rs. {b['total']:.2f}\nPayment Method: {b['method']}\n"
                   "Simulated school project booking.")

        st.download_button("📥 Download Ticket", ticket,
                           file_name=f"SkyBook_{b['id']}.txt", mime="text/plain")
        if st.button("View My Bookings"):
            go("Bookings")
        if st.button("Back to Home"):
            go("Home")

# ---------- My Bookings ----------
elif page == "Bookings":
    st.header("📚 My Bookings")
    bookings = st.session_state.bookings
    if not bookings:
        st.info("You don't have any bookings yet. Search for a flight to get started.")
    else:
        st.metric("Total spent", f"₹{sum(b['total'] for b in bookings):,.2f}",
                  f"{len(bookings)} booking(s)")
        for b in reversed(list(bookings)):
            with st.expander(f"🎫 {b['id']} · {b['from']} → {b['to']} · {b['date']}"):
                st.write(f"{b['airline']} ({b['flight']}) · {b['time']} · {b['class']}")
                st.write(f"Total: ₹{b['total']:,.2f}")
                for p in b["passengers"]:
                    st.write(f"👤 {p['name']} — Seat {p['seat']}")
                if st.button("Cancel this booking", key="cancel_" + b["id"]):
                    bookings.remove(b)
                    st.rerun()

    if st.button("✈️ Book Another Flight", type="primary"):
        go("Search")
