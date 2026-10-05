# cbz-jxl

`cbx-jackal book.cbz` → `book.jxl.cbz`. Every JPEG page re-encoded to JXL; everything else copied verbatim.
Python entry point, no Python imaging libraries, `cjxl` the only external tool, preflight-checked.

## Locked

- **Lossless by default.** Bare invocation never destroys quality. On the test page it is also *smaller* than lossy `-q 95` and level with `-q 90` — smallest, lossless, and reversible at once.
- **Lossless output is reversible.** `-q 100` embeds JPEG bitstream reconstruction data; `djxl` recovers the **byte-identical** source JPEG. Verified. Use libjxl's term: *lossless transcoding*.
- **Reversibility is exclusive to lossless.** Any `-q N<100` drops reconstruction data and adds a generation of loss permanently.
- **`cjxl -q N` for N<100 fails outright** on JPEG input unless `--lossless_jpeg=0` is also passed. Every lossy run needs it.
- **One rule: convert what `cjxl` can, copy verbatim everything else.** A corrupt JPEG is not a special case — just a failed conversion.
- **Order = source ZIP stored order, verbatim.** No sorting, no renumbering. Readers own the sort; we never silently reorder a book. Consequences: `ComicInfo.xml` needs no rewriting, and a skipped page shifts nothing.
- **`<name>.jxl.cbz` beside the input.** Never in-place.
- **Exit non-zero only if a JPEG failed to convert.** Non-JPEG pass-throughs are normal. One line per failure plus a summary.
- **Atomic output.** Temp file in the destination directory, then rename. A failed run leaves nothing. `--strict` aborts on first failure; `--dry-run` writes nothing.
- ZIP entries STORED, not deflated. No `--effort` (7 measured free). No parallelism (200 pages ≈ 16–32s serial).

## Rejected

- **Bundling libjxl** — two copies on Linux fight over global decoder handler registration; silent corruption.
- **A separate `--lossless` flag** — `-q 100` already *is* lossless; two spellings of one thing.
- **Sidecar `.jxl` beside retained JPEGs** — superseded by the choice to go JXL-only, now that JXL-only is reversible.
- **Page-level parallelism** — nothing to win at 0.08–0.16s/page.

## Open for the spec

- **DPI is not stored.** `jxlinfo` reports no density; 150/300/600 dpi all come back 72/undefined. Pixel dimensions survive. Comic readers size pages by physical DPI, so rendered page size may be wrong. Needs checking against a JXL-aware reader.
- Whether a `--verify` mode is wanted — lossless mode now makes one cheap and airtight via the `djxl` round-trip.