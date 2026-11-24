"""Unit tests for Fact Guard (requirement FR-13, NFR-04)."""
from app import factguard

PASSPORT = ["18.4", "2.89", "12.1", "2700", 9]


def test_supported_numbers_pass():
    text = "Площадь гостиной 18,4 м², высота потолка 2,89 м, свет 2700 K. Квартира на 9-м этаже."
    assert factguard.check(text, PASSPORT) == []


def test_english_and_dot_decimal_pass():
    assert factguard.check("The living room is 18.4 m² with a 2.89 m ceiling.", PASSPORT) == []


def test_rounding_to_fewer_decimals_is_supported():
    # 2.89 rounded to one decimal = 2.9
    assert factguard.check("Потолок почти 2,9 м.", PASSPORT) == []


def test_invented_area_is_rejected():
    issues = factguard.check("Площадь гостиной 25 м².", PASSPORT)
    assert [i.number for i in issues] == ["25"]
    assert issues[0].unit == "м²"


def test_wrong_rounding_is_rejected():
    # 2.89 can be said as 2.9, but never as 3.0
    issues = factguard.check("Ceiling height 3.0 m.", PASSPORT)
    assert [i.number for i in issues] == ["3.0"]


def test_price_or_term_is_rejected():
    issues = factguard.check("Ремонт займёт 45 дней и обойдётся в 1 200 000 сом.", PASSPORT)
    assert {i.number for i in issues} == {"45", "1 200 000"}


def test_thousands_with_space():
    assert factguard.check("Тёплый свет 2 700 K.", PASSPORT) == []


def test_text_without_numbers_passes():
    assert factguard.check("Скрытые двери в цвет стен делают коридор шире.", PASSPORT) == []


def test_empty_passport_rejects_any_number():
    assert len(factguard.check("Room 1 of 2.", [])) == 2
