// Validates Firebase mobile config files. Exit code 1 on any problem.
//
//   dart run tool/validate_firebase_config.dart [--production] \
//       [android/app/google-services.json] [ios/Runner/GoogleService-Info.plist]
//
// Prints project id, package/bundle id and Firebase app ids - never API keys.
import 'dart:io';

import 'firebase_config_check.dart';

void main(List<String> args) {
  final bool production = args.contains('--production');
  final List<String> files = args.where((a) => !a.startsWith('--')).toList();
  if (files.isEmpty) {
    files.addAll([
      'android/app/google-services.json',
      'ios/Runner/GoogleService-Info.plist',
    ]);
  }
  final problems = <String>[];
  FirebaseConfigFacts? android;
  FirebaseConfigFacts? ios;
  for (final path in files) {
    final file = File(path);
    if (!file.existsSync()) {
      problems.add('$path: missing');
      continue;
    }
    final result = path.endsWith('.json')
        ? checkGoogleServicesJson(
            file.readAsStringSync(),
            production: production,
          )
        : checkGoogleServiceInfoPlist(
            file.readAsStringSync(),
            production: production,
          );
    if (result.facts case final facts?) {
      stdout.writeln(facts);
      if (facts.platform == 'android') android = facts;
      if (facts.platform == 'ios') ios = facts;
    }
    problems.addAll(result.problems.map((p) => '$path: $p'));
  }
  if (android != null && ios != null) problems.addAll(crossCheck(android, ios));
  for (final p in problems) {
    stderr.writeln('ERROR $p');
  }
  if (problems.isNotEmpty) exit(1);
  stdout.writeln(production ? 'OK for production' : 'OK');
}
