| SLICE TOOLS -- one DRAM unit: TLEN SLICES, CREATE LINEAR, AUTO LINEAR.
| GNU as, ColdFire (m68k-elf-as). The manifest wires the entries:
|   tlen_slices    CREATE SLICE GRID's 12th row (a grown table): N = the
|                  active track's length, then the stock setter
|                  0x40073984(N) (its guards, ZERO-CROSS ALIGN?, the writer).
|   create_linear  a SLICE menu row: confirm, then cl_yes.
|   auto_linear    a SLICE menu row: toggle the active track's flag.
|   menu_open      jmp detour at 0x40072c30 (the opener's `lea 0x4006d94c,%a0`):
|                  rewrites auto_label for the active track, replays the lea.
|   auto_hook      jmp detour at 0x40051aea (the step key's empty-step add,
|                  `move.l #1165,%d4`, after the trig bit is in the bank's
|                  mask): the STRT lock for the step when the flag is on.
|
| Stock facts (docs/firmware/PARAM_PAGES.md section 5g, modules/slice-tools/README.md):
|   bank   = *0x46c82456                 the current bank's RAM record
|   part   = bank + 0x8ed80 + P * 0x18b2 P = byte 0x100b14cf; SRAM twin 0x100a4ece + P * 0x18b2
|   track  = byte 0x100b14cc (t)         machine part+0x22+t (0 STATIC, 1 FLEX)
|   slot   = part + 0x2ca + 5t + m       the settings record: (m ? 0x100b14f0 : 0x100d5b30) + slot * 0x448,
|                                        slice count long at +0x444
|   flag   = part + 0x2cc + 5t           THRU's slot byte, 0/1 (README: why this byte)
|   TRAC   = bank + pat * 0x8ed8 + t * 0x91a, pat = byte 0x100b14d0; SRAM twin from 0x1001614e
|            +0x00 the trig mask (64-bit BE, step s = bit s-1), STRT lock +0x5a + 32(s-1), 0xff none
|   length = pattern + 0x8e55 ? TRAC + 0x50 : pattern + 0x8e53, pattern from byte 0x80000004
|            (stock CREATE LINEAR LOCKS' own rule, 0x4007356e..0x400735b0)

        .equ    BANKP,      0x46c82456
        .equ    CUR_TRACK,  0x100b14cc
        .equ    CUR_PART,   0x100b14cf
        .equ    CUR_PAT,    0x100b14d0
        .equ    SEL_PAT,    0x80000004
        .equ    SRAM_PART,  0x100a4ece
        .equ    SRAM_BANK,  0x1001614e
        .equ    FLEX_REC,   0x100b14f0
        .equ    STATIC_REC, 0x100d5b30
        .equ    ED_SLOT,    0x46c8d19c
        .equ    ED_KIND,    0x46c8d1a0
        .equ    STEP_IDX,   0x460d1746

        .text
        .global tlen_slices, create_linear, auto_linear, menu_open, auto_hook
        .global tlen_label, cl_label, auto_label

| ---- helpers (d0/d1/a0/a1 scratch, the rest preserved) ---------------------

| track_len -> d0 = the active track's length, clamped 1..64.
track_len:
        move.l  %d2,-(%sp)
        movea.l BANKP,%a0
        mvz.b   SEL_PAT,%d1
        mulu.w  #0x8ed8,%d1
        adda.l  %d1,%a0                 | a0 = the pattern
        lea     0x7fff(%a0),%a1
        adda.l  #0x8e50-0x7fff,%a1      | a1 = pattern + 0x8e50
        tst.b   5(%a1)                  | PER TRACK? (+0x8e55)
        beq     1f
        mvz.b   CUR_TRACK,%d2
        mulu.w  #0x91a,%d2
        mvs.b   0x50(%a0,%d2.l),%d0     | the track's length
        bra     2f
1:      mvs.b   3(%a1),%d0              | the pattern's length (+0x8e53)
2:      moveq   #1,%d1
        cmp.l   %d1,%d0
        bge     3f
        move.l  %d1,%d0
3:      moveq   #64,%d1
        cmp.l   %d1,%d0
        ble     4f
        move.l  %d1,%d0
4:      move.l  (%sp)+,%d2
        rts

| part_off -> d0 = P * 0x18b2, a0 = the bank's part, d1 = the track
part_off:
        mvz.b   CUR_PART,%d0
        mulu.w  #0x18b2,%d0
        movea.l BANKP,%a0
        adda.l  %d0,%a0
        adda.l  #0x8ed80,%a0
        mvz.b   CUR_TRACK,%d1
        rts

| machine -> d0 = the active track's machine (0 STATIC, 1 FLEX, 2.. others)
machine:
        bsr     part_off
        mvz.b   0x22(%a0,%d1.l),%d0
        rts

| flag_get -> d0 = the active track's AUTO LINEAR flag (0/1)
flag_get:
        bsr     part_off
        mulu.w  #5,%d1
        adda.l  #0x2cc,%a0
        mvz.b   (%a0,%d1.l),%d0
        rts

| flag_set(d0 = 0/1): the bank's part and its SRAM twin, then the part dirty
| as stock marks a part edit (0x40073682..0x400736cc).
|
| With Octakit in the image the working part is her workspace Kit, and the
| write goes through her editing functions as her own wrapper around stock's
| linear-lock writer does it (gk_slice_lock_prepare / _finish,
| slice_lock_operations.S): context, gk_workspace_prepare, gk_physical_acquire,
| gk_descriptor_store_byte, the stock marks, gk_workspace_mark_dirty_pending,
| gk_workspace_commit_update, gk_descriptor_release. Her symbols are weak
| here: without her runtime they resolve to 0 and the stock write runs alone.
| If any of her calls refuses, what she has opened is closed as her wrapper
| closes it, and the stock write runs (the flag still holds for the session;
| her Kit misses it, as before).
        .weak   gk_stock_current_context_validate, gk_workspace_prepare
        .weak   gk_physical_acquire, gk_descriptor_store_byte
        .weak   gk_workspace_mark_dirty_pending, gk_workspace_commit_update
        .weak   gk_descriptor_release, gk_workspace_abort_update
        .weak   __gk_workspace_descriptor, __gk_current_kit
flag_set:
        lea     -12(%sp),%sp
        movem.l %d2-%d3/%a2,(%sp)
        move.l  %d0,%d2
        bsr     ok_begin                | d0 = her descriptor, or < 0: stock only
        movea.l %d0,%a2                 | a2 = descriptor (kept across the stock marks)
        bsr     part_off                | d0 = P * 0x18b2, a0 = part, d1 = t
        mulu.w  #5,%d1
        move.l  %a2,%d3
        bmi     1f
        move.l  %d0,-(%sp)
        move.l  %d1,-(%sp)
        move.l  %a2,%d0                 | gk_descriptor_store_byte(d0 desc, d1 offset, d2 value)
        addi.l  #0x2cc,%d1
        jsr     gk_descriptor_store_byte
        move.l  %d0,%d3
        move.l  (%sp)+,%d1
        move.l  (%sp)+,%d0
        tst.l   %d3
        beq     2f
        bsr     ok_close                | refused: close, then the stock store
        suba.l  %a2,%a2
        subq.l  #1,%a2
1:      movea.l BANKP,%a0               | (part_off's a0, reloaded: ok_close clobbers it)
        adda.l  %d0,%a0
        adda.l  #0x8ed80+0x2cc,%a0
        move.b  %d2,(%a0,%d1.l)
2:      lea     SRAM_PART+0x2cc,%a1
        adda.l  %d0,%a1
        move.b  %d2,(%a1,%d1.l)
        moveq   #1,%d3
        mvz.b   CUR_PART,%d0
        lsl.l   %d0,%d3                 | 1 << P
        movea.l BANKP,%a0
        adda.l  #0x95048,%a0
        move.b  (%a0),%d0
        or.l    %d3,%d0
        move.b  %d0,(%a0)
        move.b  0x100b145e,%d0
        or.l    %d3,%d0
        move.b  %d0,0x100b145e
        bsr     bank_dirty
        move.l  %a2,%d0
        bmi     3f
        bsr     ok_end
3:      movem.l (%sp),%d2-%d3/%a2
        lea     12(%sp),%sp
        rts

| ok_begin -> d0 = Octakit's workspace descriptor, opened for an edit of the
| current part (prepared and acquired), or -1: no Octakit, or she refused.
| Her own wrapper's checks (gk_slice_lock_prepare): the context is settled,
| the workspace is the one already open (PRESERVE_NAME, never a new stage),
| for the current part, and the acquired payload is the prepared one.
| d0/d1/a0/a1 scratch; d2-d7/a2-a6 preserved (hers preserve them too).
ok_begin:
        move.l  #gk_workspace_prepare,%d0
        beq     9f
        lea     -24(%sp),%sp
        movem.l %d2-%d6/%a3,(%sp)
        jsr     gk_stock_current_context_validate
        tst.l   %d0
        bmi     8f
        move.l  %d0,%d4                 | d4 = bank
        move.l  %d1,%d5                 | d5 = pattern
        mvz.b   __gk_workspace_descriptor,%d6
        cmpi.l  #127,%d6                | GK_DESCRIPTOR_COUNT - 1: no workspace open
        bhi     8f
        move.l  %d4,%d0
        move.l  %d5,%d1
        mvz.b   __gk_current_kit,%d2
        moveq   #0,%d3
        jsr     gk_workspace_prepare    | (bank, pattern, kit, flags 0) -> d0 desc, d1 part, a0 payload
        tst.l   %d0
        bmi     8f
        cmp.l   %d6,%d0
        bne     7f
        mvz.b   CUR_PART,%d2
        cmp.l   %d2,%d1
        bne     7f
        movea.l %a0,%a3
        move.l  %d4,%d0
        move.l  %d2,%d1
        jsr     gk_physical_acquire     | (bank, part) -> d0 desc, a0 payload, pinned
        tst.l   %d0
        bmi     7f
        cmp.l   %d6,%d0
        bne     6f
        cmpa.l  %a3,%a0
        bne     6f
        move.l  %d4,ok_bank
        move.l  %d5,ok_pattern
        move.l  %d2,ok_part
        move.l  %a3,ok_payload
        move.l  %d6,%d0
        bra     5f
6:      move.l  %d6,%d0
        jsr     gk_descriptor_release
7:      jsr     gk_workspace_abort_update
8:      moveq   #-1,%d0
5:      movem.l (%sp),%d2-%d6/%a3
        lea     24(%sp),%sp
        rts
9:      moveq   #-1,%d0
        rts

| ok_close(d0 ignored, a2 = descriptor): release and abort, as her wrapper
| does on a refusal after the acquire. Every register but d0/d1/a0/a1 kept.
ok_close:
        move.l  %a2,%d0
        jsr     gk_descriptor_release
        jsr     gk_workspace_abort_update
        rts

| ok_end(a2 = descriptor): the edit published -- dirty pending, committed,
| released (gk_slice_lock_finish's sequence). A refusal after the store
| leaves the part written; it is closed the way her wrapper closes it.
ok_end:
        lea     -8(%sp),%sp
        movem.l %d2-%d3,(%sp)
        move.l  %a2,%d0
        move.l  ok_bank,%d1
        move.l  ok_pattern,%d2
        move.l  ok_part,%d3
        movea.l ok_payload,%a0
        jsr     gk_workspace_mark_dirty_pending
        tst.l   %d0
        bne     1f
        jsr     gk_workspace_commit_update
        tst.l   %d0
        bne     1f
        move.l  %a2,%d0
        jsr     gk_descriptor_release
        bra     2f
1:      bsr     ok_close
2:      movem.l (%sp),%d2-%d3
        lea     8(%sp),%sp
        rts

| bank_dirty: the bank's dirty long, the SRAM flag, 0x40027e00 (stock's
| sequence after every pattern or part write)
bank_dirty:
        movea.l BANKP,%a0
        adda.l  #0x9b332,%a0
        moveq   #1,%d0
        move.l  %d0,(%a0)
        move.l  %d0,0x100f8598
        jsr     0x40027e00
        rts

| count -> d0 = the active track's slice count (0 when its machine has no
| sample slot or the slot is out of range), clamped to 64
count:
        bsr     part_off                | a0 = part, d1 = t
        mvz.b   0x22(%a0,%d1.l),%d0     | machine
        cmpi.l  #1,%d0
        bhi     9f
        mulu.w  #5,%d1
        add.l   %d0,%d1
        adda.l  #0x2ca,%a0
        mvz.b   (%a0,%d1.l),%d1         | slot
        tst.l   %d0
        bne     1f
        cmpi.l  #127,%d1                | STATIC 0..127
        bhi     9f
        lea     STATIC_REC+0x444,%a1
        bra     2f
1:      cmpi.l  #135,%d1                | FLEX 0..135 (128.. the recorder buffers)
        bhi     9f
        lea     FLEX_REC+0x444,%a1
2:      mulu.w  #0x448,%d1
        move.l  (%a1,%d1.l),%d0
        ble     9f
        moveq   #64,%d1
        cmp.l   %d1,%d0
        ble     3f
        move.l  %d1,%d0
3:      rts
9:      moveq   #0,%d0
        rts

| msg(a0 = string): stock's short message (0x4005a2b8(str, 0x30), as CLEAR
| TRACK TRIGS shows its own)
msg:
        pea     0x30
        move.l  %a0,-(%sp)
        jsr     0x4005a2b8
        addq.l  #8,%sp
        rts

| ---- CREATE SLICE GRID: TLEN SLICES -----------------------------------------

tlen_slices:
        bsr     track_len
        move.l  %d0,-(%sp)
        jsr     0x40073984              | the stock grid setter: guards, ZERO-CROSS ALIGN?, writer
        addq.l  #4,%sp
        rts

| ---- SLICE menu: AUTO LINEAR ------------------------------------------------

| auto_linear(): the menu has closed (0x4006d8f4 closes it before the call)
auto_linear:
        bsr     machine
        cmpi.l  #1,%d0
        bls     1f
        lea     m_nosample:l,%a0        | a THRU / NEIGHBOR / PICKUP track: its slot bytes are live
        bra     msg
1:      bsr     flag_get
        eori.l  #1,%d0
        move.l  %d0,-(%sp)
        bsr     flag_set
        bsr     menu_label
        move.l  (%sp)+,%d0
        lea     m_on:l,%a0
        bne     msg
        lea     m_off:l,%a0
        bra     msg

| menu_label: auto_label := "AUTO LINEAR:ON" / "AUTO LINEAR:OFF" for the active track
menu_label:
        move.l  %a2,-(%sp)
        bsr     flag_get
        lea     s_on:l,%a0
        tst.l   %d0
        bne     1f
        lea     s_off:l,%a0
1:      lea     auto_label:l,%a1
        lea     s_prefix:l,%a2
2:      move.b  (%a2)+,(%a1)+
        bne     2b
        subq.l  #1,%a1
3:      move.b  (%a0)+,(%a1)+
        bne     3b
        movea.l (%sp)+,%a2
        rts

| menu_open: jmp detour at 0x40072c30, before the list is built
menu_open:
        lea     -16(%sp),%sp
        movem.l %d0-%d1/%a0-%a1,(%sp)
        bsr     menu_label
        movem.l (%sp),%d0-%d1/%a0-%a1
        lea     16(%sp),%sp
        lea     0x4006d94c,%a0          | displaced
        jmp     0x40072c36

| ---- SLICE menu: CREATE LINEAR ----------------------------------------------

create_linear:
        jsr     0x4006e2cc              | the recorder slot records: no (stock's guards)
        tst.l   %d0
        bne     1f
        pea     -1
        jsr     0x4006dae4              | no sample: no
        addq.l  #4,%sp
        tst.l   %d0
        beq     1f
        pea     cl_yes:l
        pea     s_sure:l
        jsr     0x400581c4              | confirm(title, callback(yes))
        addq.l  #8,%sp
1:      rts

| cl_yes(yes)
cl_yes:
        tst.l   4(%sp)
        beq     cl_done
        lea     -20(%sp),%sp
        movem.l %d2-%d5/%a2,(%sp)
        | the editor's sample must be the active track's: stock's linear-lock
        | writer (0x40073544) takes the count from the EDITOR's slot and the
        | trigs from the ACTIVE track, and needs an editor kind of 0 or 1
        move.l  ED_KIND,%d2
        cmpi.l  #1,%d2
        bhi     cl_other
        bsr     part_off                | a0 = part, d1 = t
        mvz.b   0x22(%a0,%d1.l),%d0
        cmp.l   %d0,%d2
        bne     cl_other
        mulu.w  #5,%d1
        add.l   %d2,%d1
        adda.l  #0x2ca,%a0
        mvz.b   (%a0,%d1.l),%d0
        cmp.l   ED_SLOT,%d0
        bne     cl_other
        bsr     count
        tst.l   %d0
        bne     1f
        lea     m_noslices:l,%a0
        bsr     msg
        bra     cl_out
1:      mvz.b   CUR_TRACK,%d3           | d3 = t
        mvz.b   CUR_PAT,%d4             | d4 = pattern
        move.l  %d3,-(%sp)              | undo, as CLEAR TRACK TRIGS saves it (0x4005f10e)
        move.l  %d4,-(%sp)
        pea     0xa
        jsr     0x40029584
        lea     12(%sp),%sp
        pea     1                       | clear every step of the track (0x40039df4)
        move.l  %d3,-(%sp)
        move.l  %d4,-(%sp)
        jsr     0x40039df4
        lea     12(%sp),%sp
        bsr     track_len               | d0 = L, 1..64
        moveq   #0,%d1                  | d1:d2 = (1 << L) - 1, high:low
        moveq   #-1,%d2
        cmpi.l  #32,%d0
        bge     2f
        moveq   #1,%d2
        lsl.l   %d0,%d2
        subq.l  #1,%d2
        bra     3f
2:      subi.l  #32,%d0
        moveq   #-1,%d1
        cmpi.l  #32,%d0
        bge     3f
        moveq   #1,%d1
        lsl.l   %d0,%d1
        subq.l  #1,%d1
3:      move.l  %d4,%d0                 | the trig mask, bank and SRAM
        mulu.w  #0x8ed8,%d0
        move.l  %d3,%d5
        mulu.w  #0x91a,%d5
        add.l   %d5,%d0
        movea.l BANKP,%a0
        move.l  %d1,(%a0,%d0.l)
        move.l  %d2,4(%a0,%d0.l)
        lea     SRAM_BANK,%a0
        move.l  %d1,(%a0,%d0.l)
        move.l  %d2,4(%a0,%d0.l)
        bsr     bank_dirty
        moveq   #1,%d0                  | AUTO LINEAR on
        bsr     flag_set
        pea     1                       | stock: STRT 2k on every trig, SLIC on, refresh
        jsr     0x40073544
        addq.l  #4,%sp
        bra     cl_out
cl_other:
        lea     m_other:l,%a0
        bsr     msg
cl_out:
        movem.l (%sp),%d2-%d5/%a2
        lea     20(%sp),%sp
cl_done:
        rts

| ---- the step key: AUTO LINEAR ---------------------------------------------

| jmp detour at 0x40051aea, on the empty-step add only (0x40051970..),
| after the bank's trig mask holds the new bit; every register is live.
auto_hook:
        lea     -60(%sp),%sp
        movem.l %d0-%d7/%a0-%a6,(%sp)
        bsr     flag_get
        tst.l   %d0
        beq     9f
        bsr     count                   | 0 for a machine without a slot
        tst.l   %d0
        beq     9f
        move.l  %d0,%d3                 | d3 = count
        move.l  STEP_IDX,%d2            | d2 = s - 1
        cmpi.l  #63,%d2
        bhi     9f
        mvz.b   CUR_PAT,%d0
        mulu.w  #0x8ed8,%d0
        mvz.b   CUR_TRACK,%d1
        mulu.w  #0x91a,%d1
        add.l   %d1,%d0
        move.l  %d2,%d1
        lsl.l   #5,%d1
        add.l   %d1,%d0
        addi.l  #0x5a,%d0               | d0 = the step's STRT byte, bank-relative
        movea.l BANKP,%a0
        move.b  (%a0,%d0.l),%d1
        cmpi.b  #-1,%d1
        bne     9f                      | a lock is there: leave it
        move.l  %d2,%d1
        remu.l  %d3,%d4:%d1             | d4 = (s - 1) mod count
        add.l   %d4,%d4
        move.b  %d4,(%a0,%d0.l)
        lea     SRAM_BANK,%a1
        move.b  %d4,(%a1,%d0.l)
        jsr     0x400339d8              | the pattern's lock bitmaps (as 0x40073806)
9:      movem.l (%sp),%d0-%d7/%a0-%a6
        lea     60(%sp),%sp
        move.l  #1165,%d4               | displaced
        jmp     0x40051af0
| the bank's dirty flag and 0x40027e00 follow at 0x40051afc, after the
| SRAM mask store.

        .data
        .align  2
ok_bank:        .long   0               | ok_begin's context, for ok_end
ok_pattern:     .long   0
ok_part:        .long   0
ok_payload:     .long   0
tlen_label:     .asciz  "TLEN SLICES"
cl_label:       .asciz  "CREATE LINEAR"
auto_label:     .asciz  "AUTO LINEAR:OFF"
                .byte   0,0,0,0
s_prefix:       .asciz  "AUTO LINEAR:"
s_on:           .asciz  "ON"
s_off:          .asciz  "OFF"
s_sure:         .asciz  "CLEAR TRACK? SURE?"
m_on:           .asciz  "AUTO LINEAR ON"
m_off:          .asciz  "AUTO LINEAR OFF"
m_nosample:     .asciz  "NO SAMPLE TRACK"
m_noslices:     .asciz  "NO SLICES"
m_other:        .asciz  "NOT THIS TRACK"
