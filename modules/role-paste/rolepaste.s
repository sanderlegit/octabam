| ROLE PASTE -- an FX2 page paste, or a track paste, in the rig keeps the
| destination track's role: T1 stays BusDelay, T5 BusVerb, T8 RETURNS (with
| RETURNS in the remix), every other track SEND. Only the sends (DEL, REV:
| page-1 slots 0 and 1 on SEND, BusDelay and BusVerb alike) cross between
| two of those; the destination keeps the rest of its own FX2 page.
|
| A page paste copies the effect id with its values (stock 0x40027e4c, the
| page restore, case page 4: clipboard + 18 is the id, + 0..5 page 1,
| + 6..11 page 2, written to the working part, its SRAM mirror and the
| live id 0x80000ecc[track] the DSP runs). So T1's page pasted on T2 gave
| T2 the hidden BusDelay, a dry pass off its host slot, with a page that
| reads like SEND's (RIGPF11B, 9 Oct 2026). A track paste (GRID REC, FUNC +
| STOP; stock 0x4002b654) carries the FX2 id the same way (clipboard
| + 0x91b, its FX2 pages at + 0x972 and + 0x98a).
|
| Four detours, two per paste, none at a site Octakit's recipe claims:
|
|   4005df40  move.l 0x80000012,-(sp)  | page PASTE handler head: rp_page
|   4005dfe8  moveq #-1,d0             | its join of every way out (paste,
|   4005dfea  move.l d0,4(sp)          | undo, nothing to paste): rp_page_done
|   4002b996  move.l 8(sp),-(sp) x2    | track paste, past its tag check:
|                                      | rp_track (then the stock `jsr
|                                      | 0x4002b654` at 0x4002b9a4 as before)
|   4002b9a8  moveq #1,d0              | that jsr's return (Octakit checks the
|   4002b9aa  lea 12(sp),sp            | ADDRESS, which stays): rp_track_done
|
| The head rewrites the clipboard for THIS track, the paste itself is
| stock's -- its writes, undo and dirty marks, and Octakit's checks (working
| part == mirror, the paste tag, the marker counts, the caller) see a stock
| paste -- and the tail puts the clipboard back, so the next paste on
| another track starts from the copied bytes again.
|
| The rewrite (S = the clipboard's id, R = the track's role, D = its FX2
| now):
|   S == R      nothing: stock's paste (T3 -> T2, T1 -> T1 in another part)
|   otherwise   id = R; page = D's own bytes when D is already R, else R's
|               descriptor defaults (FX2_IDS[R] + 0x5e / + 0x64, the bytes
|               RIG HOSTS and the chooser write); then, when S and R both
|               carry sends (BusDelay, BusVerb, SEND), slots 0 and 1 are
|               the source's
| T8 without RETURNS has no role: R is the id it holds (a paste there
| changes the page only when the source is the same effect).

        .include "remix.inc"            | ID_DELAY, ID_VERB, ID_SEND, ID_T8 (0: no RETURNS)

        .set    PAGESEL,   0x46c7d8d8   | the page on screen, 4 = FX2 (Octakit's GK_STOCK_PAGE_SELECTOR)
        .set    TRMODE,    0x80000012   | 0 = audio track (her GK_STOCK_TRACK_MODE)
        .set    TAG,       0x460d0ffa   | the clipboard's tag (her GK_STOCK_PASTE_TAG)
        .set    CLIP,      0x460c8122   | the clipboard (her GK_STOCK_PASTE_BUFFER)
        .set    TRACK,     0x100b14cc   | the current track, 0 = T1
        .set    PARTIDX,   0x100b14cf   | the current part
        .set    BANKPTR,   0x46c82456   | the current bank's blob
        .set    WORKOFF,   0x0008ed80   | its working parts
        .set    PARTSZ,    0x18b2       | one part
        .set    PATSZ,     0x8ed8       | one pattern
        .set    PATPART,   0x8e57       | pattern + 0x8e57: its part (stock 0x4002b6ac)
        .set    FX2ID,     8            | part + 8 + t: FX2 id
        .set    P1OFF,     0x12c        | part + 0x12c + 24 t: FX2 page 1
        .set    P2OFF,     0x304        | part + 0x304 + 30 t: FX2 page 2
        .set    PG_ID,     18           | page clipboard: + 18 id, + 0 page 1, + 6 page 2
        .set    TR_ID,     0x91b        | track clipboard: FX2 id
        .set    TR_P1,     0x972        | ... FX2 page 1 (+ 0x960 + 18)
        .set    TR_P2,     0x98a        | ... FX2 page 2 (+ 0x978 + 18)
        .set    FX2_IDS,   0x400d5fdc   | id -> descriptor P (build_bus.py FX2_IDS)
        .set    DEF1,      0x5e         | P + 0x5e: page-1 defaults (RIG HOSTS)
        .set    DEF2,      0x64         | P + 0x64: page-2 defaults
        .set    PAGE_NEXT,  0x4005df46
        .set    PDONE_NEXT, 0x4005dfee
        .set    TRACK_NEXT, 0x4002b99e
        .set    TDONE_NEXT, 0x4002b9ae

        .text
        .global rp_page, rp_page_done, rp_track, rp_track_done

| ---- 0x4005df40: the page PASTE handler's head --------------------------
rp_page:
        lea     (-40,%sp),%sp
        movem.l %d0-%d4/%a0-%a4,(%sp)
        moveq   #0,%d0
        move.b  (PAGESEL).l,%d0
        moveq   #4,%d1
        cmp.l   %d1,%d0
        bne.s   9f                      | not FX2
        tst.l   (TRMODE).l
        bne.s   9f                      | a MIDI track
        moveq   #0x1d,%d1
        cmp.l   (TAG).l,%d1
        bne.s   9f                      | no FX page in the clipboard
        moveq   #0,%d2
        move.b  (TRACK).l,%d2           | d2 = t
        moveq   #0,%d0
        move.b  (PARTIDX).l,%d0         | d0 = the part
        bsr.w   rp_part                 | a0 = the working part, or Z
        beq.s   9f
        lea     (CLIP).l,%a2            | page 1
        lea     (6,%a2),%a3             | page 2
        lea     (PG_ID,%a2),%a1         | id
        bsr.w   rp_fix
9:      movem.l (%sp),%d0-%d4/%a0-%a4
        lea     (40,%sp),%sp
        move.l  (TRMODE).l,-(%sp)       | displaced
        jmp     (PAGE_NEXT).l

| ---- 0x4005dfe8: the page PASTE handler's join of every way out ---------
rp_page_done:
        bsr.w   rp_restore
        moveq   #-1,%d0                 | displaced
        move.l  %d0,(4,%sp)
        jmp     (PDONE_NEXT).l

| ---- 0x4002b996: the track paste, its tag checked (4(sp) = the pattern,
| 8(sp) = the track); the stock pushes and `jsr 0x4002b654` follow --------
rp_track:
        lea     (-40,%sp),%sp
        movem.l %d0-%d4/%a0-%a4,(%sp)
        tst.l   (TRMODE).l
        bne.s   9f                      | a MIDI track (its own paste)
        move.l  (48,%sp),%d2            | d2 = t
        move.l  (44,%sp),%d0            | the pattern
        moveq   #15,%d1
        cmp.l   %d1,%d0
        bhi.s   9f
        move.l  (BANKPTR).l,%d1
        beq.s   9f
        movea.l %d1,%a0
        mulu.w  #PATSZ,%d0
        adda.l  %d0,%a0
        adda.l  #PATPART,%a0
        moveq   #0,%d0
        move.b  (%a0),%d0               | d0 = the pattern's part, as stock reads it
        bsr.w   rp_part
        beq.s   9f
        lea     (CLIP).l,%a1
        lea     (TR_P1,%a1),%a2
        lea     (TR_P2,%a1),%a3
        adda.l  #TR_ID,%a1
        bsr.w   rp_fix
9:      movem.l (%sp),%d0-%d4/%a0-%a4
        lea     (40,%sp),%sp
        move.l  (8,%sp),-(%sp)          | displaced: the track,
        move.l  (8,%sp),-(%sp)          | the pattern
        jmp     (TRACK_NEXT).l          | pea CLIP; jsr 0x4002b654 (return 0x4002b9a8)

| ---- 0x4002b9a8: the return of that jsr --------------------------------
rp_track_done:
        bsr.w   rp_restore
        moveq   #1,%d0                  | displaced
        lea     (12,%sp),%sp
        jmp     (TDONE_NEXT).l          | its rts

| ---- a0 = the working part d0 of the current bank (Z set: none); d2 must
| be a track 0..7 too ------------------------------------------------------
rp_part:
        moveq   #3,%d1
        cmp.l   %d1,%d0
        bhi.s   1f
        moveq   #7,%d1
        cmp.l   %d1,%d2
        bhi.s   1f
        mulu.w  #PARTSZ,%d0
        move.l  (BANKPTR).l,%d1
        beq.s   1f
        movea.l %d1,%a0
        adda.l  #WORKOFF,%a0
        adda.l  %d0,%a0
        moveq   #1,%d1                  | Z clear
        rts
1:      moveq   #0,%d1                  | Z set
        rts

| ---- the clipboard's FX2 for track d2 of part a0: a1 = its id byte, a2 =
| its page 1, a3 = its page 2 (six bytes each) -----------------------------
rp_fix:
        moveq   #0,%d3
        move.b  (FX2ID,%a0,%d2.l),%d3   | d3 = D's id
        bsr.w   rp_role                 | d4 = R
        moveq   #0,%d1
        move.b  (%a1),%d1               | d1 = S
        cmp.l   %d4,%d1
        beq.w   9f                      | the role's own: stock's paste
| keep the clipboard to put back
        lea     (rp_ptrs).l,%a4
        move.l  %a1,(%a4)+
        move.l  %a2,(%a4)+
        move.l  %a3,(%a4)+
        move.b  (%a1),(%a4)+
        movea.l %a2,%a1                 | (a1 is reloaded below)
        bsr.w   rp_six_to_a4            | the clipboard's page 1
        movea.l %a3,%a1
        bsr.w   rp_six_to_a4            | ... page 2
        moveq   #1,%d0
        move.b  %d0,(rp_armed).l
| the page this track keeps: D's own when it is already R, else R's defaults
        cmp.l   %d4,%d3
        beq.s   2f
        lea     (FX2_IDS).l,%a4
        move.l  (%a4,%d4.l*4),%d0
        beq.s   2f                      | no descriptor: D's own
        movea.l %d0,%a4
        lea     (DEF1,%a4),%a0
        lea     (DEF2,%a4),%a4
        bra.s   3f
2:      movea.l %a0,%a4                 | the part
        move.l  %d2,%d0
        mulu.w  #24,%d0
        adda.l  #P1OFF,%a0
        adda.l  %d0,%a0                 | D's page 1
        move.l  %d2,%d0
        mulu.w  #30,%d0
        adda.l  #P2OFF,%a4
        adda.l  %d0,%a4                 | D's page 2
3:      movea.l %a2,%a1
        bsr.s   rp_six                  | (a0) -> page 1
        movea.l %a4,%a0
        movea.l %a3,%a1
        bsr.s   rp_six                  | (a4) -> page 2
        movea.l (rp_ptrs).l,%a1
        move.b  %d4,(%a1)               | the role's id
| the sends cross when both ends carry them
        move.l  %d1,%d0
        bsr.s   rp_sends
        beq.s   9f
        move.l  %d4,%d0
        bsr.s   rp_sends
        beq.s   9f
        lea     (rp_save+1).l,%a4       | the source's page 1
        move.b  (%a4),(%a2)             | DEL
        move.b  (1,%a4),(1,%a2)         | REV
9:      rts

| six bytes (a0)+ -> (a1)+
rp_six:
        moveq   #6,%d0
1:      move.b  (%a0)+,(%a1)+
        subq.l  #1,%d0
        bne.s   1b
        rts

| six bytes (a1)+ -> (a4)+
rp_six_to_a4:
        moveq   #6,%d0
1:      move.b  (%a1)+,(%a4)+
        subq.l  #1,%d0
        bne.s   1b
        rts

| d4 = the FX2 role of track d2 (d3 = the id it holds now)
rp_role:
        moveq   #ID_SEND,%d4
        tst.l   %d2
        bne.s   1f
        moveq   #ID_DELAY,%d4           | T1: BusDelay's host
        rts
1:      moveq   #4,%d0
        cmp.l   %d0,%d2
        bne.s   2f
        moveq   #ID_VERB,%d4            | T5: BusVerb's host
        rts
2:      moveq   #7,%d0
        cmp.l   %d0,%d2
        bne.s   3f
        moveq   #ID_T8,%d4              | T8: RETURNS
        bne.s   3f
        move.l  %d3,%d4                 | no RETURNS: T8 keeps what it holds
3:      rts

| Z clear when id d0 carries the sends in slots 0 and 1
rp_sends:
        cmpi.l  #ID_DELAY,%d0
        beq.s   1f
        cmpi.l  #ID_VERB,%d0
        beq.s   1f
        cmpi.l  #ID_SEND,%d0
        beq.s   1f
        moveq   #0,%d0                  | Z set: no sends
        rts
1:      moveq   #1,%d0                  | Z clear
        rts

| the clipboard back as copied, when rp_fix changed it; every register kept
rp_restore:
        tst.b   (rp_armed).l
        beq.s   9f
        lea     (-16,%sp),%sp
        movem.l %d0/%a0-%a2,(%sp)
        lea     (rp_ptrs).l,%a0
        movea.l (%a0)+,%a1              | (a0 = rp_ptrs + 4)
        move.b  (8,%a0),(%a1)           | the id (rp_save + 0)
        lea     (9,%a0),%a2             | rp_save + 1
        movea.l (%a0)+,%a1
        moveq   #6,%d0
1:      move.b  (%a2)+,(%a1)+           | page 1
        subq.l  #1,%d0
        bne.s   1b
        movea.l (%a0),%a1
        moveq   #6,%d0
2:      move.b  (%a2)+,(%a1)+           | page 2
        subq.l  #1,%d0
        bne.s   2b
        clr.b   (rp_armed).l
        movem.l (%sp),%d0/%a0-%a2
        lea     (16,%sp),%sp
9:      rts

        .data
        .even
rp_ptrs:  .long   0, 0, 0               | the clipboard's id, page 1, page 2
rp_save:  .space  13                    | id, page 1, page 2 as copied
rp_armed: .byte   0
        .even
