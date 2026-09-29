"""The Admin RTDB projection and the client read rule share one schema."""

import json
from pathlib import Path

import pytest

from app.services.firebase.firebase_provider import FirebasePresenceProviderImpl


class MemoryReference:
    def __init__(self, tree, path):
        self.tree = tree
        self.parts = path.split("/")

    def get(self):
        node = self.tree
        for part in self.parts:
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node

    def set(self, value):
        node = self.tree
        for part in self.parts[:-1]:
            node = node.setdefault(part, {})
        node[self.parts[-1]] = value

    def delete(self):
        node = self.tree
        for part in self.parts[:-1]:
            if part not in node:
                return
            node = node[part]
        node.pop(self.parts[-1], None)

    def transaction(self, update):
        value = update(self.get())
        if value is None:
            self.delete()
        else:
            self.set(value)
        return value


@pytest.mark.asyncio
async def test_provider_projection_matches_restrictive_presence_rule(monkeypatch):
    tree = {}
    provider = FirebasePresenceProviderImpl()
    monkeypatch.setattr(FirebasePresenceProviderImpl, "available", property(lambda _: True))
    monkeypatch.setattr(
        provider, "_reference", lambda path: MemoryReference(tree, path)
    )

    rules_path = Path(__file__).resolve().parents[2] / "firebase" / "database.rules.json"
    rules = json.loads(rules_path.read_text(encoding="utf-8"))["rules"]
    read_rule = rules["presence"]["$uid"][".read"]
    assert rules[".read"] is False
    assert rules[".write"] is False
    assert rules["presenceVisibility"]["$uid"][".write"] is False
    assert read_rule == (
        "auth != null && (auth.uid === $uid || "
        "root.child('presenceVisibility').child($uid).child(auth.uid).exists())"
    )

    def may_read(reader, target):
        if reader == target:
            return True
        return bool(tree.get("presenceVisibility", {}).get(target, {}).get(reader))

    await provider.publish_membership("first", ["user-a", "expert-b"])
    assert tree["presenceVisibility"]["user-a"]["expert-b"] == {"first": True}
    assert tree["presenceVisibility"]["expert-b"]["user-a"] == {"first": True}
    assert may_read("user-a", "expert-b")
    assert may_read("expert-b", "user-a")
    assert not may_read("random-c", "expert-b")

    await provider.publish_membership("second", ["user-a", "expert-b"])
    await provider.revoke_membership("first")
    assert tree["presenceVisibility"]["user-a"]["expert-b"] == {"second": True}
    assert may_read("user-a", "expert-b")
    assert may_read("expert-b", "user-a")

    await provider.revoke_membership("second")
    assert not may_read("user-a", "expert-b")
    assert not may_read("expert-b", "user-a")
    assert "expert-b" not in tree["presenceVisibility"]["user-a"]
