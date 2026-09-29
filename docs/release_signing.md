# Release signing (Android) and Firebase fingerprints

The app id is `com.astrofrekans.astrofrekans` on both stores.

## Keys

Google Play uses **Play App Signing**:

- You sign uploads with an **upload key**.
- Google re-signs each release with the **app signing key** it keeps.

Both keys have fingerprints, and Firebase needs both. The debug key (`~/.android/debug.keystore`) is registered for development only. A release is never signed with it: `android/app/build.gradle.kts` stops the build at the signing step when no upload key is configured.

## Status (28 Sep 2026)

- Upload key created: `%USERPROFILE%\.astrofrekans-keys\astrofrekans-upload.jks` (PKCS12, RSA 4096, alias `astrofrekans-upload`, valid until Feb 2054).
- Fingerprints:
  - SHA-1 `E5:8E:0C:0E:70:CB:6B:D7:D0:1C:45:B1:53:06:05:D2:4A:2E:B4:16`
  - SHA-256 `28:5A:F8:59:C6:33:FE:E8:FF:9B:26:61:92:52:73:EC:AF:20:DD:72:44:CE:7B:75:0B:8B:39:6A:CA:93:3E:6B`
- The password was generated at creation. It exists only in the git-ignored `android/key.properties`. Move it into a password manager and back up the `.jks` file offline.

## 1. Create the upload key (once, offline) - done, kept for reference

```bash
mkdir -p ~/.astrofrekans-keys
keytool -genkeypair -v \
  -keystore ~/.astrofrekans-keys/astrofrekans-upload.jks \
  -storetype PKCS12 -keyalg RSA -keysize 4096 -validity 10000 \
  -alias astrofrekans-upload \
  -dname "CN=Astrofrekans, O=Astrofrekans, C=TR"
```

- Keep the `.jks` file and both passwords in a password manager, plus one offline backup.
- Losing the upload key is recoverable through Play support. Leaking it is not harmless.
- Never put the keystore inside the repository (`*.jks` and `*.keystore` are git-ignored anyway).

## 2. Use it

**Local release build:**

1. Copy `android/key.properties.example` to `android/key.properties` (git-ignored).
2. Fill it in.
3. Run `flutter build appbundle --release ...`.

**Codemagic:**

1. Team settings → Code signing identities → Android keystores → upload the `.jks` as **`astrofrekans_upload`**.
2. The workflow references it (`android_signing`), and Codemagic exposes it as `CM_KEYSTORE_PATH` / `CM_KEYSTORE_PASSWORD` / `CM_KEY_ALIAS` / `CM_KEY_PASSWORD`.

## 3. Fingerprints

**Upload key:**

```bash
keytool -list -v -keystore ~/.astrofrekans-keys/astrofrekans-upload.jks -alias astrofrekans-upload
```

This prints `SHA1:` and `SHA256:`.

**App signing key:** Play Console → the app → Test and release → **App integrity** → App signing. Copy the SHA-1 and SHA-256 of the *App signing key certificate*. They exist only after the first upload to any track.

## 4. Register them in Firebase (production project)

1. Firebase Console → Project settings → Your apps → Android app `com.astrofrekans.astrofrekans` → **Add fingerprint**:
   - upload key SHA-1 and SHA-256;
   - Play app signing key SHA-1 and SHA-256.
2. Download the updated `google-services.json`.
3. Store it base64 in Codemagic as `FIREBASE_ANDROID_JSON_B64`. For a local production build, put it in `android/app/google-services.json`.

Result:

- The Gradle build refuses `APP_ENVIRONMENT=production` with a staging/dev `google-services.json`.
- The app refuses at runtime a Firebase project that differs from the backend's.

Why the fingerprints matter:

- Phone auth, App Check (Play Integrity) and Google sign-in check them.
- Google sign-in is off in the first release, but register them now.
- Without them, a later switch-on fails only for Play-installed builds.
