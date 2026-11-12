import pytest

from nsr.corpactions import parse_purpose, rights_factor


@pytest.mark.parametrize("text,factor", [
    ("FV SPLIT RS.10 TO RE.1", 0.1),
    ("FV SPLIT RS.10/- TO RS.2/-", 0.2),
    ("FV SPLT FRM RS 5 TO RE 1", 0.2),
    ("FVSPLT FRM RS 10 TO RS 5", 0.5),
    ("BONUS 1:1", 0.5),
    ("BONUS 1:2", 2 / 3),
    ("BONUS 3: 2", 0.4),
    ("BON 1:1/FV SPL RS.10TORE.1", 0.05),
    ("FV SPL-RS10TORS2/BON-1:1", 0.1),
    ("BONS1:1/FV SPLT RS10TO RE1", 0.05),
])
def test_split_and_bonus_factors(text, factor):
    a = parse_purpose(text)
    assert a.factor == pytest.approx(factor)
    assert not a.unresolved and a.dividend == 0


@pytest.mark.parametrize("text,div", [
    ("DIVIDEND-RE.1/- PER SHARE", 1.0),
    ("AGM/DIV-RS.3.50 PER SHARE", 3.5),
    ("AGM/DIV-RE.0.60 PER SHARE", 0.6),
    ("INTDIV - RS 4 PER SH", 4.0),
    ("INTDIV - RS 10.25 PER SH", 10.25),
    ("FIN DIV RS 6+SPL DIV RS 4", 10.0),
    ("DIV-FIN RS.5+SPL RS.2", 7.0),
    ("AGM/DIV-FIN 5+SPL 2", 7.0),
    ("DIVIDEND RS2 PER SHARE", 2.0),
])
def test_dividend_amounts(text, div):
    a = parse_purpose(text)
    assert a.dividend == pytest.approx(div)
    assert a.factor == 1.0 and not a.unresolved and not a.div_unknown


@pytest.mark.parametrize("text", ["INTERIM DIVIDEND", "2ND INTERIM DIVIDEND", "AGM/DIVIDEND", "DIVIDEND - 20%"])
def test_dividend_without_amount_is_flagged_not_guessed(text):
    a = parse_purpose(text)
    assert a.div_unknown and a.dividend == 0 and a.factor == 1.0


@pytest.mark.parametrize("text", [
    "SCHEME OF ARRANGEMENT", "SCHEME OF DEMERGER", "CAPITAL REDUCTION",
    "BONUS 1 DVR : 10 EQ SHARE", "DIV-RE.0.5/SCH OF ARRGMNT", "RIGHTS-EQ1:1 & 1WRNT:2EQ", "RHT EQ1:5@PRM 20&1W:2EQ",
])
def test_unquantifiable_events_are_unresolved(text):
    assert parse_purpose(text).unresolved


@pytest.mark.parametrize("text", ["ANNUAL GENERAL MEETING", "EGM", "BUYBACK OF SHARES", "ANNUAL BOOK CLOSURE"])
def test_non_price_events_are_neutral(text):
    a = parse_purpose(text)
    assert a.factor == 1.0 and a.dividend == 0 and not a.unresolved and not a.div_unknown


def test_special_dividend_is_not_mistaken_for_a_split():
    a = parse_purpose("FIN DIV RS 6+SPL DIV RS 4")
    assert a.factor == 1.0


def test_rights_terp():
    a = parse_purpose("RIGHTS 1:5 @PREM RS.90/-")
    assert a.rights == (1, 5, 90.0) and not a.unresolved
    # 5 old shares at 150 + 1 new at 90 -> TERP 140
    assert rights_factor(a.rights, 150.0) == pytest.approx(140 / 150)
    assert rights_factor(a.rights, 80.0) == 1.0  # out-of-the-money rights


def test_combined_dividend_and_typoed_split():
    # real text from 24-Nov-2010 (GREAVESCOT): split keyword is misspelt
    a = parse_purpose("DIV-RS 2/FV-SPTLRS10TORS2")
    assert a.factor == pytest.approx(0.2) and a.dividend == pytest.approx(2.0)
    assert not a.unresolved


def test_register_wording_for_splits_is_not_read_as_a_dividend():
    a = parse_purpose("FACE VALUE SPLIT (SUB-DIVISION) - FROM RS 10/- PER SHARE TO RE 1/- PER SHARE")
    assert a.factor == pytest.approx(0.1) and not a.div_unknown and a.dividend == 0 and not a.unresolved
    b = parse_purpose("ANNUAL GENERAL MEETING/ DIVIDEND - RS 29.50/- PER SHARE AND BONUS 1:1")
    assert b.factor == pytest.approx(0.5) and b.dividend == pytest.approx(29.5)
    c = parse_purpose("INTERIM DIVIDEND RS 2/- PER SHARE AND FACE VALUE SPLIT FROM RS 10/- TO RS 2/-")
    assert c.factor == pytest.approx(0.2) and c.dividend == pytest.approx(2.0)
