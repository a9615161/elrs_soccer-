#!/usr/bin/env bash
# Build golden FHSS sequences by compiling the *actual* ExpressLRS sources
# (random.cpp + FHSSrandomiseFHSSsequenceBuild) for ISM2G4 (80 ch, sync=40).
# Usage: tools/gen_elrs_golden.sh <ExpressLRS checkout> <out.json>
set -euo pipefail
ELRS=$(realpath "$1"); OUT=$(realpath -m "$2")
WORK=$(mktemp -d -p "${TMPDIR:-/data/richardlin/tmp}")
trap 'rm -rf "$WORK"' EXIT
FHSS=$ELRS/src/lib/FHSS
START=$(grep -n '^void FHSSrandomiseFHSSsequenceBuild' "$FHSS/FHSS.cpp" | cut -d: -f1)
END=$(awk -v s="$START" 'NR>s && /^}/ {print NR; exit}' "$FHSS/FHSS.cpp")
sed -n "${START},${END}p" "$FHSS/FHSS.cpp" > "$WORK/build_fn.inc"
cat > "$WORK/harness.cpp" <<'CPP'
#include <cstdint>
#include <cstdio>
#include "random.cpp"
static volatile uint8_t FHSSptr;
static uint16_t FHSSgetSequenceCount() { return (256 / 80) * 80; }
#include "build_fn.inc"
int main() {
    const uint32_t seeds[] = {0x01020304u, 0u, 0xDEADBEEFu, 0x12345678u ^ 4u, 0xFFFFFFFFu};
    uint8_t seq[256];
    printf("{\n  \"freq_count\": 80, \"sync_channel\": 40, \"seq_len\": %u,\n  \"vectors\": [\n", FHSSgetSequenceCount());
    for (unsigned s = 0; s < sizeof seeds / sizeof seeds[0]; s++) {
        FHSSrandomiseFHSSsequenceBuild(seeds[s], 80, 40, seq);
        printf("    {\"seed\": %u, \"seq\": [", seeds[s]);
        for (unsigned i = 0; i < FHSSgetSequenceCount(); i++) printf(i ? ",%u" : "%u", seq[i]);
        printf("]}%s\n", s + 1 < sizeof seeds / sizeof seeds[0] ? "," : "");
    }
    printf("  ],\n  \"elrs_commit\": \"%s\"\n}\n", ELRS_COMMIT);
}
CPP
g++ -O1 -I"$FHSS" -I"$WORK" -DELRS_COMMIT="\"$(git -C "$ELRS" rev-parse HEAD)\"" "$WORK/harness.cpp" -o "$WORK/h"
"$WORK/h" > "$OUT"
echo "wrote $OUT (FHSS.cpp L${START}-L${END})"
