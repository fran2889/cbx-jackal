# Entry transformations

Every entry in the source archive gets exactly one of these outcomes, in the source's stored order. There is
no sorting and no renumbering: the pass-through rule and the stored order are what make CAP-3 true.

| Entry | Action | Output name | Notes |
|---|---|---|---|
| `.jpg` / `.jpeg` (any case), fits the box, or no box was requested | Transcode | same basename, `.jxl` | Lossless unless `--quality < 100`; source JPEG byte-for-byte recoverable. |
| `.jpg` / `.jpeg`, over the box, recognised as a spread | Downscale by `--max-height` only | same basename, `.jxl` | `--max-width` deliberately not applied. One entry stays one entry. |
| `.jpg` / `.jpeg`, over the box, not a spread | Downscale to fit | same basename, `.jxl` | Largest box that fits, aspect preserved, never enlarged. |
| `.jpg` / `.jpeg`, downscale attempted and failed | Copy verbatim, unchanged | **original name kept** | Reported as a failure; drives non-zero exit. Not dropped. |
| `.jpg` / `.jpeg` that `cjxl` rejects | Copy verbatim, unchanged | **original name kept** | Reported as a failure; drives non-zero exit. Not dropped. |
| Extension says `.jpg`, content is another image format | Transcode | `.jxl` | `cjxl` sniffs content, not extension, so a mislabelled file still converts correctly. |
| Already `.jxl` | Copy verbatim | unchanged | Never re-encoded; re-encoding would drop the reconstruction data and break reversibility. |
| `ComicInfo.xml` | Copy verbatim | unchanged | Never rewritten. Entry count never changes, so `<Pages Count>` stays correct. |
| `readme.txt`, `Info.txt`, any non-image | Copy verbatim | unchanged | Normal pass-through; does not affect exit code. |
| `__MACOSX/` and other resource-fork junk | Copy verbatim | unchanged | The tool does not clean archives; that is a separate opinion the owner has not asked for. |
| Nested folders | Copy verbatim, structure preserved | unchanged | Path structure is preserved as-is. |
| Anything unreadable from the source | Abort that input | — | An archive we cannot read entries from is not safe to rewrite. Leave no output. A missing container archiver skips only this input; the rest of the list still converts. |

## Consequences worth stating explicitly

- **A skipped page shifts nothing.** Because nothing is ever renumbered, a page that fails and is copied
  through stays at its original position with its original name. The book keeps a hole, not a misnumbering.
- **A failed conversion may leave a mixed archive.** A corrupt page remains a `.jpg` among `.jxl` pages.
  That is deliberate: the entry is preserved rather than discarded, and the exit code plus report make the
  outcome unmissable.
- **Never re-encode an existing `.jxl`.** Round-tripping it through the transcoder is the one way to silently
  destroy the reconstruction data that makes CAP-1 verifiable.
- **Reversibility is per page, and a downscaled page is a weaker guarantee.** A downscaled page keeps its
  reconstruction data, so `djxl` still recovers *something* byte-for-byte — the downscaled intermediate,
  not the source. A book in which every page was downscaled is not a CAP-1 book, and the report must not
  let it look like one. `jxlinfo` reporting `reconstruction data available` proves nothing on its own: it
  only confirms that the *intermediate* has reconstruction data, which is exactly what the source does not
  under CAP-6.

## Reporting

Classification is three-way, because conflating the second and third would make a healthy run look broken:

| Class | Meaning | Affects exit code |
|---|---|---|
| converted | JPEG page successfully transcoded | no |
| passed through | non-JPEG entry, or an entry deliberately not transcoded | no |
| **not converted** | a JPEG entry that was left as-is because `cjxl` failed | **yes** |

Report format, one line per failure plus a summary:

```
199/200 converted, 1 passed through, 1 not converted
page014.jpg: cjxl exited 1 (truncated JPEG)
```
