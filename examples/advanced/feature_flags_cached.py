"""
Feature flag reads cached with short TTL.

This example shows:
- Caching feature flag reads from a remote config source
- Manual invalidation when config changes
"""

import time

from omni_cache import cached, setup

setup(log_level="INFO")

REMOTE_FLAGS: dict[str, dict[str, bool]] = {
    "pro": {"new_checkout": True, "beta_dashboard": True},
    "free": {"new_checkout": False, "beta_dashboard": False},
}


def _fetch_flags_for_tier(tier: str) -> dict[str, bool]:
    print(f"Remote flags fetch for tier={tier}")
    time.sleep(0.2)
    return REMOTE_FLAGS[tier].copy()


@cached(ttl=15, namespace="flags")
def get_flags_for_tier(tier: str) -> dict[str, bool]:
    return _fetch_flags_for_tier(tier)


def is_feature_enabled(tier: str, feature_name: str) -> bool:
    flags = get_flags_for_tier(tier)
    return bool(flags.get(feature_name, False))


def main() -> None:
    print("=== Feature flags cached example ===")
    print("Initial free/new_checkout:", is_feature_enabled("free", "new_checkout"))
    print("Second read (cached):", is_feature_enabled("free", "new_checkout"))

    print("\nUpdating remote flags for free tier...")
    REMOTE_FLAGS["free"]["new_checkout"] = True
    print("Before invalidation:", is_feature_enabled("free", "new_checkout"))

    get_flags_for_tier.invalidate("free")
    print("After invalidation:", is_feature_enabled("free", "new_checkout"))


if __name__ == "__main__":
    main()
