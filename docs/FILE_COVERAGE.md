# Coverage of all three supplied input archives

Every entry of the supplied archives was inventoried against the maintained source. No missing runtime source was found. Complete releases add the generated tools and boot images; private backup ZIPs are not a substitute for maintained source and runnable downloads.

| Input | Entries | Coverage |
| --- | ---: | --- |
| Living Universe v0.3 complete kit | 128 | Visual modules, observer, tests and kernel retained; generated outputs rebuilt; historical/private references classified separately |
| C Native Kernel v0.2 QEMU kit | 32 | Both architecture ports, common kernel, build/image tools and QEMU harness retained; v0.3 adds shared serial observations |
| Source / Destination original | 32 | Original scene, geometry, navigation, world, XR, data, tests and editable build retained; original standalone/runtime vendored |

The optional authored reference images, animation, chat notes, nested backup archives and host-specific authoring configuration are not runtime dependencies and are excluded from public source. Earlier manifests and backup verification scripts are superseded by maintained publication docs and release checksums. Historical local logs do not count as validation of a new commit.

Required complete-kit artifacts are enforced by scripts/package_release.py: Windows x64 observer EXE, Linux observer, x86-64 EFI, generic ARM64 EFI, ARM64 QEMU EFI, four 64-MiB boot images and the firmware checksums. The kit also carries the maintained source, standalone HTML, launchers, examples, licenses and tests. Packaging fails if any required build artifact is missing.

## Supplied archive identities

- Living_Universe_v0.3_Source_Bridge_DualArch_Test_Kit(1).zip: SHA-256 `9a3dc34ecfd470f47ccec3f065c6c2eec42e87b7b7ec2ddb9186866152c20fd6`
- C_Native_Kernel_v0.2_DualArch_QEMU_Boot_Test_Kit(4).zip: SHA-256 `55169515ce32ed76fd7074844383f9cda608e86fae9b3e1e9c286f413dc3bd57`
- SourceDestination (1)(2).zip: SHA-256 `045456a4d2593e8aaf0a5f3fa334f2348413cb33dea70dcdd3b5ff8396027826`

Maintained revisions are not claimed byte-identical to older archives. Build metadata identifies the exact source commit. Passing image checks is not a real boot or physical-hardware qualification.
