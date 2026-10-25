# Exact examples, not machine observations

precision.bin: six bytes `81 42 00 FF 80 41`. First byte bits are `10000001`
(MSB first), second `01000010`. Import, open Bits and compare the hex and readout.
precision.json: authored JSON; original whitespace bytes stay available separately
from the semantic property view. Extract `/enabled` to verify false remains false.
kernel-contract-fixture.log: both architecture wire examples, explicitly marked
simulated by the importer. It is not a real boot log, never an attestation.
