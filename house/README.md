# Home Studio — 3D walkthrough of the house

Private tool, lives at **/house**. Not linked from the site, `noindex`, and blocked in
`robots.txt`. Nothing about it touches the coaching pages.

## The house

`house/house.json` is The Arisaig (CALA) built to the published room sizes, and
**handed** — the plan as CALA draw it is the mirror of this plot, so it has been
flipped: coming in the front door, the WC and utility cupboard are on your left
and the kitchen on your right. If that turns out to be the wrong way round,
select a level and hit **Mirror this level ↔** to flip it back.

Room sizes marked on the plan are exact. Corridors, cupboards and the stair
position are worked out from the photos, so nudge anything that reads wrong.
The app loads this file on first run; **Reload house layout** in Setup puts it
back if you want a clean start.

Interior photos are deliberately **not** in this repo — it is public. They live
in a separate `.house.json` pack that gets imported straight into the browser.

## What it does

- **Plan** — draw rooms, drop in doors and windows, place furniture. Everything is real
  measurements, so if it does not fit on the plan it will not fit in the house.
- **3D** — the dollhouse view. Orbit round it, drag to spin, right-drag to pan.
- **Walk** — first person. Click to grab the mouse, `WASD` to move, `Shift` to jog,
  `Q` to crouch, `Esc` to let go. Look at something and press `E` to open its shop link.

## Adding stuff from websites

Hit **+ Add from link**, paste a product URL, press *Pull the details*. The page is read
server-side by `/api/product-lookup` (a browser cannot read another site's page itself),
and you get back the name, photo, price and — where the listing prints them — the real
width, depth and height. Anything it cannot find you type in yourself.

Every item carries its link, price and status (idea / ordered / owned), so the sidebar
doubles as a budget and **Export shopping list (CSV)** gives you the lot in a spreadsheet.

## Photos and floor plans

- Import the photo pack (**Import**, pick the `.house.json`) and every room photo
  arrives already attached to its room.
- **Photos tab → Upload** for new pictures of rooms as they are now. Attach a photo to a room
  and it appears in the corner while you walk through that room. *Hang it on a wall* turns
  a photo into a framed picture you can place in 3D.
- **Floor plan underlay**: upload a plan for the level, hit *Set scale* and drag along
  something you know the length of (a door is usually 0.9 m), then trace the rooms over
  the top with the room tool. That is the fastest way to get a real house in here.

## Where the data lives

In your browser (IndexedDB), on that device only. **Export** writes a `.house.json`
backup you can import on another machine — do that before clearing site data. Photos are
shrunk on upload so the file stays manageable.

## Files

| File | What it is |
| --- | --- |
| `house/index.html` | the page |
| `house/house.css` | styles |
| `house/house.js` | plan editor, geometry, three.js scene, walkthrough |
| `api/product-lookup.js` | server-side product page reader (https only, public addresses only, no storage) |

three.js is pulled from cdnjs at runtime; if it cannot load, the plan view still works.
