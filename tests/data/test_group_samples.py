from scripts.group_samples import group_samples


def test_publisher_and_event_edges_form_one_transitive_group():
    def row(publisher, event, body, url, checksum):
        return {"publisher": publisher, "event_id": event, "body": body, "title": None,
                "source_url": url, "image": {"sha256": checksum}}

    rows = {
        "a": row("City News", None, "school project", "https://example.org/a", "a"),
        "b": row(" city news ", "traffic-event", "railway construction", "https://example.org/b", "b"),
        "c": row("State News", "TRAFFIC-EVENT", "opening ceremony", "https://example.org/c", "c"),
        "d": row("Other News", None, "river wildlife", "https://example.org/d", "d"),
    }
    image_hashes = {"a": 0, "b": 2**64 - 1, "c": 2**32 - 1, "d": (2**32 - 1) << 32}
    mapping, edges, _ = group_samples(rows, image_hashes)
    assert mapping["a"] == mapping["b"] == mapping["c"] != mapping["d"]
    assert [(left, right, kind) for left, right, kind, _ in edges] == [
        ("a", "b", "publisher"), ("b", "c", "event_id")]
    assert mapping == group_samples(dict(reversed(list(rows.items()))), image_hashes)[0]
