---
id: 12
type: story
title: "Implement unrar reader for RAR/CBR files"
parent: epic-archive-containers
covers: ["R4"]
after: [2, 3]
hitl: false
risk: medium
---

# Implement unrar reader for RAR/CBR files

## Description

Implements a staged-extraction reader using unrar specifically for RAR/CBR/CBT files, separate from the 7z reader used for CB7 and 7Z. Adds unrar to the preflight check and registers it as the required tool for .rar, .cbr and .cbt inputs. No fallback to 7z for these formats.

## Acceptance Criteria

Verify: cbx-jackal book.rar writes book.jxl.cbz using unrar; with unrar absent and a .rar input, the conversion is refused with a message naming unrar. CB7 and 7Z files continue to use 7z.

## References

- parent — _bmad-output/initiative-cbx-jackal/epic-archive-containers/epic-archive-containers.md