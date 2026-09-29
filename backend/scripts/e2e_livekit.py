"""End-to-end against a real (local) LiveKit server.

Needs the LiveKit *client* SDK, which the backend itself does not depend on.
Run it from a separate environment:

    python -m venv .e2e && .e2e/Scripts/pip install livekit
    python -m scripts.e2e_livekit_prepare setup > e2e.json   # backend venv
    .e2e/Scripts/python scripts/e2e_livekit.py e2e.json
    python -m scripts.e2e_livekit_prepare cleanup           # backend venv

What it proves, that the fake provider cannot:

* our join tokens are accepted by a real LiveKit, for the right room;
* the permissions LiveKit *reports back* are the least-privilege ones we asked
  for - no data channel, only the allowed track sources;
* an audio call's token genuinely cannot publish a camera track;
* real, signed webhooks reach the API and drive the call through RINGING and
  ACTIVE to ENDED - no client ever says "started";
* a second device with the same identity replaces the first
  (DUPLICATE_IDENTITY) without the call ending;
* ending the call deletes the room, and a leftover token cannot reopen it.

No media is inspected, recorded or stored; silent frames are published only
to prove what may and may not be published.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import urllib.error
import urllib.request

from livekit import rtc

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append((name, passed, detail))
    print(f"  {'PASS' if passed else 'FAIL'}: {name}{(' - ' + detail) if detail else ''}")


class Api:
    def __init__(self, base: str, token: str) -> None:
        self.base = base
        self.token = token

    def call(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status, json.loads(response.read() or b"{}"), dict(response.headers)
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"{}"), dict(error.headers)


async def wait_for(api: Api, call_id: str, statuses: set[str], timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    body: dict = {}
    while time.monotonic() < deadline:
        _, body, _ = api.call("GET", f"/calls/{call_id}")
        if body.get("status") in statuses:
            return body
        await asyncio.sleep(0.5)
    return body


async def connect(url: str, token: str) -> rtc.Room:
    room = rtc.Room()
    await room.connect(url, token, rtc.RoomOptions(auto_subscribe=False))
    return room


async def publish(room: rtc.Room, kind: str) -> Exception | None:
    """Try to publish a silent track. Returns the error, if refused."""
    try:
        if kind == "microphone":
            source = rtc.AudioSource(48000, 1)
            track = rtc.LocalAudioTrack.create_audio_track("mic", source)
            options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        else:
            source = rtc.VideoSource(64, 64)
            track = rtc.LocalVideoTrack.create_video_track("cam", source)
            options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_CAMERA)
        await asyncio.wait_for(room.local_participant.publish_track(track, options), 15)
        return None
    except Exception as exc:  # noqa: BLE001 - reported
        return exc


async def quietly(awaitable, seconds: float = 10.0) -> None:
    """Disconnecting from a room the server already deleted can hang."""
    try:
        await asyncio.wait_for(awaitable, seconds)
    except Exception:  # noqa: BLE001 - teardown only
        pass


def sources(room: rtc.Room) -> set[str]:
    permissions = room.local_participant.permissions
    return {rtc.TrackSource.Name(item) for item in permissions.can_publish_sources}


async def main(path: str) -> int:
    with open(path, encoding="utf-8") as handle:
        prep = json.load(handle)
    user = Api(prep["base_url"], prep["user_token"])
    expert = Api(prep["base_url"], prep["expert_token"])
    order_id = prep["order_id"]

    print("\n== video call")
    status, call, _ = user.call("POST", "/calls", {"order_id": order_id, "call_type": "video"})
    check("user opens a video call", status == 201, f"{status} {call.get('status')}")
    call_id = call["id"]

    status, joined, headers = user.call("POST", f"/calls/{call_id}/join")
    check("join returns a token", status == 200 and bool(joined.get("token")))
    check(
        "join response is not cacheable",
        "no-store" in headers.get("Cache-Control", headers.get("cache-control", "")),
    )

    user_room = await connect(joined["livekit_url"], joined["token"])
    check("a real LiveKit accepts our token", user_room.isconnected())
    check(
        "the identity LiveKit sees is the opaque one",
        user_room.local_participant.identity == joined["participant_identity"],
    )
    permissions = user_room.local_participant.permissions
    check("LiveKit reports no data channel", permissions.can_publish_data is False)
    check(
        "LiveKit reports camera + microphone only",
        sources(user_room) == {"SOURCE_CAMERA", "SOURCE_MICROPHONE"},
        str(sorted(sources(user_room))),
    )

    body = await wait_for(user, call_id, {"ringing"})
    check("a signed webhook made the call RINGING", body.get("status") == "ringing", body.get("status", ""))

    status, expert_join, _ = expert.call("POST", f"/calls/{call_id}/join")
    expert_room = await connect(expert_join["livekit_url"], expert_join["token"])
    body = await wait_for(user, call_id, {"active"})
    check("both in the room made it ACTIVE", body.get("status") == "active", body.get("status", ""))
    check("started_at came from the server", bool(body.get("started_at")))

    error = await publish(user_room, "microphone")
    check("a video call may publish its microphone", error is None, repr(error) if error else "")

    print("\n== a second device replaces the first")
    status, again, _ = user.call("POST", f"/calls/{call_id}/join")
    check("the same identity on reissue", again.get("participant_identity") == joined["participant_identity"])
    replaced = asyncio.Event()
    reasons: list[str] = []

    @user_room.on("disconnected")
    def _on_disconnect(reason) -> None:  # noqa: ANN001
        reasons.append(str(reason))
        replaced.set()

    second_room = await connect(again["livekit_url"], again["token"])
    try:
        await asyncio.wait_for(replaced.wait(), 10)
    except asyncio.TimeoutError:
        pass
    check("the first connection was replaced", replaced.is_set(), ", ".join(reasons))
    await asyncio.sleep(2)
    _, body, _ = user.call("GET", f"/calls/{call_id}")
    check("the call survived the device switch", body.get("status") == "active", body.get("status", ""))

    print("\n== hanging up")
    await quietly(second_room.disconnect())
    body = await wait_for(user, call_id, {"ended"}, timeout=30)
    check("leaving past the grace ended the call", body.get("status") == "ended", body.get("status", ""))
    check("recorded as the user ending it", body.get("end_reason") == "user_ended", str(body.get("end_reason")))
    check(
        "duration from server timestamps",
        isinstance(body.get("duration_seconds"), int) and body["duration_seconds"] >= 0,
        str(body.get("duration_seconds")),
    )
    await quietly(expert_room.disconnect())

    print("\n== a leftover token cannot reopen the call")
    try:
        leftover = await connect(again["livekit_url"], again["token"])
        reopened = leftover.isconnected()
        await leftover.disconnect()
    except Exception:  # noqa: BLE001 - refusal is the expected outcome
        reopened = False
    check("the deleted room does not come back", not reopened)
    status, body, _ = user.call("POST", f"/calls/{call_id}/join")
    check("and no new token is issued", status == 409 and body["error"]["code"] == "call_already_ended", str(status))

    print("\n== audio call")
    status, call, _ = user.call("POST", "/calls", {"order_id": order_id, "call_type": "audio"})
    check("a new attempt is a new session", status == 201 and call["id"] != call_id, str(status))
    audio_id = call["id"]
    status, joined, _ = user.call("POST", f"/calls/{audio_id}/join")
    audio_room = await connect(joined["livekit_url"], joined["token"])
    check(
        "LiveKit reports microphone only",
        sources(audio_room) == {"SOURCE_MICROPHONE"},
        str(sorted(sources(audio_room))),
    )
    # Microphone first: LiveKit does not answer an unauthorised publish - it
    # lets it time out - and the client SDK queues later publishes behind it.
    error = await publish(audio_room, "microphone")
    check("an audio call can publish its microphone", error is None, repr(error) if error else "")
    error = await publish(audio_room, "camera")
    check("but cannot publish a camera", error is not None, repr(error)[:100] if error else "published!")
    camera_published = any(
        publication.source == rtc.TrackSource.SOURCE_CAMERA
        for publication in audio_room.local_participant.track_publications.values()
    )
    check("and no camera track exists in the room", not camera_published)

    status, body, _ = user.call("POST", f"/calls/{audio_id}/end")
    check("ending before an answer cancels", body.get("status") == "cancelled", body.get("status", ""))
    await asyncio.sleep(1)
    await quietly(audio_room.disconnect())

    failed = [name for name, passed, _ in RESULTS if not passed]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1])))
