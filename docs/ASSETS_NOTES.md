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

## XMD stream table (decoded)

`python tools/assets/xmd_streams.py FILE` walks the offset table and clusters
streams by their first four bytes:

- `PLC_BNR34.mdl`: 129 streams, **all** start with `NDWD`.
- `PLC_BNR34.tex`: 4 streams, **all** start with `NTWD`.

So `XMD.001` is only a wrapper; `NDWD`/`NTWD` is the real container. The offset
table starts at payload `0x10` (`u32 version`, `u32 count`, then `u32 offsets`).
The first stream is not at `0x10 + 4*count`: there is another table between the
offsets and the payload, whose meaning is still unknown.

## NDWD mesh layout (decoded)

`python tools/assets/ndwd_mesh.py FILE --stream 0 --out out.obj` reconstructs a
Wavefront OBJ. Layout measured on `PLC_BNR34.mdl` streams 0 and 1:

| offset | field |
|---|---|
| `0x00` | `NDWD` / `NTWD` |
| `0x04` | `u32` id/hash (`0xb5f1`, `0x5164`, …) |
| `0x08` | `u16` version = 2 |
| `0x0a` | `u16` kind = 1 |
| `0x10` | three `u32` section byte sizes; sections start at `0x50` |
| section 0 | material / bone records (ends with a `12 06 …` marker) |
| section 1 | `u16` indices, `0xffff` ends a triangle strip |
| section 2 | 28-byte vertices: `f32 x,y,z`, `f32 param`, `u32 0xffffffff`, `f32 u,v` |

Section 2 is a run of vertices with the `0xffffffff` marker at word 4 of every
28-byte record. Gaps exist where another layout starts; the tool finds the runs
by their markers instead of assuming one stride over the whole section. Section
1 has ~12 trailing words that are not index data (values like `0xc0e1`), also
skipped. Stream 0 yields 920 vertices and 1,438 triangles as a sanity check.

The decoded z values are near zero for many vertices, so this stream may be a
decal/sprite mesh rather than the car body. No claim about mesh semantics yet.

## Next decode steps

1. Decode section 0 records (material/bone ids) and align them with the vertex
   runs; explain the gaps in section 2.
2. For textures: parse the `NTWD` header inside `.tex` for width/height/format,
   then the `GIDX` entries; identify DXT/BCn blocks by size (`w*h/2` for DXT1,
   `w*h` for DXT5).
3. Confirm the `GIDX` hash is a name hash (compare with the car id strings in
   `data/car/**/*.lua`).
