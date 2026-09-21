from formslang.project_projection import PreparedProjection, ProjectionCache, ProjectionKey


def key(scope="store-a", revision="1", review=0, freshness="CURRENT"):
    return ProjectionKey(
        store_scope=scope,
        project_id="a" * 32,
        analysis_revision=revision * 64,
        review_revision=review,
        target=("Oracle APEX", "26.1", "APEXlang"),
        freshness=freshness,
    )


def prepared(projection_key, name):
    return PreparedProjection(
        projection_key, {"name": name}, {}, {"project": {"name": name}}, {}, {},
    )


def test_projection_cache_builds_once_and_separates_store_scope():
    cache = ProjectionCache(max_entries=8)
    calls = []

    first = cache.get_or_build(key("store-a"), lambda: calls.append("a") or prepared(
        key("store-a"), "First",
    ))
    again = cache.get_or_build(key("store-a"), lambda: calls.append("repeat") or prepared(
        key("store-a"), "Wrong",
    ))
    other = cache.get_or_build(key("store-b"), lambda: calls.append("b") or prepared(
        key("store-b"), "Second",
    ))

    assert first is again
    assert first.overview_data["project"]["name"] == "First"
    assert other.overview_data["project"]["name"] == "Second"
    assert calls == ["a", "b"]


def test_projection_cache_keys_every_revision_and_evicts_lru():
    cache = ProjectionCache(max_entries=2)
    first_key, second_key, third_key = key(revision="1"), key(revision="2"), key(
        revision="3",
    )
    built = []
    cache.get_or_build(first_key, lambda: prepared(first_key, "First"))
    cache.get_or_build(second_key, lambda: prepared(second_key, "Second"))
    cache.get_or_build(first_key, lambda: prepared(first_key, "Wrong"))
    cache.get_or_build(third_key, lambda: prepared(third_key, "Third"))

    cache.get_or_build(second_key, lambda: built.append("rebuilt") or prepared(
        second_key, "Second rebuilt",
    ))

    assert built == ["rebuilt"]


def test_projection_cache_clear_project_does_not_clear_other_store():
    cache = ProjectionCache(max_entries=8)
    first_key, other_key = key("store-a"), key("store-b")
    first = cache.get_or_build(first_key, lambda: prepared(first_key, "First"))
    other = cache.get_or_build(other_key, lambda: prepared(other_key, "Other"))
    cache.clear_project("store-a", "a" * 32)

    rebuilt = cache.get_or_build(first_key, lambda: prepared(first_key, "Rebuilt"))
    retained = cache.get_or_build(other_key, lambda: prepared(other_key, "Wrong"))

    assert rebuilt is not first
    assert retained is other
