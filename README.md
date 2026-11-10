# Themed Buildings

A UCP3 module for Stronghold Crusader: chapels, churches and cathedrals take the look of their
owner's lord - European lords build Christian buildings, Arabian lords build mosques. See
[module/locale/description-en.md](module/locale/description-en.md).

## What is in here

| Path | What |
| --- | --- |
| `module/` | the module (`init.lua`, options, locale, `resources/tile_churches_themed.gm1`) |
| `tools/build_gm1.py` | slices the themed PNGs into `tile_churches_themed.gm1` |
| `tools/publish.py` | copies `module/` into the game's `ucp/modules/themed-buildings-<version>` |

## Working on it

1. Edit the PNGs (Reconquista's `resources/themed buildings`): grand_mosque 414, church 286,
   small_mosque 190 px wide, the footprint's front corner on the bottom row.
2. `python tools/build_gm1.py --check` - rebuilds the sheet and draws it back into `check/`.
3. `python tools/publish.py --bump`, then F5 in the UCP3 GUI.

## How it works

* At game start the church sheet (gm 49) is copied into a free gm slot and gmResourceModifier
  loads the themed sheet into it.
* renderMap reads each map tile's picture twice (ground diamonds, building strips); both reads
  are hooked and a church-sheet picture is moved to the themed slot when the owner's lord
  side differs from the side the game files show.
* The side comes from the game's lord type function, asked once per player per tick.
