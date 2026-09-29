// Emulator tests for firebase/database.rules.json (B9 presence contract).
//
//   cd firebase
//   firebase emulators:exec --only database --project demo-astrofrekans "npm --prefix rules-tests test"
//
// The rules never see a conversation's status. They check one thing: does the
// backend's projection presenceVisibility/{targetUid}/{readerUid}/{conversationId}
// exist. Which statuses get a projection is the backend's `grants_presence`
// (ACTIVE and READ_ONLY yes; SUSPENDED and CLOSED no) - proven in the Python
// suite (tests/test_presence_backfill.py). Here each scenario seeds exactly
// what the backend leaves behind for that status, then asks the rules.

import { readFileSync } from "node:fs";
import { after, before, beforeEach, describe, test } from "node:test";

import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
} from "@firebase/rules-unit-testing";

const RULES = readFileSync(new URL("../database.rules.json", import.meta.url), "utf8");

let env;

before(async () => {
  env = await initializeTestEnvironment({
    projectId: "demo-astrofrekans",
    database: { rules: RULES },
  });
});

after(async () => {
  await env?.cleanup();
});

beforeEach(async () => {
  await env.clearDatabase();
});

/** Write as the backend (Admin SDK): rules do not apply. */
async function asBackend(path, value) {
  await env.withSecurityRulesDisabled(async (context) => {
    await context.database().ref(path).set(value);
  });
}

const db = (uid) => env.authenticatedContext(uid).database();

/** What the backend leaves in RTDB for a conversation in `status`. */
async function projectConversation(status, { conversationId, user, expert }) {
  await asBackend(`presence/${user}`, { state: "online", lastChanged: 1 });
  await asBackend(`presence/${expert}`, { state: "online", lastChanged: 1 });
  if (status === "active" || status === "read_only") {
    await asBackend(`conversationMembers/${conversationId}`, { [user]: true, [expert]: true });
    await asBackend(`presenceVisibility/${user}/${expert}/${conversationId}`, true);
    await asBackend(`presenceVisibility/${expert}/${user}/${conversationId}`, true);
  }
  // suspended / closed: provision revoked the membership and every grant.
}

describe("presence visibility follows the backend projection", () => {
  for (const [status, allowed] of [
    ["active", true],
    ["read_only", true],
    ["suspended", false],
    ["closed", false],
  ]) {
    test(`${status.toUpperCase()} conversation -> partner presence ${allowed ? "allowed" : "denied"}`, async () => {
      await projectConversation(status, { conversationId: "c1", user: "user-a", expert: "expert-b" });
      const assertion = allowed ? assertSucceeds : assertFails;
      await assertion(db("expert-b").ref("presence/user-a").get());
      await assertion(db("user-a").ref("presence/expert-b").get());
    });
  }

  test("one of two shared conversations closes -> still visible through the other", async () => {
    await projectConversation("active", { conversationId: "c1", user: "user-a", expert: "expert-b" });
    await asBackend("presenceVisibility/user-a/expert-b/c2", true);
    await asBackend("presenceVisibility/user-a/expert-b/c1", null); // c1 revoked
    await assertSucceeds(db("expert-b").ref("presence/user-a").get());
  });

  test("an unrelated user cannot read anyone's presence", async () => {
    await projectConversation("active", { conversationId: "c1", user: "user-a", expert: "expert-b" });
    await assertFails(db("stranger-c").ref("presence/user-a").get());
    await assertFails(db("stranger-c").ref("presence/expert-b").get());
  });

  test("an unauthenticated client reads nothing", async () => {
    await projectConversation("active", { conversationId: "c1", user: "user-a", expert: "expert-b" });
    const anon = env.unauthenticatedContext().database();
    await assertFails(anon.ref("presence/user-a").get());
    await assertFails(anon.ref("/").get());
  });

  test("a user always sees their own presence", async () => {
    await asBackend("presence/user-a", { state: "online", lastChanged: 1 });
    await assertSucceeds(db("user-a").ref("presence/user-a").get());
  });
});

describe("clients cannot grant themselves access", () => {
  test("a client cannot invent a visibility grant", async () => {
    await assertFails(db("stranger-c").ref("presenceVisibility/user-a/stranger-c/fake").set(true));
    await assertFails(db("user-a").ref("presenceVisibility/user-a/stranger-c/fake").set(true));
    await assertFails(db("stranger-c").ref("presenceVisibility/user-a").set({ "stranger-c": { fake: true } }));
  });

  test("a client cannot add itself to a conversation", async () => {
    await assertFails(db("stranger-c").ref("conversationMembers/c1/stranger-c").set(true));
  });

  test("a reader sees only their own visibility node", async () => {
    await projectConversation("active", { conversationId: "c1", user: "user-a", expert: "expert-b" });
    await assertSucceeds(db("user-a").ref("presenceVisibility/user-a").get());
    await assertFails(db("expert-b").ref("presenceVisibility/user-a").get());
  });
});

describe("legacy and wrong paths grant nothing", () => {
  test("the old {targetUid}/{conversationId}/{readerUid} layout does not grant", async () => {
    await asBackend("presence/user-a", { state: "online", lastChanged: 1 });
    await asBackend("presenceVisibility/user-a/c1/expert-b", true); // pre-fix layout
    await assertFails(db("expert-b").ref("presence/user-a").get());
  });

  test("the root and unknown top-level paths are closed", async () => {
    await assertFails(db("user-a").ref("/").get());
    await assertFails(db("user-a").ref("anythingElse").get());
    await assertFails(db("user-a").ref("anythingElse").set(true));
  });
});

describe("presence writes", () => {
  test("a user writes only their own presence, in the allowed shape", async () => {
    await assertSucceeds(db("user-a").ref("presence/user-a").set({ state: "online", lastChanged: 1 }));
    await assertFails(db("user-a").ref("presence/expert-b").set({ state: "offline", lastChanged: 1 }));
    await assertFails(db("user-a").ref("presence/user-a").set({ state: "busy", lastChanged: 1 }));
    await assertFails(db("user-a").ref("presence/user-a/extra").set("x"));
  });
});

describe("typing is scoped to members and their own uid", () => {
  test("member writes own typing; non-member and impersonation denied", async () => {
    await projectConversation("active", { conversationId: "c1", user: "user-a", expert: "expert-b" });
    await assertSucceeds(db("user-a").ref("typing/c1/user-a").set({ typing: true, updatedAt: 1 }));
    await assertSucceeds(db("expert-b").ref("typing/c1").get());
    await assertFails(db("user-a").ref("typing/c1/expert-b").set({ typing: true, updatedAt: 1 }));
    await assertFails(db("stranger-c").ref("typing/c1/stranger-c").set({ typing: true, updatedAt: 1 }));
    await assertFails(db("stranger-c").ref("typing/c1").get());
  });

  test("a closed conversation (membership revoked) stops typing", async () => {
    await projectConversation("closed", { conversationId: "c1", user: "user-a", expert: "expert-b" });
    await assertFails(db("user-a").ref("typing/c1/user-a").set({ typing: true, updatedAt: 1 }));
  });
});
