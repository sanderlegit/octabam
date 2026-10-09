| QREC TLEN -- a manual recording quantised to the recording track's own
| loop point. QREC raw 17 (past the ladder's 256), drawn TLEN.
| Three entries in one cave:
|   cave   hooked at 0x400a42d0, the master step of the sequencer tick
|          (FUN_400a1e10), after the ladder bits and before PLEN's bit 0;
|          the two displaced instructions are replayed. Measured (stock,
|          port): a track step processed at tick P sounds tt ticks later
|          (its own step), the mask this master step builds fires mt ticks
|          later (the master's). For each running audio track
|          (0x80006500[t] == 1) with e = step x tt + tick the ticks since its
|          loop's step 1 was processed and L = length x tt, bit 17+t is set
|          in the mask (a2) when (e - tt + mt) mod L < mt: the first master
|          step whose mask fires at or after the loop start. Same scale
|          (tt == mt): the loop start's own sample and subframe, from the
|          stock comparator (0x4000b2ce). Otherwise late by fewer than mt
|          ticks. Master-length and pattern-change restarts are PLEN's bit 0.
|   cls    hooked at 0x400051cc (the scheduler FUN_40005178's class
|          lookup, `lea 0x400d8120,a0`, replayed): raw 17 stages class
|          (1 << (17+t)) | 1 -- the track's own bit, or PLEN's bit 0.
|          d0 (the raw) and a0 are the lookup's; d0 is dead after it.
|   fmt    the QREC slot's formatter (descriptor word 0x400d3d9a):
|          17 -> "TLEN", anything else the stock formatter 0x4003b150.
| Reads: a4 (the playing pattern's record: length +0x8e53, PER TRACK flag
| +0x8e55, the track record's length at t x 0x91a + 0x50), 0x80006500,
| 0x800064d0, 0x800064f0, 0x8000663e (the sequencer's per-track running
| flags, step counters, tick counters and scales; one byte per track), the
| tick table 0x400aba50.
| Writes: the mask at (a2); d0/d1/a0 at the scheduler site (dead or
| reloaded). Every other register is restored.
| Assemble: m68k-elf-as -mcpu=5475 -o tlen.o tlen_cave.s

        .text
        .globl  qrt_cave, qrt_cls, qrt_fmt
qrt_cave:
        mvs.b   %d3,%d5                 | displaced: d5 = mt, ticks per master step
        move.l  #2646000,%d6            | displaced
        lea     -28(%sp),%sp
        movem.l %d0-%d4/%a0-%a1,(%sp)
        moveq   #7,%d0                  | t
        move.l  #0x01000000,%d1         | 1 << (17 + t)
        lea     0x800064d0,%a0          | step[t]; tick[t] at +0x20, running[t] at +0x30
next:
        mvz.b   0x30(%a0,%d0.l),%d2
        subq.l  #1,%d2
        bne     skip                    | not running: PLEN's bit 0 only
        lea     0x8000663e,%a1
        mvs.b   (%a1,%d0.l),%d2         | the track's scale
        lea     0x400aba50,%a1
        move.l  (%a1,%d2.l*4),%d2       | d2 = tt, ticks per track step
        move.l  %a4,%a1                 | a4: the playing pattern's record
        adda.l  #0x8e53,%a1
        mvs.b   (%a1),%d4               | the pattern's length
        tst.b   2(%a1)                  | PER TRACK (+0x8e55)?
        beq     havelen
        move.l  #0x91a,%d3
        mulu.l  %d0,%d3
        move.l  %a4,%a1
        adda.l  %d3,%a1
        mvs.b   0x50(%a1),%d4           | the track's own length
havelen:
        tst.l   %d4
        ble     skip
        mulu.l  %d2,%d4                 | d4 = L, ticks per loop
        mvz.b   (%a0,%d0.l),%d3         | step (0-based)
        mulu.l  %d2,%d3
        sub.l   %d2,%d3
        mvz.b   0x20(%a0,%d0.l),%d2
        add.l   %d2,%d3                 | e - tt: e = ticks since the loop's step 1 was processed,
        add.l   %d5,%d3                 | x = e - tt + mt   which sounds tt ticks after (this mask: mt)
        cmp.l   %d5,%d4
        ble     set                     | a loop no longer than a master step: every step
        tst.l   %d3
        bge     pos
        add.l   %d4,%d3
pos:
        cmp.l   %d4,%d3
        blt     inloop
        sub.l   %d4,%d3                 | x mod L
inloop:
        cmp.l   %d5,%d3
        bge     skip                    | the loop start sounds before or more than a master step after this mask
set:
        or.l    %d1,(%a2)
skip:
        lsr.l   #1,%d1
        subq.l  #1,%d0
        bge     next
        movem.l (%sp),%d0-%d4/%a0-%a1
        lea     28(%sp),%sp
        rts

qrt_cls:
        moveq   #17,%d1                 | d1 is dead here (the -1 compare's)
        cmp.l   %d1,%d0
        beq     tlen
        lea     0x400d8120,%a0          | displaced: the one-hot class table
        rts
tlen:
        move.l  %d3,%d0                 | the track: the stock index reads class[t]
        lea     classes(%pc),%a0
        rts

qrt_fmt:
        moveq   #17,%d0
        cmp.l   8(%sp),%d0              | value
        bne     stock
        lea     name(%pc),%a0
        move.l  %a0,8(%sp)
        jmp     0x40013a08              | sprintf(buf, "TLEN")
stock:
        jmp     0x4003b150

        .balign 4
classes:
        .long   0x00020001, 0x00040001, 0x00080001, 0x00100001
        .long   0x00200001, 0x00400001, 0x00800001, 0x01000001
name:
        .asciz  "TLEN"
        .balign 2
