"""Generate the four hierarchical sheets with a clean, wired layout.

    python hardware/tools/gen_schematic.py

The netlist must stay identical to the reviewed design; check with
    python hardware/tools/check_netlist.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schgen import Sheet, g  # noqa: E402

ROOT = '85633eb7-cf01-4fcf-93cc-694bd24a43ba'
SHEETS = {
    'power': 'c67045ad-ad78-40ef-adb2-4c081ee4501d',
    'vehicle': 'fa1dd39e-b547-4d98-ad46-16b1323df42c',
    'mcu': '6ff62bc4-23e3-4296-bf60-cd67ba8c0f07',
    'lte': '01715d65-cdba-4655-b5fc-0dddd6752831',
    'battery': 'c6ae1c68-acef-4152-829a-0cb506f6fd18',
}

R0402, R0603, R1206 = 'Resistor_SMD:R_0402_1005Metric', 'Resistor_SMD:R_0603_1608Metric', 'Resistor_SMD:R_1206_3216Metric'
C0402, C0603, C0805, C1210 = ('Capacitor_SMD:C_0402_1005Metric', 'Capacitor_SMD:C_0603_1608Metric',
                              'Capacitor_SMD:C_0805_2012Metric', 'Capacitor_SMD:C_1210_3225Metric')
SOT23 = 'Package_TO_SOT_SMD:SOT-23'

# Sourcing (checked 2026-11-11 with tools/check_stock.py; LCSC = one of PCBWay's suppliers).
# ref: (MPN, Manufacturer, LCSC#)
SOURCING = {
    'F101': ('0466002.NRHF', 'Littelfuse', 'C3105'),
    'D101': ('SMCJ33CA', 'Littelfuse', 'C310048'),
    'U101': ('LM74700QDBVRQ1', 'TI', 'C2941042'),
    'Q101': ('PSMN7R0-60YS,115', 'Nexperia', 'C478143'),
    'D102': ('SS14', 'MDD', 'C2480'),
    'U102': ('TPS54360DDAR', 'TI', 'C44377'),
    'D103': ('B560C-13-F', 'Diodes Inc', 'C85100'),
    'L101': ('MWSA0605S-6R8MT', 'Sunlord', 'C408466'),
    'U103': ('TLV75733PDBVR', 'TI', 'C485517'),
    'Q102': ('AO3401A', 'AOS', 'C15127'),
    'Q103': ('2N7002', 'onsemi', 'C8545'),
    'U201': ('TCAN334DR', 'TI', 'C2871143'),
    'D201': ('SZNUP2105LT1G', 'onsemi', 'C233494'),
    'U202': ('TJA1021T/20/CM,118', 'NXP', 'C128810'),
    'D202': ('B0540WS-7', 'Diodes Inc', 'C52754523'),
    'D203': ('PESD1LIN,115', 'Nexperia', 'C58901'),
    'U301': ('ESP32-C5-WROOM-1U-N16R8-V1.2', 'Espressif', 'C54951857'),
    'D301': ('SK6812MINI-HS', 'OPSCO', 'C2922787'),   # top-emitting 3535 (the -E is reverse-mount, other footprint)
    'U302': ('USBLC6-2SC6', 'ST', 'C2827654'),
    'J301': ('TYPE-C-31-M-12', 'HRO', 'C165948'),
    'SW301': ('TL3342F450QG', 'E-Switch', 'C2886897'),
    'SW302': ('TL3342F450QG', 'E-Switch', 'C2886897'),
    'U401': ('EC200UEUAA-N05-SGNSA', 'Quectel', 'C2942341'),
    'U402': ('TXS0108EPWR', 'TI', 'C17206'),
    'Q401': ('MMBT3904', 'onsemi', 'C20526'),
    'Q402': ('MMBT3904', 'onsemi', 'C20526'),
    'J401': ('SIM8060-6-0-14-00-A', 'GCT', 'C6296715'),
    'U403': ('MFF2 eSIM, optional (DNP)', '', ''),
    'U501': ('BQ25171QWDRCRQ1', 'Texas Instruments', 'C2861221'),
    'U502': ('TPS2121RUXR', 'Texas Instruments', 'C485916'),
    'J501': ('B2B-PH-SM4-TB(LF)(SN)', 'JST', 'C160352'),
    'RT501': ('SDNT1608X103F3435FTF', 'Sunlord', 'C525660'),
    'D501': ('SMF24A', 'Littelfuse', 'C315999'),
    'C506': ('T495D227K006ATE100', 'KEMET', 'C2798131'),
    'J402': ('U.FL-R-SMT-1(10)', 'Hirose', 'C88373'),
    'J403': ('U.FL-R-SMT-1(10)', 'Hirose', 'C88373'),
    'C401': ('T495D227K006ATE100', 'Kemet', 'C2798131'),
    'J201': ('CR-PG001 (OBD2 male 90deg PCB, hand-fitted)', 'Jiatel or equivalent', ''),
}


def V(x, y):
    """Field placement for a vertical 2-pin part (text to the right)."""
    return {'ref': (x + 2.032, y - 1.27, 'left'), 'val': (x + 2.032, y + 1.27, 'left')}


def H(x, y):
    """Field placement for a horizontal 2-pin part (ref above, value below)."""
    return {'ref': (x, y - 2.54, None), 'val': (x, y + 2.54, None)}


def IC(x, top, bottom, left=None, above=False):
    j = 'left' if left is not None else None
    lx = left if left is not None else x
    if above:   # both fields above the body (bottom edge busy with GND symbols)
        return {'ref': (lx, top - 3.81, j), 'val': (lx, top - 1.27, j)}
    return {'ref': (lx, top - 1.27, j), 'val': (lx, bottom + 1.27, j)}


def VL(x, y):
    """Vertical 2-pin part, text to the left."""
    return {'ref': (x - 2.032, y - 1.27, 'right'), 'val': (x - 2.032, y + 1.27, 'right')}


def rv(sh, lib, ref, val, fp, x, y_top, flip=False, **kw):
    """Vertical 2-pin part with its top pin at (x, y_top). Pin 1 on top unless flip."""
    y = y_top + 3.81
    return sh.part(lib, ref, val, fp, x, y, 180 if flip else 0, fields=V(x, y), **kw)


def dv(sh, lib, ref, val, fp, x, y_top, top_pin, **kw):
    """Vertical diode/TVS (library drawn horizontally). top_pin = name of the pin to put on top."""
    y = y_top + 3.81
    for rot in (90, 270):
        p = sh.part(lib, ref, val, fp, x, y, rot, fields=V(x, y), **kw)
        if abs(p[top_pin][1] - y_top) < 1e-6:
            return p
        sh.parts.remove(p)
    raise ValueError(ref)


def rh(sh, lib, ref, val, fp, x_left, y, **kw):
    """Horizontal 2-pin part whose pin 1 sits at (x_left, y)."""
    x = x_left + 3.81
    return sh.part(lib, ref, val, fp, x, y, 90, fields=H(x, y), **kw)


def cap_to_gnd(sh, ref, val, fp, x, y_rail, drop=1, lib='Device:C', **kw):
    """Decoupling cap hanging from a horizontal rail at y_rail."""
    c = rv(sh, lib, ref, val, fp, x, y_rail + g(drop), **kw)
    sh.w((x, y_rail), c[1])
    sh.gnd(c[2])
    return c


# =====================================================================================
def power():
    sh = Sheet('Power', 'power.kicad_sch', SHEETS['power'], ROOT, 'Power: protection, buck 3.8 V, LDO 3.3 V')
    y0 = g(14)

    sh.text('Input protection: fuse, TVS, ideal-diode reverse protection', g(5), g(6), 1.5, True)
    F = sh.part('Device:Fuse', 'F101', '2A slow', 'Fuse:Fuse_1206_3216Metric', g(14), y0, 90, fields=H(g(14), y0))
    sh.glabel('OBD_VBAT', F.out(1, 1), 'L', 'input')
    sh.w(F.out(1, 1), F[1])

    xt = g(19)
    D = dv(sh, 'Device:D_TVS', 'D101', 'SMCJ33CA', 'Diode_SMD:D_SMC', xt, y0 + g(2), 'A1')
    sh.w((xt, y0), D['A1'])
    sh.gnd(D['A2'])

    X = g(34)
    Q = sh.part('Transistor_FET:PSMN5R2-60YL', 'Q101', 'PSMN7R0-60YS', 'Package_TO_SOT_SMD:LFPAK56',
                X, y0 + 2.54, 270, 'x', fields={'ref': (X - 3.81, y0 - 5.08, 'right'), 'val': (X - 3.81, y0 - 2.54, 'right')})
    assert Q['S'][1] == y0 and Q['D'][1] == y0 and Q['G'][1] > y0, (Q['S'], Q['D'], Q['G'])
    U = sh.part('Power_Management:LM74700', 'U101', 'LM74700-Q1', 'Package_TO_SOT_SMD:SOT-23-6',
                X, Q['G'][1] + g(3) + 10.16, 0)
    U.fields = IC(X, U['GATE'][1] + 2.54, U['GND'][1], left=X + g(5))
    sh.w(Q['G'], U['GATE'])
    xa, xc = U['ANODE'][0], U['CATHODE'][0]
    sh.w(U['ANODE'], (xa, y0))
    sh.w(U['CATHODE'], (xc, y0))
    sh.gnd(U['GND'])
    # VCAP cap to ANODE, EN to ANODE (VBAT_F)
    xv = X - g(9)
    C = rv(sh, 'Device:C', 'C101', '100nF', C0603, xv, U['VCAP'][1] - 7.62, flip=True)
    C.fields = VL(C.x, C.y)
    sh.w(C[1], U['VCAP'])
    sh.w(C[2], (xv, y0))
    sh.w(U['EN'], (xv - g(2), U['EN'][1]))
    sh.label('VBAT_F', (xv - g(2), U['EN'][1]), 'L')
    sh.label('VBAT_F', (xt + g(3), y0), 'R')
    # main line, input side
    sh.w(F[2], (xt, y0), (xt + g(3), y0), (xv, y0), (xa, y0), Q['S'])
    sh.rail('VIN_PROT', (xc + g(3), y0))

    # USB bench supply into VIN_PROT
    xu = xc + g(7)
    Dv = dv(sh, 'Device:D_Schottky', 'D102', 'SS14', 'Diode_SMD:D_SMA', xu, y0 - g(3) - 7.62, 'A')
    Dv.fields = {'ref': (xu + 2.54, Dv.y - 1.27, 'left'), 'val': (xu + 2.54, Dv.y + 1.27, 'left')}
    sh.w(Dv['K'], (xu, y0))
    sh.w(Dv['A'], (xu, Dv['A'][1] - g(1)), (xu - g(1), Dv['A'][1] - g(1)))
    sh.glabel('VBUS_USB', (xu - g(1), Dv['A'][1] - g(1)), 'L', 'input')

    # input caps
    xc1, xc2 = xu + g(4), xu + g(9)
    cap_to_gnd(sh, 'C102', '10uF 50V', C1210, xc1, y0, 2)
    cap_to_gnd(sh, 'C103', '100nF 50V', C0603, xc2, y0, 2)

    # ---------------- buck TPS54360 -> 3.8 V
    sh.text('Buck 3.8 V / 3.5 A (TPS54360, 600 kHz)', g(56), g(6), 1.5, True)
    XB = g(76)
    B = sh.part('Regulator_Switching:TPS54360DDA', 'U102', 'TPS54360DDA', 'Package_SO:TI_SO-PowerPAD-8_ThermalVias',
                XB, y0 + 5.08, 0)
    B.fields = {'ref': (XB - g(4), y0 - g(2.5), 'left'), 'val': (XB - g(4), y0 - g(1.5), 'left')}
    assert B['VIN'][1] == y0
    sh.w(Q['D'], (xc, y0), (xc + g(3), y0), (xu, y0), (xc1, y0), (xc2, y0), B['VIN'])
    sh.w(B['GND'], (B['GND'][0], B['GND'][1] + g(1)), (B['GNDPAD'][0], B['GND'][1] + g(1)), B['GNDPAD'])
    sh.gnd((B['GNDPAD'][0], B['GND'][1] + g(1)))
    # RT to GND (wire left, then down)
    xrt = B['RT/CLK'][0] - g(6)
    sh.w(B['RT/CLK'], (xrt, B['RT/CLK'][1]))
    R3 = rv(sh, 'Device:R', 'R103', '162k', R0603, xrt, B['RT/CLK'][1])
    R3.fields = {'ref': (xrt - 2.032, R3.y - 1.27, 'right'), 'val': (xrt - 2.032, R3.y + 1.27, 'right')}
    sh.gnd(R3[2])
    # EN divider (labelled)
    sh.label('BUCK_EN', B['EN'], 'L', stub=1)
    xen = g(62)
    R1 = rv(sh, 'Device:R', 'R101', '470k', R0603, xen, y0 + g(9))
    sh.rail('VIN_PROT', R1[1])
    R2 = rv(sh, 'Device:R', 'R102', '120k', R0603, xen, R1[2][1] + g(2))
    sh.w(R1[2], R2[1])
    sh.label('BUCK_EN', (xen, R1[2][1] + g(1)), 'R', stub=0)
    sh.gnd(R2[2])
    # BOOT cap (horizontal, above) between BOOT and SW
    x1 = B['BOOT'][0] + g(1)
    yb = B['BOOT'][1] - g(3)
    Cb = rh(sh, 'Device:C', 'C104', '100nF', C0603, x1, yb)
    sh.w(B['BOOT'], (x1, B['BOOT'][1]), Cb[1])
    xsw = Cb[2][0]
    sh.w(Cb[2], (xsw, B['SW'][1]))
    sh.w(B['SW'], (xsw, B['SW'][1]))
    # catch diode + inductor
    xd = B['SW'][0] + g(8)
    sh.w((xsw, B['SW'][1]), (xd, B['SW'][1]))
    Dc = dv(sh, 'Device:D_Schottky', 'D103', 'B560C', 'Diode_SMD:D_SMC', xd, B['SW'][1] + g(2), 'K')
    sh.w((xd, B['SW'][1]), Dc['K'])
    sh.gnd(Dc['A'])
    L = rh(sh, 'Device:L', 'L101', '6.8uH 4.5A', 'Inductor_SMD:L_Sunlord_MWSA0605S', xd + g(2), B['SW'][1])
    sh.w((xd, B['SW'][1]), L[1])
    yo = B['SW'][1]
    xo = L[2][0]
    # FB divider (labelled to the FB pin)
    xf = xo + g(4)
    Rf1 = rv(sh, 'Device:R', 'R104', '37.4k', R0603, xf, yo)
    Rf2 = rv(sh, 'Device:R', 'R105', '10k', R0603, xf, Rf1[2][1] + g(2))
    sh.w(Rf1[2], Rf2[1])
    sh.gnd(Rf2[2])
    sh.label('BUCK_FB', (xf, Rf1[2][1] + g(1)), 'L', stub=0)
    sh.w((xf, Rf1[2][1] + g(1)), (xf - g(1), Rf1[2][1] + g(1)))
    sh.labels[-1] = ('label', 'BUCK_FB', (xf - g(1), Rf1[2][1] + g(1)), 180, None)
    sh.label('BUCK_FB', B['FB'], 'R', stub=1)
    # output caps
    xo1, xo2 = xf + g(5), xf + g(11)
    cap_to_gnd(sh, 'C107', '47uF 10V', C1210, xo1, yo, 2)
    cap_to_gnd(sh, 'C108', '47uF 10V', C1210, xo2, yo, 2)
    sh.w(L[2], (xf, yo), (xo1, yo), (xo2, yo), (xo2 + g(3), yo))
    sh.rail('VBUCK_3V8', (xo2 + g(3), yo))   # -> TPS2121 IN1 (battery sheet); loads are on VSYS_3V8
    # compensation (COMP -> R106 -> C105 -> GND, C106 || to GND), labelled
    sh.label('BUCK_COMP', B['COMP'], 'R', stub=1)
    yc = B['GND'][1] + g(5)
    xcmp = XB - g(2)
    sh.label('BUCK_COMP', (xcmp, yc), 'L')
    sh.w((xcmp, yc), (xcmp + g(6), yc))
    Rc = rv(sh, 'Device:R', 'R106', '7.5k', R0603, xcmp + g(2), yc)
    Cc = rv(sh, 'Device:C', 'C105', '6.8nF', C0603, xcmp + g(2), Rc[2][1] + g(1))
    sh.w(Rc[2], Cc[1])
    sh.gnd(Cc[2])
    Cp = rv(sh, 'Device:C', 'C106', '47pF', C0603, xcmp + g(6), yc)
    sh.gnd(Cp[2])
    sh.text('Compensation values: first pass,\nverify with TI WEBENCH', xcmp + g(9), yc + g(1), 1.27)

    # ---------------- LDO 3.3 V
    yl = g(50)
    sh.text('LDO 3.3 V (logic)', g(5), yl - g(6), 1.5, True)
    XL = g(20)
    Ld = sh.part('Regulator_Linear:TLV75733PDBV', 'U103', 'TLV75733PDBV', 'Package_TO_SOT_SMD:SOT-23-5', XL, yl, 0)
    Ld.fields = IC(XL, Ld['IN'][1] - 2.54, Ld['GND'][1], left=XL - g(2))
    yin = Ld['IN'][1]
    xin = Ld['IN'][0] - g(3)
    sh.w(Ld['EN'], (Ld['EN'][0] - g(1), Ld['EN'][1]), (Ld['EN'][0] - g(1), yin))
    sh.w(Ld['IN'], (Ld['EN'][0] - g(1), yin), (xin, yin), (xin - g(3), yin))
    sh.rail('VSYS_3V8', (xin - g(3), yin))
    cap_to_gnd(sh, 'C109', '1uF', C0603, xin, yin, 2)
    sh.gnd(Ld['GND'])
    sh.nc(Ld, 'NC')
    xout = Ld['OUT'][0] + g(3)
    cap_to_gnd(sh, 'C110', '10uF', C0805, xout, Ld['OUT'][1], 2)
    sh.w(Ld['OUT'], (xout, Ld['OUT'][1]), (xout + g(3), Ld['OUT'][1]))
    sh.rail('+3V3', (xout + g(3), Ld['OUT'][1]))

    # ---------------- LTE supply switch
    sh.text('LTE modem supply switch (LTE_PWR_EN high = on)', g(42), yl - g(6), 1.5, True)
    XQ = g(58)
    qf = {'ref': (XQ - 1.27, yl - 7.62, None), 'val': (XQ - 1.27, yl - 5.08, None)}
    Qp = sh.part('Transistor_FET:AO3401A', 'Q102', 'AO3401A', SOT23, XQ, yl, 90, fields=qf)
    s, d, gt = Qp['S'], Qp['D'], Qp['G']
    if s[0] > d[0]:
        sh.parts.remove(Qp)
        Qp = sh.part('Transistor_FET:AO3401A', 'Q102', 'AO3401A', SOT23, XQ, yl, 270, 'x', fields=qf)
        s, d, gt = Qp['S'], Qp['D'], Qp['G']
    ys = s[1]
    sh.w(s, (s[0] - g(8), ys))
    sh.rail('VSYS_3V8', (s[0] - g(8), ys))
    sh.w(d, (d[0] + g(4), ys))
    sh.rail('VBAT_LTE', (d[0] + g(4), ys))
    Rg = rv(sh, 'Device:R', 'R107', '100k', R0603, s[0] - g(4), ys)
    sh.w(Rg[2], (Rg[2][0], gt[1] + (g(1) if gt[1] > ys else -g(1))))
    yg = Rg[2][1] + g(1)
    sh.w(Rg[2], (Rg[2][0], yg), (gt[0], yg), gt) if gt[1] > ys else None
    Qn = sh.part('Transistor_FET:2N7002', 'Q103', '2N7002', SOT23, gt[0] - 2.54, yg + g(2) + 5.08, 0,
                 fields={'ref': (gt[0] + 1.27, yg + g(2) + 3.81, 'left'), 'val': (gt[0] + 1.27, yg + g(2) + 6.35, 'left')})
    sh.w((gt[0], yg), Qn['D'])
    sh.gnd(Qn['S'])
    sh.w(Qn['G'], (Qn['G'][0] - g(4), Qn['G'][1]))
    sh.glabel('LTE_PWR_EN', (Qn['G'][0] - g(4), Qn['G'][1]), 'L', 'input')
    Rpd = rv(sh, 'Device:R', 'R108', '100k', R0603, Qn['G'][0] - g(2), Qn['G'][1])
    sh.gnd(Rpd[2])

    # ---------------- battery sense
    sh.text('Battery sense (VSENSE = VIN / 11, full scale ~35 V)', g(82), yl - g(6), 1.5, True)
    xs = g(88)
    Rs1 = rv(sh, 'Device:R', 'R109', '100k', R0603, xs, yl - g(2))
    sh.rail('VIN_PROT', Rs1[1])
    Rs2 = rv(sh, 'Device:R', 'R110', '10k', R0603, xs, Rs1[2][1] + g(2))
    sh.w(Rs1[2], Rs2[1])
    sh.gnd(Rs2[2])
    yn = Rs1[2][1] + g(1)
    Cs = rv(sh, 'Device:C', 'C111', '100nF', C0603, xs + g(4), yn)
    sh.w((xs, yn), Cs[1], (xs + g(8), yn))
    sh.gnd(Cs[2])
    sh.glabel('VSENSE', (xs + g(8), yn), 'R', 'output')

    # ---------------- power flags
    yf = g(72)
    sh.text('ERC power flags', g(5), yf - g(5), 1.27)
    for i, net in enumerate(['VBAT_F', 'VIN_PROT', 'VBUCK_3V8', 'VBAT_LTE', 'GND']):
        x = g(6 + 6 * i)
        flg = sh.part('power:PWR_FLAG', f'#FLG10{i + 1}', 'PWR_FLAG', '', x, yf, 0)
        if net == 'GND':
            sh.gnd(flg[1])
        elif net == 'VBAT_F':
            sh.w(flg[1], (x, yf + g(1)), (x + g(1), yf + g(1)))
            sh.label('VBAT_F', (x + g(1), yf + g(1)), 'R')
        else:
            sh.w(flg[1], (x, yf + g(1)))
            sh.parts.append(None) if False else None
            sh.rail(net, (x, yf + g(1)))
            # rail symbol arrow points up into the flag: rotate it down instead
            sh.parts[-1].rot = 180
    return sh


def decap(sh, ref, val, fp, x, y_top, rail, lib='Device:C'):
    """Stand-alone decoupling cap: rail symbol on top, GND below."""
    c = rv(sh, lib, ref, val, fp, x, y_top)
    sh.rail(rail, c[1])
    sh.gnd(c[2])
    return c


def testpad(sh, ref, net, x, y, rail=None):
    """Test pad drawn horizontally: connection at (x, y), pad to the right, label to the left."""
    x, y = round(x, 4), round(y, 4)
    tp = sh.part('Connector:TestPoint', ref, net, 'TestPoint:TestPoint_Pad_D1.0mm', x, y, 270,
                 fields={'ref': (x + g(2.5), y - 1.27, 'left'), 'val': (x + g(2.5), y + 1.27, 'left')})
    assert tp['1'] == (x, y)
    if net == 'GND':
        sh.w(tp['1'], (x - g(1), y))
        sh.gnd((x - g(1), y), rot=270)
    elif rail:
        sh.w(tp['1'], (x - g(1), y))
        sh.rail(net, (x - g(1), y), rot=90)
    else:
        sh.w(tp['1'], (x - g(1), y))
        sh.label(net, (x - g(1), y), 'L')
    return tp


def lab_row(sh, part, pins, side, stub, glob, shape='bidirectional'):
    """Labels on a list of (pin, net) pairs. glob: set of nets that need global labels."""
    for pin, net in pins:
        if net is None:
            sh.nc(part, pin)
        elif net in glob:
            sh.glabel(net, part.out(pin, stub), side, shape if not isinstance(shape, dict) else shape.get(net, 'bidirectional'))
            sh.w(part[pin], part.out(pin, stub))
        else:
            sh.label(net, part.out(pin, stub), side)
            sh.w(part[pin], part.out(pin, stub))


# =====================================================================================
def vehicle():
    sh = Sheet('Vehicle', 'vehicle.kicad_sch', SHEETS['vehicle'], ROOT, 'Vehicle interface: OBD-II, CAN, K-Line')
    J = sh.part('obd-v2x:OBD2_J1962_Plug', 'J201', 'OBD2_J1962_Plug', 'obd-v2x:OBD2_J1962_Plug_PCB', g(16), g(30), 0)
    J.fields = IC(g(16), g(30) - g(7), g(30) + g(7))
    for pin in ('1', '3', '8', '9', '11', '12', '13', '2', '10', '15'):
        sh.nc(J, pin)
    sh.text('OBD-II plug (vehicle side)', g(6), g(18), 1.5, True)
    # battery
    sh.w(J['16'], (g(30), J['16'][1]))
    sh.glabel('OBD_VBAT', (g(30), J['16'][1]), 'R', 'output')
    # grounds
    xg = J['5'][0] + g(2)
    sh.w(J['5'], (xg, J['5'][1]))
    sh.w(J['4'], (xg, J['4'][1]))
    sh.w((xg, J['5'][1]), (xg, J['4'][1]))
    sh.gnd((xg, J['4'][1]))

    # ---------------- CAN
    sh.text('High-speed CAN (ISO 15765), no termination in the dongle', g(30), g(10), 1.5, True)
    ych, ycl = J['6'][1], J['14'][1]
    XU = g(56)
    U = sh.part('Interface_CAN_LIN:TCAN334', 'U201', 'TCAN334', 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',
                XU, ych + 2.54, 0, 'y')
    U.fields = IC(XU, U['VCC'][1] - g(1), U['GND'][1] + g(1), left=XU - g(3))
    U.fields = {'ref': (XU + g(1), U['VCC'][1] - 1.27, 'left'), 'val': (XU - g(2), U['GND'][1] + g(1), 'right')}
    assert abs(U['CANH'][1] - ych) < 1e-6
    xj = g(44)
    xk1, xk2 = g(36) - 2.54, g(36) + 2.54
    sh.w(J['6'], (xk1, ych), U['CANH'])
    sh.w(J['14'], (xk2, ycl), (xj, ycl), (xj, U['CANL'][1]), U['CANL'])
    D = sh.part('Power_Protection:NUP2105L', 'D201', 'NUP2105L', SOT23, g(36), ycl + g(4) + 5.08, 0)
    D.fields = {'ref': (g(36) + g(2), D.y - 1.27, 'left'), 'val': (g(36) + g(2), D.y + 1.27, 'left')}
    sh.w(D['1'], (xk1, ych))
    sh.w(D['2'], (xk2, ycl))
    sh.gnd(D['3'])
    sh.rail('+3V3', U['VCC'], stub=1)
    sh.gnd(U['GND'])
    xr = U['TXD'][0]
    sh.w(U['TXD'], (xr + g(3), U['TXD'][1]))
    sh.glabel('CAN_TX', (xr + g(3), U['TXD'][1]), 'R', 'input')
    sh.w(U['RXD'], (xr + g(3), U['RXD'][1]))
    sh.glabel('CAN_RX', (xr + g(3), U['RXD'][1]), 'R', 'output')
    sh.gnd(U['SHDN'], stub=1, rot=90)
    ys = U['STB'][1]
    R = rv(sh, 'Device:R', 'R201', '10k', R0603, xr + g(12), ys - 7.62)
    sh.rail('+3V3', R[1])
    sh.w(U['STB'], (xr + g(12), ys), (xr + g(15), ys))
    sh.glabel('CAN_STB', (xr + g(15), ys), 'R', 'input')
    decap(sh, 'C201', '100nF', C0603, XU + g(8), U['VCC'][1] - g(6), '+3V3')

    # ---------------- K-Line
    sh.text('K-Line (ISO 9141 / KWP2000) via LIN transceiver + 510R tester pull-up', g(30), J['7'][1] + g(25), 1.5, True)
    ylin = J['7'][1] + g(16)
    XK = g(56)
    K = sh.part('Interface_CAN_LIN:TJA1021xT', 'U202', 'TJA1021T/20', 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',
                XK, ylin - 2.54, 0, 'y')
    K.fields = {'ref': (XK + g(1), K['VBAT'][1] - 1.27, 'left'), 'val': (XK - g(2), K['GND'][1] + g(1), 'right')}
    assert abs(K['LIN'][1] - ylin) < 1e-6
    xkl = g(26)
    xc, xt, xp = g(30), g(35), g(41)
    sh.w(J['7'], (xkl, J['7'][1]), (xkl, ylin), (xc, ylin), (xt, ylin), (xp, ylin), K['LIN'])
    Ck = rv(sh, 'Device:C', 'C203', '220pF 50V', C0603, xc, ylin + g(1))
    sh.w((xc, ylin), Ck[1])
    sh.gnd(Ck[2])
    Ck.fields = VL(Ck.x, Ck.y)
    Dt = dv(sh, 'Device:D_TVS', 'D203', 'PESD1LIN', 'Diode_SMD:D_SOD-323', xt, ylin + g(1), 'A1')
    sh.w((xt, ylin), Dt['A1'])
    sh.gnd(Dt['A2'])
    Rp = rv(sh, 'Device:R', 'R204', '510 0.5W', R1206, xp, ylin - g(1) - 7.62)
    sh.w(Rp[2], (xp, ylin))
    Dp = dv(sh, 'Device:D_Schottky', 'D202', 'B0540WS', 'Diode_SMD:D_SOD-323', xp, Rp[1][1] - g(1) - 7.62, 'A')
    sh.w(Dp['K'], Rp[1])
    sh.rail('VIN_PROT', Dp['A'])
    sh.nc(K, 'INH')
    sh.rail('VIN_PROT', K['VBAT'], stub=1)
    sh.gnd(K['GND'])
    xr = K['RXD'][0]
    yrx = K['RXD'][1]
    Rx = rv(sh, 'Device:R', 'R202', '4.7k', R0603, xr + g(6), yrx - 7.62)
    sh.rail('+3V3', Rx[1])
    sh.w(K['RXD'], (xr + g(6), yrx), (xr + g(10), yrx))
    sh.glabel('KL_RX', (xr + g(10), yrx), 'R', 'output')
    sh.w(K['TXD'], (xr + g(10), K['TXD'][1]))
    sh.glabel('KL_TX', (xr + g(10), K['TXD'][1]), 'R', 'input')
    ysl = K['~{SLP}'][1]
    sh.w(K['~{SLP}'], (xr + g(6), ysl), (xr + g(10), ysl))
    sh.glabel('KL_SLP_N', (xr + g(10), ysl), 'R', 'input')
    Rs = rv(sh, 'Device:R', 'R203', '100k', R0603, xr + g(6), ysl + g(2))
    sh.w((xr + g(6), ysl), Rs[1])
    sh.gnd(Rs[2])
    sh.w(K['~{WAKE}'], (xr + g(2), K['~{WAKE}'][1]), (xr + g(2), K['~{WAKE}'][1] + g(3)))
    sh.rail('VIN_PROT', (xr + g(2), K['~{WAKE}'][1] + g(3)), rot=180)
    decap(sh, 'C202', '100nF 50V', C0603, XK + g(8), K['VBAT'][1] - g(6), 'VIN_PROT')
    return sh


# =====================================================================================
MCU_GLOBAL = {'KL_RX', 'VSENSE', 'LTE_PWRKEY_CTL', 'LTE_RESET_CTL', 'CAN_TX', 'CAN_RX', 'KL_TX', 'KL_SLP_N',
              'LTE_PWR_EN', 'LTE_STATUS_3V3', 'CAN_STB', 'MCU_TX_LTE', 'MCU_RX_LTE', 'MCU_CTS_LTE', 'MCU_RTS_LTE'}


def mcu():
    sh = Sheet('MCU', 'mcu.kicad_sch', SHEETS['mcu'], ROOT, 'MCU: ESP32-C5 (ITS-G5 RX, CAN FD, BLE), USB-C')
    X, Y = g(66), g(34)
    U = sh.part('obd-v2x:ESP32-C5-WROOM-1U', 'U301', 'ESP32-C5-WROOM-1U-N16R8', 'obd-v2x:ESP32-C5-WROOM-1U', X, Y, 0)
    U.fields = {'ref': (X - g(8), U['2'][1] - g(2.5), 'left'), 'val': (X - g(8), U['2'][1] - g(1.5), 'left')}
    sh.text('ESP32-C5: 5.9 GHz ITS-G5 receive via U.FL on the module', g(40), g(8), 1.5, True)
    left = [('6', 'KL_RX'), ('7', 'VSENSE'), ('4', 'LTE_PWRKEY_CTL'), ('5', 'LTE_RESET_CTL'), ('17', 'CAN_TX'),
            ('16', 'CAN_RX'), ('8', 'KL_TX'), ('9', 'KL_SLP_N'), ('10', 'LTE_PWR_EN'), ('11', 'LTE_STATUS_3V3'),
            ('12', 'CAN_STB'), ('19', None)]
    shapes = {'VSENSE': 'input', 'KL_RX': 'input', 'CAN_RX': 'input', 'LTE_STATUS_3V3': 'input'}
    shapes.update({n: 'output' for n in ('LTE_PWRKEY_CTL', 'LTE_RESET_CTL', 'CAN_TX', 'KL_TX', 'KL_SLP_N', 'LTE_PWR_EN', 'CAN_STB')})
    lab_row(sh, U, left, 'L', 2, MCU_GLOBAL, shapes)
    right = [('25', 'UART0_TX'), ('24', 'UART0_RX'), ('13', 'USB_DN'), ('14', 'USB_DP'), ('21', 'MCU_TX_LTE'),
             ('23', 'MCU_RX_LTE'), ('26', 'MCU_CTS_LTE'), ('27', 'MCU_RTS_LTE'), ('18', 'LED_DIN'), ('15', 'ESP_BOOT'),
             ('31', None), ('20', None), ('22', None)]
    lab_row(sh, U, right, 'R', 2, MCU_GLOBAL, {'MCU_TX_LTE': 'output', 'MCU_RX_LTE': 'input',
                                                'MCU_CTS_LTE': 'input', 'MCU_RTS_LTE': 'output'})
    sh.gnd(U['1'])
    # 3V3 + EN
    p3 = U['2']
    sh.w(p3, (p3[0] - g(4), p3[1]), (p3[0] - g(4), p3[1] - g(2)))
    sh.rail('+3V3', (p3[0] - g(4), p3[1] - g(2)))
    pen = U['3']
    xe = pen[0] - g(18)
    sh.w(pen, (xe, pen[1]))
    R1 = rv(sh, 'Device:R', 'R301', '10k', R0603, xe, pen[1] - g(1) - 7.62)
    sh.rail('+3V3', R1[1])
    sh.w(R1[2], (xe, pen[1]))
    C1 = rv(sh, 'Device:C', 'C301', '1uF', C0603, xe, pen[1] + g(1))
    sh.w((xe, pen[1]), C1[1])
    sh.gnd(C1[2])
    xs = xe - g(5)
    S1 = sh.part('Switch:SW_Push', 'SW301', 'RESET', 'Button_Switch_SMD:SW_SPST_TL3342', xs, pen[1] + g(1) + 5.08, 270,
                 fields={'ref': (xs - g(2), pen[1] + g(1) + 3.81, 'right'), 'val': (xs - g(2), pen[1] + g(1) + 6.35, 'right')})
    top, bot = S1['1'], S1['2']
    assert top[1] < bot[1]
    sh.w((xe, pen[1]), (xs, pen[1]), top)
    sh.gnd(bot)
    sh.label('ESP_EN', (xe - g(1), pen[1]), 'U') if False else None
    decap(sh, 'C302', '10uF', C0805, g(8), g(14), '+3V3')
    decap(sh, 'C303', '100nF', C0603, g(13), g(14), '+3V3')

    # BOOT button + pull-up
    yb = g(14)
    sh.text('Boot / status LED', g(96), g(8), 1.5, True)
    xb = g(100)
    Rb = rv(sh, 'Device:R', 'R302', '10k', R0603, xb, yb)
    sh.rail('+3V3', Rb[1])
    Sb = sh.part('Switch:SW_Push', 'SW302', 'BOOT', 'Button_Switch_SMD:SW_SPST_TL3342', xb, Rb[2][1] + g(2) + 5.08, 270,
                 fields={'ref': (xb + g(2), Rb[2][1] + g(2) + 3.81, 'left'), 'val': (xb + g(2), Rb[2][1] + g(2) + 6.35, 'left')})
    top, bot = Sb['1'], Sb['2']
    assert top[1] < bot[1]
    sh.w(Rb[2], top)
    sh.gnd(bot)
    yn = Rb[2][1] + g(1)
    sh.w((xb, yn), (xb - g(3), yn))
    sh.label('ESP_BOOT', (xb - g(3), yn), 'L')
    # LED
    Dl = sh.part('LED:SK6812MINI', 'D301', 'SK6812MINI', 'LED_SMD:LED_SK6812MINI_PLCC4_3.5x3.5mm_P1.75mm', g(98), g(36), 0)
    Dl.fields = {'ref': (g(98) + g(4), g(35), 'left'), 'val': (g(98) + g(4), g(37), 'left')}
    sh.rail('VSYS_3V8', Dl['VDD'])
    sh.gnd(Dl['VSS'])
    sh.w(Dl['DIN'], Dl.out('DIN', 2))
    sh.label('LED_DIN', Dl.out('DIN', 2), 'L')
    sh.nc(Dl, 'DOUT')
    decap(sh, 'C304', '100nF', C0603, g(106), g(30), 'VSYS_3V8')

    # USB-C
    sh.text('USB-C: flashing / bench power', g(6), g(44), 1.5, True)
    Jx, Jy = g(14), g(60)
    J = sh.part('Connector:USB_C_Receptacle_USB2.0_16P', 'J301', 'USB-C', 'Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12', Jx, Jy, 0)
    J.fields = {'ref': (Jx - g(6), Jy - g(10), 'left'), 'val': (Jx - g(6), Jy - g(9), 'left')}
    xr = J['A4'][0]
    sh.w(J['A4'], (xr + g(8), J['A4'][1]))
    sh.glabel('VBUS_USB', (xr + g(8), J['A4'][1]), 'R', 'output')
    Rc1 = rh(sh, 'Device:R', 'R303', '5.1k', R0603, xr + g(2), J['A5'][1])
    sh.w(J['A5'], Rc1[1])
    sh.gnd(Rc1[2], rot=90)
    Rc2 = rh(sh, 'Device:R', 'R304', '5.1k', R0603, xr + g(7), J['B5'][1])
    sh.w(J['B5'], Rc2[1])
    sh.gnd(Rc2[2], rot=90)
    xd = xr + g(2)
    sh.w(J['A7'], (xd, J['A7'][1]), (xd, J['B7'][1]), J['B7'])
    sh.w((xd, J['A7'][1]), (xd + g(3), J['A7'][1]))
    sh.label('USB_DN', (xd + g(3), J['A7'][1]), 'R')
    sh.w(J['A6'], (xd, J['A6'][1]), (xd, J['B6'][1]), J['B6'])
    sh.w((xd, J['B6'][1]), (xd + g(3), J['B6'][1]))
    sh.label('USB_DP', (xd + g(3), J['B6'][1]), 'R')
    sh.nc(J, 'A8')
    sh.nc(J, 'B8')
    sh.w(J['SH'], J['A1'])
    sh.gnd(J['A1'])
    # ESD
    E = sh.part('Power_Protection:USBLC6-2SC6', 'U302', 'USBLC6-2SC6', 'Package_TO_SOT_SMD:SOT-23-6', g(44), g(62), 0)
    E.fields = {'ref': (g(44) + g(2), g(62) - g(3), 'left'), 'val': (g(44) + g(2), g(62) + g(4), 'left')}
    for pin, net, side in (('1', 'USB_DP', 'L'), ('3', 'USB_DN', 'L'), ('6', 'USB_DP', 'R'), ('4', 'USB_DN', 'R')):
        sh.w(E[pin], E.out(pin, 2))
        sh.label(net, E.out(pin, 2), side)
    sh.w(E['VBUS'], E.out('VBUS', 1))
    sh.glabel('VBUS_USB', E.out('VBUS', 1), 'U', 'input')
    sh.gnd(E['GND'])
    # test points
    sh.text('UART0 test pads', g(64), g(56), 1.5, True)
    for i, (ref, net) in enumerate((('TP301', 'UART0_TX'), ('TP302', 'UART0_RX'), ('TP303', 'GND'))):
        testpad(sh, ref, net, g(76), g(60) + g(3) * i)
    return sh


# =====================================================================================
LTE_GLOBAL = {'MCU_TX_LTE', 'MCU_RX_LTE', 'MCU_RTS_LTE', 'MCU_CTS_LTE', 'LTE_STATUS_3V3', 'LTE_PWRKEY_CTL', 'LTE_RESET_CTL'}


def lte():
    sh = Sheet('LTE', 'lte.kicad_sch', SHEETS['lte'], ROOT, 'LTE Cat 1 + GNSS: Quectel EC200U-EU (1.8 V I/O)')
    X, Y = g(46), g(36)
    U = sh.part('obd-v2x:EC200U-EU', 'U401', 'EC200U-EU', 'obd-v2x:Quectel_EC200U', X, Y, 0)
    U.fields = {'ref': (X - g(9), U['59'][1] - g(2.5), 'left'), 'val': (X - g(9), U['59'][1] - g(1.5), 'left')}
    # VBAT pins joined
    xv = U['59'][0] - g(2)
    for pin in ('59', '60', '57', '58'):
        sh.w(U[pin], (xv, U[pin][1]))
    sh.w((xv, U['59'][1]), (xv, U['58'][1]))
    sh.w((xv, U['59'][1]), (xv, U['59'][1] - g(2)))
    sh.rail('VBAT_LTE', (xv, U['59'][1] - g(2)))
    sh.w(U['7'], (xv - g(4), U['7'][1]), (xv - g(4), U['7'][1] - g(3)))
    sh.rail('LTE_1V8', (xv - g(4), U['7'][1] - g(3)))
    left = [('21', 'LTE_PWRKEY'), ('20', 'LTE_RESET_N'), ('61', 'LTE_STATUS'), ('6', None), ('5', None), ('4', None),
            ('2', None), ('1', None), ('115', 'LTE_USB_BOOT'), ('71', 'LTE_USB_VBUS'), ('69', 'LTE_USB_DP'),
            ('70', 'LTE_USB_DM'), ('45', None), ('44', None)]
    lab_row(sh, U, left, 'L', 2, LTE_GLOBAL)
    right = [('68', 'LTE_RXD_1V8'), ('67', 'LTE_TXD_1V8'), ('65', 'LTE_RTS_1V8'), ('64', 'LTE_CTS_1V8'), ('66', None),
             ('62', None), ('63', None), ('11', 'LTE_DBG_RXD'), ('12', 'LTE_DBG_TXD'), ('14', 'SIM_VDD'),
             ('15', 'LTE_USIM_DATA'), ('16', 'LTE_USIM_CLK'), ('17', 'LTE_USIM_RST'), ('13', None),
             ('49', 'LTE_ANT_MAIN'), ('35', None), ('47', 'LTE_ANT_GNSS')]
    lab_row(sh, U, right, 'R', 2, LTE_GLOBAL)
    sh.w(U['10'], (U['10'][0] + g(2), U['10'][1]))
    sh.gnd((U['10'][0] + g(2), U['10'][1]), rot=90)
    sh.gnd(U['8'])
    # VBAT decoupling
    sh.text('VBAT_LTE bulk/decoupling (close to pins 57-60)', g(3), g(55), 1.27, True)
    decap(sh, 'C401', '220uF 6.3V', 'Capacitor_Tantalum_SMD:CP_EIA-7343-31_Kemet-D', g(5), g(58), 'VBAT_LTE', lib='Device:C_Polarized')
    decap(sh, 'C402', '100nF', C0603, g(13), g(58), 'VBAT_LTE')
    decap(sh, 'C403', '33pF', C0402, g(19), g(58), 'VBAT_LTE')
    decap(sh, 'C404', '10pF', C0402, g(25), g(58), 'VBAT_LTE')

    # PWRKEY / RESET drivers
    sh.text('PWRKEY / RESET_N open-collector drivers (MCU high = pull low)', g(4), g(8), 1.27, True)
    for i, (q, rb, rp, ctl, net, base) in enumerate((('Q401', 'R401', 'R402', 'LTE_PWRKEY_CTL', 'LTE_PWRKEY', 'PWRKEY_B'),
                                                      ('Q402', 'R403', 'R404', 'LTE_RESET_CTL', 'LTE_RESET_N', 'RESET_B'))):
        xq, yq = g(16 + 18 * i), g(16)
        Q = sh.part('Transistor_BJT:MMBT3904', q, 'MMBT3904', SOT23, xq, yq, 0,
                    fields={'ref': (xq + g(2), yq + 1.27, 'left'), 'val': (xq + g(2), yq + 3.81, 'left')})
        sh.w(Q['C'], Q.out('C', 1), (Q['C'][0] + g(2), Q.out('C', 1)[1]))
        sh.label(net, (Q['C'][0] + g(2), Q.out('C', 1)[1]), 'R')
        sh.gnd(Q['E'])
        Rb = rh(sh, 'Device:R', rb, '4.7k', R0603, Q['B'][0] - g(1) - 7.62, Q['B'][1])
        sh.w(Rb[2], Q['B'])
        sh.w(Rb[1], (Rb[1][0] - g(1), Rb[1][1]))
        sh.glabel(ctl, (Rb[1][0] - g(1), Rb[1][1]), 'L', 'input')
        xp = Q['B'][0] - g(1)
        Rp = rv(sh, 'Device:R', rp, '47k', R0603, xp, Q['B'][1] + g(1))
        Rp.fields = VL(Rp.x, Rp.y)
        sh.w((xp, Q['B'][1]), Rp[1])
        sh.gnd(Rp[2])

    # level shifter
    sh.text('1.8 V <-> 3.3 V level shifter (disabled while modem is off)', g(80), g(8), 1.27, True)
    XS, YS = g(92), g(24)
    T = sh.part('Logic_LevelTranslator:TXS0108EPW', 'U402', 'TXS0108EPW', 'Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm', XS, YS, 0)
    T.fields = {'ref': (XS + g(2), YS - g(9), 'left'), 'val': (XS + g(2), YS + g(9), 'left')}
    sh.w(T['VCCA'], (T['VCCA'][0], T['VCCA'][1] - g(1)), (T['VCCA'][0] - g(3), T['VCCA'][1] - g(1)))
    sh.rail('LTE_1V8', (T['VCCA'][0] - g(3), T['VCCA'][1] - g(1)))
    sh.w(T['VCCB'], (T['VCCB'][0], T['VCCB'][1] - g(1)), (T['VCCB'][0] + g(3), T['VCCB'][1] - g(1)))
    sh.rail('+3V3', (T['VCCB'][0] + g(3), T['VCCB'][1] - g(1)))
    sh.w(T['OE'], (T['OE'][0] - g(2), T['OE'][1]), (T['OE'][0] - g(2), T['VCCA'][1] - g(1)),
         (T['VCCA'][0] - g(3), T['VCCA'][1] - g(1)))
    sh.gnd(T['GND'])
    lab_row(sh, T, [('A1', 'LTE_RXD_1V8'), ('A2', 'LTE_TXD_1V8'), ('A3', 'LTE_RTS_1V8'), ('A4', 'LTE_CTS_1V8'),
                    ('A5', 'LTE_STATUS'), ('A6', None), ('A7', None), ('A8', None)], 'L', 2, LTE_GLOBAL)
    lab_row(sh, T, [('B1', 'MCU_TX_LTE'), ('B2', 'MCU_RX_LTE'), ('B3', 'MCU_RTS_LTE'), ('B4', 'MCU_CTS_LTE'),
                    ('B5', 'LTE_STATUS_3V3'), ('B6', None), ('B7', None), ('B8', None)], 'R', 2, LTE_GLOBAL,
            {'MCU_TX_LTE': 'input', 'MCU_RX_LTE': 'output', 'MCU_RTS_LTE': 'input', 'MCU_CTS_LTE': 'output',
             'LTE_STATUS_3V3': 'output'})
    decap(sh, 'C405', '100nF', C0603, g(104), g(10), 'LTE_1V8')
    decap(sh, 'C406', '100nF', C0603, g(109), g(10), '+3V3')

    # SIM 1 = nano-SIM holder J401 (default: any operator, incl. consumer SIMs / removable eUICC cards);
    # the soldered MFF2 eSIM U403 shares the lines and is not fitted by default
    sh.text('SIM 1 = nano-SIM J401 (default): R405-R407 fitted.\nOptional soldered eSIM: fit U403, C415, R411-R413, remove R405-R407 (never both).',
            g(44), g(5.6), 1.27, True)
    XE, YE = g(74), g(20)
    E = sh.part('obd-v2x:eSIM_MFF2', 'U403', 'eSIM MFF2', 'Package_SON:WSON-8-1EP_6x5mm_P1.27mm_EP3.4x4mm', XE, YE, 0,
                dnp=True)
    E.fields = {'ref': (XE + g(1), E['8'][1] - g(2.5), 'left'), 'val': (XE + g(1), E['8'][1] - g(1.5), 'left')}
    # series resistors on rows 3 grid apart; each wire drops in its own column to its pin row (no crossings)
    for yr, xc, pin, src, rref in ((g(10), g(62), '7', 'LTE_USIM_RST', 'R413'), (g(13), g(60), '6', 'LTE_USIM_CLK', 'R412'),
                                   (g(16), g(58), '3', 'LTE_USIM_DATA', 'R411')):
        Re = rh(sh, 'Device:R', rref, '22R', R0402, g(52), yr, dnp=True)
        sh.w(Re[2], (xc, yr), (xc, E[pin][1]), E[pin])
        sh.w(Re[1], (g(51), yr))
        sh.label(src, (g(51), yr), 'L')
    xv, yv = g(66), g(7.5)
    sh.w(E['8'], (xv, E['8'][1]), (xv, yv))
    sh.label('SIM_VDD', (xv, yv), 'L')
    Ce = rv(sh, 'Device:C', 'C415', '100nF', C0402, g(70), yv, dnp=True)
    sh.w((xv, yv), Ce[1])
    sh.gnd(Ce[2])
    sh.w(E['1'], (E['1'][0] + g(2), E['1'][1]))
    sh.gnd((E['1'][0] + g(2), E['1'][1]), rot=90)
    for pin in ('2', '4', '5', '9'):
        sh.nc(E, pin)

    # SIM holder (alternative to the eSIM)
    sh.text('Nano-SIM (default SIM)', g(80), g(38), 1.27, True)
    XJ, YJ = g(104), g(44)
    S = sh.part('Connector:SIM_Card', 'J401', 'Nano-SIM', 'Connector_Card:nanoSIM_GCT_SIM8060-6-0-14-00', XJ, YJ, 0)
    S.fields = {'ref': (XJ - g(4), YJ - g(5), 'left'), 'val': (XJ - g(4), YJ + g(4), 'left')}
    sh.nc(S, 'VPP')
    sh.w(S['GND'], S.out('GND', 1))
    sh.gnd(S.out('GND', 1), rot=270)
    xj = S['VCC'][0]
    sh.w(S['VCC'], (xj - g(2), S['VCC'][1]))
    sh.label('SIM_VDD', (xj - g(2), S['VCC'][1]), 'L')
    xR = xj - g(12)
    for pin, net, rref, src, dy in (('RST', 'SIM_RST', 'R407', 'LTE_USIM_RST', -2), ('CLK', 'SIM_CLK', 'R406', 'LTE_USIM_CLK', 0),
                                    ('I/O', 'SIM_IO', 'R405', 'LTE_USIM_DATA', 0)):
        y = S[pin][1]
        yr = y + g(dy)
        Rs = rh(sh, 'Device:R', rref, '22R', R0402, xR, yr)
        sh.w(Rs[2], (xj - g(7), yr), (xj - g(7), y), S[pin])
        sh.label(net, (xj - g(6), y), 'R')
        sh.w(Rs[1], (xR - g(1), yr))
        sh.label(src, (xR - g(1), yr), 'L')
    # SIM caps + data pull-up
    for i, (ref, val, net, fp) in enumerate((('C407', '33pF', 'SIM_IO', C0402), ('C408', '33pF', 'SIM_CLK', C0402),
                                             ('C409', '33pF', 'SIM_RST', C0402), ('C410', '100nF', 'SIM_VDD', C0402))):
        x = g(80 + 6 * i)
        c = rv(sh, 'Device:C', ref, val, fp, x, g(56))
        sh.w(c[1], (x, g(54)))
        sh.label(net, (x, g(54)), 'U')
        sh.gnd(c[2])
    Rpu = rv(sh, 'Device:R', 'R408', '15k', R0402, g(106), g(55))
    Rpu.fields = {'ref': (g(106) + g(1), Rpu.y - 1.27, 'left'), 'val': (g(106) + g(1), Rpu.y + 1.27, 'left')}
    sh.w(Rpu[1], (g(106), g(54)))
    sh.label('SIM_VDD', (g(106), g(54)), 'U')
    sh.w(Rpu[2], (g(106), Rpu[2][1] + g(1)), (g(108), Rpu[2][1] + g(1)))
    sh.label('LTE_USIM_DATA', (g(108), Rpu[2][1] + g(1)), 'R')

    # antennas
    sh.text('Antennas (pi-match, shunt caps DNP until tuned)', g(22), g(64), 1.27, True)
    for i, (r, c1, c2, j, src, rf, val) in enumerate((('R409', 'C411', 'C412', 'J402', 'LTE_ANT_MAIN', 'ANT_MAIN_RF', 'U.FL LTE main'),
                                                      ('R410', 'C413', 'C414', 'J403', 'LTE_ANT_GNSS', 'ANT_GNSS_RF', 'U.FL GNSS'))):
        x0, y = g(24 + 16 * i), g(69)
        sh.label(src, (x0, y), 'L')
        Rr = rh(sh, 'Device:R', r, '0R', R0402, x0 + g(3), y)
        sh.w((x0, y), (x0 + g(2), y), Rr[1])
        Ca = rv(sh, 'Device:C', c1, 'DNP', C0402, x0 + g(2), y + g(1), dnp=True)
        Ca.fields = VL(Ca.x, Ca.y)
        sh.w((x0 + g(2), y), Ca[1])
        sh.gnd(Ca[2])
        xr2 = Rr[2][0] + g(1)
        Cb = rv(sh, 'Device:C', c2, 'DNP', C0402, xr2, y + g(1), dnp=True)
        sh.w(Rr[2], (xr2, y))
        sh.w((xr2, y), Cb[1])
        sh.gnd(Cb[2])
        xjc = xr2 + g(1) + 5.08
        Jc = sh.part('Connector:Conn_Coaxial', j, val, 'Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical',
                     xjc, y, 0, fields={'ref': (xjc - g(1), y - g(3), None), 'val': (xjc - g(1), y - g(2), None)})
        sh.w((xr2, y), Jc['1'])
        sh.gnd(Jc['2'])

    # test points
    sh.text('Test pads: modem USB\n(firmware update), debug UART', g(3), g(29), 1.27, True)
    for i, (ref, net) in enumerate((('TP401', 'LTE_USB_VBUS'), ('TP402', 'LTE_USB_DP'), ('TP403', 'LTE_USB_DM'),
                                    ('TP404', 'LTE_USB_BOOT'), ('TP405', 'LTE_DBG_TXD'), ('TP406', 'LTE_DBG_RXD'),
                                    ('TP407', 'LTE_1V8'))):
        testpad(sh, ref, net, g(10), g(33) + g(3) * i, rail=(net == 'LTE_1V8'))
    return sh


# =====================================================================================
def battery():
    sh = Sheet('Backup battery', 'battery.kicad_sch', SHEETS['battery'], ROOT,
               'Backup battery: 1S Li-ion charger (BQ25171-Q1) + priority power mux (TPS2121)')
    # ---------------- charger
    sh.text('Li-ion charger, fed from the car side (VIN_PROT)', g(5), g(8), 1.5, True)
    XC, YC = g(34), g(24)
    U = sh.part('obd-v2x:BQ25171-Q1', 'U501', 'BQ25171-Q1', 'Package_SON:Texas_DRC0010J', XC, YC, 0)
    U.fields = IC(XC, U['1'][1] - g(1), U['5'][1], left=XC + g(1), above=True)
    # input: VIN_PROT -> 33R -> (TVS, 1uF) -> IN ; enters from above so the left side stays free
    yi = U['1'][1] - g(5)
    xn = U['1'][0] - g(2)
    sh.w(U['1'], (xn, U['1'][1]), (xn, yi))
    Ri = rh(sh, 'Device:R', 'R501', '33R 0.5W', R1206, g(9), yi)
    sh.w((g(9), yi), (g(7), yi))
    sh.rail('VIN_PROT', (g(7), yi))
    sh.w(Ri[2], (g(24), yi), (xn, yi))
    flg = sh.part('power:PWR_FLAG', '#FLG501', 'PWR_FLAG', '', g(24), yi - g(2), 0)   # fed via R501
    sh.w(flg[1], (g(24), yi))
    Dt = dv(sh, 'Device:D_Zener', 'D501', 'SMF24A', 'Diode_SMD:D_SOD-123F', g(17), yi + g(1), 'K')
    sh.w((g(17), yi), Dt['K'])
    sh.gnd(Dt['A'])
    cap_to_gnd(sh, 'C501', '1uF 50V', C0805, g(21), yi, 1)
    # /CE low = charge enabled
    sh.w(U['3'], (U['3'][0] - g(1), U['3'][1]))
    sh.gnd((U['3'][0] - g(1), U['3'][1]), rot=270)
    # programming resistors / NTC: lower pins land closest, so nothing crosses
    for xk, pin, ref, val, lib, fp in ((g(8), '4', 'RT501', '10k NTC', 'Device:Thermistor_NTC', R0603),
                                       (g(13), '2', 'R502', '4.3k', 'Device:R', R0603),
                                       (g(18), '9', 'R503', '24k 1%', 'Device:R', R0603),
                                       (g(23), '6', 'R504', '82k 1%', 'Device:R', R0603)):
        y = U[pin][1]
        sh.w(U[pin], (xk, y))
        r = rv(sh, lib, ref, val, fp, xk, y)
        sh.gnd(r[2])
    sh.text('ISET 4.3k: 70 mA charge (kept low: linear from 14 V, ~0.6 W)\nVSET 24k: 4.10 V float   CHM_TMR 82k: Li-ion, 10 h timer\n'
            'TS: 10k NTC next to the cell -> charging only 0..45 C', g(5), g(48), 1.27)
    sh.nc(U, '7')
    sh.nc(U, '8')
    sh.gnd(U['5'])
    # output = cell
    yo = U['10'][1]
    xo = U['10'][0]
    sh.w(U['10'], (xo + g(6), yo))
    sh.rail('VCELL', (xo + g(6), yo))
    cap_to_gnd(sh, 'C502', '1uF', C0603, xo + g(3), yo, 1)
    # cell connector
    sh.text('1S Li-ion/LiPo cell, 250-400 mAh, with protection PCM', g(46), g(40), 1.27, True)
    XJ, YJ = g(62), g(45)
    J = sh.part('Connector_Generic:Conn_01x02', 'J501', 'Battery 1S',
                'Connector_JST:JST_PH_B2B-PH-SM4-TB_1x02-1MP_P2.00mm_Vertical',
                XJ, YJ, 0, fields={'ref': (XJ + g(1), YJ - g(1), 'left'), 'val': (XJ + g(1), YJ + g(2), 'left')})
    sh.w(J['1'], (J['1'][0] - g(7), J['1'][1]))
    sh.rail('VCELL', (J['1'][0] - g(7), J['1'][1]))
    cap_to_gnd(sh, 'C505', '1uF', C0603, J['1'][0] - g(4), J['1'][1], 2)
    sh.w(J['2'], (J['2'][0] - g(1), J['2'][1]))
    sh.gnd((J['2'][0] - g(1), J['2'][1]), rot=270)

    # ---------------- power mux
    sh.text('Priority power mux: buck (IN1) while VIN_PROT > ~9.7 V, else cell (IN2)', g(62), g(8), 1.5, True)
    XM, YM = g(86), g(24)
    M = sh.part('obd-v2x:TPS2121', 'U502', 'TPS2121', 'Package_DFN_QFN:Texas_VQFN-HR-12_2x2.5mm_P0.5mm', XM, YM, 0)
    M.fields = IC(XM, M['7'][1] - g(1), M['12'][1], left=XM + g(1), above=True)
    sh.w(M['7'], (M['7'][0] - g(6), M['7'][1]))
    sh.rail('VBUCK_3V8', (M['7'][0] - g(6), M['7'][1]))
    sh.w(M['2'], (M['2'][0] - g(10), M['2'][1]))
    sh.rail('VCELL', (M['2'][0] - g(10), M['2'][1]))
    # PR1 = VIN_PROT / 9.2 (trips at ~9.7 V; 53 V surge -> 5.8 V < 6 V abs max)
    y3 = M['6'][1]
    xd = M['6'][0] - g(4)
    sh.w(M['6'], (xd, y3))
    Rb = rv(sh, 'Device:R', 'R506', '10k 1%', R0603, xd, y3)
    Rb.fields = VL(Rb.x, Rb.y)
    sh.gnd(Rb[2])
    Rt = rh(sh, 'Device:R', 'R505', '82k 1%', R0603, xd - g(7), y3)
    sh.w(Rt[2], (xd, y3))
    sh.w(Rt[1], (Rt[1][0] - g(2), y3))
    sh.rail('VIN_PROT', (Rt[1][0] - g(2), y3))
    # CP2 / OV1 / OV2 unused -> GND
    xb = M['3'][0] - g(1)
    sh.w(M['3'], (xb, M['3'][1]))
    sh.w(M['5'], (xb, M['5'][1]))
    sh.w(M['4'], (xb, M['4'][1]), (xb, M['4'][1] + g(1)))
    sh.w((xb, M['3'][1]), (xb, M['4'][1]))
    sh.gnd((xb, M['4'][1] + g(1)))
    # outputs -> VSYS_3V8 with hold-up for modem bursts on battery
    xr = M['1'][0] + g(2)
    sh.w(M['1'], (xr, M['1'][1]))
    sh.w(M['8'], (xr, M['8'][1]), (xr, M['1'][1]))
    yv = M['1'][1]
    sh.w((xr, yv), (g(110), yv))
    sh.rail('VSYS_3V8', (g(110), yv))
    cap_to_gnd(sh, 'C506', '220uF', 'Capacitor_Tantalum_SMD:CP_EIA-7343-31_Kemet-D', g(103), yv, 1,
               lib='Device:C_Polarized')
    cap_to_gnd(sh, 'C507', '10uF', C0805, g(107), yv, 1)
    # ST unused -> GND ; ILIM 30.1k ~ 3.5 A ; SS 10 nF
    sh.w(M['9'], (M['9'][0] + g(1), M['9'][1]))
    sh.gnd((M['9'][0] + g(1), M['9'][1]), rot=90)
    for xk, pin, ref, val, lib, fp in ((M['10'][0] + g(6), '10', 'R507', '30.1k 1%', 'Device:R', R0603),
                                       (M['11'][0] + g(3), '11', 'C504', '10nF', 'Device:C', C0603)):
        y = M[pin][1]
        sh.w(M[pin], (xk, y))
        r = rv(sh, lib, ref, val, fp, xk, y)
        sh.gnd(r[2])
    sh.gnd(M['12'])
    sh.text('ILIM 30.1k: ~3.5 A   SS 10 nF\nFirmware on battery: LTE only (lower burst current),\n'
            'shut the modem down below ~3.6 V cell', g(80), g(40), 1.27)
    return sh


if __name__ == '__main__':
    only = sys.argv[1:] or ['power', 'vehicle', 'mcu', 'lte', 'battery']
    import subprocess
    from schgen import HW
    from kicad_env import CLI as cli
    for name in only:
        sh = globals()[name]()
        for p in sh.parts:
            if p.ref in SOURCING:
                mpn, mfr, lcsc = SOURCING[p.ref]
                p.extra = {'MPN': mpn, 'Manufacturer': mfr, 'LCSC': lcsc}
        sh.write()
        # let KiCad re-save in its own latest format (avoids the "older version" banner)
        subprocess.run([str(cli), 'sch', 'upgrade', str(HW / sh.file)], check=True, capture_output=True)
        print('wrote', sh.file, len(sh.parts), 'symbols', len(sh.wires), 'wires')
