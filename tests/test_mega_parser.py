from gpcore.serialproto import AckLine, BPacket, DPacket, STSPacket, parse_line

D_V2 = 'D:12345,100,101,102,103,10,-20,8190,5,-6,7'
D_V4 = 'D:12345,100,101,102,103,10,-20,8190,5,-6,7,-300,150,420'
D_V5 = D_V4 + ',1,95,0'


def test_d_packet_v2_no_mag():
    p = parse_line(D_V2)
    assert isinstance(p, DPacket)
    assert p.t_ms == 12345
    assert p.enc == (100, 101, 102, 103)
    assert p.accel == (10, -20, 8190)
    assert p.gyro == (5, -6, 7)
    assert p.mag is None and p.pump is None and p.estop is None


def test_d_packet_v4_with_mag():
    p = parse_line(D_V4)
    assert p.mag == (-300, 150, 420)
    assert p.pump is None


def test_d_packet_v5_accessories():
    p = parse_line(D_V5)
    assert p.pump is True
    assert p.servo_deg == 95
    assert p.estop is False


def test_d_packet_truncated_and_garbage():
    assert parse_line('D:123,1,2,3') is None
    assert parse_line('D:12345,100,101,102,103,10,-20,oops,5,-6,7') is None
    assert parse_line('') is None
    assert parse_line('\x00\xffnoise') is None
    assert parse_line('IMU:OK') is None


def test_b_packet():
    p = parse_line('B:5000,101325,231')
    assert isinstance(p, BPacket)
    assert (p.t_ms, p.pressure_pa, p.temp_deci_c) == (5000, 101325, 231)
    assert parse_line('B:5000,101325') is None


def test_sts_csv_form_from_robot2_bridge():
    p = parse_line('STS:180,0,11,22,33,44')
    assert isinstance(p, STSPacket)
    assert p.speed == 180
    assert p.estop is False
    assert p.enc == (11, 22, 33, 44)


def test_sts_text_form_from_robot1_firmware():
    p = parse_line('STS:IDLE,SPD:0')
    assert isinstance(p, STSPacket)
    assert p.speed == 0
    assert p.enc is None
    p2 = parse_line('STS:ESTOP,SPD:140')
    assert p2.estop is True and p2.speed == 140


def test_ack_lines():
    ok = parse_line('OK:PUMP=ON')
    assert isinstance(ok, AckLine) and ok.ok and ok.detail == 'PUMP=ON'
    err = parse_line('ERR:PUMP_COOLDOWN')
    assert isinstance(err, AckLine) and not err.ok and err.detail == 'PUMP_COOLDOWN'
