# Realtime Database rules - notes

RTDB rules files accept only a top-level `rules` object and no comment
keys, so the explanation that used to live inside `database.rules.json`
lives here. The rules themselves are unchanged.

## Overview

Astrofrekans Realtime Database rules: presence and typing only.

RTDB is used here and not Firestore because presence needs onDisconnect,
which only a connected client can arm. The backend cannot know that a
phone went into a tunnel; the client's own connection can.

Three rules run through everything below:
  1. A user writes only their own presence. Writing somebody else's would
     let anybody mark a stranger online or offline.
  2. Presence is readable only by a conversation partner. A global
     presence list would let any account watch when any other account is
     using the app, which is surveillance rather than a feature.
  3. Typing is scoped to a conversation and to one's own uid. It is
     ephemeral UI state and never reaches Postgres.

conversationMembers/* is written by the Admin SDK only. It is the
projection these rules consult, which is why a client must not be able to
add itself to it.

There is no permissive default. The root denies read and write, and every
allowance below is explicit.

## Per-path notes

* `rules/conversationMembers` (note): Backend-written membership projection. Readable by members so the rules below can be evaluated client-side too; never writable by a client.
* `rules/presence/$uid` (note): Own presence only. `onDisconnect` writes offline from the client, which is the whole reason this lives in RTDB.
* `rules/presence/$uid` (read rule): A partner may see this only if they share a conversation with $uid. Without the membership check, any signed-in account could watch any other account come online.
* `rules/presenceVisibility` (note): Backend-written: presenceVisibility/{targetUid}/{readerUid}/{conversationId}: true. A reader is allowed only while at least one shared conversation remains; clients cannot grant themselves access.
* `rules/typing/$conversationId` (note): Only a member of this conversation, and only under their own uid.
