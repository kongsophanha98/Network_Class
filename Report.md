# Lab 6: TCP Evidence and Performance Design

SE026 Networks System Design · 2026–27

> **Data label:** the TCP trace (`tcp-study.csv`) and trial results (`sample-trials.csv`) are **supplied, modeled/fictional teaching data**, not live captures. Times are modeled transmission times.
>
> **Assumptions:** each direction has its own sequence space; SYN uses one sequence number, a pure ACK uses zero; ACKs are cumulative; B buffers out-of-order data; every listed ACK reaches A; decimal units (1 MB = 1,000,000 bytes, 1 Mb/s = 1,000,000 bit/s).

## 1. Warm-up

Last byte = sequence + payload − 1; number after the range = sequence + payload.

Case: receiver expects 81.

```
byte:     81 82 83 | 84 85 | 86 87
          [ received ] [gap] [buffered]
```

| Arrival | Range | Received so far | Next expected byte |
|---|---|---|---|
| 3 bytes at 81 | 81–83 | 81–83 | **84** |
| 2 bytes at 86 (84, 85 missing) | 86–87 | 81–83 and 86–87 | **84** (stays; gap 84–85) |

The number after the second range is 88, but the receiver still expects 84.

## 2. Handshake (see `handshake-worksheet.csv`)

- Row 1: A→B **SYN**, seq 1000, ACK flag clear (ACK field 0 meaningless). A's next seq = 1001.
- Row 2: B→A **SYN+ACK**, seq 5000, ACK 1001 → acknowledges A's SYN. B's next seq = 5001.
- Row 3: A→B **ACK**, seq 1001, ACK 5001 → acknowledges B's SYN. Pure ACK uses zero numbers, A's next seq stays 1001.

## 3. The missing range (see `tcp-worksheet.csv`)

Byte-range sketch (A→B, bytes of A's sequence space):

```
byte:      1001      1501      2001      2501
            |---------|---------|---------|
Row 4:      [ 1001–1500 ]                       arrives, B ACK 1501 (row 5)
Row 6:                [ 1501–2000 ]   X LOST    no ACK shown
Row 7:                          [ 2001–2500 ]   buffered, B ACK still 1501 (row 8)
After 7:    [ have    ][  GAP   ][ buffered ]    B expects 1501
Row 9:                [ 1501–2000 ]   retransmit fills gap
After 9:    [ have 1001–2500 contiguous        ]  B expects 2501, ACK 2501 (row 10)
```

| Row | First | Last | After range | B next expected | B ACK |
|---|---|---|---|---|---|
| 4 | 1001 | 1500 | 1501 | 1501 | row 5: 1501 |
| 6 | 1501 | 2000 | 2001 | 1501 | none shown (lost, nothing added to buffer) |
| 7 | 2001 | 2500 | 2501 | 1501 | row 8: 1501 (gap 1501–2000) |
| 9 | 1501 | 2000 | 2001 | 2501 | row 10: 2501 |

## 4. Recovery

**Which range does the repeated ACK point to?** ACK 1501 (rows 5 and 8) points at byte 1501, the first byte of the missing range 1501–2000.

**Why can the ACK jump beyond the retransmission?** Row 9 retransmits only 1501–2000, but B had already buffered 2001–2500 from row 7. Once the gap is filled, 1001–2500 is contiguous, so the cumulative ACK jumps to 2501 (not 2001). This assumes B kept the out-of-order bytes in its buffer rather than discarding them.

**Duplicate ACKs:** exactly **one** duplicate ACK is shown (row 8 repeating row 5's 1501).

**Retransmission trigger:** the trace does **not** identify it. One duplicate ACK is shown, and the timestamps are modeled. The 0.300 s retransmission after the 0.080 s row 7 shows a delay but doesn't prove a timeout, and the loss cause is unspecified. To identify the trigger you'd need the sender's retransmission-timer/RTO state and a sender-side capture, plus knowledge of fast-retransmit or SACK behaviour.

**Partner check:** the missing bytes are 1501–2000. Row 7's payload ends at 2500, so the byte right after it is 2501, but B's next expected byte is 1501 because ACKs are cumulative and a gap sits before the buffered data.

## 5. Ideal lower bound

8 MB = 8 × 1,000,000 B = 8,000,000 B × 8 = **64,000,000 bits**.
64,000,000 bits / 10,000,000 bit/s = **6.4 s**.

Three reasons a measured transfer can take longer: (1) setup, such as the TCP handshake, request and file open; (2) protocol overhead and retransmissions, since headers use link capacity and lost data is sent twice; (3) sender/receiver limits (disk, CPU, buffers, window) or other traffic sharing the bottleneck.

## 6. Trials (see `trial-analysis.csv`)

| Trial | Elapsed | Hash | Useful rate | Meets ≤ 9 s + verified |
|---|---|---|---|---|
| A | 8 s | yes | 8.00 Mb/s | **yes** |
| B | 10 s | yes | 6.40 Mb/s | **no** (too slow) |
| C | 7 s | **no** | N/A | **no** (invalid) |

Trial C's 7 s doesn't count: the hash mismatch means the intended file wasn't delivered (data may be incomplete or corrupt), so its time isn't a successful transfer.

**Does the run meet the rule?** No. The rule requires every trial to deliver a verified copy within 9 s; B is too slow and C is not a valid copy.

**Fastest-trial-only reporting:** C is the fastest (7 s) but invalid; A (8 s) is the fastest valid one and would pass. Reporting only the best trial would hide B's failure and C's corruption and falsely suggest success.

**Receiver and path:** a slow receiver might show a shrinking or zero advertised receive window, or high disk/CPU use on the receiver. A congested path might show retransmissions, rising RTT/queueing delay or high link utilization from other traffic. Elapsed time alone can't tell which limit applied because both give a longer time; you need window, retransmission and utilization evidence.

## 7. Performance test design

See `performance-plan.csv`. Summary: fixed 8,000,000-byte file with published SHA-256; one client, quiet 10 Mb/s bottleneck path; timer from client request to last byte written and file closed; 10 trials, all must be hash-verified and ≤ 9 s; failed trials logged and counted as failures, never excluded; target approved in advance by the instructor or requirement owner. When comparing with another team, revise any ambiguous condition (for example, exactly what "request start" means, or whether caches are cleared).

## Explain your findings

1. **SYNs and ACKs:** each SYN uses one number in its sender's own sequence space. A's SYN (1000) is confirmed by B's ACK 1001 in row 2. B's SYN (5000) is confirmed by A's ACK 5001 in row 3.
2. **B's ACK stays at the gap:** ACKs are cumulative and name the next contiguous byte B needs. Buffered later bytes don't move it until the gap (1501–2000) is filled.
3. **Recovery:** the table shows a lost range, one duplicate ACK, a retransmission of exactly the lost bytes, and an ACK jump to 2501. Identifying the trigger needs sender-side timer/RTO information and a fuller capture.
4. **Useful throughput below the bottleneck rate:** the 10 Mb/s rate is raw link capacity. Setup, headers, retransmissions, endpoint limits and other traffic reduce the file bits delivered per second. The ideal 6.4 s is only a lower bound.
5. **Verification rule:** a timing result only counts if the correct file arrives. A fast but corrupt transfer (trial C) is invalid, which changes both the pass/fail result and the statistics.