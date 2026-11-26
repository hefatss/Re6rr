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

## NTWD textures (decoded from Ghidra)

`python tools/assets/ntwd_texture.py FILE` parses every NTWD stream. The
loader functions `FUN_140cae1a0`, `FUN_140cbc000`, `FUN_140cbc0d0`,
`FUN_140cbc0f0`, `FUN_140cbc190` and `FUN_140cbc270` in `wmn6r.exe` give this
layout:

| offset | field |
|---|---|
| `0x00` | `NTWD` |
| `0x04` | `u8` type = 2 in this dump (1 also handled), `u8` pad, `u16` texture count |
| `0x08` | two `u32` zeros |
| `0x10` | texture headers, `count` of them, stride = `u16` at header `+0xc` (normally `0x50`) |

Texture header (relative to its start):

| offset | field |
|---|---|
| `+0x00` | `u32` type-1 stride / total size |
| `+0x08` | `u32` pixel byte count |
| `+0x0c` | `u16` header stride (`0x50`) |
| `+0x11` | `u8` mip-level count (also drives the eXt/GIDX table skip) |
| `+0x13` | `u8` format: `0` = BC1, `1` = BC2, `2` = BC3, `0x0e` = ARGB8, `0x15` = A8R8G8B8 |
| `+0x14` | `u16` width, `u16` height |
| `+0x1c` | `u32` flags; bit 9 shifts the `eXt`/`GIDX` chunks by `0x10`, bit 17 marks cube maps |
| `+0x20` | `u32` type-2 pixel offset from header start |
| `+0x30` | face table, then `eXt` chunk, then `GIDX` chunk; hash at `GIDX+8` |

All texture headers come first; pixel blobs start after them. Blob range
`header + data_off .. + data_size` was valid for all 10,555 textures in 3,374
NTWD streams from 683 `.tex` files (8 files were not gzip members), checked by
`python tools/assets/ntwd_validate.py DIR`. Payload size is the sum of
`+0x11` mip levels, each rounded to 16 bytes; cube flags multiply the chain by
six. Size ratios of 5.33/10.67 bpp come from full mip chains (`4/3` of the base
size). The same model validates 50,177 type-2 `.nut` entries in
`tools/engine/test_nut_texture.py`; three NPOT BC3 entries are short one mip.
`GIDX` value is a texture id: `FUN_140c8f7d0` formats it as `"0x%08x"` and
uses that string as a lookup key, not a name hash.

## NDWD section 0 records (decoded from Ghidra)

`python tools/assets/ndwd_records.py FILE --stream N` prints the structures
below. Loader functions are `FUN_140ca78b0`, `FUN_140ca7b00`, `FUN_140ca7c10`
and `FUN_140ca7ed0`.

| offset | field |
|---|---|
| `0x00` | `NDWD`, `u32` id, `u16` version = 2, `u16` group count |
| `0x10` | four `u32` section sizes; sections start at `0x50` |
| `0x30` | group records, `0x30` bytes each: `u32` name offset at `+0x20`, `u16` subrecord count at `+0x2a`, `u32` subrecord start at `+0x2c` |
| subrecord | `0x30` bytes; four `u32` texture hashes at `+0x10..0x1c`, `u16` extra count at `+0xa`; material chain at `+0x20 + extra*0x18`, walking `u32` strides while the byte at `+0xb` is nonzero |

Section 1 is `u16` triangle-strip indices with `0xffff` separators. Section 2
contains `28-byte` vertex runs with a `0xffffffff` word at index 4 (bone id
`-1`), but other layouts also occur in the same section, so a single stride
does not cover the whole section. `PLC_BNR34.mdl` stream 0 has three runs of
449, 790 and 88 such vertices with gaps between them; those gaps are the
other layouts, not padding.

## Remaining unknowns

- Which subrecord layout selects each section-2 vertex format.
- Meaning of the `u32` values at subrecord `+0x20`/`+0x24` (chain records and
  texture hashes are decoded; their role in geometry is not).
- The three NPOT BC3 entries that store one mip level fewer than declared.
