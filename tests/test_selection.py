from collections import Counter

from esenin_epub import curate
from esenin_epub.slug import slugify

MANDATORY = [
    "Сиротка (Есенин)",
    "Сказка о пастушонке Пете, его комиссарстве и коровьем царстве (Есенин)",
    "Письмо к женщине (Есенин)",
    "Чёрный человек (Есенин)",
    "До свиданья, друг мой, до свиданья (Есенин)",
]
LYUBOV_KHULIGANA = [
    "Заметался пожар голубой (Есенин)", "Ты такая ж простая, как все (Есенин)", "Пускай ты выпита другим (Есенин)",
    "Дорогая, сядем рядом (Есенин)", "Мне грустно на тебя смотреть (Есенин)", "Ты прохладой меня не мучай (Есенин)",
    "Вечер чёрные брови насопил (Есенин)",
]


def test_selection_loads_and_is_unique():
    sel = curate.load_selection()
    titles = [w.source_title for _, w in sel.all_specs()]
    assert len(titles) == len(set(titles))
    assert 50 <= len(titles) <= 80
    assert sel.book.language == "ru"
    assert sel.book.identifier.startswith("urn:uuid:")


def test_mandatory_works_present():
    sel = curate.load_selection()
    titles = {w.source_title for _, w in sel.all_specs()}
    for t in MANDATORY:
        assert t in titles, t


def test_cycles_complete_and_ordered():
    sel = curate.load_selection()
    by_section = {s.title: [w.source_title for w in s.works] for s in sel.sections}
    assert by_section["Любовь хулигана"] == LYUBOV_KHULIGANA
    assert len(by_section["Персидские мотивы"]) == 15
    assert by_section["Персидские мотивы"][0] == "Улеглась моя былая рана (Есенин)"
    assert by_section["Персидские мотивы"][-1] == "Голубая да весёлая страна (Есенин)"


def test_slugs_ascii_and_unique():
    sel = curate.load_selection()
    slugs = [slugify(w.source_title) for _, w in sel.all_specs()]
    assert all(s.isascii() and " " not in s for s in slugs)
    assert max(Counter(slugs).values()) == 1
    assert slugify("Сиротка (Есенин)") == "sirotka"
    assert slugify("Чёрный человек (Есенин)") == "chyornyy-chelovek"
