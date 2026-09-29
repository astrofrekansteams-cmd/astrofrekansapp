/// Checks Firebase mobile config files before they go into a build.
///
/// `google-services.json` (Android) and `GoogleService-Info.plist` (iOS) are
/// generated per Firebase project. The wrong one - staging in a production
/// build, another app's package, a file from a different project than its
/// sibling - fails quietly at runtime (wrong user base, no push). This says
/// so at build time. Used by `tool/validate_firebase_config.dart` and CI.
library;

import 'dart:convert';

const String appId = 'com.astrofrekans.astrofrekans';

final RegExp _devProject = RegExp(
  r'(^demo-|staging|(^|[-_])(dev|test|local)([-_]|$))',
  caseSensitive: false,
);

/// What a config file says, without its API key.
class FirebaseConfigFacts {
  const FirebaseConfigFacts({
    required this.platform,
    required this.projectId,
    required this.projectNumber,
    required this.appIdentifier,
    required this.googleAppId,
  });
  final String platform;
  final String projectId;
  final String projectNumber;

  /// Android package name or iOS bundle id.
  final String appIdentifier;

  /// Firebase app id (`1:<number>:android|ios:<hex>`).
  final String googleAppId;

  @override
  String toString() =>
      '$platform: project=$projectId ($projectNumber) '
      'app=$appIdentifier firebaseAppId=$googleAppId';
}

class FirebaseConfigResult {
  const FirebaseConfigResult(this.facts, this.problems);
  final FirebaseConfigFacts? facts;
  final List<String> problems;
  bool get ok => problems.isEmpty;
}

FirebaseConfigResult checkGoogleServicesJson(
  String source, {
  required bool production,
}) {
  final Map<String, dynamic> json;
  try {
    json = jsonDecode(source) as Map<String, dynamic>;
  } on Object {
    return const FirebaseConfigResult(null, [
      'google-services.json is not valid JSON',
    ]);
  }
  final Map<String, dynamic> project =
      (json['project_info'] as Map?)?.cast<String, dynamic>() ?? const {};
  final String projectId = '${project['project_id'] ?? ''}';
  final String projectNumber = '${project['project_number'] ?? ''}';
  final List<Map<String, dynamic>> clients = [
    for (final c in (json['client'] as List? ?? const []))
      (c as Map).cast<String, dynamic>(),
  ];
  final List<Map<String, dynamic>> ours = clients
      .where(
        (c) =>
            (c['client_info']
                as Map?)?['android_client_info']?['package_name'] ==
            appId,
      )
      .toList();
  final problems = <String>[
    if (projectId.isEmpty) 'google-services.json has no project_id',
    if (ours.length != 1)
      'google-services.json must contain exactly one Android app $appId '
          '(found ${ours.length})',
  ];
  final String googleAppId = ours.length == 1
      ? '${(ours.single['client_info'] as Map)['mobilesdk_app_id'] ?? ''}'
      : '';
  if (ours.length == 1 &&
      !RegExp('^1:$projectNumber:android:[0-9a-f]+\$').hasMatch(googleAppId)) {
    problems.add(
      'google-services.json app id $googleAppId does not belong to project '
      'number $projectNumber',
    );
  }
  if (production && _devProject.hasMatch(projectId)) {
    problems.add(
      'google-services.json is for $projectId, a staging/dev project, '
      'not production',
    );
  }
  return FirebaseConfigResult(
    FirebaseConfigFacts(
      platform: 'android',
      projectId: projectId,
      projectNumber: projectNumber,
      appIdentifier: ours.length == 1 ? appId : '?',
      googleAppId: googleAppId,
    ),
    problems,
  );
}

FirebaseConfigResult checkGoogleServiceInfoPlist(
  String source, {
  required bool production,
}) {
  String value(String key) =>
      RegExp(
        '<key>$key</key>\\s*<string>([^<]*)</string>',
      ).firstMatch(source)?.group(1)?.trim() ??
      '';
  final String projectId = value('PROJECT_ID');
  final String bundleId = value('BUNDLE_ID');
  final String googleAppId = value('GOOGLE_APP_ID');
  final String sender = value('GCM_SENDER_ID');
  final problems = <String>[
    if (projectId.isEmpty) 'GoogleService-Info.plist has no PROJECT_ID',
    if (bundleId != appId)
      'GoogleService-Info.plist BUNDLE_ID is "$bundleId", not $appId',
    if (!RegExp('^1:$sender:ios:[0-9a-f]+\$').hasMatch(googleAppId))
      'GoogleService-Info.plist GOOGLE_APP_ID $googleAppId does not belong to '
          'project number $sender',
    if (production && _devProject.hasMatch(projectId))
      'GoogleService-Info.plist is for $projectId, a staging/dev project, '
          'not production',
  ];
  return FirebaseConfigResult(
    FirebaseConfigFacts(
      platform: 'ios',
      projectId: projectId,
      projectNumber: sender,
      appIdentifier: bundleId,
      googleAppId: googleAppId,
    ),
    problems,
  );
}

/// Both files must describe the same Firebase project.
List<String> crossCheck(FirebaseConfigFacts android, FirebaseConfigFacts ios) =>
    [
      if (android.projectId != ios.projectId ||
          android.projectNumber != ios.projectNumber)
        'Android (${android.projectId}) and iOS (${ios.projectId}) configs '
            'are from different Firebase projects',
    ];
