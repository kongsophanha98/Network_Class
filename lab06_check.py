#!/usr/bin/env python3
"""
SE026 Lab 6 helper: computes the numbers for the worksheets from the CSVs.

Usage (from VS Code terminal, inside the SE026-Lab-06-Resources folder):
    python lab06_check.py
or point it at the folder:
    python lab06_check.py path/to/SE026-Lab-06-Resources

What it does
  1. Handshake  : prints flags, what each ACK covers, next sequence number
  2. Data rows  : first byte, last byte, number after range
  3. Receiver B : simulates cumulative ACKs (buffers out-of-order data)
                  and compares with the ACK values in the trace
  4. Trials     : useful throughput and the 9 s + hash rule
  5. Ideal time : 8 MB over 10 Mb/s
  6. Writes filled copies of the worksheets into ./output/
     (numbers only: YOU still write the Reason / explanation columns)

All data is modeled (supplied teaching data).
"""
import csv
import sys
from pathlib import Path

# ---- Assumptions taken from SCENARIO.md --------------------------------
LOST_ROWS = {6}            # row 6 is transmitted but lost before reaching B
DEADLINE_S = 9             # sample rule: every trial within 9 s, verified
FILE_BYTES = 8_000_000     # 8 MB, decimal units
BOTTLENECK_BPS = 10_000_000  # 10 Mb/s, decimal units
# -------------------------------------------------------------------------


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    trace = read_csv(folder / "tcp-study.csv")
    out = folder / "output"
    out.mkdir(exist_ok=True)

    for r in trace:
        r["row"] = int(r["synthetic_row"])
        r["seq"] = int(r["sequence"])
        r["ack"] = int(r["acknowledgement"])
        r["len"] = int(r["payload_bytes"])

    # ------------------------------------------------------------------
    # 1. Handshake (rows 1-3)
    # ------------------------------------------------------------------
    print("=" * 60)
    print("1. HANDSHAKE")
    print("=" * 60)
    hs_rows = []
    for r in trace[:3]:
        flags = r["flags"]
        syn = "SYN" in flags
        has_ack = "ACK" in flags  # SYN_ACK and ACK carry a valid ACK
        used = 1 if syn else r["len"]  # SYN uses one sequence number
        next_seq = r["seq"] + used
        if has_ack:
            valid_ack = r["ack"]
            covers = f"everything before {r['ack']} in the other side's space"
            if "SYN" in trace[0]["flags"] and r["row"] == 2:
                covers = f"A's SYN (byte {r['ack'] - 1})"
            if r["row"] == 3:
                covers = f"B's SYN (byte {r['ack'] - 1})"
        else:
            valid_ack = "N/A"
            covers = "nothing (ACK flag clear)"
        print(f"Row {r['row']}: {r['direction']} {flags:8s} seq={r['seq']} "
              f"ACK={valid_ack} | covers: {covers} | next seq = {next_seq}")
        hs_rows.append([r["row"], r["direction"], flags, r["seq"],
                        valid_ack, covers, next_seq, ""])  # Reason: yours
    write_csv(out / "handshake-worksheet.csv",
              ["Trace row", "Direction", "Flags", "Sequence",
               "Valid ACK or N/A", "What the ACK covers",
               "Next sequence for sender", "Reason"], hs_rows)

    # ------------------------------------------------------------------
    # 2 + 3. Data rows and receiver B simulation
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("2/3. A's DATA AND B's CUMULATIVE ACKs")
    print("=" * 60)

    # B's first expected byte = A's ISN + 1 (SYN used one number)
    next_expected = trace[0]["seq"] + 1
    received = []  # list of (first, last) ranges B actually holds
    data_rows = []

    def advance(ne, ranges):
        """Move next_expected forward while a buffered range starts there."""
        moved = True
        while moved:
            moved = False
            for first, last in ranges:
                if first <= ne <= last:
                    ne = last + 1
                    moved = True
        return ne

    tcp_rows = []
    for idx, r in enumerate(trace):
        if r["direction"] != "A_to_B" or r["len"] == 0:
            continue
        first = r["seq"]
        last = r["seq"] + r["len"] - 1
        after = r["seq"] + r["len"]
        lost = r["row"] in LOST_ROWS

        if not lost:
            received.append((first, last))
            next_expected = advance(next_expected, received)

        # matching ACK = next B_to_A row after this data row in the trace
        ack_row = None
        if not lost:
            for later in trace[idx + 1:]:
                if later["direction"] == "B_to_A":
                    ack_row = later
                    break

        if lost:
            ack_text = "no ACK shown"
        else:
            ack_text = f"row {ack_row['row']}: ACK {ack_row['ack']}"
            status = "OK" if ack_row["ack"] == next_expected else "MISMATCH"
            ack_text += f"  [{status} vs my simulation]"

        # gap report
        gap = ""
        if received:
            top = max(l for _, l in received)
            if next_expected <= top:
                gap = f"gap starts at {next_expected} (B holds up to {top})"

        print(f"Row {r['row']}: bytes {first}-{last}, number after range = {after}"
              f"{'  ** LOST **' if lost else ''}")
        print(f"        B next expected = {next_expected}"
              f"{'  (nothing arrived)' if lost else ''}; ACK: {ack_text}")
        if gap and not lost:
            print(f"        {gap}")

        tcp_rows.append([r["row"], first, last, after, next_expected,
                         ack_text.split("  [")[0], ""])  # Reason: yours
        data_rows.append(r["row"])

    write_csv(out / "tcp-worksheet.csv",
              ["Data row", "First byte", "Last byte", "Number after range",
               "B next expected byte",
               "Matching B ACK row and value or no ACK shown", "Reason"],
              tcp_rows)

    # duplicate ACK count: B_to_A rows repeating the previous ACK value
    acks = [r for r in trace if r["direction"] == "B_to_A" and r["flags"] == "ACK"]
    dups = [b["row"] for a, b in zip(acks, acks[1:]) if a["ack"] == b["ack"]]
    print(f"\nDuplicate ACKs shown: {len(dups)} (row(s) {dups})")
    print("The trace does NOT identify the retransmission trigger.")

    # ------------------------------------------------------------------
    # 5. Ideal lower bound
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("5. IDEAL LOWER BOUND")
    print("=" * 60)
    bits = FILE_BYTES * 8
    ideal = bits / BOTTLENECK_BPS
    print(f"{FILE_BYTES:,} bytes x 8 = {bits:,} bits")
    print(f"{bits:,} / {BOTTLENECK_BPS:,} bit/s = {ideal} s")

    # ------------------------------------------------------------------
    # 6. Trials
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("6. TRIAL ANALYSIS (modeled data)")
    print("=" * 60)
    trials = read_csv(folder / "sample-trials.csv")
    ta_rows = []
    all_pass = True
    for t in trials:
        size = int(t["Expected file bytes"])
        secs = float(t["Elapsed seconds"])
        verified = t["Hash matches expected"].strip().lower() == "yes"
        if verified:
            rate = size * 8 / secs / 1_000_000
            rate_txt = f"{rate:.1f}"
            meets = secs <= DEADLINE_S
        else:
            rate_txt = "N/A"
            meets = False
        all_pass = all_pass and meets
        print(f"Trial {t['Trial']}: {secs:g} s, hash ok={verified} -> "
              f"rate {rate_txt} Mb/s, meets {DEADLINE_S} s + verification: "
              f"{'yes' if meets else 'no'}")
        ta_rows.append([t["Trial"], "yes" if verified else "no", rate_txt,
                        "yes" if meets else "no", ""])  # Reason: yours
    print(f"\nWhole sample run meets the rule: {'YES' if all_pass else 'NO'}")

    fastest = min(trials, key=lambda t: float(t["Elapsed seconds"]))
    print(f"Fastest trial alone would be Trial {fastest['Trial']} "
          f"({fastest['Elapsed seconds']} s). Reporting only that hides the failures.")

    write_csv(out / "trial-analysis.csv",
              ["Trial", "Eligible for useful-rate calculation",
               "Useful rate Mb/s or N/A",
               "Meets 9 s and verification rule", "Reason"], ta_rows)

    print()
    print(f"Filled copies written to: {out.resolve()}")
    print("Reason columns are left blank on purpose: write them in your own words.")


if __name__ == "__main__":
    main()
