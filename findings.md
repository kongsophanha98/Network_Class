# Lab 6 Findings: TCP Evidence and Performance Design

**SE026 Networks System Design, 2026-27**

> **Note on data:** The packet trace (`tcp-study.csv`) and the trial results (`sample-trials.csv`) are **modeled data** supplied for teaching. They are not a live capture.

## Assumptions

- Units are decimal: 1 MB = 1,000,000 bytes and 1 Mb/s = 1,000,000 bit/s.
- Receiver B **buffers out-of-order data** instead of discarding it.
- Row 6 is lost before it reaches B (as stated in SCENARIO.md), and every listed data ACK reaches A.
- Times in the trace are modeled transmission times. They show event order only. I do not calculate a timeout or infer a loss cause from them.
- The 9 s limit is the sample rule from the lab, and every trial must also pass the hash check.

## Warm-up case (separate example)

B expects byte 81. It receives bytes 81-83, so the next expected byte becomes 84. Then it receives bytes 86-87 while 84-85 are missing, so the next expected byte stays 84 and bytes 86-87 wait in the buffer.

## Byte ranges from the trace

| Row | Bytes | Number after range | B next expected | B ACK |
|---|---|---|---|---|
| 4 | 1001-1500 | 1501 | 1501 | row 5: 1501 |
| 6 | 1501-2000 | 2001 | 1501 (lost) | no ACK shown |
| 7 | 2001-2500 | 2501 | 1501 | row 8: 1501 |
| 9 | 1501-2000 | 2001 | 2501 | row 10: 2501 |

## Partner check (done solo)

I worked alone, so I did both roles of the partner check myself.

- **Pointing to the missing bytes:** bytes 1501-2000 are missing because row 6 was lost.
- **Difference at row 7:** the byte immediately after row 7's payload is 2501, but B's next expected byte is 1501. The first number is arithmetic on one segment (sequence + payload). The second depends on what B holds in an unbroken run from the start, and the gap at 1501-2000 blocks it.

## Section 4: Explain the recovery

**Which range does the repeated ACK point to?** The repeated ACK (1501) points to the first missing byte, so it asks for the range 1501-2000.

**Why can the ACK advance beyond the retransmitted range?** When row 9 fills bytes 1501-2000, B already holds 2001-2500 from row 7. The data is now continuous up to 2500, so B's cumulative ACK jumps to 2501 (row 10).

**Buffering assumption:** B stores out-of-order data. If B had discarded row 7, the ACK would only have reached 2001.

**Duplicate ACKs shown:** exactly one (row 8, repeating ACK 1501 from row 5).

**Does the trace identify the retransmission trigger?** No. The scenario leaves the trigger unspecified. One duplicate ACK does not show a duplicate-ACK trigger, and the timestamps alone do not show a timeout. To identify the trigger I would need sender-side evidence, such as retransmission timer logs or more complete capture data.

## Section 5: Ideal lower bound

8 MB = 8,000,000 bytes x 8 = 64,000,000 bits.
64,000,000 bits / 10,000,000 bit/s = **6.4 s**.

This assumes the full bottleneck rate carries file bits continuously. A measured transfer can take longer because of:

1. **Setup:** the connection handshake and the request take time before file data flows.
2. **Protocol overhead:** headers and ACKs use link capacity that is not file data.
3. **Retransmissions:** lost data is sent again, as in rows 6 and 9.

Sender limits and other traffic on the path can also add time.

## Section 6: Trial analysis

| Trial | Eligible | Useful rate | Meets 9 s + verified |
|---|---|---|---|
| A | yes | 8.0 Mb/s | yes (8 s) |
| B | yes | 6.4 Mb/s | no (10 s) |
| C | no (hash mismatch) | N/A | no |

**Invalid transfer:** Trial C's hash does not match, so it did not deliver the intended file. Its 7 s elapsed time cannot count as a successful transfer.

**Does the sample run meet the rule?** No. Every trial must be verified and finish within 9 s. B is too slow and C is invalid.

**Reporting only the fastest trial:** the fastest trial is C (7 s), but it is invalid. Even the fastest *verified* trial, A at 8 s, would pass and hide B's failure.

**Slow receiver vs congested path:** a slow receiver might show a small advertised window or a busy receiver. A congested path might show retransmissions or rising delay. Elapsed time alone cannot separate them because both just make the transfer take longer.

## Section 7: Plan review (done solo)

No other team's plan was available, so I reviewed my own plan as if I were a stranger who had to run it without guessing.

- **Ambiguity found:** [WRITE YOURS: for example, "file server S and client C" did not name real machines.]
- **Revision:** [WRITE YOURS: for example, "Source: lab PC 12; destination: lab PC 15; both on the same switch."]

## Explain your findings

**1. Which SYNs use sequence space, and which ACK fields confirm them?**
Both SYNs use one sequence number each. A's SYN (sequence 1000) is confirmed by ACK 1001 in row 2. B's SYN (sequence 5000) is confirmed by ACK 5001 in row 3.

**2. Why does B's ACK stay at the gap even after later bytes arrive?**
The ACK is cumulative: it means "I have every byte before this number." The gap at 1501 means B cannot claim anything past it, even though 2001-2500 is buffered.

**3. What does the table show about recovery, and what would I need to identify its trigger?**
It shows that the lost range (1501-2000) is sent again in row 9, and that B's ACK then jumps to 2501. To identify the trigger I would need sender-side evidence such as timer logs, because the trace leaves it unspecified.

**4. Why can useful throughput be below the bottleneck bit rate?**
Setup time, protocol overhead, retransmissions, sender limits and other traffic all use time or capacity that does not carry new file bits.

**5. How does the file verification rule affect a timing test?**
A fast transfer only counts if the received file matches the intended one. Trial C finished quickly but failed the hash check, so it is a failed trial and not a good result.
