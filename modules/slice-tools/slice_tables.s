| pf-slice-qrec: the six grown SLICE-page arrays as DRAM data (the
| bottleservice-pf clone window is full). Stock entries read from the stock
| 1.40C image at their old addresses; the module's rows sit where
| TableGrow.insert_at puts them. Generated, do not edit by hand.
        .text
        .align  2
        .globl  st_menu6_handlers
st_menu6_handlers:   | stock 0x400ceb74, 6 + 2
        .long   0x400730f0
        .long   0x40072004
        .long   0x40072cb8
        .long   0x400720b8
        .long   0x40072088
        .long   create_linear
        .long   auto_linear
        .long   0x40072c88
        .globl  st_menu6_labels
st_menu6_labels:   | stock 0x400ceb8c, 6 + 2
        .long   0x400b6bf1
        .long   0x400b6c00
        .long   0x400b6c12
        .long   0x400b6c24
        .long   0x400b6c38
        .long   cl_label
        .long   auto_label
        .long   0x400b6a3f
        .globl  st_menu9_handlers
st_menu9_handlers:   | stock 0x400ceba4, 9 + 2
        .long   0x40071f00
        .long   0x40072058
        .long   0x40072dac
        .long   0x40072cfc
        .long   0x40072004
        .long   0x40072cb8
        .long   0x400720b8
        .long   0x40072088
        .long   create_linear
        .long   auto_linear
        .long   0x40072c88
        .globl  st_menu9_labels
st_menu9_labels:   | stock 0x400cebc8, 9 + 2
        .long   0x400b6c4c
        .long   0x400b6c59
        .long   0x400b6c66
        .long   0x400b6c74
        .long   0x400b6c00
        .long   0x400b6c12
        .long   0x400b6c24
        .long   0x400b6c38
        .long   cl_label
        .long   auto_label
        .long   0x400b6a3f
        .globl  st_grid_handlers
st_grid_handlers:   | stock 0x400cec08, 11 + 1
        .long   0x40073a5c
        .long   0x40073a50
        .long   0x40073a44
        .long   0x40073a38
        .long   0x40073a2c
        .long   0x40073a20
        .long   0x40073a14
        .long   0x40073a08
        .long   0x400739fc
        .long   0x400739f0
        .long   0x400739e4
        .long   tlen_slices
        .globl  st_grid_labels
st_grid_labels:   | stock 0x400cec34, 11 + 1
        .long   0x400b6c84
        .long   0x400b6c8e
        .long   0x400b6c98
        .long   0x400b6ca2
        .long   0x400b6cac
        .long   0x400b6cb6
        .long   0x400b6c8f
        .long   0x400b6cad
        .long   0x400b6ca3
        .long   0x400b6cc0
        .long   0x400b6cb7
        .long   tlen_label
