import java.util.Base64
import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
    id("com.google.gms.google-services")
}

// ---------------------------------------------------------------- release
// Upload-key signing. CI (Codemagic) injects CM_KEYSTORE_PATH / _PASSWORD /
// CM_KEY_ALIAS / CM_KEY_PASSWORD; a local release build reads
// android/key.properties (git-ignored: storeFile, storePassword, keyAlias,
// keyPassword). The keystore itself lives outside the repository. Release is
// never signed with the debug key: without an upload key the build stops at
// the signing step.
val keyProperties = Properties().apply {
    val file = rootProject.file("key.properties")
    if (file.exists()) file.inputStream().use { load(it) }
}

fun signingValue(env: String, property: String): String? =
    System.getenv(env)?.takeIf { it.isNotBlank() }
        ?: keyProperties.getProperty(property)?.takeIf { it.isNotBlank() }

val releaseSigningReady = signingValue("CM_KEYSTORE_PATH", "storeFile") != null

// A production build (--dart-define=APP_ENVIRONMENT=production) must carry the
// production Firebase config, never the staging/dev google-services.json.
// Same rule as the app and the backend: staging, dev, test, local, demo-.
val dartDefines: Map<String, String> =
    (project.findProperty("dart-defines") as String?)
        ?.split(",")
        ?.mapNotNull { encoded ->
            runCatching { String(Base64.getDecoder().decode(encoded)) }.getOrNull()
        }
        ?.mapNotNull { define ->
            define.split("=", limit = 2).takeIf { it.size == 2 }?.let { it[0] to it[1] }
        }
        ?.toMap()
        ?: emptyMap()

if (dartDefines["APP_ENVIRONMENT"] == "production") {
    val config = file("google-services.json")
    val projectId = if (config.exists()) {
        Regex("\"project_id\"\\s*:\\s*\"([^\"]+)\"").find(config.readText())?.groupValues?.get(1)
    } else {
        null
    }
    val devProject = Regex("(^demo-|staging|(^|[-_])(dev|test|local)([-_]|$))", RegexOption.IGNORE_CASE)
    if (projectId == null || devProject.containsMatchIn(projectId)) {
        throw GradleException(
            "Production build with a non-production Firebase config " +
                "(google-services.json project_id=${projectId ?: "missing"}). " +
                "Use the production project's google-services.json " +
                "(Codemagic: FIREBASE_ANDROID_JSON_B64)."
        )
    }
}

android {
    namespace = "com.astrofrekans.astrofrekans"
    // permission_handler_android 14.x compiles against API 37 and its AAR
    // metadata requires consumers to do the same; Flutter 3.44 defaults to 36.
    compileSdk = maxOf(flutter.compileSdkVersion, 37)
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.astrofrekans.astrofrekans"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = 24
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            val keyPath = signingValue("CM_KEYSTORE_PATH", "storeFile")
            if (keyPath != null) {
                storeFile = file(keyPath)
                storePassword = signingValue("CM_KEYSTORE_PASSWORD", "storePassword")
                keyAlias = signingValue("CM_KEY_ALIAS", "keyAlias")
                keyPassword = signingValue("CM_KEY_PASSWORD", "keyPassword")
            }
        }
    }

    buildTypes {
        release {
            // CI injects a real upload key. Never sign release with the debug key.
            signingConfig = signingConfigs.getByName("release")
        }
    }
}

// Stop exactly at signing, with the reason, rather than an AGP stack trace.
tasks.configureEach {
    if (!releaseSigningReady && (name == "validateSigningRelease" || name == "signReleaseBundle")) {
        doFirst {
            throw GradleException(
                "Release signing is not configured: set CM_KEYSTORE_PATH, " +
                    "CM_KEYSTORE_PASSWORD, CM_KEY_ALIAS, CM_KEY_PASSWORD (CI) or create " +
                    "android/key.properties (local). The debug key is never used for release. " +
                    "See docs/release_signing.md."
            )
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

dependencies {
    // AstroCallMessagingService uses RemoteMessage / FirebaseMessagingService
    // directly, but FlutterFire only exposes them to its own module. Same BoM
    // as firebase_core 4.15.0 (FirebaseSDKVersion) so versions stay aligned.
    implementation(platform("com.google.firebase:firebase-bom:34.19.0"))
    implementation("com.google.firebase:firebase-messaging")
    testImplementation("junit:junit:4.13.2")
}
