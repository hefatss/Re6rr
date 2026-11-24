/* The MSVC CRT normally provides _fltused; with -nostdlib nothing does. */
int _fltused = 1;

/* Entry point for the freestanding Windows host test DLL. */
int __stdcall DllMain(void *module, unsigned reason, void *reserved) {
    (void)module;
    (void)reason;
    (void)reserved;
    return 1;
}
