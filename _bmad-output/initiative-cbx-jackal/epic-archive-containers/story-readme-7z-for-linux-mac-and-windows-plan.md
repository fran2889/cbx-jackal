---
type: story
title: "README: 7z for linux, mac and windows"
id: 9
epic: epic-archive-containers
initative: initiative-cbx-jackal
covers: ["R4"]
after: [3, 6, 8]
hitl: false
risk: low
status: done
---

# README: 7z for linux, mac and windows

## Done When

A reader on each platform installs 7z from the README alone and knows what a solid or an encrypted archive does.

## Changes Made

### README.md

1. **Added "Installing 7z" section** with platform-specific instructions:
   - Linux: p7zip-full (Debian/Ubuntu), p7zip (Fedora), p7zip (Arch)
   - macOS: brew install p7zip
   - Windows: Download from 7-Zip website
   - Note: `7z` must be available as `7z`, not `7zz` or `7za` (needs symlink/alias if system only has those)

2. **Added "Container-specific behaviour" table** documenting:
   - CBZ, ZIP: standard library only
   - CB7, 7Z, RAR: uses 7z for reading
   - Solid archives: byte-exact entries but internal layout not preserved
   - Encrypted archives: refused with message, exit 1, other inputs still convert

3. **Updated "Scanned" row** in the behaviour table to include `.rar`

4. **Updated "Install" section** to reference the new "Installing 7z" section

## Verification

A reader can:
- Follow the README to install 7z on their platform
- Understand that solid archives have a known cost (internal layout not preserved)
- Understand that encrypted archives are refused with a message

## Notes

Entry 6 established the solid cost as behaviour, entry 8 established the encrypted refusal as behaviour. This entry documents both in the README.
