# Asset containers — first look

Only the outermost layer is decoded so far. Everything below is observed bytes
from this dump, not documentation.

## Car model — `data/car/car_data/playerCar/PLC_<car>/PLC_<car>.mdl`

```
gzip member  ->  XMD.001 container, 2,225,264 bytes for PLC_BNR34
```

XMD header (little endian):

| Offset | Bytes | Meaning |
|---|---|---|
| 0x00 | `58 4d 44 00 30 30 31` | `"XMD\0"` + `"001"` (ASCII tag, not a word) |
| 0x07 | `03 00 00 00` | 3 — version or platform id |
| 0x0B | `81 00 00 00` | 129 — entry count |
| 0x0F | `40 06 00 00` … | 129 uint32 offsets, first at `0x640`, then `0xBC40`, `0x10DB0`, … |

The offsets are monotonically increasing and land inside the payload, so the
container is simply "header + offset table + streams". Chunk payloads are
probably per-material geometry, animation and collision streams.

## Car texture — `PLC_<car>.tex`

Same XMD.001 wrapper with 4 entries, but the first stream starts with `NTWD`
(see below). `XMD.001` is therefore a generic wrapper, and `NTWD` is the real
texture/scene bank format.

## Scene / traffic model — `OTH_*.nut`

`NTWD`, no gzip-in-gzip. Header words: version `2`, entries `3`, then a table of
offsets to streams (`0x2AB50`, `0x2AAD0`, …). Streams carry four-letter tags:

- `eXt ` (0x655874) — extended chunk header, `u32 0x20` size field
- `GIDX` (0x58444947) — index chunk, followed by a 32-bit hash (`a9 68 e2 11` in
  OTH_KDH201V, `HGP`-style ids appear in `.nuf` fonts too)

Stream headers repeat the same field pattern (`50 ab 02 00 | 00 00 00 00 | d0 aa
02 00 | 80 00 00 00 | …`), consistent with `{size, ?, offset, flags}` records.

## Course geometry — `data/course/**/*.bin`

Raw float32, no header: `KKS_Sect1.bin` starts with `d2 a6 fe 46` (≈ 32627.4).
These are the per-section vertex/height streams referenced from
`course/stage/<stage>/<CITY>/clip/*.lua` tables.

## Next decode steps

1. Walk the XMD offset table for `PLC_BNR34.mdl` and tag each stream (dump the
   first 32 bytes of every entry, cluster identical patterns).
2. Locate vertex declarations (float triplets with plausible ranges, an index
   buffer with `u16`/`u32` monotonic runs) and reconstruct one mesh.
3. For textures: parse the `NTWD` header inside `.tex` for width/height/format,
   then the `GIDX` entries; identify DXT/BCn blocks by size (`w*h/2` for DXT1,
   `w*h` for DXT5).
4. Confirm the `GIDX` hash is a name hash (compare with the car id strings in
   `data/car/**/*.lua`).
