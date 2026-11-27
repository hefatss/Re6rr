---
name: Re6rr Project Context
description: Use when working in the Re6rr WMMT6RR native Android port repository: project layout, grounded recon evidence, freestanding C/JNI/Java bridge rules, validation, status and blockers.
---

# Konteks proyek Re6rr

Port native Android untuk *Wangan Midnight Maximum Tune 6RR* (Enma, x86-64,
DirectX 11, Lua 5.1). Targetnya reproduksi engine shipped dengan fidelity
setinggi mungkin, bukan perkiraan. Setiap fakta harus berasal dari dump atau
evidence dekompilasi; jangan mengarang field, semantik, mapping atau instance.

## Sumber kebenaran

- `README.md`: status table (**Done**, **Partial**, **Open**, **Out of scope**)
  dan ringkasan tiap area. Baca ini lebih dulu.
- `docs/RECON.md`, `docs/ENGINE.md`, `docs/ANDROID_HOST.md`: peta evidence, API C,
  wrapper Java, dan prosedur build/push blob.
- `docs/P1_STATUS.md`, `docs/P3_LUA_HOST.md`, `docs/P4_PHYSICS.md`,
  `docs/P4_COURSE_RACE.md`, `docs/P5_*.md`, `docs/ASSETS_NOTES.md`: detail phase.
- `docs/recon/*.json`: laporan turunan dari dump, **gitignored**. Regenerasi
  dengan `tools/recon/*.py` bila belum ada.
- `build/tmp/*.r6*`: blob turunan, **gitignored**. Dibuat oleh
  `tools/engine/*_catalog.py`. Jangan commit game data atau blob mentah.

Dump otoritatif: `D:\Games\W6W-05` (`wmn6r.exe`, `data/`, `data_jp/`).

## Peta kode

- `tools/recon/`: PE, `.pdata`, Lua, assets, Enma facts dari dump.
- `tools/x64/`: annotated disassembly, IR lift, C emit, Unicorn difftest,
  string/name-table xrefs.
- `tools/assets/`: gzip/NTWD, NDWD → OBJ, NSHR/DXBC, nut texture decode.
- `tools/lua/`: stock Lua 5.1.5 probe dan script-set queries.
- `engine/include/r6/r6_*.h`: public C API. `engine/src/core`: core freestanding.
  `engine/src/assets`, `src/game`, `src/host`: reader aset/game dan JNI.
- `platform/android/java/com/wmmt/re6rr/`: wrapper Java untuk JNI.
- `CMakeLists.txt` dan `tools/engine/build_host.py`: registrasi source C,
  build host, syntax check JNI/Java, dan test registration.

## Aturan inti

- Core freestanding: tanpa file I/O, inflate, WinAPI, CRT atau libm. Host
  menyuplai byte, memori dan callback math (`pow`/`exp2` untuk envelope, engine,
  config_3d dB).
- JNI mengembalikan nilai biasa atau byte hasil salinan. Pointer native tetap
  di native code; di Java hanya opaque integer bila memang diperlukan.
- Reader C wajib memvalidasi magic, versi, count, offset, capacity dan batas
  sebelum membaca. Kembalikan `R6_ERR_ARG`, `R6_ERR_FORMAT`, `R6_ERR_BUFFER`
  atau `R6_ERR_NOT_FOUND` sesuai kasus.
- Nama, RVA, path dan byte disalin apa adanya. Tidak ada interpretasi field
  yang belum terbukti, tidak ada binding buatan.

## Pola chunk turunan

Saat menambah inventory baru dari `docs/recon/*.json`:

1. Packer `tools/engine/<nama>_catalog.py` menghasilkan `build/tmp/<nama>.r6xx`.
2. Header `engine/include/r6/r6_<nama>.h` + reader di `engine/src/core`,
   `src/assets` atau `src/game`; daftarkan source di `CMakeLists.txt` dan
   `tools/engine/build_host.py`.
3. Wrapper Java di `platform/android/java/com/wmmt/re6rr/` + fungsi
   `Java_com_wmmt_re6rr_<Class>_native*` di `engine/src/host/jni.c`.
4. Test `tools/engine/test_<nama>_c.py` mencocokkan semua row dengan JSON dan
   menolak blob/index/row/capacity rusak.
5. Update `README.md`, `docs/ENGINE.md`, `docs/ANDROID_HOST.md` bila relevan.
6. Jalankan validasi penuh, lalu commit + push `origin/master` dengan pesan
   lengkap.

## Validasi

```powershell
python tools/engine/build_host.py --test --dump D:\Games\W6W-05
Get-ChildItem tools/engine/test_*.py | ForEach-Object { python $_.FullName --dump D:\Games\W6W-05 }
git diff --check
```

`git diff --check` hanya boleh menampilkan peringatan konversi CRLF. Jangan
anggap hijau tanpa menjalankan seluruh `test_*.py`.

## Status dan batas

- **Done**: P0 recon, P1 lift spike, P2 asset decode, P3 core + Lua, P4
  physics/course/race, P5 flow + catalogs, test suite.
- **Partial/Open**: instance predicate story per episode, playback/mixer audio,
  semantik field `.EES`, texture upload GPU, renderer driver nyata, Vulkan,
  build APK dan runtime Android.
- **Out of scope**: online, HASP/DRM dan All.Net.

Blocker yang sudah diketahui: import Ghidra/REA segar kena `provider_timeout`
(pakai evidence `docs/recon/ghidra_c/`), PDB tidak ada, trace Enma mandiri
gagal di `yt::CSeq::Init()`, mapping shader → `.nut` belum ada, dan tidak ada
driver GLES/perangkat audio untuk validasi runtime. Jangan mengulang percobaan
yang sama tanpa alasan baru.
