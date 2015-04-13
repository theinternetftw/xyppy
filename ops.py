from ops_impl import *

dispatch = {}
has_store_var = {}
has_branch_var = {}

ext_dispatch = {}
ext_has_store_var = {}
ext_has_branch_var = {}

def op(opcode, f, svar=False, bvar=False):
    dispatch[opcode] = f
    has_store_var[opcode] = svar
    has_branch_var[opcode] = bvar

def ext(opcode, f, svar=False, bvar=False):
    ext_dispatch[opcode] = f
    ext_has_store_var[opcode] = svar
    ext_has_branch_var[opcode] = bvar

def setup_opcodes(env):

    op(1,   je,                         bvar=True)
    op(2,   jl,                         bvar=True)
    op(3,   jg,                         bvar=True)
    op(4,   dec_chk,                    bvar=True)
    op(5,   inc_chk,                    bvar=True)
    op(6,   jin,                        bvar=True)
    op(7,   test,                       bvar=True)
    op(8,   or_,           svar=True)
    op(9,   and_,          svar=True)
    op(10,  test_attr,                  bvar=True)
    op(11,  set_attr)
    op(12,  clear_attr)
    op(13,  store)
    op(14,  insert_obj)
    op(15,  loadw,         svar=True)
    op(16,  loadb,         svar=True)
    op(17,  get_prop,      svar=True)
    op(18,  get_prop_addr, svar=True)
    op(19,  get_next_prop, svar=True)
    op(20,  add,           svar=True)
    op(21 , sub,           svar=True)
    op(22,  mul,           svar=True)
    op(23,  div,           svar=True)
    op(24,  mod,           svar=True)
    if env.hdr.version >= 4:
        op(25, call_2s, svar=True)
    if env.hdr.version >= 5:
        op(26, call_2n)

    op(33,  je,                         bvar=True)
    op(34,  jl,                         bvar=True)
    op(35,  jg,                         bvar=True)
    op(36,  dec_chk,                    bvar=True)
    op(37,  inc_chk,                    bvar=True)
    op(38,  jin,                        bvar=True)
    op(39,  test,                       bvar=True)
    op(40,  or_,           svar=True)
    op(41,  and_,          svar=True)
    op(42,  test_attr,                  bvar=True)
    op(43,  set_attr)
    op(44,  clear_attr)
    op(45,  store)
    op(46,  insert_obj)
    op(47,  loadw,         svar=True)
    op(48,  loadb,         svar=True)
    op(49,  get_prop,      svar=True)
    op(50,  get_prop_addr, svar=True)
    op(51,  get_next_prop, svar=True)
    op(52,  add,           svar=True)
    op(53,  sub,           svar=True)
    op(54,  mul,           svar=True)
    op(55,  div,           svar=True)
    op(56,  mod,           svar=True)
    if env.hdr.version >= 4:
        op(57, call_2s, svar=True)
    if env.hdr.version >= 5:
        op(58, call_2n)

    op(65,  je,                         bvar=True)
    op(66,  jl,                         bvar=True)
    op(67,  jg,                         bvar=True)
    op(68,  dec_chk,                    bvar=True)
    op(69,  inc_chk,                    bvar=True)
    op(70,  jin,                        bvar=True)
    op(71,  test,                       bvar=True)
    op(72,  or_,           svar=True)
    op(73,  and_,          svar=True)
    op(74,  test_attr,                  bvar=True)
    op(75,  set_attr)
    op(76,  clear_attr)
    op(77,  store)
    op(78,  insert_obj)
    op(79,  loadw,         svar=True)
    op(80,  loadb,         svar=True)
    op(81,  get_prop,      svar=True)
    op(82,  get_prop_addr, svar=True)
    op(83,  get_next_prop, svar=True)
    op(84,  add,           svar=True)
    op(85,  sub,           svar=True)
    op(86,  mul,           svar=True)
    op(87,  div,           svar=True)
    op(88,  mod,           svar=True)
    if env.hdr.version >= 4:
        op(89, call_2s, svar=True)
    if env.hdr.version >= 5:
        op(90, call_2n)

    op(97,  je,                         bvar=True)
    op(98,  jl,                         bvar=True)
    op(99,  jg,                         bvar=True)
    op(100, dec_chk,                    bvar=True)
    op(101, inc_chk,                    bvar=True)
    op(102, jin,                        bvar=True)
    op(103, test,                       bvar=True)
    op(104, or_,           svar=True)
    op(105, and_,          svar=True)
    op(106, test_attr,                  bvar=True)
    op(107, set_attr)
    op(108, clear_attr)
    op(109, store)
    op(110, insert_obj)
    op(111, loadw,         svar=True)
    op(112, loadb,         svar=True)
    op(113, get_prop,      svar=True)
    op(114, get_prop_addr, svar=True)
    op(115, get_next_prop, svar=True)
    op(116, add,           svar=True)
    op(117, sub,           svar=True)
    op(118, mul,           svar=True)
    op(119, div,           svar=True)
    op(120, mod,           svar=True)
    if env.hdr.version >= 4:
        op(121, call_2s, svar=True)
    if env.hdr.version >= 5:
        op(122, call_2n)

    op(128, jz,                         bvar=True)
    op(129, get_sibling,   svar=True,   bvar=True)
    op(130, get_child,     svar=True,   bvar=True)
    op(131, get_parent,    svar=True)
    op(132, get_prop_len,  svar=True)
    op(133, inc)
    op(134, dec)
    op(135, print_addr)
    if env.hdr.version >= 4:
        op(136, call_1s, svar=True)
    op(137, remove_obj)
    op(138, print_obj)
    op(139, ret)
    op(140, jump)
    op(141, print_paddr)
    op(142, load,          svar=True)
    if env.hdr.version < 5:
        op(143, not_, svar=True)
    else:
        op(143, call_1n)

    op(144, jz,                         bvar=True)
    op(145, get_sibling,   svar=True,   bvar=True)
    op(146, get_child,     svar=True,   bvar=True)
    op(147, get_parent,    svar=True)
    op(148, get_prop_len,  svar=True)
    op(149, inc)
    op(150, dec)
    op(151, print_addr)
    if env.hdr.version >= 4:
        op(152, call_1s, svar=True)
    op(153, remove_obj)
    op(154, print_obj)
    op(155, ret)
    op(156, jump)
    op(157, print_paddr)
    op(158, load,          svar=True)
    if env.hdr.version < 5:
        op(159, not_, svar=True)
    else:
        op(159, call_1n)

    op(160, jz,                         bvar=True)
    op(161, get_sibling,   svar=True,   bvar=True)
    op(162, get_child,     svar=True,   bvar=True)
    op(163, get_parent,    svar=True)
    op(164, get_prop_len,  svar=True)
    op(165, inc)
    op(166, dec)
    op(167, print_addr)
    if env.hdr.version >= 4:
        op(168, call_1s, svar=True)
    op(169, remove_obj)
    op(170, print_obj)
    op(171, ret)
    op(172, jump)
    op(173, print_paddr)  
    op(174, load,          svar=True)
    if env.hdr.version < 5:
        op(175, not_, svar=True)
    else:
        op(175, call_1n)

    op(176, rtrue)
    op(177, rfalse)
    op(178, print_)
    op(179, print_ret)
    op(184, ret_popped)
    if env.hdr.version < 5:
        op(185, pop)
    else:
        pass # (catch) not impl'd yet
    op(186, quit)
    op(187, new_line)
    if env.hdr.version == 3:
        op(188, show_status)
    else:
        pass # illegal opcode

    op(193, je,                         bvar=True)
    op(194, jl,                         bvar=True)
    op(195, jg,                         bvar=True)
    op(196, dec_chk,                    bvar=True)
    op(197, inc_chk,                    bvar=True)
    op(198, jin,                        bvar=True)
    op(199, test,                       bvar=True)
    op(200, or_,           svar=True)
    op(201, and_,          svar=True)
    op(202, test_attr,                  bvar=True)
    op(203, set_attr)
    op(204, clear_attr)
    op(205, store)
    op(206, insert_obj)
    op(207, loadw,         svar=True)
    op(208, loadb,         svar=True)
    op(209, get_prop,      svar=True)
    op(210, get_prop_addr, svar=True)
    op(211, get_next_prop, svar=True)
    op(212, add,           svar=True)
    op(213, sub,           svar=True)
    op(214, mul,           svar=True)
    op(215, div,           svar=True)
    op(216, mod,           svar=True)
    if env.hdr.version >= 4:
        op(217, call_2s, svar=True)
    if env.hdr.version >= 5:
        op(218, call_2n)

    op(224, call,          svar=True)
    op(225, storew)
    op(226, storeb)
    op(227, put_prop)
    if env.hdr.version < 4:
        op(228, read)
    else:
        pass # different signatures of read (not impld yet)
    op(229, print_char)
    op(230, print_num)
    op(231, random_,       svar=True)
    op(232, push)
    op(233, pull)
    if env.hdr.version >= 4:
        op(236, call, svar=True) # impl's call_vs2
        op(241, set_text_style)
    op(245, sound_effect)
    if env.hdr.version >= 5:
        op(248, not_, svar=True)
        op(249, call_vn)
        op(250, call_vn) # impl's call_vn2
        op(255, check_arg_count, bvar=True)

